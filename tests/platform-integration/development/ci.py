#!/usr/bin/env python3
"""Real Docker lifecycle and crash-recovery drills; not INT-03C qualification."""
import json
import secrets
import sys
import time

sys.dont_write_bytecode = True
import dev


def orphan(run_id, deadline):
    name = 'dev01-' + run_id + '-recovery'
    dev.call(['docker', 'volume', 'create', '--label', 'io.baobab.dev.namespace=' + dev.NAMESPACE,
              '--label', 'io.baobab.dev.run=' + run_id, '--label', 'io.baobab.dev.deadline=' + str(deadline), name])


def main():
    checks = {}
    try:
        # A real owned resource survives simulated interrupted startup; recovery
        # uses its durable ownership ledger, not a guessed canonical CP record.
        interrupted = dev.prepare()
        directory, state = dev.current(interrupted)
        orphan(interrupted, state['deadline'])
        dev.persist(directory, state, 'STARTING')
        dev.recover(all_runs=True)
        dev.require(not directory.exists() and not dev.resources(interrupted), 'INTERRUPTED_STARTUP_SURVIVED')
        checks['interrupted_startup_recovered'] = True

        run_id = dev.prepare()
        with dev.guarded(run_id):
            dev.up(run_id)
            dev.test(run_id)
            checks['fresh_real_iam_cp_bootstrap_and_replay'] = True
            directory, state = dev.current(run_id)
            dev.compose(directory, state, 'stop', 'cp')
            try:
                dev.test(run_id)
            except dev.Refused:
                checks['failed_health_rejected'] = True
            else:
                raise dev.Refused('STOPPED_COMPONENT_PASSED')
            dev.compose(directory, state, 'up', '-d', 'cp')
            dev.test(run_id)
            checks['recovery_retested'] = True
            # Loss of the compose/env handle must not defeat ownership cleanup.
            (directory / 'compose.json').unlink()
            dev.down(run_id)
        dev.require(not directory.exists() and not dev.resources(run_id), 'RUN_SURVIVED')
        checks['teardown_without_compose_verified'] = True

        expired = secrets.token_hex(16)
        orphan(expired, int(time.time()) - 1)
        dev.recover()
        dev.require(not dev.resources(expired), 'EXPIRED_ORPHAN_SURVIVED')
        checks['expired_orphan_without_state_recovered'] = True
        dev.require(not dev.resources(), 'OWNED_RESOURCE_SURVIVED')
        dev.write(dev.EVIDENCE / 'dev01-lifecycle-suite.json', {
            'schema': 'infrastructure.dev01.lifecycle-suite.v1', 'harness_sha': dev.source_identity(),
            'checks': checks, 'evidence_class': 'REAL_COMPONENT_SYNTHETIC_DATA',
            'scope': 'DEV01_LIFECYCLE_ONLY', 'int03c_qualified': False, 'nab03_qualified': False,
            'protected_acceptance': False, 'production_authorized': False})
        print('DEV01_REAL_LIFECYCLE_AND_RECOVERY_PASS')
        return 0
    finally:
        dev.recover(all_runs=True)


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception:
        raise SystemExit('DEV01_REAL_LIFECYCLE_FAILED; private state retained when cleanup fails')
