#!/usr/bin/env python3
"""Verify a coordinated cut against successful publisher receipts; no AWS calls."""
import argparse
import json
import os
import pathlib
import re
import subprocess
import tempfile

TAG = re.compile(r'v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)-staging')
DIGEST = re.compile(r'sha256:[0-9a-f]{64}')
REPOS = {'shared': ('shared', 'staging-release.yml', 'contracts'),
         'cp': ('baobab-cp', 'staging-ci.yml', 'cp'),
         'iam': ('baobab-iam', 'staging-ci.yml', 'iam'),
         'pulse': ('baobab-pulse', 'staging-ci.yml', 'pulse'),
         'keycloak': ('baobab-iam', 'staging-ci.yml', 'keycloak')}
IMAGES = {'shared': 'baobab-contracts', 'cp': 'baobab-cp',
          'iam': 'baobab-iam-federation-authority', 'pulse': 'baobab-pulse',
          'keycloak': 'baobab-iam'}


def unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result: raise ValueError('duplicate release field')
        result[key] = value
    return result


def load(path):
    return json.loads(pathlib.Path(path).read_text(), object_pairs_hook=unique)


def api(path):
    return json.loads(subprocess.run(['gh', 'api', path], capture_output=True,
                                    text=True, check=True, timeout=30).stdout)


def receipt(repo, run, artifact):
    with tempfile.TemporaryDirectory() as directory:
        subprocess.run(['gh', 'run', 'download', str(run), '--repo', repo,
                        '--name', artifact, '--dir', directory], check=True,
                       capture_output=True, timeout=60)
        return load(pathlib.Path(directory) / 'staging-image.json')


def verify_selection(tag, coordination, fetch=api, read=receipt):
    """Verify publisher truth before account-specific deployment inputs exist."""
    if not TAG.fullmatch(tag): raise ValueError('invalid staging cut tag')
    if set(coordination) != {'release_tag', 'components'} or coordination['release_tag'] != tag or set(coordination['components']) != set(REPOS):
        raise ValueError('incomplete coordinated release')
    evidence = []
    for key, (name, workflow, suffix) in REPOS.items():
        selected = coordination['components'][key]
        if set(selected) != {'tag', 'source_revision', 'digest'} or not TAG.fullmatch(selected['tag']) or not re.fullmatch(r'[0-9a-f]{40}', selected['source_revision']) or not DIGEST.fullmatch(selected['digest']):
            raise ValueError('invalid component selection')
        repo = 'baobab-platform/' + name
        obj = fetch('repos/' + repo + '/git/ref/tags/' + selected['tag'])['object']
        for _ in range(5):
            if obj['type'] == 'commit': break
            if obj['type'] != 'tag': raise ValueError('tag is not a commit')
            obj = fetch('repos/' + repo + '/git/tags/' + obj['sha'])['object']
        if obj['type'] != 'commit' or obj['sha'] != selected['source_revision']:
            raise ValueError('component tag moved or selects different source')
        runs = fetch('repos/' + repo + '/actions/workflows/' + workflow + '/runs?head_sha=' + selected['source_revision'] + '&status=success&per_page=100')['workflow_runs']
        matches = [x for x in runs if x['head_sha'] == selected['source_revision'] and x['head_branch'] == selected['tag'] and x['event'] in {'push', 'workflow_dispatch'} and x['status'] == 'completed' and x['conclusion'] == 'success']
        if not matches: raise ValueError('successful component publisher is absent')
        run = matches[0]['id']
        value = read(repo, run, 'staging-' + selected['tag'] + '-' + suffix)
        expected = 'ghcr.io/baobab-platform/' + IMAGES[key] + '@' + selected['digest']
        if value.get('operational_acceptance') is not False:
            raise ValueError('publisher receipt must not claim operational acceptance')
        if any(value.get(k) != v for k, v in {'release_tag': selected['tag'], 'repository': repo, 'source_revision': selected['source_revision'], 'image': expected, 'run_url': 'https://github.com/' + repo + '/actions/runs/' + str(run), 'operational_acceptance': False}.items()):
            raise ValueError('publisher receipt does not match selected artifact')
        evidence.append({'component': key, **selected, 'run_id': run})
    return {'release_tag': tag, 'components': evidence, 'operational_acceptance': False}


def verify(tag, release_path, release, coordination, fetch=api, read=receipt):
    if release_path != 'deploy/releases/staging/' + tag + '.tfvars.json':
        raise ValueError('manifest is not bound to this cut')
    # Account-free selection verification never replaces this runtime binding.
    for key in REPOS:
        if key != 'shared':
            selected = coordination['components'][key]
            service = release['workload_release']['services'][key]
            if service['source_revision'] != selected['source_revision'] or service['image'].split('@')[-1] != selected['digest']:
                raise ValueError('promoted runtime differs from selected component')
    return verify_selection(tag, coordination, fetch, read)


def main():
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--release')
    mode.add_argument('--coordination')
    parser.add_argument('--output', default='staging-cut-verification.json')
    args = parser.parse_args()
    if args.coordination:
        coordination = load(args.coordination)
        evidence = verify_selection(coordination['release_tag'], coordination)
        with open(args.output, 'x', encoding='utf-8') as stream:
            json.dump(evidence, stream, indent=2)
            stream.write('\n')
        return
    ref = os.environ['GITHUB_REF']
    if ref == 'refs/heads/main': return  # Existing reviewed manual recovery path.
    if not ref.startswith('refs/tags/'): raise ValueError('unreviewed deployment ref')
    release = load(args.release)
    coordination = load(args.release.removesuffix('.tfvars.json') + '.coordination.json')
    evidence = verify(ref.removeprefix('refs/tags/'), args.release, release, coordination)
    with open(args.output, 'x', encoding='utf-8') as stream:
        json.dump(evidence, stream, indent=2)


if __name__ == '__main__':
    try: main()
    except (ValueError, KeyError, TypeError, OSError, subprocess.SubprocessError):
        raise SystemExit('Coordinated staging release verification failed')
