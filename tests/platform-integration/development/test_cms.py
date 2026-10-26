"""Source failure contracts only; these results never qualify NAB-03."""
import copy
import importlib
import json
import os
import re
from types import SimpleNamespace
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
import cms_contract
import cms_vertical
import dev
import ci_cms

class CMSContracts(unittest.TestCase):
    def test_estate_failure_logs_publish_only_closed_classes(self):
        raw='private secret body\nserver | {"event":"content.capability","key":"home","outcome":"unavailable:CAPABILITY_NOT_RESOLVED"}\nserver | {"event":"content.capability","key":"private-tenant","outcome":"private body"}\nRequired published content unavailable'
        with patch.object(dev,'compose',return_value=raw),patch('builtins.print') as output:
            cms_vertical.estate_diagnostics(Path('/private'),{})
        self.assertEqual([x.args[0] for x in output.call_args_list],[
            'DEV05_ESTATE_DIAGNOSTIC=HOME_UNAVAILABLE_CAPABILITY_NOT_RESOLVED',
            'DEV05_ESTATE_DIAGNOSTIC=UNAVAILABLE_CONTENT'])

    def test_estate_requires_rendered_heading_and_footer_not_metadata_or_serialized_data(self):
        with patch('ssl.create_default_context',return_value=SimpleNamespace()):
            probe=importlib.import_module('cms_probe')
        expected=['Synthetic & current','Native footer']
        self.assertTrue(probe.rendered_markers('<h1><span>Synthetic &amp; current</span></h1><footer><p>Native footer</p></footer>',expected))
        for page in ('<title>Synthetic &amp; current</title><footer>Native footer</footer>',
                     '<h1>Synthetic &amp; current</h1><script>Native footer</script>',
                     '<h1>Other</h1><footer>Native footer</footer><script>Synthetic &amp; current</script>'):
            self.assertFalse(probe.rendered_markers(page,expected))

    def test_revoked_grant_cannot_substitute_for_original_missing_grant_case(self):
        with patch('ssl.create_default_context',return_value=SimpleNamespace()):
            probe=importlib.import_module('cms_probe')
        for action,reason,expected in (('revoked-grant','GRANT_REVOKED','BLOCKED'),
                                       ('unentitled','GRANT_NOT_FOUND','PASS'),
                                       ('unentitled','GRANT_REVOKED','FAIL')):
            with self.subTest(action=action,reason=reason),tempfile.TemporaryDirectory() as temp:
                root=Path(temp);run='a'*32;value=cms_contract.fresh(run)
                value['cases']['published-home-nav-footer'].update(result='PASS',reason='OBSERVED')
                (root/'cms-report.json').write_text(json.dumps(value))
                (root/'cms-capability.json').write_text(json.dumps({'source_present':action!='unentitled',
                    'source_active':action!='unentitled','grant_active':action=='unentitled','binding_active':True}))
                (root/'cms-published-markers.json').write_text('[]')
                with patch.object(probe.p,'ROOT',root),patch.dict(os.environ,{'DEV01_RUN_ID':run}), \
                     patch.object(probe,'config',return_value=({}, {}, {})), \
                     patch.object(probe,'context',return_value=('cp',{'context_id':'context'})), \
                     patch.object(probe,'token',return_value='cms'), \
                     patch.object(probe.p,'request',return_value=(200,{'decision':'DENIED','reason_code':reason},None)), \
                     patch.object(probe,'resolve',return_value=(403,{'code':'CONTENT_CONTEXT_REJECTED'},None)), \
                     patch.object(probe,'estate_page',return_value=(500,True)):
                    if expected=='FAIL':
                        with self.assertRaises(SystemExit):probe.main(action)
                    else:probe.main(action)
                self.assertEqual(json.loads((root/'cms-report.json').read_text())['cases']['missing-grant']['result'],expected)

    def test_issuer_client_readback_uses_native_duration_and_rejects_changed_ttl(self):
        with patch('ssl.create_default_context',return_value=SimpleNamespace()):
            probe=importlib.import_module('cms_probe')
        for changed in (None,probe.CONSUMER,probe.VALIDATOR,probe.BFF):
            with self.subTest(changed=changed),tempfile.TemporaryDirectory() as temp:
                root=Path(temp)
                state={'run_id':'a'*32,'secrets':{key:'private-test-secret' for key in ('cms_consumer','cms_validator','bff')}}
                created={}
                def api(method,path,body=None):
                    name=path.rsplit('/',1)[-1]
                    if method=='POST':
                        created[body['client_id']]=copy.deepcopy(body)
                        return 201,{}
                    if name not in created:return 404,{}
                    actual=copy.deepcopy(created[name])
                    actual['client_credentials_grant_access_token_lifespan']=(
                        '55s' if name==probe.VALIDATOR else '1m0s')
                    if name==changed:actual['client_credentials_grant_access_token_lifespan']='1m1s'
                    return 200,actual
                with patch.object(probe,'config',return_value=({'clients':{}},{},{})), \
                     patch.object(probe.p,'read',return_value=state),patch.object(probe.p,'ROOT',root), \
                     patch.object(probe.p,'api',side_effect=api):
                    if changed:
                        with self.assertRaisesRegex(ValueError,'^HYDRA_READBACK$'):probe.clients()
                        self.assertFalse((root/'native.json').exists())
                    else:
                        probe.clients()
                        self.assertEqual(set(json.loads((root/'native.json').read_text())['clients']),
                                         {probe.CONSUMER,probe.VALIDATOR,probe.BFF})
                        self.assertEqual(created[probe.VALIDATOR]['client_credentials_grant_access_token_lifespan'],'55s')

    def test_package_access_is_private_scoped_and_removed_on_every_exit(self):
        for failure in ('none','login','build'):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as temp:
                directory=Path(temp)
                def command(args,**kwargs):
                    self.assertEqual(args[:3],['docker','login','ghcr.io'])
                    self.assertEqual(kwargs['stdin'],'private-package-fixture')
                    self.assertNotIn('DEV05_NPM_TOKEN',kwargs['env'])
                    self.assertEqual(kwargs['env']['DOCKER_CONFIG'],str(directory/'build-docker-config'))
                    self.assertEqual((directory/'build-docker-config').stat().st_mode & 0o777,0o700)
                    if failure=='login':raise dev.Refused('IMAGE_UNAVAILABLE')
                with patch.dict(os.environ,{'DEV05_NPM_TOKEN':'private-package-fixture','DEV05_REGISTRY_USERNAME':'test-owner'}), patch.object(dev,'call',side_effect=command) as call:
                    def build():
                        with cms_vertical.package_access(directory,{}) as (env,tokenfile):
                            self.assertEqual(tokenfile.read_text(),'private-package-fixture')
                            self.assertEqual(tokenfile.stat().st_mode & 0o777,0o600)
                            self.assertEqual(env['DOCKER_CONFIG'],str(directory/'build-docker-config'))
                            if failure=='build':raise dev.Refused('COMMAND_FAILED')
                    if failure=='none':build()
                    else:
                        with self.assertRaises(dev.Refused):build()
                    call.assert_called_once()
                self.assertFalse((directory/'package-token').exists())
                self.assertFalse((directory/'build-docker-config').exists())

    def test_fixture_failure_classification_is_closed_and_never_leaks_logs(self):
        # The CMS candidate emits a fixed phase identifier instead of raw
        # Payload/SQL/tenant material. Unknown or forged labels remain opaque.
        for stderr, expected in (
            ('CMS_INT03_STAGE_FAILED=CONTENT_SEED\nprivate db secret', 'CMS_FIXTURE_CONTENT_SEED'),
            ('CMS_INT03_STAGE_FAILED=NOT_REVIEWED\n', 'COMMAND_FAILED'),
            ('CMS_INT03_STAGE_FAILED=CONTENT_SEED secret=abc\n', 'COMMAND_FAILED'),
        ):
            with self.subTest(stderr=stderr.splitlines()[0]):
                completed=SimpleNamespace(returncode=1,stdout='',stderr=stderr)
                with patch.object(dev.subprocess,'run',return_value=completed):
                    with self.assertRaises(dev.Refused) as caught:
                        dev.call(['docker','compose','run','cms-tool','node','--import','tsx',
                                  'scripts/qualification/int03-fixture.ts','seed'])
                self.assertEqual(str(caught.exception),expected)
                self.assertNotIn('secret',str(caught.exception))

    def test_original_inventory_cannot_omit_or_promote_a_blocker(self):
        run='a'*32;report=cms_contract.fresh(run)
        self.assertEqual(len(report['cases']),14)
        self.assertEqual(set(report['cases']),{'published-home-nav-footer','wrong-audience-token','wrong-credential','disabled-caller',
            'expired-caller-token','revoked-caller-token','missing-grant','wrong-owner-or-context','neighbour-tenant',
            'draft-or-preview','withdrawn-content','dependency-outage-and-restoration','validator-negatives','teardown'})
        cms_contract.validate(report,run)
        for change in (lambda r:r['cases'].pop('missing-grant'),lambda r:r.update(nab03_qualified=True),
            lambda r:r.update(protected_acceptance=True),lambda r:r['component_checks'].update(private_token=True),
            lambda r:r['cases']['teardown'].update(result='PASS')):
            bad=copy.deepcopy(report);change(bad)
            with self.assertRaises(ValueError):cms_contract.validate(bad,run)

    def test_fourteen_pass_labels_cannot_replace_native_binding_and_audit_evidence(self):
        report=cms_contract.fresh('a'*32)
        for row in report['cases'].values():row.update(result='PASS',reason='OBSERVED')
        report['nab03_qualified']=True;report['component_checks']['provider_declared_partial']=False
        with self.assertRaises(ValueError):cms_contract.validate(report,'a'*32)
        report['component_checks'].update({key:True for key in cms_contract.BOUND_COMPONENTS})
        cms_contract.validate(report,'a'*32)
        for key in cms_contract.BOUND_COMPONENTS:
            changed=copy.deepcopy(report);changed['component_checks'][key]=False
            with self.subTest(key=key),self.assertRaises(ValueError):cms_contract.validate(changed,'a'*32)

    def test_preparation_failure_removes_previous_green_suite(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for name in ('dev05-cms-suite.json','dev05-cms-suite.sha256.json'):(root/name).write_text('stale')
            with patch.object(dev,'EVIDENCE',root),patch.object(ci_cms.cms_vertical,'prepare',side_effect=ValueError('private-bearer')),patch.object(dev,'recover'):
                with self.assertRaisesRegex(dev.Refused,'^DEV05_PREPARATION_FAILED$'):ci_cms.main()
            self.assertFalse((root/'dev05-cms-suite.json').exists())
            self.assertFalse((root/'dev05-cms-suite.sha256.json').exists())

    def test_owner_proof_uses_file_owner_without_public_or_root_override(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);run='a'*32
            dev.write(root/'subjects.json',{'maker':'maker','checker':'checker'})
            dev.write(root/'cms-source.json',{'source_sha':'b'*40})
            state={'uid':1234,'gid':1235,'run_id':run,'bootstrap_lease':300}
            with patch.object(dev,'compose',return_value=json.dumps({'run_id':run})) as compose:
                cms_vertical.owner_fixture(root,state,'register')
            args=compose.call_args.args
            self.assertEqual(args[args.index('--user')+1],'1234:1235')
            self.assertEqual(args[args.index('--volume')+1],cms_vertical.adapter.host(root/'cms-source.json')+':/cms-source.json:ro')
            self.assertEqual((root/'cms-source.json').stat().st_mode & 0o777,0o600)

    def test_native_read_audit_requires_independent_matching_cp_decision(self):
        run='a'*32
        owner={'tenant_id':'tn_fixture','grant_id':'1'*32,'binding_id':'2'*32,'provider_id':'3'*32,'engine_instance_id':'4'*32}
        proof={'grant_id':'grant_'+'1'*32,'binding_id':'bind_'+'2'*32,'provider_id':'provider_'+'3'*32,
            'engine_instance_id':'ei_'+'4'*32,'resolution_id':'res_'+'5'*32,'context_id':'actual-context',
            'content_key':'home','record_id':'actual-record'}
        audit={'count':1,'latest':{'actor_id':cms_vertical.CONSUMER,'resource_id':'actual-record','correlation_id':'actual-correlation','resulting_state':proof}}
        with patch.object(dev,'read',return_value=owner),patch.object(cms_vertical,'read_audit',return_value=audit), \
             patch.object(dev,'compose',return_value='f') as compose:
            with self.assertRaisesRegex(dev.Refused,'DEV05_INDEPENDENT_CP_AUDIT_REQUIRED'):
                cms_vertical.verify_audit(Path('/private'),{'run_id':run})
            sql=compose.call_args.args[-1]
            self.assertIn("context_id='actual-context'",sql)
            self.assertIn("correlation_id::text='actual-correlation'",sql)

    def test_bff_epoch_matches_nabhold_store_and_preserves_all_run_bits(self):
        # Nabhold permits a lowercase initial letter and at most 32 characters.
        a='0'*32
        b='0'*31+'1'
        value=cms_vertical.bff_epoch(a)
        self.assertTrue(re.fullmatch(r'[a-z][a-z0-9-]{0,31}',value))
        self.assertLessEqual(len(value),32)
        self.assertNotEqual(value,cms_vertical.bff_epoch(b))
        self.assertEqual(cms_vertical.bff_epoch(a),value)
        for invalid in ('','0'*31,'0'*33,'g'*32,'A'*32):
            with self.subTest(invalid=invalid),self.assertRaises(dev.Refused):
                cms_vertical.bff_epoch(invalid)

    def test_source_profile_uses_immutable_owner_images_and_sources(self):
        value=cms_vertical.lock()
        self.assertEqual(set(value['sources']),{'baobab-cms','nabhold'})
        self.assertTrue(all(dev.SHA.fullmatch(sha) for sha in value['sources'].values()))
        for key in ('node','redis','frontend'):self.assertIn('@sha256:',value[key])
    def test_host_cleanup_never_promotes_partial_provider(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);state=root/'state';state.mkdir(mode=0o700);run='a'*32
            directory=state/run;directory.mkdir(mode=0o700)
            report=cms_contract.fresh(run)
            for row in report['cases'].values():row.update(result='PASS',reason='OBSERVED')
            report['cases']['published-home-nav-footer'].update(result='BLOCKED',reason='PROVIDER_NOT_ELIGIBLE')
            report['cases']['teardown'].update(result='BLOCKED',reason='TEARDOWN_PENDING')
            report['component_checks'].update(provider_declared_partial=True,native_clients_deleted=True,native_tokens_inactive=True)
            dev.write(directory/'state.json',{'run_id':run,'sources':{},'harness_sha':'b'*40,'image_ids':{},'lock_sha256':'c'*64,'tests':True,'cms':report})
            with patch.object(dev,'STATE',state),patch.object(dev,'EVIDENCE',root/'evidence'),patch.object(dev,'resources',return_value=[]):
                dev.down(run)
                receipt=dev.read(root/'evidence'/('dev01-'+run)/'completed/receipt.json')
            self.assertFalse(directory.exists());self.assertFalse(receipt['nab03_qualified'])
            self.assertEqual(receipt['cms']['cases']['teardown']['result'],'PASS')
            self.assertFalse(receipt['protected_acceptance'])

    def test_validator_proof_ceiling_is_below_runtime_max(self):
        with patch('ssl.create_default_context',return_value=SimpleNamespace()):
            probe=importlib.import_module('cms_probe')
        self.assertEqual(probe.VALIDATOR_CEILING,'55s')
        self.assertLess(int(probe.VALIDATOR_CEILING[:-1]),60)

    def test_validator_profile_reports_only_closed_current_claim_classes(self):
        with patch('ssl.create_default_context',return_value=SimpleNamespace()):
            probe=importlib.import_module('cms_probe')
        state={'secrets':{'cms_validator':'synthetic-private-test-secret'}}
        issued={'access_token':'synthetic-test-bearer','expires_in':60}
        valid={'active':True,'iss':probe.p.ISSUER,'client_id':probe.VALIDATOR,
               'actor_type':'workload','scope':'context:validate',
               'aud':['baobab-control-plane'],'sub':'synthetic-id',
               'iat':int(probe.time.time())-1,'exp':int(probe.time.time())+59}
        for claims,label in ((valid,'READY'),({**valid,'actor_type':'human'},'ACTOR_MISMATCH'),
                             ({**valid,'aud':['baobab-control-plane','baobab-cms']},'AUDIENCE_MISMATCH')):
            with self.subTest(label=label),patch.object(probe.p,'read',return_value=state), \
                 patch.object(probe.p,'request',side_effect=[(200,issued,None),(200,claims,None)]), \
                 patch('builtins.print') as printed:
                probe.validator_profile()
                self.assertEqual(printed.call_args.args[0],'DEV05_VALIDATOR_PROFILE='+label)
                self.assertNotIn('synthetic-private-test-secret',printed.call_args.args[0])

    def test_cms_failure_classification_is_closed_and_precise(self):
        with patch('ssl.create_default_context',return_value=SimpleNamespace()):
            probe=importlib.import_module('cms_probe')
        examples=[
            (503,{'code':'CONTENT_CONTEXT_UNAVAILABLE','title':'Not configured'},'CONFIG_NOT_READY'),
            (503,{'code':'CONTENT_CONTEXT_UNAVAILABLE','title':'Caller status unavailable'},'CALLER_STATUS_UNAVAILABLE'),
            (503,{'code':'CONTENT_CONTEXT_UNAVAILABLE','detail':'The Control Plane could not be reached to validate the context.'},'VALIDATOR_UNAVAILABLE'),
            (503,{'code':'CONTENT_CONTEXT_UNAVAILABLE','detail':'The projection could not be checked.'},'PROJECTION_UNAVAILABLE'),
            (503,{'code':'CONTENT_CONTEXT_UNAVAILABLE'},'CONTEXT_UNAVAILABLE'),
            (500,{'internal':'private error'},'HTTP_500'),
            (502,None,'HTTP_502'),
            (503,{'arbitrary':'unsafe content'},'HTTP_503'),
            (504,None,'HTTP_504'),
        ]
        for code,body,expected in examples:
            with self.subTest(code=code,expected=expected):
                self.assertEqual(probe.record_failure_class((code,body,None),'home'),expected)
                self.assertNotIn('private',expected)
    def test_native_delivery_request_preserves_cp_issued_legal_scope(self):
        with patch('ssl.create_default_context',return_value=SimpleNamespace()):
            probe=importlib.import_module('cms_probe')
        own={'tenant_id':'tn_dev','legal_entity_id':'DEV-0123456789ab-NABHOLD',
             'digital_estate_id':'11111111-1111-4111-8111-111111111111'}
        bootstrap={'market_ids':{'ZA':'mkt_devfixtureza'}}
        with patch.object(probe,'config',return_value=({},bootstrap,own)), \
             patch.object(probe.p,'request',return_value=(200,{},None)) as request:
            probe.resolve('synthetic-bearer','22222222-2222-4222-8222-222222222222')
            body=request.call_args.args[2]
            self.assertEqual(body['legal_entity_id'],own['legal_entity_id'])
            self.assertEqual(body['tenant_id'],own['tenant_id'])
            self.assertEqual(body['digital_estate_id'],own['digital_estate_id'])
            self.assertEqual(body['market_id'],bootstrap['market_ids']['ZA'])
    def test_outage_failure_is_attributed_without_overwriting_publication(self):
        with patch('ssl.create_default_context',return_value=SimpleNamespace()):
            probe=importlib.import_module('cms_probe')
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);report=cms_contract.fresh('a'*32)
            report['cases']['published-home-nav-footer'].update(result='BLOCKED',reason='PROVIDER_NOT_ELIGIBLE')
            (root/'cms-report.json').write_text(json.dumps(report))
            with patch.object(probe.p,'ROOT',root),patch.object(probe,'config',return_value=({}, {}, {})):
                with self.assertRaises(SystemExit):probe.main('outage')
            retained=json.loads((root/'cms-report.json').read_text())
            self.assertEqual(retained['cases']['published-home-nav-footer'],report['cases']['published-home-nav-footer'])
            self.assertEqual(retained['cases']['dependency-outage-and-restoration']['result'],'FAIL')

if __name__=='__main__':unittest.main()

