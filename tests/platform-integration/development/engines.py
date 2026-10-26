#!/usr/bin/env python3
"""DEV-14 engine-neutral lifecycle; owner adapters run only in containers."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import secrets
import sys
import tempfile
import time

import adapter
import dev
import engine_contract as contract
import external_oci


BASE=Path(__file__).resolve().parent

def lock():
    value=json.loads((BASE/'engine-lock.json').read_text(),object_pairs_hook=dev.unique)
    dev.require(set(value)=={'schema','profiles','native_images'} and value['schema']=='infrastructure.engine-integration.sources.v1','ENGINE_LOCK_INVALID')
    for key,item in value['profiles'].items():
        dev.require(__import__('re').fullmatch('[a-z][a-z0-9-]{1,62}',key) and set(item)=={'repository','source_sha','profile_path'} and dev.SHA.fullmatch(item['source_sha']) and
            __import__('re').fullmatch('baobab-[a-z0-9-]{1,56}',item['repository']) and
            item['profile_path']=='development/v1/examples/engines/'+key+'.json','ENGINE_SOURCE_PIN_REQUIRED')
    dev.require(all(k in {'postgresql','qdrant','redis'} and dev.DIGEST.fullmatch(v) and '@sha256:' in v for k,v in value['native_images'].items()),'ENGINE_NATIVE_DIGEST_REQUIRED')
    return value

def shared_module(shared):
    # Shared is platform-owned pinned source. Engine code is never imported here.
    sys.path.insert(0,str(shared/'scripts'))
    spec=importlib.util.spec_from_file_location('shared_engine_profiles',shared/'scripts/engine_integration_profile.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

def profile_for(shared,key,owner=None):
    item=lock()['profiles'].get(key);dev.require(item is not None,'ENGINE_PROFILE_NOT_LOCKED')
    module=shared_module(shared);profile=module.read_profile(shared/'contracts'/item['profile_path'])
    plan=module.validate(profile,shared_root=shared,engine_root=owner)
    dev.require(profile['subject_engine']==item['repository'],'ENGINE_PROFILE_OWNER_MISMATCH')
    for node in profile['services']['required']:
        dev.require(node['kind'] in {'iam','control-plane','engine'} or node['kind'] in lock()['native_images'],'ENGINE_NATIVE_ADAPTER_UNAVAILABLE')
    return profile,plan,module

def clone(target,repo,sha,state=None):
    dev.call(['git','init','-q',str(target)],state=state)
    dev.call(['git','-C',str(target),'fetch','--quiet','--depth','1','https://github.com/baobab-platform/'+repo+'.git',sha],timeout=180,state=state)
    dev.call(['git','-C',str(target),'checkout','--quiet','--detach','FETCH_HEAD'],state=state)
    dev.require(dev.call(['git','-C',str(target),'rev-parse','HEAD'])==sha,'ENGINE_SOURCE_MISMATCH')

def doctor(key,shared=None,owner=None,static=False):
    if shared is None:
        with tempfile.TemporaryDirectory(prefix='baobab-engine-plan-') as temporary:
            root=Path(temporary);pins=dev.load_lock('engine-base-lock.json')['sources'];item=lock()['profiles'][key]
            clone(root/'shared','shared',pins['shared']);clone(root/item['repository'],item['repository'],item['source_sha'])
            return doctor(key,root/'shared',root/item['repository'],static)
    expected=dev.load_lock('engine-base-lock.json')['sources']['shared']
    dev.require(dev.call(['git','-C',str(shared),'rev-parse','HEAD'])==expected and not dev.call(['git','-C',str(shared),'status','--porcelain']),'ENGINE_SHARED_SOURCE_DRIFT')
    if owner is not None:
        dev.require(dev.call(['git','-C',str(owner),'rev-parse','HEAD'])==lock()['profiles'][key]['source_sha'] and not dev.call(['git','-C',str(owner),'status','--porcelain']),'ENGINE_OWNER_SOURCE_DRIFT')
    profile,plan,_=profile_for(shared,key,owner)
    if not static:dev.doctor(lock_name='engine-base-lock.json')
    return {**plan,'source_pins':{**dev.load_lock('engine-base-lock.json')['sources'],profile['subject_engine']:lock()['profiles'][key]['source_sha']},'static_only':static,'runtime_qualified':False}

def prepare(key,lease=3600):
    item=lock()['profiles'][key];run=dev.prepare(lease,lock_name='engine-base-lock.json')
    try:
        directory,state=dev.current(run);source=directory/'sources'/item['repository']
        clone(source,item['repository'],item['source_sha'],state)
        state['sources'][item['repository']]=item['source_sha']
        shared=directory/'sources/shared';profile,_,module=profile_for(shared,key,source)
        dev.require(profile['mode']=='l4','ENGINE_COMPONENT_PROFILE_NOT_QUALIFIED')
        dev.require(lease<=profile['run_policy']['max_lease_seconds'],'ENGINE_PROFILE_LEASE_EXCEEDED')
        dev.check_dockerfile(source/profile['adapter']['dockerfile'])
        schema='development/v1/engine-integration-profile.schema.json'
        dev.require((directory/'sources/baobab-cp/internal/contracts/shared'/schema).read_bytes()==(shared/'contracts'/schema).read_bytes(),'ENGINE_EMBEDDED_SCHEMA_DRIFT')
        state['contract_hashes'][schema]=hashlib.sha256((shared/'contracts'/schema).read_bytes()).hexdigest()
        state['engine_profile']=profile;state['engine_integration']=contract.fresh(profile,run)
        state['engine_lock_sha256']=hashlib.sha256((BASE/'engine-lock.json').read_bytes()).hexdigest()
        state['runtime_images'].update({'engine-'+k:v for k,v in lock()['native_images'].items()})
        for role in ('caller','neighbour','validator'):state['secrets']['engine_'+role]=secrets.token_hex(32)
        for service in profile['services']['required']:
            if service['kind'] in lock()['native_images']:state['secrets']['engine_store_'+service['key']]=secrets.token_hex(32)
        dev.write(directory/'engine-profile.json',profile)
        dev.write(directory/'engine-registration.json',module.registration(profile,source,shared))
        invalid={**profile,'force_active':True}
        try:module.validate(invalid,shared_root=shared)
        except Exception:pass
        else:raise dev.Refused('ENGINE_UNKNOWN_FIELD_ACCEPTED')
        state['engine_integration']['cases']['ENG-ONB-01']={'result':'PASS','reason':'OBSERVED'}
        dev.persist(directory,state,'PREPARED');return run
    except BaseException:
        dev.down(run);raise

def owner_fixture(directory,state,phase):
    subjects=dev.read(directory/'subjects.json')
    args=['run','--rm','--no-deps','--user',str(state['uid'])+':'+str(state['gid'])]
    for name in ('engine-profile','engine-source','engine-registration'):
        args+=['--volume',adapter.host(directory/(name+'.json'))+':/'+name+'.json:ro']
    args+=['-e','BAOBAB_DEV_BOOTSTRAP_ENABLED=true','--entrypoint','/development-bootstrap','cp',
        '--engine-profile','/engine-profile.json','--engine-capability-source','/engine-source.json',
        '--engine-registration','/engine-registration.json','--engine-capability-phase',phase,
        '--run-id',state['run_id'],'--issuer',adapter.ISSUER,'--maker-subject',subjects['maker'],
        '--checker-subject',subjects['checker'],'--lease',str(state['bootstrap_lease'])+'s']
    raw=dev.compose(directory,state,*args,timeout=120);result=json.loads(raw.splitlines()[-1])
    dev.require(result['run_id']==state['run_id'] and result['source']==dev.read(directory/'engine-source.json'),'ENGINE_AUTHORITY_PROOF_MISMATCH')
    if phase in {'activate','restore','regrant','refresh','rebind'}:
        dev.require(all(result[k] for k in ('source_present','source_active','grant_active','binding_active','projection_current','provider_active')),'ENGINE_CURRENT_AUTHORITY_NOT_ESTABLISHED')
        dev.require(set(result['grants'])==set(c['capability_key'] for c in state['engine_profile']['capabilities'])==set(result['bindings']),'ENGINE_PARTIAL_AUTHORITY_REFUSED')
    dev.write(directory/'engine-capability.json',result);return result

def bind_environment(profile,context):
    result={}
    for key,binding in profile['adapter']['environment'].items():
        if 'constant' in binding:result[key]=binding['constant'];continue
        value=context
        for part in binding['source'].split('.'):value=value[part]
        dev.require(isinstance(value,str) and bool(value),'ENGINE_ENVIRONMENT_BINDING_INVALID');result[key]=value
    return result

def engine_tool(directory,state,phase):
    raw=dev.compose(directory,state,'run','--rm','--no-deps','engine-tool',phase,timeout=180)
    result=json.loads(raw.splitlines()[-1]);dev.require(isinstance(result,dict),'ENGINE_ADAPTER_RESULT_INVALID')
    return result

def native_service_name(profile,node):
    same=[item for item in profile['services']['required'] if item['kind']==node['kind']]
    suffix=('-db' if node['kind']=='postgresql' else '-qdrant' if node['kind']=='qdrant' else '-redis') if len(same)==1 else '-'+node['key']
    name=profile['subject_engine'].removeprefix('baobab-')+suffix
    dev.require(__import__('re').fullmatch('[a-z][a-z0-9-]{1,62}',name),'ENGINE_NATIVE_DNS_REFUSED')
    return name

def up(run):
    print('ENGINE_PHASE=BASE_UP',flush=True)
    dev.up(run);directory,state=dev.current(run);profile=state['engine_profile'];source=directory/'sources'/profile['subject_engine'];labels=dev.labels(state)
    image=state['project']+'-subject';state['images']['subject']=image;dev.persist(directory,state,'RUNNING')
    args=['docker','build','--tag',image,'--file',str(source/profile['adapter']['dockerfile'])]
    for k,v in {**labels,'org.opencontainers.image.revision':state['sources'][profile['subject_engine']]}.items():args+=['--label',k+'='+v]
    print('ENGINE_PHASE=BUILD',flush=True)
    dev.call([*args,str(source)],timeout=1800,state=state)
    state['image_ids']['subject']=dev.call(['docker','image','inspect',image,'--format','{{.Id}}'])
    archive=directory/'subject.tar';dev.call(['docker','image','save','--output',str(archive),image],timeout=180,state=state)
    digest=external_oci.publish(archive,directory/'engine-oci',state['image_ids']['subject']);archive.unlink()
    state['engine_oci_manifest_digest']=digest;dev.persist(directory,state,'RUNNING')
    dev.write(directory/'engine-source.json',{'source_sha':state['sources'][profile['subject_engine']],'manifest_digest':digest,
        'declaration_digest':'sha256:'+hashlib.sha256((source/profile['references']['capability_provider']).read_bytes()).hexdigest()})
    authority=owner_fixture(directory,state,'register');bootstrap=dev.read(directory/'bootstrap.json')
    def enterprise(seed):
        own=next(e for e in bootstrap['enterprises'] if e['key']==seed);country=own['markets'][0]
        return {'id':own['tenant_id'],'organisation_id':own['organisation_id'],'legal_entity_id':own.get('legal_entity_id',''),
            'market_id':bootstrap['market_ids'][country],'country':country}
    iam={role:{**identity,'client_secret':state['secrets']['engine_'+role]} for role,identity in profile['iam'].items()}
    context={'schema':'baobab.engine-adapter-context.v1','run':{'id':run},'tenant':enterprise(profile['enterprise_seed']),
        'neighbour':enterprise(profile['neighbour_seed']),'iam':{**iam,'issuer':adapter.ISSUER,'jwks':adapter.ISSUER+'/.well-known/jwks.json',
            'token':adapter.ISSUER+'/oauth2/token','introspection_url':adapter.ISSUER+'/oauth2/introspect',
            'allowed_clients':','.join(identity['client_id']+'='+profile['subject_engine'] for role,identity in iam.items() if role!='validator')},
        'cp':{'origin':'https://cp.baobab-dev.test','context_validation':'https://cp.baobab-dev.test/v1/platform-context/validate',
            'capability_resolution':'https://cp.baobab-dev.test/v1/capabilities/resolve','provider_id':'provider_'+authority['provider_id'].replace('-',''),
            'engine_instance_id':'ei_'+authority['engine_instance_id'].replace('-','')},'tls':{'ca_file':'/tls/ca.pem'},'native':{}}
    composition=dev.read(directory/'compose.json');services=composition['services'];stores=[]
    for node in profile['services']['required']:
        kind=node['kind']
        if kind not in lock()['native_images']:continue
        key=node['key'];name=native_service_name(profile,node);volume='engine-'+key+'-data';password=state['secrets']['engine_store_'+key]
        native={'image':lock()['native_images'][kind],'networks':['engine'],'volumes':[volume+(':/var/lib/postgresql/data' if kind=='postgresql' else ':/qdrant/storage' if kind=='qdrant' else ':/data')]}
        if kind=='postgresql':
            native.update(environment={'POSTGRES_DB':profile['subject_engine'].removeprefix('baobab-'),'POSTGRES_USER':profile['subject_engine'].removeprefix('baobab-'),'POSTGRES_PASSWORD':password},healthcheck={'test':['CMD','pg_isready','-U',profile['subject_engine'].removeprefix('baobab-'),'-d',profile['subject_engine'].removeprefix('baobab-')],'interval':'3s','timeout':'3s','retries':40})
            db=profile['subject_engine'].removeprefix('baobab-');url='postgresql://'+db+':'+password+'@'+name+':5432/'+db
        elif kind=='qdrant':url='http://'+name+':6333'
        else:
            native['command']=['redis-server','--requirepass',password];url='redis://:'+password+'@'+name+':6379'
        context['native'][key]={'url':url,'password':password};services[name]=native;stores.append(name)
        composition['volumes'][volume]={'labels':labels}
    env=bind_environment(profile,context);private=directory/'engine-private';private.mkdir(mode=0o700)
    dev.write(private/'context.json',context)
    # A fixed non-root container identity can read only its specific private
    # file mount. It never gets the enclosing operator/issuer run directory.
    set_context_owner(private/'context.json',state)
    services['subject']={'image':image,'networks':['engine'],'user':'1000:1000','environment':env,'volumes':[adapter.host(directory/'tls/ca.pem')+':/tls/ca.pem:ro'],'cap_drop':['ALL'],'security_opt':['no-new-privileges:true']}
    driver=image if profile['adapter']['driver']=='engine' else state['runtime_images']['probe']
    root=dev.call(['docker','image','inspect',image,'--format','{{.Config.WorkingDir}}']) if profile['adapter']['driver']=='engine' else '/app'
    root=root or '/app'
    dev.require(root.startswith('/') and '..' not in Path(root).parts and ':' not in root,'ENGINE_OWNER_ROOT_REFUSED')
    adapter_path=str(Path(root)/profile['adapter']['path']);sdk_path=str(Path(adapter_path).parent/'engine_sdk.py')
    dev.require(adapter_path!=sdk_path,'ENGINE_ADAPTER_NAME_RESERVED')
    state['engine_sdk_path']=sdk_path
    services['engine-tool']={'image':driver,'networks':['engine'],'user':tool_identity(state),'entrypoint':['python',adapter_path],'environment':{**env,'BAOBAB_DEV14_PRIVATE_RUN':'1'},'cap_drop':['ALL'],'security_opt':['no-new-privileges:true'],
        'volumes':[adapter.host(private/'context.json')+':/run/engine/context.json:ro',adapter.host(directory/'tls/ca.pem')+':/tls/ca.pem:ro',
        adapter.host(source/profile['adapter']['path'])+':'+adapter_path+':ro',adapter.host(BASE/'engine_sdk.py')+':'+sdk_path+':ro']}
    gateway=adapter.EDGE[:adapter.EDGE.index(' server {')]
    gateway+='server { listen 443 ssl; server_name engine.baobab-dev.test; ssl_certificate /tls/edge.pem; ssl_certificate_key /tls/edge.key; location / { set $target http://subject:'+str(profile['adapter']['port'])+'; proxy_pass $target; proxy_set_header Host engine.baobab-dev.test; } }\n'
    for host in ('hydra.int03.test','cp.baobab-dev.test'):
        gateway+='server { listen 443 ssl; server_name '+host+'; ssl_certificate /tls/edge.pem; ssl_certificate_key /tls/edge.key; '
        proxy='proxy_ssl_verify on; proxy_ssl_trusted_certificate /tls/ca.pem; proxy_ssl_server_name on; proxy_ssl_name '+host+'; set $target https://edge:443; proxy_pass $target; proxy_set_header Host '+host+'; '
        if host=='hydra.int03.test':
            for path in ('/.well-known/openid-configuration','/.well-known/jwks.json','/oauth2/token','/oauth2/revoke'):
                gateway+='location = '+path+' { '+proxy+' } '
            gateway+='location / { return 404; } '
        else:
            gateway+='location ^~ /v1/admin/ { return 404; } location /v1/ { '+proxy+' } location / { return 404; } '
        gateway+='}\n'
    gateway+='}\n'
    config=directory/'engine-gateway.conf';config.write_text(gateway)
    state['engine_gateway_sha256']=hashlib.sha256(config.read_bytes()).hexdigest()
    composition['networks']['engine']={'internal':True,'labels':labels}
    services['engine-gateway']={'image':state['runtime_images']['edge'],'user':'101:101','read_only':True,'tmpfs':['/tmp'],
        'cap_drop':['ALL'],'security_opt':['no-new-privileges:true'],'sysctls':{'net.ipv4.ip_forward':'0','net.ipv4.ip_unprivileged_port_start':'0'},
        'volumes':[adapter.host(config)+':/etc/nginx/nginx.conf:ro',adapter.host(directory/'tls')+':/tls:ro'],
        'networks':{'lab':{'aliases':['engine.baobab-dev.test']},'engine':{'aliases':['engine.baobab-dev.test','hydra.int03.test','cp.baobab-dev.test']}}}
    for service in services.values():service.update(labels=labels,restart='no');service.setdefault('networks',['lab'])
    dev.write(directory/'compose.json',composition);state['compose_sha256']=hashlib.sha256((directory/'compose.json').read_bytes()).hexdigest();dev.persist(directory,state,'RUNNING')
    dev.compose(directory,state,'up','-d','--wait','--wait-timeout','120',*stores,'engine-gateway',timeout=180)
    print('ENGINE_PHASE=OWNER_PREPARE',flush=True)
    isolated=json.loads(dev.compose(directory,state,'run','--rm','--no-deps','--entrypoint','python','engine-tool',state['engine_sdk_path'],'isolation',timeout=30).splitlines()[-1])
    dev.require(isolated=={'private_planes_unreachable':True},'ENGINE_ADMIN_NETWORK_EXPOSED')
    engine_tool(directory,state,'prepare')
    dev.compose(directory,state,'up','-d','subject')
    for _ in range(60):
        try:
            if json.loads(dev.compose(directory,state,'exec','-T','probe','python','/engine_probe.py','health',timeout=15))=={'status':'READY'}:break
        except (dev.Refused,ValueError):pass  # Startup may briefly refuse HTTP or return a non-JSON response.
        time.sleep(2)
    else:raise dev.Refused('ENGINE_READINESS_UNAVAILABLE')
    refresh_witness(directory,state)
    engine_tool(directory,state,'denied')
    owner_fixture(directory,state,'activate')
    dev.test(run);directory,state=dev.current(run)
    verify_runtime(directory,state)
    state['engine_runtime_identity_verified']=True;dev.persist(directory,state,'RUNNING')

def verify_runtime(directory,state):
    dev.verify_sources(directory,state)
    dev.require(hashlib.sha256((directory/'engine-gateway.conf').read_bytes()).hexdigest()==state['engine_gateway_sha256'],'ENGINE_GATEWAY_CONFIGURATION_DRIFT')
    dev.require(hashlib.sha256((BASE/'engine-lock.json').read_bytes()).hexdigest()==state['engine_lock_sha256'],'ENGINE_LOCK_DRIFT')
    composition=dev.read(directory/'compose.json')
    for name in ['engine-gateway','subject',*[native_service_name(state['engine_profile'],s) for s in state['engine_profile']['services']['required'] if s['kind'] in lock()['native_images']]]:
        cid=dev.compose(directory,state,'ps','-q',name);dev.require(bool(cid),'ENGINE_NOT_RUNNING')
        actual=json.loads(dev.call(['docker','inspect',cid]))[0]
        expected=dev.call(['docker','image','inspect',composition['services'][name]['image'],'--format','{{.Id}}'])
        dev.require(actual['Image']==expected and not actual['HostConfig']['PortBindings'] and not actual['HostConfig']['Privileged'] and actual['Config']['Labels'].get('io.baobab.dev.run')==state['run_id'],'ENGINE_RUNTIME_IDENTITY_REFUSED')
        if name=='subject':dev.require(actual['Config']['User']=='1000:1000' and actual['Image']==state['image_ids']['subject'] and actual['Config']['Labels'].get('org.opencontainers.image.revision')==state['sources'][state['engine_profile']['subject_engine']],'ENGINE_NATIVE_SOURCE_OR_IDENTITY_REFUSED')
        networks=actual['NetworkSettings']['Networks'];dev.require(len(networks)==(2 if name=='engine-gateway' else 1),'ENGINE_NETWORK_INVALID')
        for network in networks:
            network_info=json.loads(dev.call(['docker','network','inspect',network]))[0]
            dev.require(network_info['Internal'] is True,'ENGINE_PUBLIC_NETWORK_REFUSED')
            if name!='engine-gateway':dev.require(network_info['Name']==state['project']+'_engine','ENGINE_ADMIN_NETWORK_EXPOSED')

def tool_identity(state):
    uid=state['uid'] if state['uid'] else 1000
    gid=state['gid'] if state['uid'] else 1000
    dev.require(uid>0,'ENGINE_TOOL_ROOT_REFUSED')
    return str(uid)+':'+str(gid)

def set_context_owner(path,state):
    uid,gid=map(int,tool_identity(state).split(':'))
    current=path.stat()
    if current.st_uid!=uid or current.st_gid!=gid:os.chown(path,uid,gid)
    dev.require(path.stat().st_mode&0o777==0o600,'ENGINE_CONTEXT_NOT_PRIVATE')

def update_context(directory,values):
    path=directory/'engine-private/context.json'
    context=json.loads(path.read_text(),object_pairs_hook=dev.unique)
    context.update(values);dev.write(path,context);set_context_owner(path,dev.read(directory/'state.json'))

def refresh_witness(directory,state):
    raw=dev.compose(directory,state,'exec','-T','probe','python','/engine_probe.py','witness',timeout=40)
    dev.require(json.loads(raw.splitlines()[-1])=={'witness_created':True},'ENGINE_WITNESS_UNAVAILABLE')
    update_context(directory,{'witness':dev.read(directory/'engine-witness.json')})

def phase_observed(report,result):
    dev.require(isinstance(result,dict) and set(result) in ({'observed'},{'observed','case_updates'}) and result['observed'] is True,'ENGINE_PHASE_UNOBSERVED')
    updates=result.get('case_updates',{})
    dev.require(isinstance(updates,dict) and set(updates)<=set(report['cases'])-contract.COMMON,'ENGINE_OWNER_CANNOT_ACCEPT_COMMON_CASES')
    for case,row in updates.items():
        dev.require(report['cases'][case]['result']!='FAIL','ENGINE_CASE_FAILURE_CANNOT_BE_ERASED')
        report['cases'][case]=row
    contract.validate(report,report['run_id'])

def resolution_counts(directory,state,all_decisions=False):
    own=dev.read(directory/'engine-capability.json');counts={}
    for capability in state['engine_profile']['capabilities']:
        key=capability['capability_key']
        sql="SELECT count(*) FROM capability.capability_resolution WHERE decision='RESOLVED' AND tenant_id='"+own['tenant_id'].replace("'","''")+"' AND capability_key='"+key.replace("'","''")+"' AND provider_id::text='"+own['provider_id']+"' AND engine_instance_id::text='"+own['engine_instance_id']+"'"
        if all_decisions:sql=sql.replace("decision='RESOLVED' AND ",'')
        counts[key]=int(dev.compose(directory,state,'exec','-T','cp-db','psql','-U','baobab_dev','-d','baobab_dev_'+state['run_id'],'-tAc',sql))
    return counts

def independent_effects(directory,state):
    observed=engine_tool(directory,state,'observe')
    dev.require(set(observed)=={'effects','resolutions','checks'} and isinstance(observed['effects'],dict) and all(type(v) is int and v>=0 for v in observed['effects'].values()) and observed['checks'] and all(v is True for v in observed['checks'].values()),'ENGINE_NATIVE_STORE_OBSERVATION_FAILED')
    dev.require(isinstance(observed['resolutions'],list) and len(observed['resolutions'])<=1000,'ENGINE_NATIVE_AUDIT_INVENTORY_INVALID')
    own=dev.read(directory/'engine-capability.json')
    for rid in observed['resolutions']:
        dev.require(isinstance(rid,str) and __import__('re').fullmatch('res_[0-9a-f]{32}',rid),'ENGINE_NATIVE_RESOLUTION_INVALID')
        sql="SELECT EXISTS(SELECT 1 FROM capability.capability_resolution WHERE decision='RESOLVED' AND resolution_id='"+rid+"' AND tenant_id='"+own['tenant_id']+"' AND provider_id::text='"+own['provider_id']+"' AND engine_instance_id::text='"+own['engine_instance_id']+"')"
        dev.require(dev.compose(directory,state,'exec','-T','cp-db','psql','-U','baobab_dev','-d','baobab_dev_'+state['run_id'],'-tAc',sql)=='t','ENGINE_INDEPENDENT_CP_AUDIT_MISSING')
    if observed['effects']:dev.require(bool(observed['resolutions']),'ENGINE_NATIVE_AUDIT_REQUIRED')
    return observed

def test(run):
    directory,state=dev.current(run);verify_runtime(directory,state)
    print('ENGINE_PHASE=AUTHORITY',flush=True)
    core=json.loads(dev.compose(directory,state,'exec','-T','probe','python','/engine_probe.py','authority',timeout=180).splitlines()[-1])
    dev.require(set(core)=={'checks'} and set(core['checks'])==contract.AUTHORITY_CHECKS and all(value is True for value in core['checks'].values()),'ENGINE_COMMON_AUTHORITY_FAILED')
    refresh_witness(directory,state)
    update_context(directory,{'security_tokens':dev.read(directory/'engine-security.json')})
    report=state['engine_integration']
    def passed(case):report['cases'][case]={'result':'PASS','reason':'OBSERVED'}
    passed('ENG-ONB-02')
    before=resolution_counts(directory,state)
    print('ENGINE_PHASE=NATIVE_SCENARIOS',flush=True)
    actual=engine_tool(directory,state,'test')
    dev.require(set(actual) in ({'cases'},{'cases','native_refs'}) and set(actual['cases'])==set(report['cases'])-contract.COMMON,'ENGINE_ADAPTER_CASES_MISMATCH')
    if actual.get('native_refs'):
        refs=actual['native_refs']
        dev.require(set(refs)<={'intent_id','payment_id','refund_id'} and all(isinstance(v,str) and __import__('re').fullmatch(r'[a-z_]+[0-9a-f]{32}',v) for v in refs.values()),'ENGINE_NATIVE_REFERENCE_INVALID')
        update_context(directory,{'native_refs':refs})
    report['cases'].update(actual['cases']);contract.validate(report,run)
    # Save exact owner outcomes before any later fault can interrupt the run.
    state['engine_integration']=report;dev.persist(directory,state,'RUNNING')
    after=resolution_counts(directory,state)
    dev.require(all(after[key]>before[key] for key in before),'ENGINE_NATIVE_CP_INVOCATION_NOT_OBSERVED')
    observed=independent_effects(directory,state)
    for key in before:
        report['independent_observations']['native_cp_resolutions'][key]=after[key]-before[key]
        report['capabilities'][key]['development']='OBSERVED'
    report['independent_observations']['native_audits_joined']=len(observed['resolutions'])
    if not any(row['result']=='FAIL' for row in actual['cases'].values()):passed('ENG-ONB-05')
    else:raise dev.Refused('ENGINE_NATIVE_CASE_FAILED')
    # Legal actor/mandate and event replay gaps remain explicit. A simulation
    # cannot certify an actor merely because its tenant routing is correct.
    if any(row['result']=='BLOCKED' and row['reason']=='AUTHORITY_UNQUALIFIED' for row in actual['cases'].values()):report['cases']['ENG-ONB-03']={'result':'BLOCKED','reason':'AUTHORITY_UNQUALIFIED'}
    else:passed('ENG-ONB-03')
    dev.persist(directory,state,'RUNNING')
    for resource in ['cp','hydra',*[native_service_name(state['engine_profile'],node) for node in state['engine_profile']['services']['required'] if node['kind'] in lock()['native_images']]]:
        print('ENGINE_PHASE=FAULT_'+resource.upper().replace('-','_'),flush=True)
        owner_fixture(directory,state,'refresh')
        refresh_witness(directory,state);update_context(directory,{'fault_phase':resource})
        baseline=independent_effects(directory,state)
        dev.compose(directory,state,'stop',resource)
        try:phase_observed(report,engine_tool(directory,state,'unavailable'))
        finally:dev.compose(directory,state,'up','-d',resource)
        # Recovery must be a new successful authenticated native operation.
        for _ in range(30):
            try:
                refresh_witness(directory,state)
                phase_observed(report,engine_tool(directory,state,'restored'));break
            except (dev.Refused,ValueError):pass  # Readiness alone is insufficient.
            time.sleep(1)
        else:
            # An independently observed boundary diagnosis never supplies
            # authority or changes a case result. Keep the original refusal.
            try:
                diagnostic=json.loads(dev.compose(directory,state,'exec','-T','probe','python','/engine_probe.py','diagnose',timeout=60).splitlines()[-1])
                dev.require(set(diagnostic)=={'validation_http','context_matches','market_matches','capability_http','capability_resolved'} and
                    type(diagnostic['validation_http']) is int and 100<=diagnostic['validation_http']<=599 and
                    all(type(diagnostic[k]) is bool for k in ('context_matches','market_matches')) and
                    isinstance(diagnostic['capability_http'],list) and isinstance(diagnostic['capability_resolved'],list) and
                    len(diagnostic['capability_http'])==len(diagnostic['capability_resolved'])==len(state['engine_profile']['capabilities']) and
                    all(type(v) is int and 100<=v<=599 for v in diagnostic['capability_http']) and
                    all(type(v) is bool for v in diagnostic['capability_resolved']),'ENGINE_DIAGNOSTIC_REFUSED')
                print('ENGINE_RECOVERY_AUTHORITY='+json.dumps(diagnostic,sort_keys=True),flush=True)
            except (dev.Refused,ValueError,KeyError,TypeError):print('ENGINE_RECOVERY_AUTHORITY=UNAVAILABLE',flush=True)
            raise dev.Refused('ENGINE_RECOVERY_UNOBSERVED')
        current=independent_effects(directory,state)
        for key in ('canonical_sets','missions','mutation_audits','outbox'):
            if key in baseline['effects']:dev.require(current['effects'][key]==baseline['effects'][key],'ENGINE_RECOVERY_CHANGED_CANONICAL_DATA')
        report['independent_observations']['faults_observed'].append(resource)
        dev.persist(directory,state,'RUNNING')
    passed('ENG-ONB-07');dev.persist(directory,state,'RUNNING')
    # Withdraw/restore the normal Trial provenance and grants, and finally
    # retire native bindings. No harness SQL creates or activates authority.
    print('ENGINE_PHASE=WITHDRAWAL',flush=True)
    for phase,restored in (('unentitled','regrant'),('absent','restore'),('retire','rebind'),('suspend-provider',None)):
        owner_fixture(directory,state,'refresh')
        refresh_witness(directory,state);baseline=independent_effects(directory,state)
        owner_fixture(directory,state,phase)
        phase_observed(report,engine_tool(directory,state,'denied'))
        if baseline['effects']:
            current=engine_tool(directory,state,'observe')
            dev.require(current['effects']==baseline['effects'],'ENGINE_DENIED_NATIVE_EFFECT')
        report['independent_observations']['authority_denials']+=1
        if restored:owner_fixture(directory,state,restored)
        dev.persist(directory,state,'RUNNING')
    passed('ENG-ONB-04')
    refresh_witness(directory,state)
    owner_fixture(directory,state,'disable-principal')
    disabled=json.loads(dev.compose(directory,state,'exec','-T','probe','python','/engine_probe.py','principal',timeout=30).splitlines()[-1])
    dev.require(disabled=={'disabled_principal_denied':True},'ENGINE_PRINCIPAL_DENIAL_UNOBSERVED')
    counts=resolution_counts(directory,state,all_decisions=True)
    phase_observed(report,engine_tool(directory,state,'denied'))
    dev.require(resolution_counts(directory,state,all_decisions=True)==counts,'ENGINE_DISABLED_PRINCIPAL_REACHED_CAPABILITY')
    report['independent_observations']['principal_denial']=True
    if any(row['result']=='BLOCKED' and row['reason'] in {'NATIVE_NOT_IMPLEMENTED','AUTHORITY_UNQUALIFIED'} for key,row in report['cases'].items() if key not in contract.COMMON):report['cases']['ENG-ONB-06']={'result':'BLOCKED','reason':'NATIVE_NOT_IMPLEMENTED'}
    else:passed('ENG-ONB-06')
    verify_runtime(directory,state)
    print('ENGINE_PHASE=ISSUER_CLEANUP',flush=True)
    # Independent native issuer read-back and deletion precede host teardown.
    dev.require(json.loads(dev.compose(directory,state,'exec','-T','probe','python','/engine_probe.py','cleanup',timeout=90).splitlines()[-1])=={'issuer_cleanup_observed':True},'ENGINE_ISSUER_CLEANUP_UNOBSERVED')
    report['independent_observations']['issuer_cleanup']=True
    report['cases']['ENG-ONB-08']={'result':'BLOCKED','reason':'TEARDOWN_PENDING'}
    passed('ENG-ONB-09')
    state['tests']=True;state['engine_integration']=report;dev.persist(directory,state,'TESTED')
    return report

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=['doctor','plan','prepare','up','test','evidence','down','recover','run'])
    parser.add_argument('--profile',default='pulse-intelligence');parser.add_argument('--run-id');parser.add_argument('--lease',type=int,default=3600)
    parser.add_argument('--shared-root',type=Path);parser.add_argument('--engine-root',type=Path);parser.add_argument('--static',action='store_true')
    args=parser.parse_args(argv)
    try:
        dev.require(not args.static or args.action in {'doctor','plan','evidence'},'STATIC_CANNOT_MUTATE')
        if args.action in {'doctor','plan'}:print(json.dumps(doctor(args.profile,args.shared_root,args.engine_root,args.static),sort_keys=True))
        elif args.action=='prepare':print(prepare(args.profile,args.lease))
        elif args.action=='recover':dev.recover(all_runs=True)
        elif args.action=='run':
            run=None
            try:
                run=prepare(args.profile,args.lease)
                with dev.guarded(run):up(run);test(run)
            finally:
                if run:
                    with dev.guarded(run):dev.down(run)
            report=dev.read(dev.EVIDENCE/('dev01-'+run)/'completed/receipt.json')
            print(json.dumps(report,sort_keys=True))
            dev.require(report['teardown_verified'] and all(c['result']=='PASS' for c in report['engine_integration']['cases'].values()),'ENGINE_QUALIFICATION_INCOMPLETE')
        else:
            with dev.guarded(args.run_id):
                if args.action=='up':up(args.run_id)
                elif args.action=='test':print(json.dumps(test(args.run_id),sort_keys=True))
                elif args.action=='down':dev.down(args.run_id)
                else:
                    folder=dev.EVIDENCE/('dev01-'+args.run_id)/'completed/receipt.json'
                    dev.require(folder.is_file(),'ENGINE_FINAL_EVIDENCE_UNAVAILABLE');print(folder.read_text())
        return 0
    except Exception as error:
        code=str(error) if isinstance(error,dev.Refused) else 'ENGINE_INVALID_OR_UNAVAILABLE_STATE'
        print('ENGINE_BLOCKED '+code,file=sys.stderr);return 2

if __name__=='__main__':raise SystemExit(main())
