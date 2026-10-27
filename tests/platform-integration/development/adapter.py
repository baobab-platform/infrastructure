"""DEV-03 isolated native Ory/CP composition; no canonical provider activation."""
import os
import base64
import hashlib
from pathlib import Path

ISSUER = 'https://hydra.int03.test'
SERVICES = {'hydra-db','kratos-db','cp-db','hydra-migrate','kratos-migrate','hydra','kratos','cp','edge','probe'}
MIGRATIONS = {'hydra-migrate','kratos-migrate'}

def host(path):
    local, container = os.environ.get('LOCAL_WORKSPACE_FOLDER'), os.environ.get('CONTAINER_WORKSPACE_FOLDER')
    if bool(local) != bool(container): raise ValueError('INCOMPLETE_WORKSPACE_MAPPING')
    if local: return str(Path(local) / Path(path).resolve().relative_to(Path(container).resolve()))
    return str(path)

def unique_transport_lists(raw):
    # Two distinct loopback UI origins collapse into one isolated RP origin.
    # Kratos requires unique CORS/return-URL entries even for native API use.
    lines=[]
    for line in raw.splitlines():
        if lines and line==lines[-1] and line.lstrip().startswith('- https://rp.baobab-dev.test'): continue
        lines.append(line)
    return '\n'.join(lines)+'\n'

def configure(directory, state):
    """Derive isolated transport/secret overlays from exact IAM-owned configs."""
    source=directory/'sources/baobab-iam/config/ory'
    credentials = {'baobab-dev-introspection': state['secrets']['introspection'],
                   'baobab-int03c-issuer-verifier': state['secrets']['verifier']}
    (directory/'introspection.htpasswd').write_text(''.join(
        name + ':{SHA}' + base64.b64encode(hashlib.sha1(secret.encode()).digest()).decode() + '\n'
        for name, secret in credentials.items()))
    hydra=(source/'hydra/hydra.yml').read_text().replace('http://127.0.0.1:4444',ISSUER).replace('http://127.0.0.1:3000','https://rp.baobab-dev.test')
    hydra=hydra.replace('local_dev_only_hydra_system_secret_change_me',state['secrets']['admin']).replace('local_dev_only_pairwise_salt_change_me',state['secrets']['hook'])
    hydra=hydra.replace('  access_token: jwt','  access_token: jwt\n  jwt:\n    scope_claim: string')
    hydra=hydra.replace('  expose_internal_errors: false', '  expose_internal_errors: false\n  allowed_top_level_claims: [actor_type, azp, realm_access, client_id, acr]\n  mirror_top_level_claims: false\n  token_hook:\n    url: http://probe:8090/token-hook\n    auth:\n      type: api_key\n      config:\n        in: header\n        name: X-DEV03-Hook-Key\n        value: '+state['secrets']['hook'])
    hydra+='\nttl:\n  access_token: 2m\n'
    (directory/'hydra.yml').write_text(hydra)
    kratos=(source/'kratos/kratos.yml').read_text().replace('http://127.0.0.1:4433/','https://kratos.baobab-dev.test/').replace('http://127.0.0.1:4434/','http://kratos:4434/').replace('http://127.0.0.1:4455','https://rp.baobab-dev.test').replace('http://127.0.0.1:3000','https://rp.baobab-dev.test')
    kratos=unique_transport_lists(kratos)
    for value in ('local_dev_only_cookie_secret_32b','local_dev_only_cipher_secret_32b'): kratos=kratos.replace(value,state['secrets']['hook'][:32])
    config=directory/'kratos';config.mkdir(mode=0o755)
    (config/'kratos.yml').write_text(kratos)
    (config/'identity.schema.json').write_bytes((source/'kratos/identity.schema.json').read_bytes())
    for path in (directory/'introspection.htpasswd', directory/'hydra.yml', config/'kratos.yml', config/'identity.schema.json'): path.chmod(0o644)  # enclosing run root stays 0700

def composition(state,directory,images,namespace):
    run=state['run_id']; secret=state['secrets']; tls=host(directory/'tls')
    labels={'io.baobab.dev.namespace':namespace,'io.baobab.dev.run':run,'io.baobab.dev.deadline':str(state['deadline'])}
    def database(name,user,password,volume):
        return {'image':images['postgres'],'environment':{'POSTGRES_DB':name,'POSTGRES_USER':user,'POSTGRES_PASSWORD':password},'volumes':[volume+':/var/lib/postgresql/data'],'healthcheck':{'test':['CMD-SHELL',f'pg_isready -U {user} -d {name}'],'interval':'3s','timeout':'3s','retries':40}}
    services={'cp-db':database('baobab_dev_'+run,'baobab_dev',secret['cp_db'],'cp-data')}
    for provider in ('hydra','kratos'):
        services[provider+'-db']=database(provider,provider,secret['iam_db'],provider+'-data')
        volumes=[host(directory/'hydra.yml')+':/etc/config/hydra/hydra.yml:ro'] if provider=='hydra' else [host(directory/'kratos')+':/etc/config/kratos:ro']
        cfg='/etc/config/'+provider+'/'+provider+'.yml'
        env={'DSN':f'postgres://{provider}:{secret["iam_db"]}@{provider}-db:5432/{provider}?sslmode=disable'}
        services[provider+'-migrate']={'image':images[provider],'environment':env,'volumes':volumes,'command':['-c',cfg,'migrate','sql','-e','--yes'],'depends_on':{provider+'-db':{'condition':'service_healthy'}}}
        services[provider]={'image':images[provider],'environment':env,'volumes':volumes,'command':(['serve','all'] if provider=='hydra' else ['serve'])+['-c',cfg,'--dev'],'depends_on':{provider+'-migrate':{'condition':'service_completed_successfully'}}}
    cp_env={'DATABASE_URL':f'postgres://baobab_dev:{secret["cp_db"]}@cp-db:5432/baobab_dev_{run}?sslmode=disable','BAOBAB_ENVIRONMENT':'development','HTTP_ADDRESS':':8080','ADMIN_OIDC_ISSUER':ISSUER,'WORKLOAD_OIDC_ISSUER':ISSUER,'ADMIN_OIDC_AUDIENCE':'baobab-control-plane','WORKLOAD_OIDC_AUDIENCE':'baobab-control-plane','WORKLOAD_REGISTRY_FILE':'/registry.yaml','SSL_CERT_FILE':'/tls/ca.pem','INT03C_CP_PRINCIPAL_DEACTIVATION_ENABLED':'true'}
    for actor in ('ADMIN','WORKLOAD'):
        cp_env.update({actor+'_INTROSPECTION_ENDPOINT':ISSUER+'/oauth2/introspect',actor+'_INTROSPECTION_CLIENT_ID':'baobab-dev-introspection',actor+'_INTROSPECTION_CLIENT_SECRET':secret['introspection']})
    if state.get('subscriptions_profile'):
        cp_env.update(PEO_INTERNAL_AUTHORITY_ENABLED='true',
            PEO_SUBSCRIPTIONS_WORKLOAD_CLIENT_ID='baobab-dev-subscriptions-assessor',
            CP_SUBSCRIPTION_CURRENT_AUTHORITY_ENABLED='true',
            CP_SUBSCRIPTIONS_CURRENT_WORKLOAD_CLIENT_ID='baobab-dev-subscriptions-assessor')
    if state.get('buyer_identity_profile'):
        cp_env.update(BUYER_PRINCIPAL_RESOLUTION_ENABLED='true',
            BUYER_SUBJECT_ISSUER=ISSUER, BUYER_SUBJECT_AUTHORISED_PARTIES='baobab-dev-zuribeans-bff',
            BUYER_SUBJECT_INTROSPECTION_ENDPOINT=ISSUER+'/oauth2/introspect',
            BUYER_SUBJECT_INTROSPECTION_CLIENT_ID='baobab-dev-introspection',
            BUYER_SUBJECT_INTROSPECTION_CLIENT_SECRET=secret['introspection'],
            ESTATE_CLIENT_BINDING_ENABLED='true')
    registry=directory/'sources/shared/contracts/identity/v1/workload-registry.yaml'
    if state.get('dev15_registry_sha256'):
        # Only a reviewed, private development overlay is permitted here.
        # Merely mounting a registered client does not provision credentials,
        # create a current CP grant or make the engine provider ACTIVE.
        require_source = '9fa1bbd6ad9b5c9d4ec406c721bd75227803dcea'
        if state.get('environment')!='development' or state.get('dev15_registry_source_sha')!=require_source:
            raise ValueError('DEV15_REGISTRY_AUTHORITY_REFUSED')
        registry=directory/'dev15-workload-registry.yaml'
        if registry.is_symlink() or not registry.is_file() or hashlib.sha256(registry.read_bytes()).hexdigest()!=state['dev15_registry_sha256']:
            raise ValueError('DEV15_REGISTRY_DRIFT')
    services['cp']={'image':state['images']['cp'],'pull_policy':'never','environment':cp_env,'volumes':[tls+':/tls:ro',host(registry)+':/registry.yaml:ro']}
    services['edge']={'image':images['edge'],'read_only':True,'tmpfs':['/tmp'],'volumes':[host(directory/'nginx.conf')+':/etc/nginx/nginx.conf:ro',host(directory/'introspection.htpasswd')+':/etc/nginx/introspection.htpasswd:ro',tls+':/tls:ro'],'networks':{'lab':{'aliases':['hydra.int03.test','cp.baobab-dev.test','kratos.baobab-dev.test','rp.baobab-dev.test']}}}
    services['probe']={'image':images['probe'],'user':f'{state["uid"]}:{state["gid"]}','command':['python','/native_probe.py','serve'],'environment':{'DEV01_RUN_ID':run,'DEV03_HOOK_KEY':secret['hook'],'DEV03_INTROSPECTION_SECRET':secret['introspection'],'DEV04_VERIFIER_SECRET':secret['verifier']},'volumes':[host(directory)+':/run/dev01',tls+':/tls:ro',*[host(Path(__file__).parent/name)+':/'+name+':ro' for name in ('native_probe.py','int03c_probe.py','int03c_contract.py')]]}
    if state.get('dev15_profile'):
        # DEV-15's private HTTP observer must be present at probe startup.
        # Adding a bind after the container has started cannot make its
        # contents appear without recreating the already qualified probe.
        if state.get('dev15_profile') not in ('pulse-intelligence','payments-sandbox'):
            raise ValueError('DEV15_UNRECOGNISED_PROFILE')
        services['probe']['volumes'].append(
            host(Path(__file__).parent/'dev15_health.py')+':/dev15_health.py:ro')
    if state.get('buyer_identity_profile'):
        services['probe']['volumes'] += [host(Path(__file__).parent/'buyer_identity_probe.py')+':/buyer_identity_probe.py:ro',
            host(directory/'sources/baobab-iam/scripts/dev07_buyer_fixture.py')+':/dev07_buyer_fixture.py:ro']
    if state.get('engine_profile'):
        services['probe']['volumes'] += [host(Path(__file__).parent/name)+':/'+name+':ro' for name in ('engine_probe.py','engine_contract.py')]
    for service in services.values(): service.update(labels=labels,restart='no');service.setdefault('networks',['lab'])
    return {'name':state['project'],'services':services,'networks':{'lab':{'internal':True,'labels':labels}},'volumes':{name:{'labels':labels} for name in ('cp-data','hydra-data','kratos-data')}}

EDGE='''pid /tmp/nginx.pid;
events {}
http {
 access_log off; error_log /dev/null;
 client_body_temp_path /tmp/client; proxy_temp_path /tmp/proxy;
 fastcgi_temp_path /tmp/fastcgi; uwsgi_temp_path /tmp/uwsgi; scgi_temp_path /tmp/scgi;
 ssl_protocols TLSv1.3; resolver 127.0.0.11 ipv6=off;
'''
for name,upstream in [('hydra.int03.test','hydra:4444'),('kratos.baobab-dev.test','kratos:4433'),('cp.baobab-dev.test','cp:8080')]:
    introspection=''' location = /oauth2/introspect {
 limit_except POST { deny all; }
 auth_basic "DEV03 private introspection"; auth_basic_user_file /etc/nginx/introspection.htpasswd;
 set $introspector http://hydra:4445; proxy_pass $introspector/admin/oauth2/introspect;
 proxy_set_header Authorization "";
 }
''' if name=='hydra.int03.test' else ''
    EDGE+=''' server { listen 443 ssl; server_name '''+name+''';
 ssl_certificate /tls/edge.pem; ssl_certificate_key /tls/edge.key;
'''+introspection+''' location / { set $upstream http://'''+upstream+'''; proxy_pass $upstream;
 proxy_set_header Host '''+name+'''; proxy_set_header X-Forwarded-Proto https; }
 }
'''
EDGE+='}\n'
