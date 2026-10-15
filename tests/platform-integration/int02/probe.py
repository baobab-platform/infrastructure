#!/usr/bin/env python3
"""Real Keycloak-issued tokens exercised against a running CP process.

Only JSON summary reports are emitted; bearer tokens and provider bodies are
never printed, uploaded or included in evidence. Synthetic identities are
seeded into an entirely disposable CP database by the owning test harness.
"""
import base64
import json
import os
from pathlib import Path
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

ISSUER=os.environ["L4_ISSUER"]
CP=os.environ["L4_CP"]
RUNTIME=Path("/run/l4")
# EA v2.2 INT-02 "verified local TLS": every request to IAM and CP is
# verified against THIS run's throwaway CA, with hostname checking on. The
# probe never disables verification and never trusts any other root.
TLS=ssl.create_default_context(cafile=os.environ["L4_CA_FILE"])
TLS.minimum_version=ssl.TLSVersion.TLSv1_3

def request(method,url,body=None,token=None,context=None):
    data = (urllib.parse.urlencode(body).encode() if body is not None and
            url.endswith("/token") else
            json.dumps(body).encode() if body is not None else None)
    hdr={"Accept":"application/json"}
    if data is not None:
        hdr["Content-Type"]=("application/x-www-form-urlencoded"
                             if url.endswith("/token") else "application/json")
    if token:
        hdr["Authorization"]="Bearer "+token
    req=urllib.request.Request(url,data=data,method=method,headers=hdr)
    try:
        with urllib.request.urlopen(req,timeout=8,context=context or TLS) as response:
            status=response.status
            raw=response.read(65537)
    except urllib.error.HTTPError as exc:
        status=exc.code
        raw=exc.read(65537)
    if len(raw)>65536:
        raise ValueError("response too large")
    try:
        result=json.loads(raw) if raw else {}
    except ValueError:
        result={}
    return status,result

def token(client,secret,grant,**params):
    status,reply=request("POST",ISSUER+"/protocol/openid-connect/token",
                         {"grant_type":grant,"client_id":client,
                          "client_secret":secret,**params})
    if status!=200 or not reply.get("access_token"):
        error=reply.get("error") if isinstance(reply,dict) else None
        diagnostic(step="token_"+grant, client=client if client.replace("-","").isalnum() else "other",
                   status=status, error=error if error in OAUTH_ERRORS else "other")
        raise RuntimeError("real IAM token grant not accepted")
    return reply["access_token"]

def decode(token_value):
    # This is a diagnostic extraction ONLY, not authentication. CP independently
    # verifies issuer, signature, time, audience, actor type and scopes.
    payload=token_value.split(".")[1]
    return json.loads(base64.urlsafe_b64decode(payload+"="*(-len(payload)%4)))

def workload():
    prefix=os.environ["L4_WORKLOAD_SEED"]
    # IAM bootstrap.sh deliberately suffixes ONLY the independent
    # zuribeans-backend and thamani-backend test clients. Platform-owned
    # baobab-cms-workload receives the literal BOOTSTRAP seed.
    return token("baobab-cms-workload",prefix,"client_credentials")

def human():
    return token("l4-int02-admin",os.environ["L4_TEST_ADMIN_CLIENT_SECRET"],
                 "password",username="l4-int02-human",
                 password=os.environ["L4_TEST_USER_PASSWORD"])

def other():
    return token("l4-int02-other-audience",
                 (RUNTIME/"other-secret").read_text().strip(),
                 "client_credentials")

# Standard OAuth 2.0 / Keycloak error codes are public protocol vocabulary,
# never credentials; anything else is reported as "other".
OAUTH_ERRORS={"invalid_grant","invalid_client","unauthorized_client","invalid_request",
              "invalid_scope","unsupported_grant_type","access_denied","temporarily_unavailable"}

def diagnostic(**fields):
    """One fixed-format diagnostic line (short tokens only) that the
    orchestrator may forward to CI; never bodies, tokens or credentials."""
    print("INT02_DIAG " + " ".join(f"{k}={v}" for k,v in fields.items()), file=sys.stderr)

def verify_master_administrator():
    # Use Keycloak's unmodified built-in master/admin-cli grant. This is the
    # same password grant used by IAM's kcadm.sh product bootstrap, issued
    # by the REAL Keycloak process. Never print an access token or password.
    master=ISSUER.rsplit("/realms/",1)[0]+"/realms/master"
    code,body=request("POST",master+"/protocol/openid-connect/token",{
        "grant_type":"password","client_id":"admin-cli",
        "username":"l4admin","password":os.environ["L4_KC_ADMIN_PASSWORD"]})
    if code!=200 or not body.get("access_token"):
        error=body.get("error") if isinstance(body,dict) else None
        diagnostic(step="master_admin", status=code,
                   error=error if error in OAUTH_ERRORS else "other")
        raise RuntimeError("Keycloak master admin credential was not accepted")
    print('{"master_admin_token_verified":true}')

def wait_iam():
    # Readiness is the real OIDC discovery document, fetched over verified TLS
    # through the edge: HTTP 200 AND the exact expected issuer. The baobab
    # realm only exists after IAM's bootstrap.sh, which runs later; the
    # built-in master realm is the pre-bootstrap issuer (hostname +
    # /realms/master). The master-admin step then verifies real token
    # issuance. Neither mocks IAM, authorises CP access, or certifies L4.
    master_issuer = ISSUER.rsplit("/realms/", 1)[0] + "/realms/master"
    discovery = master_issuer + "/.well-known/openid-configuration"
    last = "unavailable"
    for _ in range(150):
        try:
            status,document = request("GET",discovery)
            last = str(status)
            if status == 200 and document.get("issuer") == master_issuer:
                print('{"issuer_ready":true,"method":"verified-tls-oidc-discovery"}')
                return
            if status == 200:
                last = "issuer_mismatch"
        except ssl.SSLCertVerificationError:
            last = "tls_unverified"
        except urllib.error.URLError as exc:
            last = "tls_unverified" if isinstance(exc.reason, ssl.SSLCertVerificationError) else "unavailable"
        except (OSError, ValueError):
            last = "unavailable"
        time.sleep(1)
    # Status classes and HTTP codes are safe; never include bodies, URLs
    # containing credentials, tokens or raw container logs in Actions. This
    # fixed-format line is the only diagnostic the orchestrator forwards.
    diagnostic(step="iam_readiness", discovery=last)
    raise RuntimeError("real Keycloak readiness unavailable: discovery=" + last)

def wait():
    for _ in range(90):
        try:
            s,_=request("GET",CP+"/health/live")
            if s==200:
                print('{"ready":true}')
                return
        except OSError:
            # CP may not yet have bound its private HTTP listener; poll until
            # readiness or the bounded deadline, never skipping the check.
            pass
        time.sleep(1)
    raise RuntimeError("real CP did not become ready")

def identities():
    h,w=decode(human()),decode(workload())
    if h.get("iss")!=ISSUER or w.get("iss")!=ISSUER:
        raise RuntimeError("IAM issuer mismatch")
    if h.get("actor_type")!="human" or w.get("actor_type")!="workload":
        raise RuntimeError("real IAM actor profile mismatch")
    print(json.dumps({"source":"keycloak-issued","issuer":ISSUER,
                      "human_sub":h["sub"],"workload_sub":w["sub"]}))

DENIED=(401,403)

def denied(token_value,body):
    """A real CP denial: 401/403 only. A 404, 5xx or transport error is not
    proof of policy and must never be counted as a negative PASS."""
    status,_=request("POST",CP+"/v1/platform-context/resolve",body,token_value)
    return status in DENIED

def unmapped():
    # Runs BEFORE the harness links this Keycloak subject to a CP Principal:
    # a validly signed, correctly scoped token for an unmapped principal
    # must be refused (L4-CP-01 negative "unmapped principal").
    fixtures=json.loads((RUNTIME/"fixtures.json").read_text())
    print(json.dumps({"unmapped_denied":denied(workload(),
        {"tenant_id":fixtures["tenant"],"organisation_id":fixtures["organisation"]})}))

def verify(expected,fn):
    try:
        return "PASS" if fn() is True else "FAIL"
    except Exception:
        return "BLOCKED"

def confirm_revoked():
    # Same in-memory-container token issued before CP link was revoked.
    # The token remains time-valid and Keycloak-signed, but CP must deny
    # identity or context lookup after the canonical external link change.
    token_path = Path("/tmp/l4-workload-issued-before-revocation")
    raw = token_path.read_text()
    token_path.unlink(missing_ok=True)
    claims = decode(raw)
    if claims.get("iss") != ISSUER or int(claims.get("exp", 0)) <= time.time():
        raise RuntimeError("Previously issued IAM token is not live")
    fixtures = json.loads((RUNTIME / "fixtures.json").read_text())
    code, data = request("POST", CP + "/v1/platform-context/resolve",
                         {"tenant_id":fixtures["tenant"],
                          "organisation_id":fixtures["organisation"]},raw)
    print(json.dumps({"revocation_denied": code in DENIED}))

def exercise():
    fixture=json.loads((RUNTIME/"fixtures.json").read_text())
    tenant,other_tenant=fixture["tenant"],fixture["other_tenant"]
    organisation=fixture["organisation"]
    good,human_token=workload(),human()
    tok = Path("/tmp/l4-workload-issued-before-revocation")
    tok.write_text(good)
    tok.chmod(0o600)
    wclaims=decode(good)
    hclaims=decode(human_token)
    def auth_good():
        return (wclaims.get("iss")==ISSUER and
                "baobab-control-plane" in
                ([wclaims.get("aud")] if isinstance(wclaims.get("aud"),str) else wclaims.get("aud",[]))
                and wclaims.get("actor_type")=="workload" and
                "context:resolve" in wclaims.get("scope","").split() and
                hclaims.get("actor_type")=="human" and
                request("GET",CP+"/v1/admin/effective-authority",token=human_token)[0]==200)
    def wrong_audience():
        wrong=other()
        w=decode(wrong)
        aud=w.get("aud",[])
        return (w.get("iss")==ISSUER and
                "baobab-pulse" in ([aud] if isinstance(aud,str) else aud) and
                "baobab-control-plane" not in ([aud] if isinstance(aud,str) else aud)
                and request("POST",CP+"/v1/platform-context/resolve",
                            {"tenant_id":tenant},wrong)[0]==401)
    state={}
    # The positive check proves actual signed token and CP acceptance.
    # Shared's L4-IAM-01 additionally REQUIRES human code+PKCE, single-use
    # state/nonce and callback replay denial; password-grant test fixture
    # alone is not that proof and MUST NOT be reported as accepted.
    state["L4-IAM-01"]="BLOCKED" if auth_good() else "FAIL"
    # Different-client wrong-audience denial is a useful real negative,
    # but is NOT sufficient for isolated same-client audience-only proof.
    # Until the same-client audience-differential test runs, BLOCKED.
    state["L4-IAM-02"]="BLOCKED" if wrong_audience() else "FAIL"
    status,context=request("POST",CP+"/v1/platform-context/resolve",
                           {"tenant_id":tenant,"organisation_id":organisation},good)
    positive=bool(status==200 and context.get("tenant_id")==tenant and
        context.get("organisation_id")==organisation and context.get("context_id"))
    # L4-CP-01 negatives (matrix): a swapped Organisation (tenant B's PRIMARY
    # Organisation under tenant A) and a fabricated tenant must be refused.
    # The unmapped-principal and revoked-identity negatives run in the
    # orchestrator, which alone may promote CP-01 to PASS.
    checks={"cp01_positive":positive,
            "cp01_swapped_organisation_denied":denied(good,
                {"tenant_id":tenant,"organisation_id":fixture["other_organisation"]}),
            "cp01_fabricated_tenant_denied":denied(good,
                {"tenant_id":"tn_l4fabricated"+uuid.uuid4().hex[:12]})}
    state["L4-CP-01"]="BLOCKED" if all(checks.values()) else "FAIL"
    if positive:
        status2,cap=request("POST",CP+"/v1/capabilities/resolve",
            {"context_id":context["context_id"],"capability_key":"intelligence.evidence.search",
             "required_contract_version":1,"correlation_id":str(uuid.uuid4())},good)
        # CP can resolve a synthetic binding without a live provider. A
        # resolved record is useful diagnostic evidence, but Accepted EA
        # L4-CP-02 also requires *current certified provider health*.
        # Do NOT report PASS until a real owner provider is running and
        # its binding, certification and live readiness are observed.
        provider_record = (status2==200 and cap.get("decision")=="RESOLVED"
            and cap.get("grant_id") and cap.get("binding_id")
            and cap.get("invocation",{}).get("engine_instance_id"))
        state["L4-CP-02"]="BLOCKED" if provider_record else "FAIL"
    else:
        state["L4-CP-02"]="BLOCKED"
    # Tenant-neutral workloads MAY resolve a second tenant context: the
    # authorised boundary is the tenant's ACTIVE scoped CapabilityGrant, not
    # an unconditional tenant claim. A missing grant MUST never resolve.
    foreign,body=request("POST",CP+"/v1/platform-context/resolve",
                         {"tenant_id":other_tenant},good)
    sibling_deny=False
    if foreign==200 and body.get("context_id"):
        sc,r=request("POST",CP+"/v1/capabilities/resolve",
          {"context_id":body["context_id"],
           "capability_key":"intelligence.evidence.search",
           "required_contract_version":1,"correlation_id":str(uuid.uuid4())},good)
        sibling_deny=(sc==200 and r.get("decision")=="DENIED" and
                      not r.get("invocation"))
    # L4-CP-03 also requires parent, independently governed subsidiary and
    # external-user cases (matrix). Only the sibling case runs here, so a
    # sibling denial is recorded but CP-03 stays BLOCKED, never PASS.
    checks["cp03_sibling_denied"]=sibling_deny
    state["L4-CP-03"]="BLOCKED" if sibling_deny else "FAIL"
    print(json.dumps({"scenarios":state,"checks":checks},sort_keys=True))

def tls():
    """Observe verified TLS on both edge names, and refusal without the CA."""
    result={"tls_iam_verified":False,"tls_cp_verified":False,"tls_untrusted_refused":False}
    try:
        master=ISSUER.rsplit("/realms/",1)[0]+"/realms/master"
        status,document=request("GET",master+"/.well-known/openid-configuration")
        result["tls_iam_verified"]=status==200 and document.get("issuer")==master
    except (OSError,ValueError):
        # A failed handshake, connection or parse is "not verified"; the
        # error itself is never reported, and acceptance stays blocked.
        result["tls_iam_verified"]=False
    try:
        result["tls_cp_verified"]=request("GET",CP+"/health/live")[0]==200
    except (OSError,ValueError):
        # As above: any failure leaves CP transport unverified.
        result["tls_cp_verified"]=False
    # A context that trusts only the image's public roots must refuse the
    # edge: this run's CA is the sole reason the requests above succeed.
    try:
        request("GET",CP+"/health/live",context=ssl.create_default_context())
    except urllib.error.URLError as exc:
        result["tls_untrusted_refused"]=isinstance(exc.reason,ssl.SSLCertVerificationError)
    except ssl.SSLCertVerificationError:
        result["tls_untrusted_refused"]=True
    except (OSError,ValueError):
        # Only a certificate-verification refusal proves the CA is required;
        # a connection or parse failure proves nothing, so the check fails.
        result["tls_untrusted_refused"]=False
    print(json.dumps(result,sort_keys=True))

def main():
    name=sys.argv[1] if len(sys.argv)>1 else ""
    if name=="wait":
        wait()
    elif name=="wait-iam":
        wait_iam()
    elif name=="master-admin":
        verify_master_administrator()
    elif name=="identities":
        identities()
    elif name=="test":
        exercise()
    elif name=="revoked":
        confirm_revoked()
    elif name=="unmapped":
        unmapped()
    elif name=="tls":
        tls()
    else:
        raise SystemExit("unsupported integration operation")
if __name__=="__main__":
    try:
        main()
    except Exception as exc:
        # Never print responses or token payloads in exception traces.
        print("INT-02 probe BLOCKED:",type(exc).__name__,file=sys.stderr)
        raise SystemExit(2)
