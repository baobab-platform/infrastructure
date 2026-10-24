#!/usr/bin/env python3
"""Real DEV-05 execution: precise blocked results are retained, never mock PASS."""
import hashlib
import sys
sys.dont_write_bytecode=True
import cms_contract
import cms_vertical
import dev


def main():
    run=None
    try:
        run=cms_vertical.prepare()
        with dev.guarded(run):
            print('DEV05_STAGE=UP',flush=True);cms_vertical.up(run)
            print('DEV05_STAGE=QUALIFY',flush=True);cms_vertical.qualify(run)
    finally:
        if run:
            with dev.guarded(run):dev.down(run)
        dev.recover(all_runs=True)
    path=dev.EVIDENCE/('dev01-'+run)/'completed/receipt.json'
    receipt=dev.read(path);cms_contract.validate(receipt['cms'],run)
    dev.require(receipt['teardown_verified'] and not dev.resources(run) and not dev.run_dir(run).exists(),'DEV05_TEARDOWN_REQUIRED')
    dev.require(not any(r['result']=='FAIL' for r in receipt['cms']['cases'].values()),'DEV05_CASE_FAILED')
    runtime=receipt['cms']
    allowed_blocked={'published-home-nav-footer','missing-grant'}
    dev.require(all(row['result']=='PASS' or (name in allowed_blocked and row['reason'] in
        {'PROVIDER_NOT_ELIGIBLE','CANONICAL_CAPABILITY_NOT_RESOLVED'}) for name,row in runtime['cases'].items()),'DEV05_UNEXECUTED_CASE')
    required={'native_cms_published_home_navigation_footer','native_bff_login_session','native_bff_logout_custody',
        'bff_token_free_session','bff_secure_opaque_cookie','cp_validator_subject_accepted','revoked_before_expiry',
        'fresh_after_revoke','cp_outage_observed','provider_outage_restored','native_clients_deleted','native_tokens_inactive',
        'private_state_absent','owned_resources_absent'}
    dev.require(all(runtime['component_checks'].get(key) is True for key in required),'DEV05_COMPONENT_OBSERVATIONS_INCOMPLETE')
    if runtime['cases']['published-home-nav-footer']['result']=='BLOCKED':
        dev.require(runtime['component_checks'].get('estate_canonical_path_unavailable') is True,'DEV05_ESTATE_BLOCKER_UNOBSERVED')
    # BLOCKED is a successful observation of unavailable authority, never a gate
    # PASS. CI may verify this expected condition while nab03_qualified is false.
    dev.write(dev.EVIDENCE/'dev05-cms-suite.json',receipt)
    dev.write(dev.EVIDENCE/'dev05-cms-suite.sha256.json',{'sha256':hashlib.sha256((dev.EVIDENCE/'dev05-cms-suite.json').read_bytes()).hexdigest()})
    print('DEV05_OBSERVED_'+('QUALIFIED' if receipt['nab03_qualified'] else 'BLOCKED_CANONICAL_PROVIDER'))


if __name__=='__main__':
    try:main()
    except Exception as error:
        code = str(error) if isinstance(error, dev.Refused) else ('DEPENDENCY_UNAVAILABLE' if isinstance(error, ImportError) else 'INVALID_OR_UNAVAILABLE_STATE')
        raise SystemExit('DEV05_RUNTIME_FAILED '+code+'; private recovery retained on cleanup failure') from None
