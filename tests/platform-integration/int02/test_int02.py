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
        # Never PASS: the synthetic provider is never a current certified one.
        self.assertIn('state["L4-CP-02"]="BLOCKED" if (entitled and (provider_record or fail_closed)) else "FAIL"',source)
        self.assertNotIn('state["L4-CP-02"]="PASS"',source)
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
        self.assertIn("L4_ISSUER: https://iam.int02.test/realms/baobab",compose)
        self.assertIn("ADMIN_OIDC_ISSUER: https://iam.int02.test/realms/baobab",compose)
        self.assertIn('"--hostname=https://iam.int02.test"',compose)

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
        self.assertIn('verified-tls-oidc-discovery',source)

    def test_admin_master_probe_checks_real_token_endpoint(self):
        source=(BASE/"probe.py").read_text()
        self.assertIn("def verify_master_administrator():",source)
        self.assertIn('master=ISSUER.rsplit("/realms/",1)[0]+"/realms/master"',source)
        self.assertIn('request("POST",master+"/protocol/openid-connect/token"',source)
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
        for check in ("cp01_unmapped_principal_denied","cp01_revoked_identity_denied",
                      "cp01_revoked_grant_denied"):
            self.assertIn(f'checks["{check}"]',runner)
        for check in ("cp01_missing_organisation_not_fabricated","cp01_fabricated_organisation_denied"):
            self.assertIn(f'"{check}"',probe)
        # Every matrix negative is required for PASS (EA v2.2 L4-CP-01).
        self.assertEqual(set(m.CP01_REQUIRED),{"cp01_positive","cp01_missing_organisation_not_fabricated",
            "cp01_fabricated_organisation_denied","cp01_swapped_organisation_denied",
            "cp01_fabricated_tenant_denied","cp01_unmapped_principal_denied",
            "cp01_revoked_grant_denied","cp01_revoked_identity_denied"})
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
        # Every scenario PASS but no observed TLS checks: never verified.
        all_pass={"scenarios":{k:"PASS" for k in m.REQUIRED},"checks":{"cp01_positive":True}}
        self.assertFalse(m.tls_verified(all_pass["checks"]))
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
        self.assertIn("or not tls_verified(checks):",runner)

    def test_outcome_summary_is_fixed_vocabulary(self):
        cases={k:"BLOCKED" for k in m.REQUIRED}; cases["L4-CP-01"]="PASS"
        checks={"cp01_positive":True,"tls_iam_verified":False,"Bad Key; rm":True,"leak":"eyJsecret"}
        out=m.outcome_summary({**cases,"L4-IAM-01":"eyJ.token"},checks)
        self.assertIn("L4-CP-01=PASS",out)
        self.assertIn("L4-IAM-01=UNKNOWN",out)
        self.assertIn("cp01_positive=true",out)
        self.assertIn("tls_iam_verified=false",out)
        self.assertIn("leak=false",out)
        self.assertNotIn("eyJ",out)
        self.assertNotIn("Bad Key",out)

    def test_tls_verified_only_when_every_observation_holds(self):
        full={name:True for name in m.TLS_CHECKS}
        self.assertTrue(m.tls_verified(full))
        for name in m.TLS_CHECKS:
            self.assertFalse(m.tls_verified({**full,name:False}))
            self.assertFalse(m.tls_verified({k:v for k,v in full.items() if k!=name}))
        self.assertFalse(m.tls_verified({**full,"tls_untrusted_refused":"true"}))


class TransportTest(unittest.TestCase):
    """EA v2.2 INT-02 runs over verified local TLS."""

    def test_no_cross_container_plain_http_to_iam_or_cp(self):
        # Only the edge's upstreams and Keycloak's in-container loopback
        # administration may name plain HTTP.
        compose=(BASE/"compose.yaml").read_text()
        probe=(BASE/"probe.py").read_text()
        self.assertNotIn("http://keycloak",compose+probe)
        self.assertNotIn("http://cp",compose+probe)
        self.assertNotIn("http://",probe)
        edge=(BASE/"edge.conf").read_text()
        self.assertIn("set $u http://keycloak:8080;",edge)
        self.assertIn("set $u http://cp:8080;",edge)
        self.assertIn("ssl_protocols TLSv1.3;",edge)
        self.assertIn("return 421;",edge)

    def test_probe_verifies_only_against_the_run_ca(self):
        probe=(BASE/"probe.py").read_text()
        self.assertIn('ssl.create_default_context(cafile=os.environ["L4_CA_FILE"])',probe)
        self.assertNotIn("CERT_NONE",probe)
        self.assertNotIn("check_hostname=False",probe)
        self.assertNotIn("_create_unverified_context",probe)
        self.assertIn("context=context or TLS",probe)

    def test_cp_trusts_the_run_ca_and_only_https_issuers(self):
        compose=(BASE/"compose.yaml").read_text()
        self.assertIn("SSL_CERT_FILE: /run/l4-tls/ca.pem",compose)
        self.assertIn("WORKLOAD_OIDC_ISSUER: https://iam.int02.test/realms/baobab",compose)
        self.assertIn("aliases: [iam.int02.test, cp.int02.test]",compose)

    def test_edge_is_digest_pinned_and_a_declared_service(self):
        data=m.load()
        self.assertIn("edge",data["services"])
        self.assertRegex(data["runtime_images"]["tls_edge"],r"^nginx@sha256:[0-9a-f]{64}$")

    def test_throwaway_ca_signs_a_verifiable_edge_certificate(self):
        import shutil, ssl, subprocess
        if shutil.which("openssl") is None:
            self.skipTest("openssl unavailable")
        with tempfile.TemporaryDirectory() as d:
            tls=Path(d)/"tls"
            m.throwaway_tls(tls)
            self.assertEqual(sorted(x.name for x in tls.iterdir()),["ca.pem","edge.key","edge.pem"])
            # The CA key is destroyed once the edge certificate is signed.
            self.assertEqual(sorted(x.name for x in Path(d).iterdir()),["tls"])
            out=subprocess.run(["openssl","verify","-CAfile",str(tls/"ca.pem"),
                                "-purpose","sslserver",str(tls/"edge.pem")],
                               capture_output=True,text=True)
            self.assertEqual(out.returncode,0,out.stdout+out.stderr)
            text=subprocess.run(["openssl","x509","-noout","-ext","subjectAltName",
                                 "-in",str(tls/"edge.pem")],capture_output=True,text=True).stdout
            self.assertIn("DNS:iam.int02.test",text)
            self.assertIn("DNS:cp.int02.test",text)
            # The CA loads as a trust anchor for Python's verifier.
            ssl.create_default_context(cafile=str(tls/"ca.pem"))

    def test_probe_uses_the_pinned_cp_health_routes(self):
        # CP b0385fa serves /healthz and /readyz; /health/live never existed.
        probe=(BASE/"probe.py").read_text()
        self.assertIn('request("GET",CP+"/readyz")',probe)
        self.assertIn('CP+"/healthz"',probe)
        self.assertNotIn("/health/live",probe)
        self.assertIn('diagnostic(step="cp_readiness", readyz=last)',probe)

    def test_token_profile_failures_report_only_fixed_facts(self):
        import re
        probe=(BASE/"probe.py").read_text()
        self.assertIn("def claim_profile(label,claims,actor):",probe)
        self.assertIn('has_sub=str(bool(claims.get("sub"))).lower()',probe)
        self.assertIn('exception=name if name.isidentifier() and len(name)<=40 else "other"',probe)
        # Every such line still fits the orchestrator's forwarding allowlist.
        allow=re.compile(r"INT02_DIAG( [a-z_]{1,24}=[A-Za-z0-9_.-]{1,40}){1,6}")
        for line in ("INT02_DIAG step=claims_workload iss_match=true has_sub=false actor=workload",
                     "INT02_DIAG step=probe_identities exception=RuntimeError",
                     "INT02_DIAG step=probe_wait_iam exception=KeyError"):
            self.assertIsNotNone(allow.fullmatch(line),line)

    def test_fixture_clients_request_keycloak_basic_scope_for_sub(self):
        runner=(BASE/"orchestrate.py").read_text()
        self.assertIn('"basic","openid","actor-type-human","authority:self"',runner)
        self.assertIn('"basic","openid","actor-type-workload","intelligence:evidence:search"',runner)

    def test_cp_sql_failures_report_only_the_sqlstate(self):
        runner=(BASE/"orchestrate.py").read_text()
        # Every fixture statement goes through one labelled helper.
        self.assertEqual(runner.count('"psql", "-X", "-v", "VERBOSITY=sqlstate",'),1)
        self.assertEqual(runner.count('"cp-db", "psql"'),1)
        self.assertNotIn('"psql", "-X", "-v", "ON_ERROR_STOP',runner)
        failed=mock.Mock(returncode=1,stdout="",stderr="ERROR:  23502\n")
        with mock.patch.object(m.subprocess,"run",return_value=failed):
            with self.assertRaises(m.Blocked) as caught:
                m.execute(["docker","compose","exec","-T","cp-db","psql","-c","SELECT 1"])
        self.assertIn("CP SQL state: 23502",str(caught.exception))
        leaky=mock.Mock(returncode=1,stdout="",stderr="ERROR:  null value in column \"x\"\n")
        with mock.patch.object(m.subprocess,"run",return_value=leaky):
            with self.assertRaises(m.Blocked) as caught:
                m.execute(["docker","compose","exec","-T","cp-db","psql","-c","SELECT 1"])
        self.assertNotIn("null value",str(caught.exception))
        self.assertNotIn("CP SQL state",str(caught.exception))

    def test_cp_fixture_failures_name_only_a_fixed_step(self):
        failed=m.Blocked("Compose exec/cp-db failed; CP SQL state: 23505")
        with mock.patch.object(m,"compose",side_effect=failed):
            with self.assertRaises(m.Blocked) as caught:
                m.cp_sql({},None,"tenant_b","INSERT INTO secret_values VALUES ('x')")
        self.assertIn("CP fixture step: tenant_b",str(caught.exception))
        self.assertNotIn("secret_values",str(caught.exception))
        with self.assertRaises(m.Blocked):
            m.cp_sql({},None,"anything else","SELECT 1")

    def test_tenant_fixtures_are_bootstrap_registered_never_onboarding(self):
        runner=(BASE/"orchestrate.py").read_text()
        self.assertIn("'row_level_security','af-south-1','active',true,'BOOTSTRAP',",runner)
        self.assertNotIn("'ONBOARDING'",runner)

    def test_identity_seed_respects_cp_workload_auto_provisioning(self):
        runner=(BASE/"orchestrate.py").read_text()
        self.assertIn("WHERE NOT EXISTS (SELECT 1 FROM found) RETURNING principal_id",runner)
        self.assertIn('must(name == "workload" or state == "created"',runner)
        self.assertIn('checks["cp_workload_principal_auto_provisioned"]',runner)
        calls=[]
        def fake(p,envfile,*args,**kw):
            calls.append(args[args.index("-c")+1])
            return "existing:workload\n" if len(calls)==1 else "created\n"
        ids={"workload_sub":"0"*8+"-0000-0000-0000-"+"0"*12,"human_sub":"1"*8+"-1111-1111-1111-"+"1"*12}
        with mock.patch.object(m,"compose",side_effect=fake):
            self.assertEqual(m.seed_identities({},None,ids),
                             {"workload":"existing:workload","human":"created"})
        # A human principal CP provisioned on its own is a refusal, not reuse.
        with mock.patch.object(m,"compose",return_value="existing:human\n"):
            with self.assertRaises(m.Blocked):
                m.seed_identities({},None,ids)

    def test_fixture_binds_to_cps_synced_canonical_capability(self):
        # CP syncs Shared's catalogue at startup; the fixture must never
        # fabricate a competing capability row (live: 23505 capability_code_key).
        runner=(BASE/"orchestrate.py").read_text()
        self.assertNotIn("INSERT INTO capability.capability(",runner)
        self.assertIn("WHERE code='intelligence.evidence.search' AND status='ACTIVE'",runner)
        self.assertIn('must(written == "1:1"',runner)
        # CP registers the baobab-pulse engine at startup: share it, never
        # duplicate it, and never activate CP's DRAFT baobab-pulse.core.
        self.assertIn("ON CONFLICT (code) DO NOTHING RETURNING engine_id",runner)
        self.assertNotIn("'baobab-pulse.core'",runner)
        self.assertIn("'int02.synthetic-pulse'",runner)

    def test_every_tls_check_is_collected_from_the_probe(self):
        runner=(BASE/"orchestrate.py").read_text()
        self.assertIn('transport = json.loads(run_probe(p, envfile, "tls"))',runner)
        probe=(BASE/"probe.py").read_text()
        for name in m.TLS_CHECKS:
            self.assertIn('"'+name+'"',probe)



class ParityTest(unittest.TestCase):
    """ADR-SHARED-036 s6.3/s6.8/s6.10: one harness for Codespaces and CI."""

    def env(self, **values):
        keys=("LOCAL_WORKSPACE_FOLDER","CONTAINER_WORKSPACE_FOLDER",
              "INT02_CANDIDATE_REPOSITORY","INT02_CANDIDATE_SHA")
        clean={k:v for k,v in m.os.environ.items() if k not in keys}
        return mock.patch.dict(m.os.environ,{**clean,**values},clear=True)

    def test_mount_sources_are_untouched_on_a_plain_runner(self):
        with self.env():
            self.assertEqual(m.host_path(BASE/"edge.conf"),str(BASE/"edge.conf"))

    def test_mount_sources_are_translated_to_the_host_workspace(self):
        root=str(m.ROOT)
        with self.env(LOCAL_WORKSPACE_FOLDER="/home/runner/work/infrastructure/infrastructure",
                      CONTAINER_WORKSPACE_FOLDER=root):
            self.assertEqual(m.host_path(BASE/"edge.conf"),
                "/home/runner/work/infrastructure/infrastructure/tests/platform-integration/int02/edge.conf")

    def test_translation_refuses_half_configuration_and_escapes(self):
        with self.env(LOCAL_WORKSPACE_FOLDER="/host"):
            with self.assertRaises(m.Blocked):
                m.host_path(BASE)
        with self.env(LOCAL_WORKSPACE_FOLDER="relative",CONTAINER_WORKSPACE_FOLDER=str(m.ROOT)):
            with self.assertRaises(m.Blocked):
                m.host_path(BASE)
        with self.env(LOCAL_WORKSPACE_FOLDER="/host",CONTAINER_WORKSPACE_FOLDER=str(BASE)):
            with self.assertRaises(m.Blocked):
                m.host_path(m.ROOT/"README.md")

    def test_only_build_contexts_stay_container_paths(self):
        runner=(BASE/"orchestrate.py").read_text()
        for name in ("L4_RUNTIME","L4_PROBE_SOURCE","L4_TLS","L4_EDGE_CONFIG"):
            self.assertRegex(runner,'"'+name+r'": host_path\(')
        for name in ("L4_IAM_SOURCE","L4_CP_SOURCE","L4_CP_DOCKERFILE"):
            self.assertNotRegex(runner,'"'+name+r'": host_path\(')
        self.assertIn("verify_bind_mounts(p, directory, envfile, lock)",runner)

    def test_candidate_replaces_exactly_one_validated_pin(self):
        data=m.load()
        with self.env():
            self.assertEqual(m.candidate_pins(data),(data["sources"],None))
        sha="a"*40
        with self.env(INT02_CANDIDATE_REPOSITORY="baobab-cp",INT02_CANDIDATE_SHA=sha):
            pins,candidate=m.candidate_pins(data)
        self.assertEqual(pins["baobab-cp"],sha)
        self.assertEqual(pins["baobab-iam"],data["sources"]["baobab-iam"])
        self.assertEqual(candidate,{"repository":"baobab-cp","sha":sha,
                                    "lock_pin":data["sources"]["baobab-cp"]})
        for repo,value in (("baobab-erp",sha),("baobab-cp","main"),("baobab-cp","a"*39),
                           ("",sha),("baobab-cp",""),("shared",sha)):
            with self.env(INT02_CANDIDATE_REPOSITORY=repo,INT02_CANDIDATE_SHA=value):
                with self.assertRaises(m.Blocked):
                    m.candidate_pins(data)

    def test_receipt_records_materialised_pins_and_candidate(self):
        data=m.load()
        candidate={"repository":"baobab-iam","sha":"b"*40,"lock_pin":data["sources"]["baobab-iam"]}
        session={"project":"l4-3333333333333333","sources":{**data["sources"],"baobab-iam":"b"*40},
                 "candidate":candidate}
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(m,"EVIDENCE",Path(d)):
                m.write_evidence(session,data,{"scenarios":{},"checks":{}},accepted=False)
            evidence=json.loads(next(Path(d).glob("*.json")).read_text())
        self.assertEqual(evidence["source_pins"]["baobab-iam"],"b"*40)
        self.assertEqual(evidence["lock_pins"],data["sources"])
        self.assertEqual(evidence["candidate"],candidate)
        self.assertRegex(evidence["harness_candidate_sha"],r"^([0-9a-f]{40}|unavailable)$")

    def test_integration_codespace_matches_the_ci_executor(self):
        dc=json.loads((m.ROOT/".devcontainer/platform-integration/devcontainer.json").read_text())
        self.assertEqual(dc["remoteEnv"],{"LOCAL_WORKSPACE_FOLDER":"${localWorkspaceFolder}",
                                          "CONTAINER_WORKSPACE_FOLDER":"${containerWorkspaceFolder}"})
        data=m.load()
        self.assertGreaterEqual(dc["hostRequirements"]["cpus"],data["requirements"]["min_cpus"])
        self.assertGreaterEqual(int(dc["hostRequirements"]["memory"].rstrip("gb")),
                                data["requirements"]["min_ram_gib"])
        self.assertEqual(dc["forwardPorts"],[])

    def test_live_job_runs_the_codespace_entrypoints_in_the_devcontainer(self):
        wf=(m.ROOT/".github/workflows/platform-int02.yml").read_text()
        # Only organisation-trusted action owners; the CLI comes from a lockfile.
        self.assertNotIn("devcontainers/ci@",wf)
        self.assertIn("npm ci --prefix tests/platform-integration/devcontainer-cli --ignore-scripts",wf)
        self.assertEqual(wf.count("--config .devcontainer/platform-integration/devcontainer.json"),2)
        self.assertIn("bash tests/platform-integration/int02/run-in-devcontainer.sh",wf)
        lock=json.loads((m.ROOT/"tests/platform-integration/devcontainer-cli/package-lock.json").read_text())
        cli=lock["packages"]["node_modules/@devcontainers/cli"]
        self.assertEqual(cli["version"],"0.89.0")
        self.assertTrue(cli["integrity"].startswith("sha512-"))
        self.assertFalse(any(v.get("hasInstallScript") for v in lock["packages"].values()))
        script=(BASE/"run-in-devcontainer.sh").read_text()
        for stage in ("materialise","up","test","evidence"):
            self.assertIn('python3 "$L4" '+stage+" iam-cp",script)
        self.assertIn("trap cleanup EXIT",script)
        self.assertIn('[ "$rc" -ne 0 ] || rc=3',script)

    def test_devcontainer_image_is_pinned_and_apt_source_repaired(self):
        dc=json.loads((m.ROOT/".devcontainer/platform-integration/devcontainer.json").read_text())
        self.assertEqual(dc["build"],{"dockerfile":"Dockerfile"})
        self.assertNotIn("image",dc)
        docker=(m.ROOT/".devcontainer/platform-integration/Dockerfile").read_text()
        self.assertRegex(docker,r"(?m)^FROM mcr\.microsoft\.com/devcontainers/python:1-3\.12-bookworm@sha256:[0-9a-f]{64}$")
        self.assertIn("RUN rm -f /etc/apt/sources.list.d/yarn.list",docker)
        self.assertRegex(docker,r"(?m)^USER vscode$")

    def test_only_organisation_trusted_action_owners(self):
        import re
        wf=(m.ROOT/".github/workflows/platform-int02.yml").read_text()
        trusted={"actions","github","docker","anchore","astral-sh","aquasecurity","codecov","sigstore",
                 "softprops","hashicorp","dtolnay","pnpm","changesets","baobab-platform"}
        steps="\n".join(l for l in wf.splitlines() if not l.lstrip().startswith("#"))
        found=re.findall(r"uses: ([A-Za-z0-9_.-]+)/[^@\s]+@([^\s#]+)",steps)
        self.assertGreaterEqual(len(found),3)
        for owner,ref in found:
            self.assertIn(owner,trusted)
            self.assertRegex(ref,r"^[0-9a-f]{40}$")

    def test_reusable_workflow_inputs_are_validated_and_never_interpolated(self):
        import re
        wf=(m.ROOT/".github/workflows/platform-int02.yml").read_text()
        self.assertIn("workflow_call:",wf)
        for name in ("harness_sha","candidate_repository","candidate_sha"):
            self.assertIn("      "+name+":",wf)
        # Caller inputs reach run: blocks only through env, never ${{ }} in shell.
        for block in re.findall(r"\n        run: \|\n((?:          .*\n?)+)",wf):
            self.assertNotIn("${{",block)
        self.assertIn("repository: ${{ inputs.harness_sha && 'baobab-platform/infrastructure' || github.repository }}",wf)
        self.assertIn('[ "$(git rev-parse HEAD)" != "$HARNESS_SHA" ]',wf)
        self.assertIn("persist-credentials: false",wf)
        self.assertNotIn("secrets:",wf)
        self.assertNotIn("pull_request_target",wf)



class ScenarioClassificationTest(unittest.TestCase):
    """The probe's real exercise() against a scripted CP (no network)."""

    def load_probe(self, runtime):
        import importlib, os, sys, types
        env={"L4_ISSUER":"https://iam.int02.test/realms/baobab","L4_CP":"https://cp.int02.test",
             "L4_CA_FILE":"/dev/null","L4_WORKLOAD_SEED":"x","L4_TEST_ADMIN_CLIENT_SECRET":"x",
             "L4_TEST_USER_PASSWORD":"x"}
        with mock.patch.dict(os.environ,env), mock.patch("ssl.create_default_context"):
            spec=importlib.util.spec_from_file_location("int02_probe",BASE/"probe.py")
            probe=importlib.util.module_from_spec(spec); spec.loader.exec_module(probe)
        probe.RUNTIME=runtime
        return probe

    def run_exercise(self, decision_a, decision_b, missing_org=(200,{"context_id":"ctx-c"})):
        import base64, io, contextlib
        with tempfile.TemporaryDirectory() as d:
            runtime=Path(d)
            (runtime/"fixtures.json").write_text(json.dumps({"tenant":"tn_a","other_tenant":"tn_b",
                "organisation":"org-a","other_organisation":"org-b","no_primary_tenant":"tn_c",
                "market":"mkt_l4test","market_country":"ZA"}))
            probe=self.load_probe(runtime)
            def jwt(claims):
                return "h."+base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")+".s"
            iss=probe.ISSUER
            tokens={"w":jwt({"iss":iss,"aud":"baobab-control-plane","actor_type":"workload","scope":"context:resolve"}),
                    "h":jwt({"iss":iss,"actor_type":"human"}),
                    "o":jwt({"iss":iss,"aud":"baobab-pulse"})}
            def request(method,url,body=None,token=None,context=None):
                if url.endswith("/effective-authority"): return 200,{}
                if url.endswith("/platform-context/resolve"):
                    if token==tokens["o"]: return 401,{}
                    if body=={"tenant_id":"tn_a","organisation_id":"org-a"}:
                        return 200,{"tenant_id":"tn_a","organisation_id":"org-a","context_id":"ctx-a",
                                    "country_code":"ZA","market_id":"mkt_l4test"}
                    if body=={"tenant_id":"tn_b"}: return 200,{"context_id":"ctx-b"}
                    if body=={"tenant_id":"tn_c"}: return missing_org
                    return 403,{}
                if url.endswith("/capabilities/resolve"):
                    return 200,dict(decision_a if body["context_id"]=="ctx-a" else decision_b)
                raise AssertionError(url)
            out=io.StringIO()
            with mock.patch.object(probe,"request",side_effect=request), \
                 mock.patch.object(probe,"workload",return_value=tokens["w"]), \
                 mock.patch.object(probe,"human",return_value=tokens["h"]), \
                 mock.patch.object(probe,"other",return_value=tokens["o"]), \
                 mock.patch.object(probe,"Path",side_effect=lambda p: runtime/"tok"), \
                 contextlib.redirect_stdout(out):
                probe.exercise()
            return json.loads(out.getvalue())

    def test_cp_refusing_an_uncertified_provider_is_blocked_not_pass(self):
        r=self.run_exercise({"decision":"UNAVAILABLE","reason_code":"PROVIDER_HEALTH_UNKNOWN"},
                            {"decision":"DENIED","reason_code":"GRANT_NOT_FOUND"})
        self.assertEqual(r["scenarios"]["L4-CP-02"],"BLOCKED")
        self.assertEqual(r["scenarios"]["L4-CP-03"],"BLOCKED")
        self.assertTrue(r["checks"]["cp03_sibling_denied"])
        self.assertTrue(r["checks"]["cp02_missing_grant_denied"])
        self.assertEqual(r["observations"]["cp02_tenant_reason"],"PROVIDER_HEALTH_UNKNOWN")

    def test_a_fixture_fault_is_fail(self):
        r=self.run_exercise({"decision":"UNAVAILABLE","reason_code":"BINDING_NOT_FOUND"},
                            {"decision":"DENIED","reason_code":"GRANT_NOT_FOUND"})
        self.assertEqual(r["scenarios"]["L4-CP-02"],"FAIL")

    def test_sibling_denial_counts_only_when_tenant_a_is_entitled(self):
        r=self.run_exercise({"decision":"DENIED","reason_code":"GRANT_NOT_FOUND"},
                            {"decision":"DENIED","reason_code":"GRANT_NOT_FOUND"})
        self.assertFalse(r["checks"]["cp03_sibling_denied"])
        self.assertEqual(r["scenarios"]["L4-CP-03"],"FAIL")
        self.assertEqual(r["scenarios"]["L4-CP-02"],"FAIL")

    def test_cp01_probe_negatives_include_missing_and_fabricated_organisation(self):
        r=self.run_exercise({"decision":"UNAVAILABLE","reason_code":"PROVIDER_HEALTH_UNKNOWN"},
                            {"decision":"DENIED","reason_code":"GRANT_NOT_FOUND"})
        for name in ("cp01_missing_organisation_not_fabricated","cp01_fabricated_organisation_denied",
                     "cp01_swapped_organisation_denied","cp01_fabricated_tenant_denied"):
            self.assertTrue(r["checks"][name],name)
        self.assertEqual(r["scenarios"]["L4-CP-01"],"BLOCKED")

    def test_missing_organisation_outcomes(self):
        ok=({"decision":"UNAVAILABLE","reason_code":"PROVIDER_HEALTH_UNKNOWN"},
            {"decision":"DENIED","reason_code":"GRANT_NOT_FOUND"})
        issued=self.run_exercise(*ok)
        self.assertEqual(issued["observations"]["cp01_missing_organisation_outcome"],"ISSUED_WITHOUT_ORGANISATION")
        self.assertTrue(issued["checks"]["cp01_missing_organisation_not_fabricated"])
        denied=self.run_exercise(*ok,missing_org=(403,{}))
        self.assertEqual(denied["observations"]["cp01_missing_organisation_outcome"],"DENIED")
        invented=self.run_exercise(*ok,missing_org=(200,{"context_id":"c","organisation_id":"x"}))
        self.assertEqual(invented["observations"]["cp01_missing_organisation_outcome"],"FABRICATED")
        self.assertFalse(invented["checks"]["cp01_missing_organisation_not_fabricated"])
        self.assertEqual(invented["scenarios"]["L4-CP-01"],"FAIL")

    def test_cp01_positive_requires_the_market_context(self):
        r=self.run_exercise({"decision":"UNAVAILABLE","reason_code":"PROVIDER_HEALTH_UNKNOWN"},
                            {"decision":"DENIED","reason_code":"GRANT_NOT_FOUND"})
        self.assertTrue(r["checks"]["cp01_positive"])
        probe=(BASE/"probe.py").read_text()
        self.assertIn('context.get("market_id")==fixture["market"]',probe)

    def test_cp01_pass_needs_a_denied_missing_organisation(self):
        runner=(BASE/"orchestrate.py").read_text()
        self.assertIn('get("cp01_missing_organisation_outcome") == "DENIED":',runner)
        self.assertIn('cases["L4-CP-01"] = "PASS"',runner)

    def test_untrusted_reason_codes_never_reach_the_log(self):
        r=self.run_exercise({"decision":"UNAVAILABLE","reason_code":"eyJ leak <script>"},
                            {"decision":"WHATEVER","reason_code":"GRANT_NOT_FOUND"})
        self.assertEqual(r["observations"]["cp02_tenant_reason"],"NONE")
        self.assertEqual(r["observations"]["cp03_sibling_decision"],"OTHER")
        summary=m.outcome_summary(r["scenarios"],r["checks"],r["observations"])
        self.assertNotIn("eyJ",summary)


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
