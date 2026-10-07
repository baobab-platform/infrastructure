#!/usr/bin/env python3
"""Read-only AWS release preflight and observed-runtime evidence.

Uses the AWS CLI's existing short-lived/OIDC credentials. Never reads secret
values, executes tasks, applies Terraform, publishes runtime profiles or logs in.
"""
import argparse
import datetime
import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys

REGION = 'af-south-1'
DIGEST = re.compile(r'^[0-9]{12}\.dkr\.ecr\.af-south-1\.amazonaws\.com/[a-z0-9_/-]+@sha256:[a-f0-9]{64}$')


def aws(*args):
    result = subprocess.run(['aws', '--region', REGION, '--no-cli-pager', '--output', 'json', *args], capture_output=True, text=True, timeout=60)
    if result.returncode:
        raise ValueError('AWS read failed: ' + args[0] + '/' + args[1])
    return json.loads(result.stdout)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON field')
        result[key] = value
    return result


def release(path):
    raw = pathlib.Path(path).read_bytes()
    doc = json.loads(raw, object_pairs_hook=unique_object)
    value = doc.get('workload_release', doc)
    if not re.fullmatch(r'[0-9]{12}', value['account_id']):
        raise ValueError('invalid account')
    if set(value['services']) != {'cp', 'iam', 'pulse', 'keycloak', 'apisix'}:
        raise ValueError('incomplete services')
    for image in [value['helper_image'], *[service['image'] for service in value['services'].values()]]:
        if not DIGEST.fullmatch(image) or not image.startswith(value['account_id'] + '.'):
            raise ValueError('image must use same-account immutable ECR digest')
    if len(value['etcd_endpoints']) != 3 or len(set(value['etcd_endpoints'])) != 3 or any(not re.fullmatch(r'https://[A-Za-z0-9.-]+:2379', endpoint) for endpoint in value['etcd_endpoints']):
        raise ValueError('durable authenticated etcd quorum required')
    if not value['browser_realms'] or any(realm.lower() == 'master' or not re.fullmatch(r'[A-Za-z0-9_-]+', realm) for realm in value['browser_realms']):
        raise ValueError('invalid public realms')
    for name, service in value['services'].items():
        if not re.fullmatch(r'[a-f0-9]{40}', service['source_revision']):
            raise ValueError('invalid source revision')
        if not service['bundle_secret_arn'].startswith('arn:aws:secretsmanager:' + REGION + ':' + value['account_id'] + ':secret:'):
            raise ValueError('cross-account bundle')
        if not re.fullmatch(r'[A-Za-z0-9-]{32,64}', service['bundle_version_id']):
            raise ValueError('secret version required')
        files = service['bundle_files']
        if len(set(files)) != len(files) or not {'ca.pem', 'service.pem', 'service.key', 'probe.pem', 'probe.key'}.issubset(files) or any(not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', file) or file == 'runtime-helper' for file in files):
            raise ValueError('invalid protected file manifest')
        for key, content in service['environment'].items():
            sensitive = re.search(r'password|secret|token|database_url|aws_access|aws_secret', key, re.I) and key != 'PULSE_IAM_TOKEN_URL'
            if sensitive and not (key.endswith('_FILE') and content.startswith('/run/baobab/') and content.removeprefix('/run/baobab/') in files):
                raise ValueError('plaintext credential environment')
        allowed = {'DATABASE_URL'} if name == 'cp' else {'PULSE_DATABASE_URL', 'PULSE_IAM_CLIENT_SECRET', 'PULSE_QDRANT_API_KEY'} if name == 'pulse' else {'KC_DB_USERNAME', 'KC_DB_PASSWORD', 'KC_BOOTSTRAP_ADMIN_PASSWORD'} if name == 'keycloak' else set()
        for key, reference in service['secret_environment'].items():
            if key not in allowed or not reference.startswith('arn:aws:secretsmanager:' + REGION + ':' + value['account_id'] + ':secret:') or not re.search(r':[^:]*::[A-Za-z0-9-]{32,64}$', reference):
                raise ValueError('unapproved or mutable credential reference')
    pulse = value['services']['pulse']
    pulse_env = pulse['environment']
    authority_urls = (
        pulse_env.get('PULSE_IAM_ISSUER_URL', ''),
        pulse_env.get('PULSE_IAM_JWKS_URL', ''),
        pulse_env.get('PULSE_IAM_TOKEN_URL', ''),
        pulse_env.get('PULSE_CONTROL_PLANE_CONTEXT_VALIDATION_URL', ''),
    )
    if (
        pulse_env.get('PULSE_ENVIRONMENT') != 'staging'
        or pulse_env.get('PULSE_IAM_CLIENT_ID') != 'baobab-pulse-workload'
        or pulse_env.get('PULSE_IAM_RESOURCE_AUDIENCE') != 'baobab-pulse'
        or any(not url.startswith('https://') for url in authority_urls)
        or not {'PULSE_DATABASE_URL', 'PULSE_IAM_CLIENT_SECRET'}.issubset(pulse['secret_environment'])
    ):
        raise ValueError('Pulse staging authority configuration is incomplete')
    return value, hashlib.sha256(raw).hexdigest()


def preflight(value, check_images=True):
    identity = aws('sts', 'get-caller-identity')
    if identity['Account'] != value['account_id']:
        raise ValueError('wrong AWS account')
    if check_images:
        for image in sorted({value['helper_image'], *[service['image'] for service in value['services'].values()]}):
            repository = image.split('/', 1)[1].split('@')[0]
            digest = image.split('@')[1]
            response = aws('ecr', 'batch-get-image', '--repository-name', repository, '--image-ids', 'imageDigest=' + digest)
            images = response.get('images', [])
            if response.get('failures') or len(images) != 1 or images[0]['imageId']['imageDigest'] != digest:
                raise ValueError('unavailable image digest')
            manifest = json.loads(images[0]['imageManifest'])
            if 'manifests' in manifest:
                raise ValueError('release must pin the linux/amd64 platform manifest, not an image index')
    required_versions = set()
    for service in value['services'].values():
        required_versions.add((service['bundle_secret_arn'], service['bundle_version_id']))
        for reference in service['secret_environment'].values():
            secret_arn, _json_key, stage, version = reference.rsplit(':', 3)
            if stage or not re.fullmatch(r'[A-Za-z0-9-]{32,64}', version):
                raise ValueError('immutable credential version required')
            required_versions.add((secret_arn, version))
    # Metadata only: validate every pinned credential version without reading values.
    for secret_arn, version in sorted(required_versions):
        metadata = aws('secretsmanager', 'describe-secret', '--secret-id', secret_arn)
        if metadata.get('DeletedDate') or version not in metadata.get('VersionIdsToStages', {}):
            raise ValueError('protected secret version unavailable')
    cert = aws('acm', 'describe-certificate', '--certificate-arn', value['certificate_arn'])['Certificate']
    hostname = value['public_hostname']
    matches = any(hostname == domain or domain.startswith('*.') and hostname.endswith(domain[1:]) and hostname.count('.') == domain.count('.') for domain in cert.get('SubjectAlternativeNames', []))
    if cert['Status'] != 'ISSUED' or not matches:
        raise ValueError('public certificate not issued')
    zone = aws('route53', 'get-hosted-zone', '--id', value['route53_zone_id'])['HostedZone']
    if zone.get('Config', {}).get('PrivateZone') or not (hostname == zone['Name'].rstrip('.') or hostname.endswith('.' + zone['Name'].rstrip('.'))):
        raise ValueError('public DNS zone mismatch')
    versions = aws('rds', 'describe-db-engine-versions', '--engine', 'postgres', '--engine-version', value['postgres']['engine_version'])
    if not versions.get('DBEngineVersions'):
        raise ValueError('PostgreSQL minor version unavailable in staging region')
    return {'account': identity['Account'], 'region': REGION, 'artifacts_available': check_images, 'bundle_versions_available': True}


def observe(value, cluster, infrastructure_revision):
    if not re.fullmatch(r'[a-f0-9]{40}', infrastructure_revision):
        raise ValueError('infrastructure revision required')
    if aws('sts', 'get-caller-identity')['Account'] != value['account_id']:
        raise ValueError('wrong AWS account')
    evidence = []
    for name, expected in value['services'].items():
        service_name = 'baobab-staging-' + name
        response = aws('ecs', 'describe-services', '--cluster', cluster, '--services', service_name)
        if response.get('failures') or len(response.get('services', [])) != 1:
            raise ValueError('service unavailable')
        service = response['services'][0]
        deployments = service.get('deployments', [])
        if service['desiredCount'] != 1 or service['runningCount'] != 1 or service['pendingCount'] != 0 or len(deployments) != 1 or deployments[0].get('rolloutState') != 'COMPLETED':
            raise ValueError('service deployment not stable')
        if name == 'iam' and service['deploymentConfiguration']['maximumPercent'] != 100:
            raise ValueError('concurrent IAM writer deployment enabled')
        listed = aws('ecs', 'list-tasks', '--cluster', cluster, '--service-name', service_name)['taskArns']
        if len(listed) != 1:
            raise ValueError('service task count is not exactly one')
        task_response = aws('ecs', 'describe-tasks', '--cluster', cluster, '--tasks', listed[0])
        if task_response.get('failures') or len(task_response.get('tasks', [])) != 1:
            raise ValueError('runtime task unavailable')
        task = task_response['tasks'][0]
        if task.get('lastStatus') != 'RUNNING' or task.get('healthStatus') != 'HEALTHY' or task['taskDefinitionArn'] != service['taskDefinition']:
            raise ValueError('task not healthy or task-definition drift')
        containers = {item['name']: item for item in task['containers']}
        app = containers.get(name, {})
        if app.get('image') != expected['image'] or app.get('imageDigest') != expected['image'].split('@')[1]:
            raise ValueError('observed application image drift')
        if containers.get('materialize', {}).get('exitCode') != 0:
            raise ValueError('protected material initialization failed')
        for helper_name in (['materialize', 'private-tls'] if name in {'cp', 'pulse'} else ['materialize']):
            if containers.get(helper_name, {}).get('imageDigest') != value['helper_image'].split('@')[1]:
                raise ValueError('observed helper image drift')
        definition = aws('ecs', 'describe-task-definition', '--task-definition', task['taskDefinitionArn'])['taskDefinition']
        if definition.get('networkMode') != 'awsvpc' or definition['runtimePlatform'].get('cpuArchitecture') != 'X86_64':
            raise ValueError('runtime platform drift')
        network = service['networkConfiguration']['awsvpcConfiguration']
        if network.get('assignPublicIp') != 'DISABLED':
            raise ValueError('public workload networking')
        evidence.append({'service': name, 'task_arn': task['taskArn'], 'task_definition': task['taskDefinitionArn'], 'image_digest': app['imageDigest'], 'source_revision_declared': expected['source_revision'], 'infrastructure_revision': infrastructure_revision, 'health': 'HEALTHY'})
    return evidence


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['validate', 'preflight', 'observe'])
    parser.add_argument('--release', required=True)
    parser.add_argument('--cluster')
    parser.add_argument('--infrastructure-revision')
    parser.add_argument('--output')
    parser.add_argument('--skip-images', action='store_true')
    args = parser.parse_args()
    if args.skip_images and args.mode != 'preflight':
        parser.error('--skip-images is valid only for preflight')
    value, digest = release(args.release)
    result = {'schema': 'baobab.staging-observation.v1', 'observed_at': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'release_sha256': digest, 'operational_acceptance': False}
    if args.mode == 'preflight':
        result['preflight'] = preflight(value, check_images=not args.skip_images)
    elif args.mode == 'observe':
        if not args.cluster or not args.infrastructure_revision:
            parser.error('observe requires cluster and infrastructure revision')
        result['services'] = observe(value, args.cluster, args.infrastructure_revision)
    else:
        result['release_valid'] = True
    # Observation is construction evidence, not a live CP/IAM/federation result.
    if args.output:
        with open(args.output, 'x', encoding='utf-8') as stream:
            json.dump(result, stream, indent=2)
            stream.write('\n')
    else:
        print(json.dumps(result, indent=2))

if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, TypeError, OSError, subprocess.SubprocessError, json.JSONDecodeError):
        print('staging verification denied; check account, release and runtime references', file=sys.stderr)
        sys.exit(1)
