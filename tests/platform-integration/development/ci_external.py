#!/usr/bin/env python3
"""Real DEV-06 component execution; canonical INT-07 acceptance stays blocked."""
import hashlib
import sys
sys.dont_write_bytecode=True
import dev
import external_contract as contract
import external_vertical as external

# The eighteen original obligations remain unchanged; no provider skip can
# replace the four formerly blocked canonical positive/negative controls.

def main():
    run=None;failure=False
    for name in ('dev06-external-suite.json','dev06-external-suite.sha256.json'):(dev.EVIDENCE/name).unlink(missing_ok=True)
    try:
        run=external.prepare()
        with dev.guarded(run):
            print('DEV06_STAGE=UP',flush=True);external.up(run)
            print('DEV06_STAGE=QUALIFY',flush=True);external.qualify(run)
    except Exception:
        failure=True
    finally:
        if run:
            with dev.guarded(run):dev.down(run)
        dev.recover(all_runs=True)
    dev.require(run is not None,'DEV06_PREPARATION_FAILED')
    receipt=dev.read(dev.EVIDENCE/('dev01-'+run)/'completed/receipt.json')
    result=contract.validate(receipt['external'],run)
    dev.require(receipt['teardown_verified'] and receipt['external_runtime_identity_verified'] and not dev.resources(run) and not dev.run_dir(run).exists(),'DEV06_TEARDOWN_REQUIRED')
    path=dev.EVIDENCE/'dev06-external-suite.json'
    dev.write(path,receipt)
    dev.write(path.with_name('dev06-external-suite.sha256.json'),{'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    dev.require(not failure and all(row['result']=='PASS' for row in result['cases'].values()),'DEV06_CASES_INCOMPLETE')
    dev.require(set(result['component_checks'])==contract.COMPONENTS and all(result['component_checks'].values()),'DEV06_COMPONENTS_INCOMPLETE')
    print('DEV06_NATIVE_18_PASS_NORMAL_BOUND_RESOURCE_AND_UNCHANGED_NEGATIVES')

if __name__=='__main__':
    try:main()
    except Exception as error:
        code=str(error) if isinstance(error,dev.Refused) else 'INVALID_OR_UNAVAILABLE_STATE'
        raise SystemExit('DEV06_RUNTIME_FAILED '+code+'; private recovery retained on cleanup failure') from None
