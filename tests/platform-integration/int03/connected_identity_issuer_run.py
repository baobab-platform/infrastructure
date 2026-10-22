"""Supervised, real IAM-issued workload token -> independent verifier.

Only uses two independently approved existing confidential IAM clients.
Does not create identities, mint Principals or accept either HELD CMS client.
Private token output is NEVER an Actions artifact; retained observations are
sanitized and SHA-pinned but do not constitute independent qualification.
"""
import argparse
import base64
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys

import cms_evidence as custody
from connected_identity_cp_run import source_pins
from connected_identity_evidence import EvidenceRefused
from connected_identity_issuer import IssuerPort, ALLOWED
from connected_identity_cp import read_private_token

CLIENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{3,99}\Z")
SHA256 = re.compile(r"sha256:[0-9a-f]{64}\Z")
FORBIDDEN = {"baobab-int03-cms-consumer", "baobab-int03-cms-validator"}
SCHEMA = "infrastructure.int03c.issuer-operator.v1"


def reviewed(path):
    root=Path(path).parent
    custody.root_dir(root)
    custody.safe_file(root,Path(path).name)
    record=json.loads(Path(path).read_bytes())
    fields={"schema","run_id","environment","sources","issuer","ca_file",
            "owner_client","verifier_client","owner_secret_file",
            "verifier_secret_file","audience","scope","approval_digest"}
    if (type(record) is not dict or set(record)!=fields or
        record["schema"]!=SCHEMA or record["environment"]!="development" or
        not re.fullmatch(r"[0-9a-f]{32}",record["run_id"]) or
        record["issuer"] not in ALLOWED or
        not SHA256.fullmatch(record["approval_digest"]) or
        not isinstance(record["owner_client"],str) or
        not isinstance(record["verifier_client"],str) or
        not CLIENT.fullmatch(record["owner_client"]) or
        not CLIENT.fullmatch(record["verifier_client"]) or
        record["owner_client"]==record["verifier_client"] or
        record["owner_client"] in FORBIDDEN or record["verifier_client"] in FORBIDDEN or
        not isinstance(record["scope"],str) or
        not re.fullmatch(r"[a-z][a-z0-9:._-]{2,79}",record["scope"]) or
        not isinstance(record["audience"],str) or
        not re.fullmatch(r"[a-z][a-z0-9:._-]{2,127}",record["audience"])):
        raise EvidenceRefused("reviewed, distinct, approved IAM fixture clients required")
    return record


def basic(client,secret):
    if (not isinstance(secret,str) or
        not 32<=len(secret)<=512 or any(ch.isspace() for ch in secret)):
        raise EvidenceRefused("private issuer client secret malformed")
    return "Basic "+base64.b64encode((client+":"+secret).encode()).decode()


def issue(record,*,issuer,now=None):
    """Token issuer and second verifier must independently agree."""
    source_pins(record)
    owner_secret=read_private_token(record["owner_secret_file"])
    checker_secret=read_private_token(record["verifier_secret_file"])
    if owner_secret==checker_secret:
        raise EvidenceRefused("issuer and verifier are not independent")
    owner=basic(record["owner_client"],owner_secret)
    checker=basic(record["verifier_client"],checker_secret)
    issuer.discover()
    response=issuer.execute("token_endpoint",
                  {"grant_type":"client_credentials","scope":record["scope"]},owner)
    bearer=response.get("access_token")
    if (not isinstance(bearer,str) or not 32<=len(bearer)<=16384 or
        str(response.get("token_type","")).lower()!="bearer" or
        type(response.get("expires_in")) is not int or
        not 60<=response["expires_in"]<=900):
        raise EvidenceRefused("native IAM did not issue bounded OAuth bearer")
    verification=issuer.execute("introspection_endpoint",
         {"token":bearer,"token_type_hint":"access_token"},checker)
    observed=issuer.assert_introspection(verification,
        client_id=record["owner_client"],audience=record["audience"],
        scope=record["scope"],now=int(now if now is not None
                                    else datetime.now(timezone.utc).timestamp()))
    return bearer, {
        "schema":"infrastructure.int03c.issuer-readback.v1",
        "run_id":record["run_id"],"issuer":record["issuer"],
        "approval_digest":record["approval_digest"],
        "client_id":observed["client_id"],"audience":observed["audience"],
        "scope":observed["scope"],"expires_at":observed["expiry"],
        "issuer_current":True,"independent_introspection":True,
        "qualified":False,"independent_acceptance":False,
    }


def persist(record,bearer,observation,*,token_output,evidence_output):
    """No receipt or uploaded artifact may contain the bearer."""
    token=Path(token_output)
    if token.exists() or token.is_symlink() or token.parent==Path(evidence_output):
        raise EvidenceRefused("existing or commingled credential destination")
    custody.root_dir(token.parent)
    evidence=Path(evidence_output)
    custody.root_dir(evidence.parent)
    if evidence.exists() or evidence.is_symlink():
        raise EvidenceRefused("existing IAM evidence directory")
    # Refuse unsafe receipt destination before any credential is written.
    evidence.mkdir(mode=0o700,exist_ok=False)
    try:
        custody.exclusive(token,(bearer+"\n").encode())
        custody.exclusive(evidence/"issuer-create.json",custody.canonical(observation))
        custody.seal(evidence,["issuer-create.json"],
             run_id=record["run_id"],sources=record["sources"])
        custody.verify(evidence)
    except BaseException:
        # Ambiguous issuer state is left for an approved reviewer to resolve.
        # Never delete the original token when issuance succeeded and failed
        # to produce its recovery evidence; retain private custody.
        raise
    return True


def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument("action",choices=("inspect","issue"))
    parser.add_argument("--plan",type=Path,required=True)
    parser.add_argument("--token-out",type=Path)
    parser.add_argument("--evidence-out",type=Path)
    args=parser.parse_args(argv)
    try:
        record=reviewed(args.plan)
        if args.action=="inspect":
            print("INT03C_NATIVE_ISSUER_REVIEW_REQUIRED; qualified=false")
            return 0
        if args.token_out is None or args.evidence_out is None:
            raise EvidenceRefused("private owner and evidence destinations required")
        issuer=IssuerPort(record["issuer"],record["ca_file"])
        token,observed=issue(record,issuer=issuer)
        persist(record,token,observed,token_output=args.token_out,
                evidence_output=args.evidence_out)
        print("INT03C_NATIVE_ISSUER_READBACK_OBSERVED; qualified=false")
        return 0
    except (EvidenceRefused,OSError,ValueError,TypeError,KeyError):
        print("INT03C_ISSUER_UNVERIFIED; qualified=false",file=sys.stderr)
        return 2


if __name__=="__main__":
    sys.exit(main())
