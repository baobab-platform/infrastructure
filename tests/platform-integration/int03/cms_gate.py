#!/usr/bin/env python3
"""INT-03 CMS registry gate and NAB-03 receipt, before any connected run.

Accepted Shared #354 (docs/architecture/int03-cms-proof-bootstrap-proposal.md)
lets exactly two named development identities produce synthetic CMS evidence,
and only once a reviewed change adds them to the canonical workload registry.
The platform owner's no-registry-activation hold keeps them out today, so
every connected NAB-03 case is BLOCKED and nothing may provision, borrow or
synthesise those identities.

This gate reads the unmodified registry at the pinned Shared commit and
answers one of:

  HELD     neither named row is present; the hold is in force
  REFUSED  a named row is present but differs from #354, only one of the two
           is present, a row is unparseable or duplicated, or a guarded
           product row changed. The registry is defective: fail the job.
  OPEN     both rows match #354 exactly. The connected CMS lane must run;
           this module never treats an open gate as evidence.

Every outcome writes a receipt in which all NAB-03 cases are BLOCKED. This
module grants nothing, contacts nothing and can never report qualification.

  python3 cms_gate.py --shared /path/to/shared/checkout --out /path/to/dir
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

import yaml

BASE = Path(__file__).resolve().parent
LOCK = BASE / 'cms-lock.json'
REGISTRY = 'contracts/identity/v1/workload-registry.yaml'
DECISION = 'docs/architecture/int03-cms-proof-bootstrap-proposal.md'
CONSUMER = 'baobab-int03-cms-consumer'
VALIDATOR = 'baobab-int03-cms-validator'

# Shared #354 "Accepted owner decision" table, field for field. `runtime` is
# free text and only has to be present; every other field is exact, and no
# other field (an authority-bearing extra) may appear.
EXPECTED = {
    CONSUMER: {
        'repository': 'baobab-platform/infrastructure',
        'owner': 'baobab-platform/infrastructure',
        'environment': 'development',
        'allowed_audiences': ['baobab-control-plane', 'baobab-cms'],
        'allowed_scopes': ['context:resolve', 'content:entry:resolve'],
        'credential_type': 'client_credentials',
        'rotation_owner': 'baobab-platform/infrastructure',
        'status': 'ACTIVE',
    },
    VALIDATOR: {
        'repository': 'baobab-platform/baobab-cms',
        'owner': 'baobab-platform/baobab-cms',
        'environment': 'development',
        'allowed_audiences': ['baobab-control-plane'],
        'allowed_scopes': ['context:validate'],
        'validates_audiences': ['baobab-cms'],
        'credential_type': 'client_credentials',
        'rotation_owner': 'baobab-platform/baobab-cms',
        'status': 'ACTIVE',
    },
}

# #354: the product caller stays PROVISIONED and the production validator
# stays production; neither may be reused or activated for this proof.
GUARDED = {
    'nabhold-backend': {'environment': 'production', 'status': 'PROVISIONED'},
    'baobab-cms-workload': {'environment': 'production'},
}

# NAB-03 (Shared ea-v2.2-integration-acceptance-matrix.md) is the normative
# scenario. These are its #354 step-4 cases; the keys refine NAB-03 and are
# not new normative IDs.
CASES = [
    'published-home-nav-footer',
    'wrong-audience-token',
    'wrong-credential',
    'disabled-caller',
    'expired-caller-token',
    'revoked-caller-token',
    'missing-grant',
    'wrong-owner-or-context',
    'neighbour-tenant',
    'draft-or-preview',
    'withdrawn-content',
    'dependency-outage-and-restoration',
    'validator-negatives',
    'teardown',
]

class RegistryLoader(yaml.SafeLoader):
    """Use maintained YAML parsing, but refuse duplicate/aliased authority."""


def registry_mapping(loader, node, deep=False):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if not isinstance(key, str) or key in result:
            raise yaml.YAMLError('duplicate or non-string registry key')
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


RegistryLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, registry_mapping)


def rows(text):
    """Parse the actual YAML document, including quoted/flow/block syntax.

    Duplicate top-level workloads sections must never be merged into a view
    that disagrees with the canonical YAML consumer. Anchors/aliases are not
    needed by this pinned registry and are refused before object construction.
    """
    if not isinstance(text, str) or len(text.encode()) > 1024 * 1024:
        raise yaml.YAMLError('registry size')
    if any(isinstance(token, (yaml.tokens.AliasToken, yaml.tokens.AnchorToken)) for token in yaml.scan(text)):
        raise yaml.YAMLError('registry aliases')
    doc = yaml.load(text, Loader=RegistryLoader)
    if not isinstance(doc, dict) or not isinstance(doc.get('workloads'), dict):
        raise yaml.YAMLError('registry shape')
    found = doc['workloads']
    if any(not re.fullmatch(r'[a-z0-9][a-z0-9-]*', name) for name in found):
        raise yaml.YAMLError('registry workload key')
    broken = {name for name, row in found.items() if not isinstance(row, dict)}
    return {name: {} if name in broken else row for name, row in found.items()}, broken


def judge(text):
    """The gate verdict and its fixed reason codes for one registry text."""
    try:
        found, broken = rows(text)
    except (yaml.YAMLError, TypeError, ValueError, RecursionError):
        return 'REFUSED', ['REGISTRY_UNPARSEABLE']
    reasons = []
    for name in sorted(EXPECTED):
        if name not in found:
            continue
        row = dict(found[name])
        runtime = row.pop('runtime', None)
        if name in broken or row != EXPECTED[name] or type(runtime) is not str or not runtime.strip():
            reasons.append('ROW_DIFFERS_FROM_DECISION:' + name)
    for name, fields in sorted(GUARDED.items()):
        row = found.get(name)
        if row is None or name in broken or any(row.get(k) != v for k, v in fields.items()):
            reasons.append('GUARDED_ROW_CHANGED:' + name)
    extra = sorted(n for n in found if n.startswith('baobab-int03-cms-') and n not in EXPECTED)
    reasons.extend('UNNAMED_CMS_PROOF_ROW:' + n for n in extra)
    present = [n for n in sorted(EXPECTED) if n in found]
    if len(present) == 1:
        reasons.append('ONLY_ONE_NAMED_IDENTITY:' + present[0])
    if reasons:
        return 'REFUSED', reasons
    if not present:
        return 'HELD', ['REGISTRY_ACTIVATION_HELD']
    return 'OPEN', ['CONNECTED_LANE_REQUIRED']


def receipt(verdict, reasons, shared_commit, registry_sha256, decision_sha256):
    """BLOCKED for every case, whatever the gate says: only a connected run's
    own scenario-complete receipt can report QUALIFIED_SYNTHETIC_RUN."""
    return {
        'schema': 'infrastructure.int03.cms-gate.v1',
        'decision': {'document': DECISION, 'sha256': decision_sha256},
        'shared': {'commit': shared_commit, 'registry_sha256': registry_sha256},
        'gate': {'verdict': verdict, 'reasons': reasons},
        'qualification_state': {
            'HELD': 'NOT_STARTED_REGISTRY_HELD',
            'OPEN': 'NOT_STARTED_CONNECTED_LANE_REQUIRED',
            'REFUSED': 'NOT_STARTED_REGISTRY_REFUSED',
        }[verdict],
        'scenario': 'NAB-03',
        'cases': {case: 'BLOCKED' for case in CASES},
        'identities_created': False,
        'synthetic_only': True,
        'qualified': False,
        'full_int03_acceptance': False,
        'generated_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
    }


def evaluate(shared, lock=None):
    """Read the pinned registry and decision from a Shared checkout."""
    lock = lock or json.loads(LOCK.read_text())
    expected = lock['sources']['shared']
    head = subprocess.run(['git', '-C', str(shared), 'rev-parse', 'HEAD'], capture_output=True,
                          text=True, check=True).stdout.strip()
    if head != expected:
        raise SystemExit('Shared checkout is not the pinned commit')
    dirty = subprocess.run(['git', '-C', str(shared), 'status', '--porcelain', '--', REGISTRY, DECISION],
                           capture_output=True, text=True, check=True).stdout
    if dirty.strip():
        raise SystemExit('Shared registry or decision differs from the pinned commit')
    registry = subprocess.check_output(['git', '-C', str(shared), 'show', head + ':' + REGISTRY])
    decision = subprocess.check_output(['git', '-C', str(shared), 'show', head + ':' + DECISION])
    verdict, reasons = judge(registry.decode())
    return receipt(verdict, reasons, head, hashlib.sha256(registry).hexdigest(),
                   hashlib.sha256(decision).hexdigest())


def write(result, out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(result, indent=2, sort_keys=True) + '\n').encode()
    (out / 'cms-gate-receipt.json').write_bytes(raw)
    (out / 'cms-gate-receipt.sha256').write_text(hashlib.sha256(raw).hexdigest() + '  cms-gate-receipt.json\n')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n', 1)[0])
    parser.add_argument('--shared', required=True, help='Shared checkout at the pinned commit')
    parser.add_argument('--out', required=True, help='directory for the receipt')
    args = parser.parse_args(argv)
    result = evaluate(args.shared)
    write(result, args.out)
    verdict = result['gate']['verdict']
    print(f"INT-03 CMS gate: {verdict} ({', '.join(result['gate']['reasons'])}); "
          f"NAB-03 {len(CASES)} cases BLOCKED; qualified=false")
    # HELD is the expected state while the owner's hold stands. REFUSED is a
    # registry defect, and OPEN means the connected lane is now owed: both fail.
    return 0 if verdict == 'HELD' else 1


if __name__ == '__main__':
    sys.exit(main())
