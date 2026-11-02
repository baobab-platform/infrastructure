#!/usr/bin/env python3
"""DEV-11 closed diagnostic proof and safe affected-profile routing.

Source tests do not qualify native runtime behaviour.
"""
from __future__ import annotations
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

VERSION = 'infrastructure.dev11.assurance.v1'
PROFILES = ('DEV-01-04', 'DEV-05', 'DEV-06', 'DEV-07', 'DEV-08',
            'DEV-09', 'DEV-14-15', 'L4-INT02-03', 'LOCAL-STACK', 'ESTATE-BROWSER')
CAUSES = frozenset(('NONE', 'NOT_EXECUTED', 'NATIVE_NOT_IMPLEMENTED',
    'AUTHORITY_UNQUALIFIED', 'PROVIDER_UNAVAILABLE', 'SOURCE_PIN_MISMATCH',
    'MISSING_EVIDENCE', 'TIMEOUT', 'INCORRECT_RESULT', 'REDACTION_FAILED',
    'TEARDOWN_UNVERIFIED', 'BROWSER_OWNER_REQUIRED'))
HOPS = ('bff', 'issuer', 'cp', 'engine', 'outbox')
UUID = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\Z')
SHA = re.compile(r'[0-9a-f]{40}\Z')
CASE = re.compile(r'[A-Z][A-Z0-9_-]{2,79}\Z')
TRACEPARENT = re.compile(r'00-([0-9a-f]{32})-([0-9a-f]{16})-([0-9a-f]{2})\Z')
HEX16 = re.compile(r'[0-9a-f]{16}\Z')

class Refused(ValueError):
    """Never echo source details on refusal."""

def require(ok):
    if not ok:
        raise Refused('DEV11_INPUT_REFUSED')

def unique_pairs(pairs):
    """Reject duplicate JSON keys before any schema/authority decision."""
    result = {}
    for key, value in pairs:
        require(key not in result)
        result[key] = value
    return result


def closed(obj, keys):
    require(isinstance(obj, dict) and set(obj) == keys)
    return obj

def traceparent(value):
    require(isinstance(value, str))
    match = TRACEPARENT.fullmatch(value)
    require(match is not None)
    trace, span, flags = match.groups()
    require(int(trace, 16) != 0 and int(span, 16) != 0)
    return trace, span

def verify_chain(obj):
    """Validate a *reference* five-hop trace, not every possible trace topology.

    Raw headers, bodies, URLs, exception strings and tokens are not accepted.
    """
    chain = closed(obj, {'schema', 'source_sha', 'profile', 'scenario',
                          'correlation_id', 'hops', 'runtime_observed',
                          'teardown_verified', 'evidence_class'})
    require(chain['schema'] == VERSION and isinstance(chain['source_sha'], str)
            and SHA.fullmatch(chain['source_sha']) is not None)
    require(chain['profile'] in PROFILES and isinstance(chain['scenario'], str)
            and CASE.fullmatch(chain['scenario']) is not None)
    require(isinstance(chain['correlation_id'], str)
            and UUID.fullmatch(chain['correlation_id']) is not None)
    require(type(chain['runtime_observed']) is bool and type(chain['teardown_verified']) is bool)
    require(chain['evidence_class'] in ('SOURCE', 'REAL_COMPONENT_SYNTHETIC_DATA'))
    rows = chain['hops']
    require(isinstance(rows, list) and len(rows) == len(HOPS))
    first_trace = previous_span = None
    seen = set()
    for expected, row in zip(HOPS, rows):
        node = closed(row, {'service_role', 'traceparent', 'parent_span_id',
                            'correlation_id', 'result', 'cause'})
        require(node['service_role'] == expected and node['correlation_id'] == chain['correlation_id'])
        trace, span = traceparent(node['traceparent'])
        require(span not in seen and (first_trace is None or first_trace == trace))
        seen.add(span)
        first_trace = trace
        if expected == HOPS[0]:
            require(node['parent_span_id'] is None)
        else:
            require(isinstance(node['parent_span_id'], str)
                    and HEX16.fullmatch(node['parent_span_id']) is not None
                    and node['parent_span_id'] == previous_span)
        previous_span = span
        require(node['result'] in ('PASS', 'FAIL', 'BLOCKED', 'NOT_RUN'))
        require(isinstance(node['cause'], str) and node['cause'] in CAUSES)
        require((node['result'] == 'PASS') == (node['cause'] == 'NONE'))
    results = [r['result'] for r in rows]
    aggregate = 'PASS' if all(r == 'PASS' for r in results) else (
        'FAIL' if 'FAIL' in results else 'BLOCKED' if 'BLOCKED' in results else 'NOT_RUN')
    qualified = False  # Caller-reported fields cannot establish independent runtime proof.
    return {'schema': VERSION, 'source_sha': chain['source_sha'],
            'profile': chain['profile'], 'scenario': chain['scenario'],
            'result': aggregate, 'trace_chain_valid': True, 'runtime_qualified': qualified,
            'runtime_observed': chain['runtime_observed'],
            'teardown_verified': chain['teardown_verified'],
            'cause_codes': sorted({r['cause'] for r in rows if r['cause'] != 'NONE'}),
            'protected_acceptance': False, 'production_authorized': False}

def route(files, full=False):
    """Fail closed on unrecognised paths. Routing never claims suite execution."""
    require(type(full) is bool)
    if full:
        selected, mode, unknown = set(PROFILES), 'FULL_NIGHTLY_OR_RELEASE', 0
    else:
        require(isinstance(files, list))
        selected, unknown, mode = set(), 0, 'AFFECTED_PR'
        for path in files:
            require(isinstance(path, str) and 0 < len(path) <= 260 and
                    not path.startswith('/') and '..' not in path.split('/') and
                    all(32 <= ord(c) <= 126 for c in path))
            if path.startswith(('docs/', 'README', '.github/ISSUE_TEMPLATE/')) or path.endswith('.md'):
                continue
            if path.startswith(('tests/platform-integration/development/dev15_',
                                'tests/platform-integration/development/engine_')):
                selected.add('DEV-14-15')
            elif path.startswith('tests/platform-integration/development/buyer_'):
                selected.update(('DEV-07', 'DEV-01-04'))
            elif path.startswith('tests/platform-integration/development/cms_'):
                selected.update(('DEV-05', 'DEV-01-04'))
            elif path.startswith('tests/platform-integration/development/external_'):
                selected.update(('DEV-06', 'DEV-01-04'))
            elif path.startswith('tests/platform-integration/development/') or path == 'tests/platform-integration/l4.py':
                selected.update(('DEV-01-04', 'DEV-05', 'DEV-06', 'DEV-07', 'DEV-14-15'))
            elif path.startswith(('tests/platform-integration/int02/', 'tests/platform-integration/int03/',
                                  'tests/platform-integration/l3/', 'tests/platform-integration/l4/')):
                selected.add('L4-INT02-03')
            elif path.startswith(('compose/', 'apisix/', 'terraform/', 'scripts/verify-local',
                                  'scripts/guard-local', '.devcontainer/')):
                selected.update(('LOCAL-STACK', 'L4-INT02-03'))
            elif path.startswith('.github/workflows/'):
                selected.update(PROFILES)
            else:
                unknown += 1
        if unknown:
            selected.update(PROFILES)
    return {'schema': VERSION, 'routing_mode': mode,
            'affected_profiles': sorted(selected), 'unmapped_path_count': unknown,
            'routing_result': 'PLANNED_NOT_EXECUTED',
            'external_owner_checks': ['ESTATE-BROWSER'] if 'ESTATE-BROWSER' in selected else [],
            'runtime_qualified': False, 'protected_acceptance': False,
            'production_authorized': False}

def changed_paths(base, head):
    require(isinstance(base, str) and isinstance(head, str)
            and SHA.fullmatch(base) is not None and SHA.fullmatch(head) is not None)
    try:
        result = subprocess.run(['git', 'diff', '--name-only', '-z', base, head],
                                capture_output=True, check=True, timeout=15)
    except (subprocess.SubprocessError, OSError):
        raise Refused('DEV11_GIT_DIFF_UNAVAILABLE') from None
    require(len(result.stdout) <= 262144)
    return [x.decode('utf-8', 'strict') for x in result.stdout.split(b'\x00') if x]

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['plan', 'verify-chain'])
    parser.add_argument('--base')
    parser.add_argument('--head')
    parser.add_argument('--full', action='store_true')
    parser.add_argument('--input', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    try:
        if args.command == 'plan':
            require(args.input is None and (args.full or (args.base and args.head)))
            data = route(None, full=True) if args.full else route(changed_paths(args.base, args.head))
        else:
            require(args.input is not None and not args.full and args.base is None and args.head is None)
            require(args.input.is_file() and not args.input.is_symlink()
                    and args.input.stat().st_size <= 32768)
            data = verify_chain(json.loads(args.input.read_text(encoding='utf-8'), object_pairs_hook=unique_pairs))
        value = json.dumps(data, sort_keys=True, separators=(',', ':')) + '\n'
        if args.output:
            require(not args.output.is_symlink() and args.output.parent.is_dir())
            args.output.write_text(value, encoding='utf-8')
        else:
            sys.stdout.write(value)
        return 0
    except (Refused, ValueError, UnicodeError, OSError, KeyError, TypeError):
        print('DEV11_ASSURANCE_REFUSED', file=sys.stderr)
        return 2

if __name__ == '__main__':
    raise SystemExit(main())
