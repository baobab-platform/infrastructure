"""Private owner-store readback; output stays in run custody, never an artifact."""
import asyncio
import json
from pathlib import Path
from baobab_pulse.configuration.settings import Settings
from baobab_pulse.infrastructure.persistence.connection import Database

async def main():
    expected=json.loads(Path('/run/l4/current-authority.json').read_text())
    database=Database(Settings().database_url);await database.connect()
    try:
        count=await database.pool.fetchval('SELECT count(*) FROM intelligence.evidence_read_audit WHERE tenant_id=$1',expected['tenant_id'])
        row=await database.pool.fetchrow('''SELECT resolution_id,grant_id,binding_id,provider_id,engine_instance_id,evidence_set_id,result_count,actor_subject,actor_client_id
          FROM intelligence.evidence_read_audit WHERE tenant_id=$1 ORDER BY occurred_at DESC LIMIT 1''',expected['tenant_id'])
        matched=row is not None and all(row[k]==expected[k] for k in ('grant_id','binding_id','provider_id','engine_instance_id')) and row['result_count']==1 and row['evidence_set_id']=='evs_int02_native' and row['actor_subject']=='baobab-dev-external-api' and row['actor_client_id']=='baobab-dev-external-api'
        print(json.dumps({'count':count,'matching_authority':matched,'resolution_id':row['resolution_id'] if row else None}))
    finally:await database.disconnect()
if __name__=='__main__':
    try:asyncio.run(main())
    except Exception:raise SystemExit('DEV06_AUDIT_READBACK_FAILED') from None
