"""INT-03 CMS registry gate: exact #354 rows, fail-closed parsing, BLOCKED receipt."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))

import cms_gate as gate

HEAD = '''schema:
  version: 1

workloads:
  nabhold-backend:
    repository: baobab-platform/nabhold
    owner: baobab-platform/nabhold
    runtime: "nabhold server-side service"
    environment: production
    allowed_audiences: ["baobab-control-plane", "baobab-cms"]
    allowed_scopes: ["context:resolve", "content:entry:resolve"]
    credential_type: client_credentials
    rotation_owner: baobab-platform/nabhold
    status: PROVISIONED

  # The production CMS validator.
  baobab-cms-workload:
    repository: baobab-platform/baobab-cms
    owner: baobab-platform/baobab-cms
    runtime: "baobab-cms service"
    environment: production
    allowed_audiences: ["baobab-control-plane"]
    allowed_scopes: ["context:resolve", "context:validate", "provider-migration:task"]
    validates_audiences: ["baobab-cms"]
    credential_type: client_credentials
    rotation_owner: baobab-platform/baobab-cms
    status: ACTIVE
'''

CONSUMER = '''
  baobab-int03-cms-consumer:
    repository: baobab-platform/infrastructure
    owner: baobab-platform/infrastructure
    runtime: "INT-03 disposable real-component CMS qualification consumer"
    environment: development
    allowed_audiences: ["baobab-control-plane", "baobab-cms"]
    allowed_scopes: ["context:resolve", "content:entry:resolve"]
    credential_type: client_credentials
    rotation_owner: baobab-platform/infrastructure
    status: ACTIVE
'''

VALIDATOR = '''
  baobab-int03-cms-validator:
    repository: baobab-platform/baobab-cms
    owner: baobab-platform/baobab-cms
    runtime: "INT-03 disposable real-component CMS context validator"
    environment: development
    allowed_audiences: ["baobab-control-plane"]
    allowed_scopes: ["context:validate"]
    validates_audiences: ["baobab-cms"]
    credential_type: client_credentials
    rotation_owner: baobab-platform/baobab-cms
    status: ACTIVE
'''

OPEN = HEAD + CONSUMER + VALIDATOR


class Gate(unittest.TestCase):
    def test_absent_rows_mean_the_hold_is_in_force(self):
        self.assertEqual(gate.judge(HEAD), ('HELD', ['REGISTRY_ACTIVATION_HELD']))

    def test_both_exact_decision_rows_open_the_gate(self):
        self.assertEqual(gate.judge(OPEN), ('OPEN', ['CONNECTED_LANE_REQUIRED']))

    def test_one_named_identity_alone_is_refused(self):
        for text, name in [(HEAD + CONSUMER, gate.CONSUMER), (HEAD + VALIDATOR, gate.VALIDATOR)]:
            verdict, reasons = gate.judge(text)
            self.assertEqual(verdict, 'REFUSED')
            self.assertIn('ONLY_ONE_NAMED_IDENTITY:' + name, reasons)

    def test_any_widened_or_changed_field_is_refused(self):
        mutations = [
            ('environment: development', 'environment: staging'),
            ('status: ACTIVE', 'status: PROVISIONED'),
            ('["context:resolve", "content:entry:resolve"]', '["context:resolve", "content:entry:resolve", "content:entry:preview"]'),
            ('["context:validate"]', '["context:validate", "context:resolve"]'),
            ('owner: baobab-platform/infrastructure', 'owner: baobab-platform/nabhold'),
            ('validates_audiences: ["baobab-cms"]', 'validates_audiences: ["baobab-cms", "baobab-pulse"]'),
            ('credential_type: client_credentials\n    rotation_owner: baobab-platform/infrastructure',
             'credential_type: client_credentials\n    deployment_regions: ["af-south-1"]\n    rotation_owner: baobab-platform/infrastructure'),
            ('runtime: "INT-03 disposable real-component CMS context validator"', 'runtime: ""'),
        ]
        for old, new in mutations:
            text = HEAD + (CONSUMER + VALIDATOR).replace(old, new, 1)
            self.assertNotEqual(text, OPEN, old)
            self.assertEqual(gate.judge(text)[0], 'REFUSED', new)

    def test_the_guarded_product_rows_must_not_move(self):
        for old, new in [('status: PROVISIONED', 'status: ACTIVE'),
                         ('runtime: "baobab-cms service"\n    environment: production',
                          'runtime: "baobab-cms service"\n    environment: development')]:
            verdict, reasons = gate.judge(OPEN.replace(old, new, 1))
            self.assertEqual(verdict, 'REFUSED')
            self.assertTrue(any(r.startswith('GUARDED_ROW_CHANGED:') for r in reasons), reasons)
        verdict, reasons = gate.judge(OPEN.replace('  nabhold-backend:', '  nabhold-backend-renamed:', 1))
        self.assertIn('GUARDED_ROW_CHANGED:nabhold-backend', reasons)

    def test_unreadable_or_duplicated_rows_fail_closed(self):
        for text in [
            OPEN + VALIDATOR,  # duplicate row
            OPEN.replace('    status: ACTIVE\n', '    status: ACTIVE\n    status: ACTIVE\n', 1),
            OPEN.replace('allowed_scopes: ["context:validate"]', 'allowed_scopes: &scopes ["context:validate"]'),
            OPEN.replace('allowed_scopes: ["context:validate"]', 'allowed_scopes: [broken'),
            OPEN + '\nworkloads: {}\n',
        ]:
            self.assertEqual(gate.judge(text)[0], 'REFUSED', text[-200:])

    def test_canonical_yaml_syntax_does_not_hide_named_rows(self):
        quoted = OPEN.replace('  baobab-int03-cms-consumer:', '  "baobab-int03-cms-consumer":')
        block = OPEN.replace('allowed_scopes: ["context:validate"]', 'allowed_scopes:\n      - context:validate')
        for text in (quoted, block):
            self.assertEqual(gate.judge(text)[0], 'OPEN')
        self.assertEqual(gate.judge(OPEN + '\nworkloads: {}\n')[0], 'REFUSED')

    def test_no_other_cms_proof_identity_may_appear(self):
        extra = CONSUMER.replace(gate.CONSUMER, 'baobab-int03-cms-editor')
        verdict, reasons = gate.judge(OPEN + extra)
        self.assertEqual(verdict, 'REFUSED')
        self.assertIn('UNNAMED_CMS_PROOF_ROW:baobab-int03-cms-editor', reasons)

    def test_a_quoted_hash_is_text_not_a_comment(self):
        text = OPEN.replace('"INT-03 disposable real-component CMS context validator"', '"validator #2 of the run"')
        self.assertEqual(gate.judge(text)[0], 'OPEN')


class Receipt(unittest.TestCase):
    def test_every_verdict_blocks_every_case_and_never_qualifies(self):
        for verdict in ('HELD', 'OPEN', 'REFUSED'):
            r = gate.receipt(verdict, ['X'], 'a' * 40, 'b' * 64, 'c' * 64)
            self.assertEqual(r['scenario'], 'NAB-03')
            self.assertEqual(set(r['cases'].values()), {'BLOCKED'})
            self.assertEqual(len(r['cases']), len(gate.CASES))
            self.assertIs(r['qualified'], False)
            self.assertIs(r['identities_created'], False)
            self.assertIs(r['full_int03_acceptance'], False)
            self.assertNotIn('QUALIFIED', r['qualification_state'])


class Pinned(unittest.TestCase):
    def shared(self, registry):
        directory = Path(tempfile.mkdtemp())
        self.addCleanup(subprocess.run, ['rm', '-rf', str(directory)])
        (directory / Path(gate.REGISTRY).parent).mkdir(parents=True)
        (directory / Path(gate.DECISION).parent).mkdir(parents=True)
        (directory / gate.REGISTRY).write_text(registry)
        (directory / gate.DECISION).write_text('# decision\n')
        git = ['git', '-C', str(directory), '-c', 'user.name=t', '-c', 'user.email=t@example.invalid']
        subprocess.run([*git, 'init', '-q'], check=True)
        subprocess.run([*git, 'add', '-A'], check=True)
        subprocess.run([*git, 'commit', '-qm', 'pin'], check=True)
        head = subprocess.run([*git, 'rev-parse', 'HEAD'], capture_output=True, text=True, check=True).stdout.strip()
        return directory, {'sources': {'shared': head}}

    def test_reads_only_the_pinned_unmodified_registry(self):
        directory, lock = self.shared(HEAD)
        result = gate.evaluate(directory, lock)
        self.assertEqual(result['gate']['verdict'], 'HELD')
        self.assertEqual(result['shared']['commit'], lock['sources']['shared'])
        (directory / gate.REGISTRY).write_text(OPEN)
        with self.assertRaises(SystemExit):
            gate.evaluate(directory, lock)
        with self.assertRaises(SystemExit):
            gate.evaluate(directory, {'sources': {'shared': '0' * 40}})

    def test_the_lock_pins_the_accepted_decision_commit(self):
        lock = json.loads(gate.LOCK.read_text())
        self.assertEqual(lock['sources']['shared'], '409d780d05f7825ab1228649541032d42a7b0b13')
        self.assertIs(lock['full_int03_acceptance'], False)
        for commit in lock['sources'].values():
            self.assertRegex(commit, r'^[0-9a-f]{40}$')


if __name__ == '__main__':
    unittest.main()
