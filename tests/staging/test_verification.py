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
        for mutation in ['image', 'account', 'file', 'plaintext', 'master', 'version']:
            value = copy.deepcopy(self.release)
            if mutation == 'image': value['services']['iam']['image'] = 'repository:latest'
            if mutation == 'account': value['services']['cp']['bundle_secret_arn'] = value['services']['cp']['bundle_secret_arn'].replace('123456789012', '999999999999')
            if mutation == 'file': value['services']['iam']['bundle_files'].append('../private')
            if mutation == 'plaintext': value['services']['cp']['environment']['DATABASE_URL'] = 'postgres://user:password@db/tenant'
            if mutation == 'master': value['browser_realms'] = ['master']
            if mutation == 'version': value['services']['cp']['secret_environment']['DATABASE_URL'] = value['services']['cp']['bundle_secret_arn'] + ':database_url:AWSCURRENT:'
            with self.subTest(mutation=mutation), self.assertRaises(ValueError): self.validate(value)
    def test_preflight_denies_wrong_account_before_artifact_reads(self):
        with patch.object(s, 'aws', return_value={'Account': '999999999999'}) as calls:
            with self.assertRaises(ValueError): s.preflight(self.release)
            self.assertEqual(calls.call_count, 1)
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
