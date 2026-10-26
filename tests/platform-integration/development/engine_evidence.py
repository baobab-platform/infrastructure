#!/usr/bin/env python3
"""Independent offline custody check. Partial results never mean acceptance."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import engine_contract as contract

BASE=Path(__file__).resolve().parent


def require(ok):
    if not ok:raise ValueError('ENGINE_EVIDENCE_REFUSED')


def verify(path,shared,harness):
    require(path.is_file() and not path.is_symlink() and path.stat().st_size<=262144)
    raw=path.read_bytes();receipt=json.loads(raw)
    require(json.loads(path.with_name('receipt.sha256.json').read_text())=={'sha256':hashlib.sha256(raw).hexdigest()})
    require(receipt['schema']=='infrastructure.dev01.lifecycle.observed.v1' and receipt['harness_sha']==harness)
    require(receipt['teardown_verified'] is True and receipt['engine_runtime_identity_verified'] is True and receipt['lifecycle_passed'] is True)
    require(receipt['protected_acceptance'] is False and receipt['production_authorized'] is False and receipt['evidence_class']=='REAL_COMPONENT_SYNTHETIC_DATA')
    report=contract.validate(receipt['engine_integration'],receipt['run_id'])
    lock=json.loads((BASE/'engine-base-lock.json').read_text());owners=json.loads((BASE/'engine-lock.json').read_text())
    key=report['profile_key'];owner=owners['profiles'][key]
    require(receipt['source_pins']=={**lock['sources'],owner['repository']:owner['source_sha']})
    require(receipt['lock_sha256']==hashlib.sha256((BASE/'engine-base-lock.json').read_bytes()).hexdigest() and receipt['engine_lock_sha256']==hashlib.sha256((BASE/'engine-lock.json').read_bytes()).hexdigest())
    require(re.fullmatch('sha256:[0-9a-f]{64}',receipt['image_ids']['subject']) and re.fullmatch('sha256:[0-9a-f]{64}',receipt['engine_oci_manifest_digest']))
    profile=json.loads((shared/'contracts'/owner['profile_path']).read_text())
    require(set(report['cases'])==set(profile['reporting']['case_ids']))
    require(set(report['capabilities'])=={c['capability_key'] for c in profile['capabilities']})
    require(all(c['development']=='OBSERVED' and c['certification']=='NOT_QUALIFIED' for c in report['capabilities'].values()))
    observed=report['independent_observations']
    require(observed['issuer_cleanup'] is True and observed['host_cleanup'] is True and observed['authority_denials']==4 and observed['principal_denial'] is True)
    require({'cp','hydra'}<=set(observed['faults_observed']))
    expected={
        'ENG-ONB-03':'AUTHORITY_UNQUALIFIED','ENG-ONB-06':'NATIVE_NOT_IMPLEMENTED',
        'PAYMENTS-ACTOR-MARKET-CURRENCY':'AUTHORITY_UNQUALIFIED','PAYMENTS-MISSING-MANDATE':'AUTHORITY_UNQUALIFIED','PAYMENTS-EVENT-REPLAY':'NATIVE_NOT_IMPLEMENTED'} if key=='payments-sandbox' else {}
    require({case:row['reason'] for case,row in report['cases'].items() if row['result']=='BLOCKED'}==expected)
    require(all(row['result']=='PASS' and row['reason']=='OBSERVED' or case in expected and row['result']=='BLOCKED' for case,row in report['cases'].items()))
    if key=='pulse-intelligence':require(observed['native_audits_joined']>0 and {'pulse-db','pulse-qdrant'}<=set(observed['faults_observed']))
    return {'profile':key,'receipt_sha256':hashlib.sha256(raw).hexdigest(),'passed':sum(row['result']=='PASS' for row in report['cases'].values()),
        'blocked':expected,'profile_fully_qualified':not expected,'dev15_package_accepted':False,'protected_acceptance':False,'production_authorized':False}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('receipt',type=Path);parser.add_argument('--shared-root',required=True,type=Path);parser.add_argument('--harness-sha',required=True)
    args=parser.parse_args()
    try:print(json.dumps(verify(args.receipt,args.shared_root,args.harness_sha),sort_keys=True));return 0
    except (ValueError,OSError,KeyError,TypeError):print('ENGINE_EVIDENCE_REFUSED',file=sys.stderr);return 2

if __name__=='__main__':raise SystemExit(main())
