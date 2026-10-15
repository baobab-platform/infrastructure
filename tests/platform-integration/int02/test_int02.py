"""Fail-closed source contracts, independent of Docker and network."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import unittest.mock as mock

BASE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("int02",BASE/"orchestrate.py")
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class ContractTest(unittest.TestCase):
    def test_pinned_profile(self):
        data=m.load()
        self.assertEqual(data["profile"],"iam-cp")
        self.assertEqual(data["evidence_class"],"REAL_COMPONENT_SYNTHETIC_DATA")
        self.assertEqual(set(data["mandatory"]),m.REQUIRED)
        m.check_prerequisites(data,static=True)

    def test_negative_mutations(self):
        data=m.load()
        cases=[("no_protected_credentials",False),
               ("evidence_class","PROTECTED_STAGING"),
               ("mandatory",["L4-IAM-01"]),
               ("sources",{**data["sources"],"baobab-cp":"main"})]
        for key,val in cases:
            with self.subTest(key=key),tempfile.TemporaryDirectory() as d:
                path=Path(d)/"lock.json"
                path.write_text(json.dumps({**data,key:val}))
                with mock.patch.object(m,"LOCK",path):
                    with self.assertRaises(m.Blocked):
                        m.load()

    def test_image_must_have_immutable_digest(self):
        data=m.load()
        data["runtime_images"]["python_probe"]="python:3.12.12-slim"
        with self.assertRaises(m.Blocked):
            m.check_prerequisites(data,static=False)

    def test_no_public_listening_ports(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"compose.yaml"
            p.write_text("services:\n  cp:\n    ports:\n      - 8080:8080\n")
            with mock.patch.object(m,"COMPOSE",p):
                with self.assertRaises(m.Blocked):
                    m.load()

    def test_provider_resolution_fixture_cannot_claim_certified_health(self):
        source=(BASE/"probe.py").read_text()
        self.assertIn('state["L4-CP-02"]="BLOCKED" if provider_record else "FAIL"',source)
        self.assertIn("wait-iam",source)

    def test_iam_bootstrap_workload_secret_contract(self):
        source=(BASE/"probe.py").read_text()
        self.assertIn('return token("baobab-cms-workload",prefix,"client_credentials")',source)
        self.assertNotIn('prefix+"-baobab-cms-workload"',source)

    def test_local_admin_transport_does_not_rewrite_public_issuer(self):
        # The product kcadm CLI lives in the Keycloak container. It must
        # use loopback for its own administration, while the independent
        # client probe continues to validate the advertised OIDC issuer.
        compose=(BASE/"compose.yaml").read_text()
        self.assertIn("KC_URL: http://localhost:8080",compose)
        self.assertIn("L4_ISSUER: http://keycloak:8080/realms/baobab",compose)
        self.assertIn("ADMIN_OIDC_ISSUER: http://keycloak:8080/realms/baobab",compose)

    def test_bootstrap_failure_classification_is_allowlisted(self):
        # Raw stderr can contain credentials; CI may receive only fixed
        # stage codes and an audited progress label.
        source=(BASE/"orchestrate.py").read_text()
        self.assertIn('stage = "ADMIN_LOGIN_UNAVAILABLE"',source)
        self.assertIn('stage = "KCADM_SESSION_UNWRITABLE"',source)
        self.assertIn('"IAM bootstrap class:", "INT-02 fixture class:"',source)

    def test_nonroot_keycloak_receives_private_stdin_fixtures(self):
        runner=(BASE/"orchestrate.py").read_text()
        script=(BASE/"keycloak-fixture.sh").read_text()
        self.assertIn("L4_FIXTURE_DIR=$(mktemp -d)",runner)
        self.assertIn('prelude.append(content.rstrip',runner)
        self.assertIn('stdin=script',runner)
        self.assertIn('rm -rf -- "$L4_FIXTURE_DIR"',script)
        self.assertIn('"$L4_FIXTURE_DIR/test-client.json"',script)
        self.assertNotIn('chmod 777',runner+script)

    def test_fixture_checks_keycloak_json_not_grep(self):
        source=(BASE/"keycloak-fixture.sh").read_text()
        self.assertIn("jq -e --arg field", source)
        self.assertNotIn("grep -q", source.split("STAGE=admin-client-lookup")[-1])
        self.assertIn("INT02_FIXTURE_HTTP_CLASS=%s", source)
        self.assertIn("return 2", source)

    def test_fixture_failures_report_only_fixed_safe_stage(self):
        shell=(BASE/"keycloak-fixture.sh").read_text()
        runner=(BASE/"orchestrate.py").read_text()
        self.assertIn("INT02_FIXTURE_FAILURE_STAGE=%s",shell)
        self.assertIn("trap cleanup EXIT",shell)
        self.assertIn("INT02_FIXTURE_FAILURE_STAGE=([a-z-]+)",runner)
        self.assertIn('"INT-02 fixture class:"',runner)

    def test_keycloak_database_identity_matches_disposable_postgres(self):
        # A healthy Postgres container is not evidence that Keycloak can
        # authenticate: the application JDBC role must match POSTGRES_USER.
        compose=(BASE/"compose.yaml").read_text()
        self.assertIn("POSTGRES_USER: baobab_iam",compose)
        env=keycloak_environment(compose)
        self.assertEqual(env.get("KC_DB_USERNAME"),"baobab_iam")
        self.assertEqual(env.get("KC_DB_PASSWORD"),"${L4_IAM_DB_PASSWORD:?required}")

    def test_keycloak_environment_is_real_yaml_not_comment_text(self):
        # A literal "\n" inside a comment once swallowed KC_DB_PASSWORD, so
        # Keycloak started without database credentials and exited. Substring
        # checks still passed. Parse the block as YAML keys: every variable
        # must be an uncommented key, defined exactly once.
        compose=(BASE/"compose.yaml").read_text()
        self.assertNotIn("\\n",compose)
        env=keycloak_environment(compose)
        for key in ("KC_DB","KC_DB_URL","KC_DB_USERNAME","KC_DB_PASSWORD","KC_URL",
                    "KEYCLOAK_ADMIN","KEYCLOAK_ADMIN_PASSWORD"):
            self.assertIn(key,env)
        with self.assertRaises(AssertionError):
            keycloak_environment(compose.replace(
                "      KC_DB_PASSWORD:","      # dropped\\n      KC_DB_PASSWORD:",1))

    def test_iam_readiness_requires_real_issuer(self):
        # Management health is optional; the fallback must still contact the
        # genuine issuer's OIDC metadata and verify its canonical issuer.
        source=(BASE/"probe.py").read_text()
        self.assertIn('"/.well-known/openid-configuration"',source)
        self.assertIn('document.get("issuer") == master_issuer',source)
        self.assertIn('"/realms/master"',source)
        self.assertIn('status == 200',source)
        self.assertIn('verified-oidc-discovery',source)

    def test_admin_master_probe_checks_real_token_endpoint(self):
        source=(BASE/"probe.py").read_text()
        self.assertIn("def verify_master_administrator():",source)
        self.assertIn("/realms/master/protocol/openid-connect/token",source)
        self.assertIn("master-admin",source)

    def test_blocked_cannot_be_certification(self):
        data=m.load()
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(m,"EVIDENCE",Path(d)):
                m.write_evidence({"project":"l4-1111111111111111"},data,
                   {"scenarios":{k:"BLOCKED" for k in m.REQUIRED}},accepted=False)
            evidence=json.loads(next(Path(d).glob("*.json")).read_text())
            self.assertFalse(evidence["passed"])
            self.assertFalse(evidence["protected_staging_accepted"])


class DiagnosticsTest(unittest.TestCase):
    def test_readiness_codes_are_forwarded_and_nothing_else(self):
        # A failed probe must surface its fixed status line, not raw output.
        with mock.patch.object(m.subprocess,"run",return_value=mock.Mock(
                returncode=2,stdout="",stderr="Traceback secret=abc\n"
                "INT02_DIAG step=iam_readiness management=503 discovery=unavailable\n"
                "INT02_DIAG step=x leak=postgres://u:p@h/db\n")):
            with self.assertRaises(m.Blocked) as raised:
                m.execute(["docker","compose","exec","-T","probe","python","/app/probe.py","wait-iam"])
        message=str(raised.exception)
        self.assertIn("IAM diagnostics: step=iam_readiness management=503 discovery=unavailable",message)
        self.assertNotIn("secret",message)
        self.assertNotIn("postgres://",message)

    def test_keycloak_log_classes_emit_codes_only(self):
        log=("2026 ERROR jdbc url postgres://u:p@iam-db FATAL: password authentication failed for user x\n"
             "Listening on: http://0.0.0.0:8080\n")
        with mock.patch.object(m.subprocess,"run",return_value=mock.Mock(stdout=log,stderr="")):
            codes=m.keycloak_log_classes({"project":"l4-0000000000000000"},Path("/nonexistent"))
        self.assertEqual(codes,"DB_AUTH_FAILED,HTTP_LISTENING")
        self.assertNotIn("postgres://",codes)


    def test_probe_diagnostics_are_allowlisted_tokens(self):
        probe=(BASE/"probe.py").read_text()
        self.assertIn('error=error if error in OAUTH_ERRORS else "other"',probe)
        self.assertIn('diagnostic(step="master_admin"',probe)
        self.assertNotIn("error_description",probe)

    def test_every_iam_startup_failure_reports_log_classes(self):
        runner=(BASE/"orchestrate.py").read_text()
        body=runner.split("def startup_with_iam(p, envfile):")[1].split("\ndef ")[0]
        for step in ('"wait-iam"','"master-admin"','"/opt/keycloak/bootstrap.sh"','seed_keycloak(p, envfile)'):
            self.assertIn(step,body)


class ProvenanceTest(unittest.TestCase):
    def test_cp_build_stages_are_digest_pinned(self):
        # EA v2.2 §4.4 (iv): a mutable tag would let one source lock build a
        # different CP binary or runtime.
        import re
        froms=[l for l in (BASE/"cp.Dockerfile").read_text().splitlines() if l.startswith("FROM ")]
        self.assertEqual(len(froms),2)
        for line in froms:
            self.assertRegex(line,r"^FROM \S+@sha256:[0-9a-f]{64}( AS \w+)?$")

    def test_receipt_is_uploaded_for_blocked_runs(self):
        workflow=(BASE.parents[2]/".github/workflows/platform-int02.yml").read_text()
        upload=workflow.split("actions/upload-artifact@")[0].rsplit("- if:",1)[1]
        self.assertTrue(upload.strip().startswith("always()"))


class ScenarioTruthTest(unittest.TestCase):
    """EA v2.2 matrix: a scenario is PASS only with its positive AND its
    negatives observed in the same run; partial coverage is BLOCKED."""

    def test_cp01_needs_every_matrix_negative(self):
        probe=(BASE/"probe.py").read_text()
        runner=(BASE/"orchestrate.py").read_text()
        for check in ("cp01_swapped_organisation_denied","cp01_fabricated_tenant_denied"):
            self.assertIn(f'"{check}"',probe)
        for check in ("cp01_unmapped_principal_denied","cp01_revoked_identity_denied"):
            self.assertIn(f'checks["{check}"]',runner)
        # Only the orchestrator, after unmapped and revoked negatives, may
        # promote CP-01; the probe alone reports at most BLOCKED.
        self.assertIn('state["L4-CP-01"]="BLOCKED" if all(checks.values()) else "FAIL"',probe)
        self.assertNotIn('state["L4-CP-01"]="PASS"',probe)

    def test_unmapped_negative_runs_before_identity_link(self):
        runner=(BASE/"orchestrate.py").read_text()
        body=runner.split("def test(lock):")[1]
        self.assertLess(body.index('run_probe(p, envfile, "unmapped")'),
                        body.index("seed_identities(p, envfile, ids)"))

    def test_revocation_never_promotes_cp03(self):
        runner=(BASE/"orchestrate.py").read_text()
        self.assertNotIn('cases["L4-CP-03"] = ("PASS"',runner)
        probe=(BASE/"probe.py").read_text()
        self.assertIn('state["L4-CP-03"]="BLOCKED" if sibling_deny else "FAIL"',probe)

    def test_only_401_or_403_is_a_policy_denial(self):
        probe=(BASE/"probe.py").read_text()
        self.assertIn("DENIED=(401,403)",probe)
        self.assertNotIn("(401,403,404)",probe)

    def test_receipt_carries_ea_v22_fields_and_tls_blocks_acceptance(self):
        data=m.load()
        self.assertFalse(m.TLS_VERIFIED)
        all_pass={"scenarios":{k:"PASS" for k in m.REQUIRED},"checks":{"cp01_positive":True}}
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(m,"EVIDENCE",Path(d)):
                m.write_evidence({"project":"l4-2222222222222222"},data,all_pass,accepted=False)
            evidence=json.loads(next(Path(d).glob("*.json")).read_text())
        for field in ("source_pins","harness_candidate_sha","images","executing_profile",
                      "components","scenario_ids","scenarios","checks","transport",
                      "evidence_sha256","manifest_sha256"):
            self.assertIn(field,evidence)
        self.assertFalse(evidence["transport"]["tls_verified"])
        self.assertFalse(evidence["passed"])
        runner=(BASE/"orchestrate.py").read_text()
        self.assertIn("or not TLS_VERIFIED:",runner)


def keycloak_environment(compose):
    """The keycloak service's environment mapping, read structurally (standard
    library only): uncommented `KEY: value` lines at environment indentation.
    A duplicate or missing key fails; comments never contribute keys."""
    lines=compose.splitlines()
    start=lines.index("  keycloak:")
    env_at=next(i for i in range(start+1,len(lines)) if lines[i]=="    environment:")
    env={}
    for line in lines[env_at+1:]:
        if line.strip()=="" or line.lstrip().startswith("#"):
            continue
        if not line.startswith("      "):
            break
        key,sep,value=line.strip().partition(":")
        assert sep and key.isupper() and key not in env, f"invalid or duplicate key {key!r}"
        env[key]=value.strip()
    assert "KC_DB_PASSWORD" in env, "KC_DB_PASSWORD is not a real environment key"
    return env


if __name__=="__main__":
    unittest.main()
