#!/usr/bin/env python3
"""Actual DEV-04 seven-case execution; uses the same CLI/lifecycle as developers.

No mocks, credentials, provider bodies or arbitrary exception text are emitted.
The lifecycle's finally/recovery paths own cleanup even after failed assertions.
"""
import hashlib
import os
from pathlib import Path
import sys

sys.dont_write_bytecode = True
import dev
import int03c_contract
import n02_connected


def main():
    run_id = dev.prepare()
    try:
        with dev.guarded(run_id):
            print('DEV04_STAGE=UP', flush=True)
            dev.up(run_id)
            dev.test(run_id)
            directory, state = dev.current(run_id)
            print('DEV04_STAGE=FAILED_HEALTH_AND_RECOVERY', flush=True)
            dev.compose(directory, state, 'stop', 'cp')
            try:
                dev.test(run_id, health_attempts=1)
            except dev.Refused:
                pass  # Expected genuine dependency failure; never credit its result.
            else:
                raise dev.Refused('STOPPED_COMPONENT_PASSED')
            dev.compose(directory, state, 'up', '-d', 'cp')
            dev.test(run_id)
            # The opt-in N02 join is deliberately BEFORE the destructive
            # Principal/issuer cases. The default DEV-04 suite remains unchanged.
            n02_mode = os.environ.get('BAOBAB_N02_JOIN')
            evidence = os.environ.get('BAOBAB_N02_ORIGINAL_DIR')
            dev.require(n02_mode in (None, 'development'), 'N02_JOIN_MODE_INVALID')
            dev.require(n02_mode is not None or evidence is None, 'N02_JOIN_OPT_IN_REQUIRED')
            if n02_mode == 'development':
                dev.require(bool(evidence), 'N02_ORIGINAL_DIRECTORY_REQUIRED')
                print('DEV04_STAGE=N02_BROWSER_PRE_DEACTIVATION', flush=True)
                n02_connected.checkpoint(run_id, Path(evidence))
            print('DEV04_STAGE=SEVEN_ORIGINAL_CASES', flush=True)
            dev.qualify_int03c(run_id)
            # Full cleanup must work without Compose. The host performs its own
            # Docker inventory independently of the in-container protocol driver.
            (directory / 'compose.json').unlink()
    finally:
        with dev.guarded(run_id):
            dev.down(run_id)
    dev.require(not dev.run_dir(run_id).exists() and not dev.resources(run_id), 'DEV04_CLEANUP_INCOMPLETE')
    path = dev.EVIDENCE / ('dev01-' + run_id) / 'completed/receipt.json'
    receipt = dev.read(path)
    dev.require(hashlib.sha256(path.read_bytes()).hexdigest() == dev.read(path.with_name('receipt.sha256.json'))['sha256'], 'EVIDENCE_HASH_MISMATCH')
    int03c_contract.validate(receipt['int03c'], run_id, complete=True)
    dev.require(receipt['int03c_qualified'] is True and receipt['teardown_verified'] is True, 'DEV04_NOT_QUALIFIED')
    # Retain the entire sanitized receipt, rather than inferring seven outcomes
    # from the earlier sixteen-case DEV-03 booleans.
    dev.write(dev.EVIDENCE / 'dev04-int03c-suite.json', receipt)
    dev.write(dev.EVIDENCE / 'dev04-int03c-suite.sha256.json', {
        'sha256': hashlib.sha256((dev.EVIDENCE / 'dev04-int03c-suite.json').read_bytes()).hexdigest()})
    print('DEV04_SEVEN_CASES_AND_TEARDOWN_PASS')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as error:
        code = str(error) if isinstance(error, dev.Refused) else 'INVALID_OR_UNAVAILABLE_STATE'
        raise SystemExit('DEV04_RUNTIME_FAILED ' + code)
