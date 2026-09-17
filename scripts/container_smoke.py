"""Integration test against disposable containers and explicitly isolated volumes."""
import json
import os
import secrets
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path


def command(*args):
    return subprocess.check_output(args, text=True).strip()


def main():
    image = sys.argv[1] if len(sys.argv) > 1 else 'personal-cloud-sync:dev'
    bootstrap = '--bootstrap' in sys.argv[2:]
    token = secrets.token_hex(32)
    name = 'pcs-smoke-' + secrets.token_hex(5)
    # Leave the isolated test files for inspection; remove only the named test container.
    root = Path(tempfile.mkdtemp(prefix='pcs-smoke-')).resolve()
    state, sources = root / 'state', root / 'sources'
    state.mkdir(mode=0o777)
    state.chmod(0o755 if bootstrap else 0o777)
    sources.mkdir(mode=0o755)
    original = sources / 'original.txt'
    original.write_bytes(b'preserve this source')
    (sources / 'duplicate.txt').write_bytes(original.read_bytes())
    (sources / 'different.txt').write_bytes(b'a second distinct file')
    url = ''

    def start():
        nonlocal url
        bootstrap_flags = ['--user', '0:0', '--cap-drop', 'ALL',
                           '--cap-add', 'CHOWN', '--cap-add', 'DAC_OVERRIDE',
                           '--cap-add', 'FOWNER', '--cap-add', 'SETGID',
                           '--cap-add', 'SETUID', '--security-opt', 'no-new-privileges:true'] if bootstrap else []
        command('docker', 'run', '-d', '--name', name, '--read-only', '--tmpfs', '/tmp', *bootstrap_flags,
                '-p', '127.0.0.1::8080', '-e', f'PCS_TOKEN={token}',
                '-v', f'{state}:/DATA/CloudSync', '-v', f'{sources}:/sources:ro', image)
        port = command('docker', 'port', name, '8080/tcp').split(':')[-1]
        url = f'http://127.0.0.1:{port}'
        ready()
        if bootstrap:
            status = command('docker', 'exec', name, 'cat', '/proc/1/status')
            assert 'Uid:\t1000\t1000\t1000\t1000' in status, 'API must not run as root'

    def call(path, body=None):
        data = None if body is None else json.dumps(body).encode()
        request = urllib.request.Request(url + path, data=data, headers={
            'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'})
        with urllib.request.urlopen(request, timeout=5) as response:
            return json.load(response)

    def ready():
        nonlocal url
        port = command('docker', 'port', name, '8080/tcp').split(':')[-1]
        url = f'http://127.0.0.1:{port}'
        for _ in range(90):
            try:
                if call('/health')['status'] == 'ok':
                    return
            except (OSError, ValueError):
                time.sleep(1)
        print(command('docker', 'logs', '--tail', '40', name))
        raise AssertionError('Container did not become healthy')

    def sync(aid):
        jid = call(f'/api/accounts/{aid}/sync', {})['job_id']
        for _ in range(90):
            job = next(j for j in call('/api/jobs') if j['id'] == jid)
            if job['status'] not in ('started', 'running'):
                assert job['status'] == 'completed', job
                return job
            time.sleep(1)
        raise AssertionError('Sync timed out')

    try:
        start()
        try:
            urllib.request.urlopen(url + '/api/dashboard')
            raise AssertionError('API accepted an unauthenticated request')
        except urllib.error.HTTPError as exc:
            assert exc.code == 401
        aid = call('/api/accounts', {'name': 'Smoke', 'provider': 'filesystem', 'location': '.', 'interval_minutes': 0})['id']
        assert sync(aid)['duplicates'] == 1
        assert call('/api/dashboard')['files'] == 2
        command('docker', 'restart', name)
        ready()
        assert sync(aid)['existing'] == 3
        command('docker', 'rm', '-f', name)
        start()  # New container, same external volume; migration runs again.
        assert sync(aid)['existing'] == 3
        assert call('/api/dashboard')['files'] == 2
        assert original.read_bytes() == b'preserve this source'
        assert len(list(sources.iterdir())) == 3
        assert len([p for p in (state / 'data').rglob('*') if p.is_file()]) == 2
        print(f'PASS: auth, deduplication, source preservation, restart, recreation, migration. State: {root}')
    finally:
        subprocess.run(['docker', 'rm', '-f', name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


if __name__ == '__main__':
    main()
