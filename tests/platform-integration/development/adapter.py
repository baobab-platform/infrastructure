"""Closed IAM/CP lifecycle adapter. This is not a DEV-14 descriptor parser.

Only owner-native setup is allowed: native IAM subjects, a fresh marked DB,
and CP's separate development command. No SQL creates canonical CP records.
"""
import os
from pathlib import Path

ISSUER = 'https://iam.baobab-dev.test/realms/baobab'
SERVICES = {'iam-db', 'cp-db', 'iam', 'cp', 'edge', 'probe'}


def host(path):
    """Translate bind sources for Docker-outside-of-Docker Codespaces."""
    local = os.environ.get('LOCAL_WORKSPACE_FOLDER')
    container = os.environ.get('CONTAINER_WORKSPACE_FOLDER')
    if bool(local) != bool(container):
        raise ValueError('INCOMPLETE_WORKSPACE_MAPPING')
    if local:
        relative = Path(path).resolve().relative_to(Path(container).resolve())
        return str(Path(local) / relative)
    return str(path)


def composition(state, directory, images, namespace):
    run_id = state['run_id']
    project = state['project']
    labels = {'io.baobab.dev.namespace': namespace, 'io.baobab.dev.run': run_id,
              'io.baobab.dev.deadline': str(state['deadline'])}
    secrets = state['secrets']
    cp_db = 'baobab_dev_' + run_id
    db = lambda name, user, password, volume: {
        'image': images['postgres'], 'environment': {'POSTGRES_DB': name, 'POSTGRES_USER': user,
                                                   'POSTGRES_PASSWORD': password},
        'volumes': [volume + ':/var/lib/postgresql/data'],
        'healthcheck': {'test': ['CMD-SHELL', f'pg_isready -U {user} -d {name}'],
                        'interval': '3s', 'timeout': '3s', 'retries': 40}}
    registry = directory / 'sources/shared/contracts/identity/v1/workload-registry.yaml'
    tls = host(directory / 'tls')
    services = {
        'iam-db': db('baobab_iam', 'baobab_iam', secrets['iam_db'], 'iam-data'),
        'cp-db': db(cp_db, 'baobab_dev', secrets['cp_db'], 'cp-data'),
        'iam': {'image': state['images']['iam'], 'pull_policy': 'never',
                'command': ['start', '--import-realm', '--http-enabled=true',
                            '--hostname=https://iam.baobab-dev.test', '--hostname-strict=false'],
                'environment': {'KC_DB': 'postgres', 'KC_DB_URL': 'jdbc:postgresql://iam-db:5432/baobab_iam',
                                'KC_DB_USERNAME': 'baobab_iam', 'KC_DB_PASSWORD': secrets['iam_db'],
                                'KC_BOOTSTRAP_ADMIN_USERNAME': 'dev01-admin',
                                'KC_BOOTSTRAP_ADMIN_PASSWORD': secrets['admin'], 'KC_PROXY_HEADERS': 'xforwarded'},
                'depends_on': {'iam-db': {'condition': 'service_healthy'}}},
        'cp': {'image': state['images']['cp'], 'pull_policy': 'never',
               'environment': {'DATABASE_URL': f'postgres://baobab_dev:{secrets["cp_db"]}@cp-db:5432/{cp_db}?sslmode=disable',
                               'BAOBAB_ENVIRONMENT': 'development', 'HTTP_ADDRESS': ':8080',
                               'ADMIN_OIDC_ISSUER': ISSUER, 'WORKLOAD_OIDC_ISSUER': ISSUER,
                               'ADMIN_OIDC_AUDIENCE': 'baobab-control-plane',
                               'WORKLOAD_OIDC_AUDIENCE': 'baobab-control-plane',
                               'WORKLOAD_REGISTRY_FILE': '/registry.yaml', 'SSL_CERT_FILE': '/tls/ca.pem'},
               'volumes': [tls + ':/tls:ro', host(registry) + ':/registry.yaml:ro']},
        'edge': {'image': images['edge'], 'read_only': True, 'tmpfs': ['/tmp'],
                 'volumes': [host(directory / 'nginx.conf') + ':/etc/nginx/nginx.conf:ro', tls + ':/tls:ro'],
                 'networks': {'lab': {'aliases': ['iam.baobab-dev.test', 'cp.baobab-dev.test']}}},
        'probe': {'image': images['probe'], 'user': f'{state["uid"]}:{state["gid"]}',
                  'command': ['sleep', 'infinity'],
                  'environment': {'DEV01_ADMIN_PASSWORD': secrets['admin'], 'DEV01_RUN_ID': run_id},
                  'volumes': [host(directory) + ':/run/dev01', tls + ':/tls:ro',
                              host(Path(__file__).resolve().parent / 'probe.py') + ':/probe.py:ro']},
    }
    for service in services.values():
        service.update(labels=labels, restart='no')
        service.setdefault('networks', ['lab'])
    return {'name': project, 'services': services,
            'networks': {'lab': {'internal': True, 'labels': labels}},
            'volumes': {name: {'labels': labels} for name in ('iam-data', 'cp-data')}}


EDGE = '''pid /tmp/nginx.pid;
events {}
http {
  access_log off;
  error_log /dev/null;
  client_body_temp_path /tmp/client;
  proxy_temp_path /tmp/proxy;
  fastcgi_temp_path /tmp/fastcgi;
  uwsgi_temp_path /tmp/uwsgi;
  scgi_temp_path /tmp/scgi;
  ssl_protocols TLSv1.3;
  resolver 127.0.0.11 ipv6=off;
  server {
    listen 443 ssl;
    server_name iam.baobab-dev.test;
    ssl_certificate /tls/edge.pem;
    ssl_certificate_key /tls/edge.key;
    location / {
      set $upstream http://iam:8080;
      proxy_pass $upstream;
      proxy_set_header Host iam.baobab-dev.test;
      proxy_set_header X-Forwarded-Host iam.baobab-dev.test;
      proxy_set_header X-Forwarded-Proto https;
      proxy_set_header X-Forwarded-Port 443;
    }
  }
  server {
    listen 443 ssl;
    server_name cp.baobab-dev.test;
    ssl_certificate /tls/edge.pem;
    ssl_certificate_key /tls/edge.key;
    location / { set $upstream http://cp:8080; proxy_pass $upstream; }
  }
}
'''
