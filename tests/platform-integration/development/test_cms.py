"""Source failure contracts only; these results never qualify NAB-03."""
import copy
import importlib
import json
import os
from types import SimpleNamespace
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
import cms_contract
import cms_vertical
import dev

class CMSContracts(unittest.TestCase):
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
            ('CMS_INT03_STAGE_FAILED=CONTENT_SEED\\nprivate db secret', 'CMS_FIXTURE_CONTENT_SEED'),
            ('CMS_INT03_STAGE_FAILED=NOT_REVIEWED\\n', 'COMMAND_FAILED'),
            ('CMS_INT03_STAGE_FAILED=CONTENT_SEED secret=abc\\n', 'COMMAND_FAILED'),
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
        cms_contract.validate(report,run)
        for change in (lambda r:r['cases'].pop('missing-grant'),lambda r:r.update(nab03_qualified=True),
            lambda r:r.update(protected_acceptance=True),lambda r:r['component_checks'].update(private_token=True),
            lambda r:r['cases']['teardown'].update(result='PASS')):
            bad=copy.deepcopy(report);change(bad)
            with self.assertRaises(ValueError):cms_contract.validate(bad,run)

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
