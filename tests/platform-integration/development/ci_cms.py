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
    # BLOCKED is a successful observation of unavailable authority, never a gate
    # PASS. CI may verify this expected condition while nab03_qualified is false.
    dev.write(dev.EVIDENCE/'dev05-cms-suite.json',receipt)
    dev.write(dev.EVIDENCE/'dev05-cms-suite.sha256.json',{'sha256':hashlib.sha256((dev.EVIDENCE/'dev05-cms-suite.json').read_bytes()).hexdigest()})
    print('DEV05_OBSERVED_'+('QUALIFIED' if receipt['nab03_qualified'] else 'BLOCKED_CANONICAL_PROVIDER'))


if __name__=='__main__':
    try:main()
    except Exception:raise SystemExit('DEV05_RUNTIME_FAILED_PRIVATE_RECOVERY_RETAINED') from None
