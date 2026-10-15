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
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

ISSUER=os.environ["L4_ISSUER"]
CP=os.environ["L4_CP"]
RUNTIME=Path("/run/l4")

def request(method,url,body=None,token=None):
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
        with urllib.request.urlopen(req,timeout=8) as response:
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
        raise RuntimeError("real IAM token grant not accepted")
    return reply["access_token"]

def decode(token_value):
    # This is a diagnostic extraction ONLY, not authentication. CP independently
    # verifies issuer, signature, time, audience, actor type and scopes.
    payload=token_value.split(".")[1]
    return json.loads(base64.urlsafe_b64decode(payload+"="*(-len(payload)%4)))

def workload():
    prefix=os.environ["L4_WORKLOAD_SEED"]
    return token("baobab-cms-workload",prefix+"-baobab-cms-workload",
                 "client_credentials")

def human():
    return token("l4-int02-admin",os.environ["L4_TEST_ADMIN_CLIENT_SECRET"],
                 "password",username="l4-int02-human",
                 password=os.environ["L4_TEST_USER_PASSWORD"])

def other():
    return token("l4-int02-other-audience",
                 (RUNTIME/"other-secret").read_text().strip(),
                 "client_credentials")

def wait_iam():
    # Keycloak 26 health management is on TCP 9000, reachable only from the
    # disposable private network. Never publish its admin or health ports.
    for _ in range(150):
        try:
            status,_=request("GET","http://keycloak:9000/health/ready")
            if status==200:
                print('{"issuer_ready":true}')
                return
        except OSError:
            # The management listener legitimately refuses connections before
            # the optimised distribution has finished booting. Retry.
            pass
        time.sleep(1)
    raise RuntimeError("real Keycloak management readiness never passed")

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
    print(json.dumps({"revocation_denied": code in (401,403,404)}))

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
    state["L4-CP-01"]="PASS" if (
        status==200 and context.get("tenant_id")==tenant and
        context.get("organisation_id")==organisation and
        context.get("context_id")) else "FAIL"
    if state["L4-CP-01"]=="PASS":
        state["L4-CP-01"]="PASS"
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
    # Canonical revocation is effective even while IAM's signed JWT remains
    # cryptographically valid. Do not use raw JWT expiry as revocation proof.
    # The harness updates identity.external_identity after successful tests.
    state["L4-CP-03"]="BLOCKED" if sibling_deny else "FAIL"
    print(json.dumps({"scenarios":state},sort_keys=True))

def main():
    name=sys.argv[1] if len(sys.argv)>1 else ""
    if name=="wait":
        wait()
    elif name=="wait-iam":
        wait_iam()
    elif name=="identities":
        identities()
    elif name=="test":
        exercise()
    elif name=="revoked":
        confirm_revoked()
    else:
        raise SystemExit("unsupported integration operation")
if __name__=="__main__":
    try:
        main()
    except Exception as exc:
        # Never print responses or token payloads in exception traces.
        print("INT-02 probe BLOCKED:",type(exc).__name__,file=sys.stderr)
        raise SystemExit(2)
