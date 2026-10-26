#!/usr/bin/env python3
"""All fourteen unchanged native NAB-03 development cases; no omitted blockers."""
import hashlib
import sys
sys.dont_write_bytecode=True
import cms_contract
import cms_vertical
import dev


def main():
    run=None;failure=False
    for name in ('dev05-cms-suite.json','dev05-cms-suite.sha256.json'):(dev.EVIDENCE/name).unlink(missing_ok=True)
    try:
        run=cms_vertical.prepare()
        with dev.guarded(run):
            print('DEV05_STAGE=UP',flush=True);cms_vertical.up(run)
            print('DEV05_STAGE=QUALIFY',flush=True);cms_vertical.qualify(run)
    except Exception as error:
        failure=True
        print('DEV05_EXECUTION_FAILED '+(str(error) if isinstance(error,dev.Refused) else 'INVALID_OR_UNAVAILABLE_STATE'),flush=True)
    finally:
        try:
            if run:
                with dev.guarded(run):dev.down(run)
        finally:dev.recover(all_runs=True)
    dev.require(run is not None,'DEV05_PREPARATION_FAILED')
    receipt=dev.read(dev.EVIDENCE/('dev01-'+run)/'completed/receipt.json')
    runtime=cms_contract.validate(receipt['cms'],run)
    dev.require(receipt['teardown_verified'] and not dev.resources(run) and not dev.run_dir(run).exists(),'DEV05_TEARDOWN_REQUIRED')
    path=dev.EVIDENCE/'dev05-cms-suite.json'
    dev.write(path,receipt)
    dev.write(path.with_name('dev05-cms-suite.sha256.json'),{'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    dev.require(not failure,'DEV05_EXECUTION_FAILED')
    dev.require(receipt['cms_runtime_identity_verified'],'DEV05_RUNTIME_IDENTITY_REQUIRED')
    dev.require(all(row['result']=='PASS' for row in runtime['cases'].values()),'DEV05_CASES_INCOMPLETE')
    required={'native_cms_published_home_navigation_footer','native_bff_login_session','native_bff_logout_custody',
        'bff_token_free_session','bff_secure_opaque_cookie','cp_validator_subject_accepted','revoked_before_expiry',
        'fresh_after_revoke','cp_outage_observed','provider_outage_restored','native_clients_deleted','native_tokens_inactive',
        'private_state_absent','owned_resources_absent'} | cms_contract.BOUND_COMPONENTS
    dev.require(all(runtime['component_checks'].get(key) is True for key in required)
        and runtime['component_checks'].get('provider_declared_partial') is False,'DEV05_COMPONENT_OBSERVATIONS_INCOMPLETE')
    dev.require(receipt['nab03_qualified'] and runtime['nab03_qualified'],'DEV05_DEVELOPMENT_QUALIFICATION_REQUIRED')
    print('DEV05_NATIVE_14_PASS_CURRENT_BOUND_CONTENT_AND_UNCHANGED_NEGATIVES')


if __name__=='__main__':
    try:main()
    except Exception as error:
        code = str(error) if isinstance(error, dev.Refused) else 'INVALID_OR_UNAVAILABLE_STATE'
        raise SystemExit('DEV05_RUNTIME_FAILED '+code+'; private recovery retained on cleanup failure') from None
