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
    mode = os.environ.get('BAOBAB_N02_JOIN')
    dev.require(mode in (None, 'development'), 'N02_JOIN_MODE_INVALID')
    # N02 requires a genuinely fresh, private run nonce before the owner
    # can prepare run-bound Kratos recovery credentials and source-pinned
    # Playwright/issuer profiles. Never guess the nonce or reuse DEV-04 data.
    if mode == 'development' and os.environ.get('BAOBAB_N02_RESERVE_ONLY') == 'true':
        dev.require(not os.environ.get('BAOBAB_N02_PREPARED_RUN_ID'),
                    'N02_RESERVATION_MUST_BE_NEW')
        run_id = dev.prepare(lock_name='n02-base-lock.json')
        print('N02_PRIVATE_DEVELOPMENT_RUN_RESERVED=' + run_id, flush=True)
        print('N02_BROWSER_AND_CLIENT_PROFILES_NOT_EXECUTED', flush=True)
        return 0
    if mode == 'development':
        reserved = os.environ.get('BAOBAB_N02_PREPARED_RUN_ID')
        dev.require(isinstance(reserved, str) and dev.NONCE.fullmatch(reserved),
                    'N02_PREPARED_RUN_NONCE_REQUIRED')
        run_id = reserved
        directory, state = dev.current(run_id)
        dev.require(state['phase'] == 'PREPARED'
                    and state.get('lock_file') == 'n02-base-lock.json',
                    'N02_EXACT_CANDIDATE_RUN_REQUIRED')
        dev.verify_sources(directory, state)
    else:
        dev.require(not os.environ.get('BAOBAB_N02_RESERVE_ONLY')
                    and not os.environ.get('BAOBAB_N02_PREPARED_RUN_ID'),
                    'N02_RESERVED_RUN_IS_OPT_IN')
        run_id = dev.prepare(lock_name='lock.json')
    try:
        with dev.guarded(run_id):
            if mode == 'development':
                profile = os.environ.get('BAOBAB_N02_PRIVATE_PROFILE')
                dev.require(bool(profile), 'N02_REAL_BROWSER_PROFILE_REQUIRED_BEFORE_UP')
                n02_connected.seal_first_party_origin(run_id, Path(profile))
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
            profile = os.environ.get('BAOBAB_N02_PRIVATE_PROFILE')
            client_profile = os.environ.get('BAOBAB_N02_CLIENT_REGISTRATION_PROFILE')
            dev.require(n02_mode in (None, 'development'), 'N02_JOIN_MODE_INVALID')
            dev.require(n02_mode is not None or
                        (evidence is None and profile is None), 'N02_JOIN_OPT_IN_REQUIRED')
            if n02_mode == 'development':
                dev.require(bool(evidence) and bool(profile) and bool(client_profile),
                            'N02_ORIGINAL_BROWSER_AND_CLIENT_PROFILES_REQUIRED')
                print('DEV04_STAGE=N02_REAL_BROWSER_PRE_DEACTIVATION', flush=True)
                n02_connected.execute_pinned_browser(run_id, Path(profile), Path(evidence))
            print('DEV04_STAGE=SEVEN_ORIGINAL_CASES', flush=True)
            dev.qualify_int03c(run_id)
            # Full cleanup must work without Compose. The host performs its own
            # Docker inventory independently of the in-container protocol driver.
            (directory / 'compose.json').unlink()
    finally:
        try:
            # The real IAM owner-only client controller independently
            # re-reads run metadata and deletes ONLY this lease's Hydra
            # registrations. Unknown/foreign clients block N02; cleanup
            # still proceeds and the original DEV-04 result cannot pass.
            if (mode == 'development'
                    and os.environ.get('BAOBAB_N02_CLIENT_REGISTRATION_PROFILE')
                    and os.environ.get('BAOBAB_N02_ORIGINAL_DIR')):
                with dev.guarded(run_id):
                    n02_connected.run_client_controller(
                        run_id,
                        Path(os.environ['BAOBAB_N02_CLIENT_REGISTRATION_PROFILE']),
                        Path(os.environ['BAOBAB_N02_ORIGINAL_DIR']),
                        'recover',
                    )
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
