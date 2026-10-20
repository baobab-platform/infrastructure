#!/usr/bin/env python3
"""Last-resort Actions cleanup if the integration devcontainer dies.

Never accepts a run or edits a PASS receipt. Targets only the validated random
project in INT-03's own private session, using Docker ownership labels. Host
paths are derived locally; a container-side path cannot authorize host deletion.
"""
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess

ROOT = Path(__file__).resolve().parents[3]
STATE = ROOT / 'tests/platform-integration/.runtime'
SESSION = STATE / 'int03-session.json'


def command(args):
    result = subprocess.run(args, capture_output=True, text=True, timeout=180, check=False)
    if result.returncode:
        raise RuntimeError('Cleanup command unavailable')
    return result.stdout.strip().splitlines()


def cleanup():
    if os.environ.get('GITHUB_ACTIONS') != 'true' or os.geteuid() != 0:
        raise RuntimeError('Host recovery is restricted to the Actions runner')
    if SESSION.is_symlink():
        raise RuntimeError('Untrusted cleanup session')
    if not SESSION.exists():
        return
    fd = os.open(SESSION, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_mode & 0o077 or info.st_size > 16384:
            raise RuntimeError('Untrusted cleanup session')
        data = os.read(fd, 16385)
        if len(data) > 16384:
            raise RuntimeError('Untrusted cleanup session')
        value = json.loads(data)
    finally:
        os.close(fd)
    project = value.get('project', '')
    declared = Path(value.get('directory', ''))
    if not re.fullmatch(r'l4-[0-9a-f]{16}', project) or declared.name != 'int02-' + project or declared.parent.name != '.runtime':
        raise RuntimeError('Untrusted cleanup project')
    directory = STATE / ('int02-' + project)
    if directory.is_symlink():
        raise RuntimeError('Untrusted cleanup directory')
    if directory.exists():
        node = directory.lstat()
        if not stat.S_ISDIR(node.st_mode) or node.st_uid != info.st_uid or node.st_mode & 0o077:
            raise RuntimeError('Untrusted cleanup directory')
    for kind, listing, remove in [('container', ['docker', 'ps', '-aq'], ['docker', 'rm', '-f']),
        ('network', ['docker', 'network', 'ls', '-q'], ['docker', 'network', 'rm']),
        ('volume', ['docker', 'volume', 'ls', '-q'], ['docker', 'volume', 'rm'])]:
        query = [*listing, '--filter', 'label=com.docker.compose.project=' + project]
        identifiers = command(query)
        for identifier in identifiers:
            valid = (re.fullmatch(r'[0-9a-f]{12,64}', identifier) or
                     kind == 'volume' and re.fullmatch(re.escape(project) + r'_[a-z0-9_-]+', identifier))
            if not valid:
                raise RuntimeError('Untrusted resource identifier')
            command([*remove, identifier])
        if command(query):
            raise RuntimeError('Host resource cleanup incomplete')
    for service in ['iam', 'cp', 'human', 'pulse', 'nabhold']:
        image = 'l4-' + service + '-' + project
        if command(['docker', 'image', 'ls', '-q', '--filter', 'reference=' + image]):
            command(['docker', 'image', 'rm', image])
    if directory.exists():
        shutil.rmtree(directory)
    SESSION.unlink()
    print('INT-03 host fallback cleanup completed; no qualification granted')


if __name__ == '__main__':
    try:
        cleanup()
    except Exception:
        print('INT-03 host cleanup failed; recovery state retained')
        raise SystemExit(2)
