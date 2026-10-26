"""Source/custody invariants, never substitutes for native INT-07 evidence."""
import hashlib
import io
import json
from contextlib import redirect_stdout
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import dev
import ci_external
import external_contract as contract
import external_oci
import external_vertical

class ExternalBindingContracts(unittest.TestCase):
    def archive(self,path,corrupt=False):
        layer=b'unit-only-uncompressed-layer'
        config=json.dumps({'rootfs':{'diff_ids':['sha256:'+hashlib.sha256(layer).hexdigest()]}}).encode()
        manifest=[{'Config':'config.json','Layers':['layer.tar']}]
        with tarfile.open(path,'w') as tar:
            for name,raw in [('manifest.json',json.dumps(manifest).encode()),('config.json',config),('layer.tar',b'corrupt' if corrupt else layer)]:
                info=tarfile.TarInfo(name);info.size=len(raw);tar.addfile(info,io.BytesIO(raw))
        return 'sha256:'+hashlib.sha256(config).hexdigest()

    def test_oci_identity_is_manifest_of_actual_config_and_uncompressed_layers(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);archive=root/'image.tar';config=self.archive(archive)
            manifest=external_oci.publish(archive,root/'oci',config)
            raw=(root/'oci/manifest.json').read_bytes()
            self.assertEqual(manifest,'sha256:'+hashlib.sha256(raw).hexdigest())
            self.assertNotEqual(config,manifest)
            image=json.loads(raw)
            self.assertEqual(image['config']['digest'],config)
            for blob in [image['config'],*image['layers']]:
                payload=(root/'oci/blobs'/blob['digest'].split(':')[1]).read_bytes()
                self.assertEqual('sha256:'+hashlib.sha256(payload).hexdigest(),blob['digest'])
                self.assertEqual(len(payload),blob['size'])

    def test_oci_rejects_wrong_running_config_or_changed_layer(self):
        for corrupt in (True,False):
            with self.subTest(corrupt=corrupt),tempfile.TemporaryDirectory() as temp:
                root=Path(temp);archive=root/'image.tar';config=self.archive(archive,corrupt)
                if not corrupt:config='sha256:'+'0'*64
                with self.assertRaises(ValueError):external_oci.publish(archive,root/'oci',config)

    def test_original_eighteen_case_inventory_and_missing_grant_binding_gates_stay_visible(self):
        expected={'zero-estates','independent-registered-workload','own-context','nabhold-tenant-denied','zuribeans-tenant-denied','thamani-tenant-denied',
            'forged-tenant-denied','fake-estate-injection-denied','wrong-owner-denied','wrong-audience-denied','expired-token-denied','revoked-token-replay-denied',
            'dependency-outage-and-recovery','bound-resource-and-audited-effect','absent-subscription-denied','retired-binding-denied','unentitled-resource-denied','teardown'}
        self.assertEqual(set(contract.CASES),expected)
        self.assertLessEqual({'controlled_absent_subscription','controlled_unentitled_resource','controlled_retired_binding','resource_audit_persisted','independent_cp_resolution_readback'},contract.COMPONENTS)

    def test_owner_command_can_read_private_proof_without_changing_permissions(self):
        import os
        import stat
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);run='a'*32
            dev.write(root/'subjects.json',{'maker':'maker','checker':'checker'})
            dev.write(root/'external-source.json',{'source_sha':'b'*40})
            state={'uid':os.getuid(),'gid':os.getgid(),'run_id':run,'bootstrap_lease':300}
            with patch.object(dev,'compose',return_value=json.dumps({'run_id':run})) as compose:
                external_vertical.owner_fixture(root,state,'register')
            args=compose.call_args.args
            self.assertEqual(args[args.index('--user')+1],str(os.getuid())+':'+str(os.getgid()))
            self.assertEqual(args[args.index('--volume')+1],external_vertical.adapter.host(root/'external-source.json')+':/external-source.json:ro')
            self.assertEqual(stat.S_IMODE((root/'external-source.json').stat().st_mode),0o600)

    def test_preparation_failure_cannot_republish_a_previous_green_suite(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for name in ('dev06-external-suite.json','dev06-external-suite.sha256.json'):(root/name).write_text('stale')
            with patch.object(dev,'EVIDENCE',root),patch.object(ci_external.external,'prepare',side_effect=ValueError('private-error')),patch.object(dev,'recover'):
                with self.assertRaises(dev.Refused):ci_external.main()
            self.assertFalse((root/'dev06-external-suite.json').exists())
            self.assertFalse((root/'dev06-external-suite.sha256.json').exists())

    def test_failed_startup_retains_hashed_receipt_and_true_cleanup_result(self):
        for error in (dev.Refused('COMMAND_FAILED'),ValueError('private-bearer')):
            with self.subTest(error=type(error).__name__),tempfile.TemporaryDirectory() as temp:
                root=Path(temp);run='a'*32;state=root/'state';directory=state/run
                directory.mkdir(parents=True,mode=0o700);state.chmod(0o700)
                dev.write(directory/'state.json',{'run_id':run,'harness_sha':'b'*40,'sources':{},
                    'image_ids':{},'tests':False,'lock_sha256':'c'*64,'external':contract.fresh(run)})
                output=io.StringIO()
                with patch.object(dev,'STATE',state),patch.object(dev,'EVIDENCE',root/'evidence'), \
                     patch.object(dev,'resources',return_value=[]),patch.object(dev,'recover'), \
                     patch.object(ci_external.external,'prepare',return_value=run), \
                     patch.object(ci_external.external,'up',side_effect=error),redirect_stdout(output):
                    with self.assertRaisesRegex(dev.Refused,'^DEV06_EXECUTION_FAILED$'):
                        ci_external.main()
                receipt=root/'evidence/dev06-external-suite.json'
                actual=dev.read(receipt)
                self.assertTrue(actual['teardown_verified'])
                self.assertFalse(actual['external_runtime_identity_verified'])
                self.assertFalse(directory.exists())
                self.assertEqual(dev.read(receipt.with_name('dev06-external-suite.sha256.json'))['sha256'],
                    hashlib.sha256(receipt.read_bytes()).hexdigest())
                self.assertTrue(all(row['result']=='BLOCKED' for row in actual['external']['cases'].values()))
                self.assertNotIn('private-bearer',output.getvalue())

