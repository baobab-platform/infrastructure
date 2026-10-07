import copy
import importlib.util
import pathlib
import unittest

spec=importlib.util.spec_from_file_location('release_cut',pathlib.Path(__file__).parents[2]/'deploy/verification/release_cut.py')
cut=importlib.util.module_from_spec(spec); spec.loader.exec_module(cut)

class CutTests(unittest.TestCase):
    def setUp(self):
        self.tag='v1.2.3-staging'; self.path='deploy/releases/staging/'+self.tag+'.tfvars.json'
        self.component={'tag':self.tag,'source_revision':'a'*40,'digest':'sha256:'+'b'*64}
        self.coordination={'release_tag':self.tag,'components':{k:copy.deepcopy(self.component) for k in cut.REPOS}}
        self.release={'workload_release':{'services':{k:{'source_revision':'a'*40,'image':'123456789012.dkr.ecr.af-south-1.amazonaws.com/'+k+'@sha256:'+'b'*64} for k in ('cp','iam','pulse','keycloak')}}}
        self.acceptance=False; self.failed=False; self.wrong_receipt=False; self.publisher_event='push'
    def fetch(self,path):
        if '/git/ref/' in path: return {'object':{'type':'tag','sha':'c'*40}}
        if '/git/tags/' in path: return {'object':{'type':'commit','sha':'a'*40}}
        return {'workflow_runs':[] if self.failed else [{'id':12,'head_sha':'a'*40,'head_branch':self.tag,'event':self.publisher_event,'status':'completed','conclusion':'success'}]}
    def receipt(self,repo,run,artifact):
        suffix=artifact.split('-')[-1]; key='shared' if suffix=='contracts' else suffix
        return {'release_tag':self.tag,'repository':repo,'source_revision':'d'*40 if self.wrong_receipt else 'a'*40,'image':'ghcr.io/baobab-platform/'+cut.IMAGES[key]+'@sha256:'+'b'*64,'run_url':'https://github.com/'+repo+'/actions/runs/12','operational_acceptance':self.acceptance}
    def verify(self): return cut.verify(self.tag,self.path,self.release,self.coordination,self.fetch,self.receipt)
    def test_annotated_tags_exact_receipts_and_promoted_digests(self):
        result=self.verify(); self.assertEqual(len(result['components']),5); self.assertIs(result['operational_acceptance'],False)
    def test_workflow_dispatch_publisher_is_accepted_for_immutable_tag(self):
        self.publisher_event='workflow_dispatch'
        result=self.verify()
        self.assertEqual(len(result['components']),5)
    def test_missing_publisher_and_forged_receipt_deny(self):
        self.failed=True
        with self.assertRaises(ValueError): self.verify()
        self.acceptance=False; self.failed=False; self.wrong_receipt=True
        with self.assertRaises(ValueError): self.verify()
    def test_moved_tag_and_wrong_runtime_digest_deny(self):
        self.coordination['components']['cp']['source_revision']='e'*40
        with self.assertRaises(ValueError): self.verify()
        self.coordination['components']['cp']['source_revision']='a'*40
        self.release['workload_release']['services']['iam']['image']='x@sha256:'+'e'*64
        with self.assertRaises(ValueError): self.verify()
    def test_unbound_manifest_and_invalid_tag_deny(self):
        self.path='deploy/releases/staging/other.tfvars.json'
        with self.assertRaises(ValueError): self.verify()
        self.path='deploy/releases/staging/'+self.tag+'.tfvars.json'; self.tag='v01.2.3-staging'
        with self.assertRaises(ValueError): self.verify()

    def test_selection_can_be_verified_before_aws_manifest_exists(self):
        result=cut.verify_selection(self.tag,self.coordination,self.fetch,self.receipt)
        self.assertEqual(len(result['components']),5)
        self.assertIs(result['operational_acceptance'],False)
    def test_selection_denies_missing_component_and_malformed_identity(self):
        for mutation in ('missing', 'digest', 'source', 'extra'):
            value=copy.deepcopy(self.coordination)
            if mutation=='missing': del value['components']['pulse']
            if mutation=='digest': value['components']['pulse']['digest']='latest'
            if mutation=='source': value['components']['iam']['source_revision']='main'
            if mutation=='extra': value['components']['cp']['certified']=True
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                cut.verify_selection(self.tag,value,self.fetch,self.receipt)
    def test_receipt_cannot_claim_acceptance_or_use_integer_false(self):
        for value in (True,0,None):
            self.acceptance=value
            with self.subTest(value=value), self.assertRaises(ValueError):
                cut.verify_selection(self.tag,self.coordination,self.fetch,self.receipt)
