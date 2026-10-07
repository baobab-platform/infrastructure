import copy
import datetime
import importlib.util
import json
import pathlib
import tempfile
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[2]
def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'deploy' / 'verification' / (name + '.py'))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result
s = module('staging')
p = module('private_authorities')

class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.release = json.loads((ROOT / 'terraform/environments/staging/tests/release.fixture.json').read_text())
    def validate(self, value):
        with tempfile.NamedTemporaryFile(mode='w') as stream:
            json.dump(value, stream); stream.flush()
            return s.release(stream.name)
    def test_offline_validates_without_aws(self):
        with patch.object(s, 'aws', side_effect=AssertionError('AWS called')):
            self.validate(self.release)
    def test_mutable_image_cross_account_extra_file_and_plaintext_deny(self):
        for mutation in ['image', 'account', 'file', 'plaintext', 'master', 'version', 'missing_pulse', 'pulse_authority']:
            value = copy.deepcopy(self.release)
            if mutation == 'image': value['services']['iam']['image'] = 'repository:latest'
            if mutation == 'account': value['services']['cp']['bundle_secret_arn'] = value['services']['cp']['bundle_secret_arn'].replace('123456789012', '999999999999')
            if mutation == 'file': value['services']['iam']['bundle_files'].append('../private')
            if mutation == 'plaintext': value['services']['cp']['environment']['DATABASE_URL'] = 'postgres://user:password@db/tenant'
            if mutation == 'master': value['browser_realms'] = ['master']
            if mutation == 'version': value['services']['cp']['secret_environment']['DATABASE_URL'] = value['services']['cp']['bundle_secret_arn'] + ':database_url:AWSCURRENT:'
            if mutation == 'missing_pulse': del value['services']['pulse']
            if mutation == 'pulse_authority': del value['services']['pulse']['environment']['PULSE_IAM_TOKEN_URL']
            with self.subTest(mutation=mutation), self.assertRaises(ValueError): self.validate(value)
    def test_preflight_denies_wrong_account_before_artifact_reads(self):
        with patch.object(s, 'aws', return_value={'Account': '999999999999'}) as calls:
            with self.assertRaises(ValueError): s.preflight(self.release)
            self.assertEqual(calls.call_count, 1)
    def test_plan_preflight_skips_ecr_but_checks_account_metadata(self):
        seen = []
        def aws(*args):
            seen.append(args)
            if args[:2] == ('sts', 'get-caller-identity'):
                return {'Account': '123456789012'}
            if args[:2] == ('secretsmanager', 'describe-secret'):
                return {'VersionIdsToStages': {'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa': ['AWSCURRENT']}}
            if args[:2] == ('acm', 'describe-certificate'):
                return {'Certificate': {'Status': 'ISSUED', 'SubjectAlternativeNames': ['sso.staging.example.test']}}
            if args[:2] == ('route53', 'get-hosted-zone'):
                return {'HostedZone': {'Name': 'staging.example.test.', 'Config': {'PrivateZone': False}}}
            if args[:2] == ('rds', 'describe-db-engine-versions'):
                return {'DBEngineVersions': [{'EngineVersion': '17.6'}]}
            raise AssertionError('unexpected AWS call: ' + repr(args))
        with patch.object(s, 'aws', side_effect=aws):
            result = s.preflight(self.release, check_images=False)
        self.assertIs(result['artifacts_available'], False)
        self.assertFalse(any(args[:2] == ('ecr', 'batch-get-image') for args in seen))

    def test_observe_denies_unstable_or_multiple_writer_service(self):
        for service in [
            {'desiredCount': 1, 'runningCount': 2, 'pendingCount': 0, 'deployments': [{'rolloutState': 'COMPLETED'}]},
            {'desiredCount': 1, 'runningCount': 1, 'pendingCount': 0, 'deployments': [{'rolloutState': 'IN_PROGRESS'}]},
        ]:
            with patch.object(s, 'aws', side_effect=[{'Account': '123456789012'}, {'services': [service]}]):
                with self.assertRaises(ValueError): s.observe(self.release, 'cluster', 'a' * 40)

class PrivateAuthorityTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime.datetime.now(datetime.timezone.utc)
        self.expected = {'binding': {'provider_id': 'provider_test', 'engine_instance_id': 'ei_test'}, 'scope': {'organisation_id': 'org_test', 'estate_id': 'estate_test'}, 'runtime_capability': 'OIDC_FEDERATION'}
        self.response = {'ProviderID': 'provider_test', 'EngineInstanceID': 'ei_test', 'Scope': {'OrganisationID': 'org_test', 'EstateID': 'estate_test'}, 'ProviderStatus': 'ACTIVE', 'InstanceStatus': 'ACTIVE', 'BindingStatus': 'ACTIVE', 'RuntimeCapability': 'OIDC_FEDERATION', 'SupportStatus': 'VERIFIED', 'ProfileRevision': 1, 'ArtifactDigest': 'sha256:' + 'a'*64, 'DeployedArtifactDigest': 'sha256:'+'a'*64, 'EvidenceExpiresAt': (self.now + datetime.timedelta(minutes=5)).isoformat()}
    def test_current_exact_scope_and_artifact_required(self):
        p.validate_binding(self.response, self.expected, self.now)
        for field, value in [('ProviderID', 'other'), ('InstanceStatus', 'SUSPENDED'), ('SupportStatus', 'CLAIMED'), ('DeployedArtifactDigest', 'sha256:'+'b'*64), ('EvidenceExpiresAt', (self.now-datetime.timedelta(seconds=1)).isoformat())]:
            response = {**self.response, field: value}
            with self.subTest(field=field), self.assertRaises(ValueError): p.validate_binding(response, self.expected, self.now)
    def test_public_or_redirected_credential_destination_denied(self):
        for origin in ['http://cp.staging.baobab.internal:8443', 'https://public.example', 'https://user@cp.staging.baobab.internal:8443', 'https://cp.staging.baobab.internal:8443?token=x']:
            with self.assertRaises(ValueError): p.endpoint(origin, 'staging.baobab.internal')

if __name__ == '__main__': unittest.main()

class OIDCTests(unittest.TestCase):
    def setUp(self):
        self.module = module('oidc_credentials')
        self.environment = {'STAGING_ACCOUNT_ID': '123456789012', 'STAGING_ROLE_ARN': 'arn:aws:iam::123456789012:role/staging-plan', 'ACTIONS_ID_TOKEN_REQUEST_URL': 'https://token.actions.githubusercontent.com/job?audience=wrong', 'GITHUB_RUN_ID': '123'}
    def test_token_audience_and_file_delivery(self):
        def get_token(path):
            self.assertIn('audience=sts.amazonaws.com', path)
            self.assertNotIn('audience=wrong', path)
            return 'header.payload.signature'
        def assume(args):
            token = args[args.index('--web-identity-token') + 1]
            self.assertTrue(token.startswith('file://'))
            self.assertNotIn('header.payload.signature', args)
            self.assertEqual(pathlib.Path(token[7:]).stat().st_mode & 0o777, 0o600)
            return {'AssumedRoleUser': {'Arn': 'arn:aws:sts::123456789012:assumed-role/staging-plan/session'}, 'Credentials': {'AccessKeyId': 'temporary', 'SecretAccessKey': 'temporary-secret', 'SessionToken': 'temporary-session'}}
        result = self.module.credentials(self.environment, get_token, assume)
        self.assertEqual(result['AWS_REGION'], 'af-south-1')
    def test_untrusted_token_endpoint_and_wrong_account_deny(self):
        wrong = {**self.environment, 'ACTIONS_ID_TOKEN_REQUEST_URL': 'https://actions.githubusercontent.com.attacker.test/token'}
        with self.assertRaises(ValueError): self.module.credentials(wrong, lambda path: 'h.p.s', None)
        response = {'AssumedRoleUser': {'Arn': 'arn:aws:sts::999999999999:assumed-role/role/session'}}
        with self.assertRaises(ValueError): self.module.credentials(self.environment, lambda path: 'h.p.s', lambda args: response)
