"""Engine-neutral source/security contracts. No mocks qualify real IAM or L4."""
import copy
import contextlib
import io
import subprocess
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

BASE=Path(__file__).resolve().parent
sys.path.insert(0,str(BASE))
import engine_contract as contract
import engines
import engine_sdk

class EngineReceiptTests(unittest.TestCase):
    def setUp(self):
        self.profile={'profile_key':'future-engine','subject_engine':'baobab-future','capabilities':[{'capability_key':'content.entry.resolve'}],
            'reporting':{'case_ids':sorted(contract.COMMON)+['FUTURE-NATIVE-POSITIVE']}}
        self.run='a'*32
        self.report=contract.fresh(self.profile,self.run)

    def test_fresh_report_is_neither_native_nor_protected_acceptance(self):
        contract.validate(self.report,self.run)
        self.assertTrue(all(row['result']=='BLOCKED' for row in self.report['cases'].values()))
        self.assertFalse(self.report['production_authorized'])

    def test_source_cannot_self_promote_native_or_protected_authority(self):
        mutations=[lambda d:d.update(production_authorized=True),lambda d:d.update(protected_acceptance=True),
            lambda d:d['capabilities']['content.entry.resolve'].update(certification='CERTIFIED'),
            lambda d:d['capabilities']['content.entry.resolve'].update(development='OBSERVED'),
            lambda d:d['cases'].pop('ENG-ONB-06'),lambda d:d.update(client_secret='not-allowed'),
            lambda d:d['cases'].update({'ENG-ONB-08':{'result':'PASS','reason':'OBSERVED'}}),
            lambda d:d['cases'].update({'ENG-ONB-05':{'result':'PASS','reason':'OBSERVED'}})]
        for mutate in mutations:
            report=copy.deepcopy(self.report);mutate(report)
            with self.assertRaises(ValueError):contract.validate(report,self.run)

    def test_cleanup_needs_both_real_issuer_and_independent_host_absence(self):
        self.report['cases']['ENG-ONB-08']={'result':'PASS','reason':'OBSERVED'}
        self.report['independent_observations']['host_cleanup']=True
        with self.assertRaises(ValueError):contract.validate(self.report,self.run)
        self.report['independent_observations']['issuer_cleanup']=True
        contract.validate(self.report,self.run)

    def test_static_requests_cannot_start_or_delete_a_runtime(self):
        for action in ('prepare','up','test','down','recover','run'):
            with patch.object(engines.dev,'prepare',side_effect=AssertionError('runtime started')) as prepare:
                self.assertEqual(engines.main([action,'--static']),2)
                prepare.assert_not_called()

    def test_profile_bootstrap_reads_private_file_as_its_operator(self):
        state={'engine_profile':{'profile_key':'future-engine'},'uid':1001,'gid':1001,
            'run_id':self.run,'lease_seconds':600,'deadline':engines.time.time()+600,'bootstrap_lease':500}
        class CapturedCommand(Exception):pass
        with patch.object(engines.dev,'read',return_value={'maker':'maker','checker':'checker'}), \
             patch.object(engines.dev,'compose',side_effect=CapturedCommand) as compose, \
             patch.object(engines.dev.adapter,'host',side_effect=str):
            with self.assertRaises(CapturedCommand):engines.dev.bootstrap(Path('/private'),state)
        args=compose.call_args.args
        self.assertEqual(args[args.index('--user')+1],'1001:1001')
        self.assertIn('/private/engine-profile.json:/engine-profile.json:ro',args)

    def test_native_diagnostics_do_not_reflect_response_or_request_values(self):
        driver=object.__new__(engine_sdk.Driver)
        driver.last_headers={'idempotent-replayed':'secret-replay-value'}
        output=io.StringIO()
        with patch.object(driver,'request',return_value=(409,{'code':'secret-code','detail':'secret-detail'})), contextlib.redirect_stdout(output):
            driver.native('/secret-path',{'secret':'secret-body'},'secret-token','secret-context')
        self.assertEqual(output.getvalue(),'ENGINE_NATIVE_HTTP=409_CODE_OTHER_REPLAY_other\n')

    def test_failed_process_only_releases_closed_native_diagnostics(self):
        allowed='ENGINE_NATIVE_HTTP=409_CODE_IDEMPOTENCY_KEY_REUSED_REPLAY_absent'
        rejected=[allowed+' secret-token','ENGINE_NATIVE_HTTP=409_CODE_secret-code_REPLAY_absent','secret-response']
        result=subprocess.CompletedProcess(['private-command'],2,'\n'.join([allowed,*rejected]),'secret-stderr')
        output=io.StringIO()
        with patch.object(engines.dev.subprocess,'run',return_value=result),contextlib.redirect_stdout(output):
            with self.assertRaises(engines.dev.Refused):engines.dev.call(['private-command'])
        self.assertEqual(output.getvalue(),allowed+'\n')

    def test_multiple_engine_owned_stores_cannot_share_dns(self):
        profile={'subject_engine':'baobab-future','services':{'required':[{'key':'canonical-store','kind':'postgresql'},{'key':'history-store','kind':'postgresql'}]}}
        names={engines.native_service_name(profile,node) for node in profile['services']['required']}
        self.assertEqual(len(names),2)
        self.assertTrue(all(name.startswith('future-') for name in names))

if __name__=='__main__':unittest.main()
