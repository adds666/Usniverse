#!/usr/bin/env python3
"""Move one reviewed CT between standalone hosts; retain the disabled source.

Run only once per CT. Restore/start failure leaves the source stopped to avoid
split-brain. Stop the target before explicitly rolling back to the source.
No bind-mounted NAS data is copied or deleted.
"""
import argparse
import json
from pathlib import Path
import shlex
import subprocess
import time

SOURCE = 'root@100.69.158.73'
TARGET = 'root@100.107.3.115'
BASE = '/mnt/pve/Global_Share/usniverse-rebalance-20260930'

def remote(host, *args):
    return subprocess.check_output(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=15', host,
                                    shlex.join(args)], text=True)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('ct', choices=['114', '116', '119'])
    parser.add_argument('--resume-backup', action='store_true', help='Reuse the single completed archive of an already stopped source')
    args = parser.parse_args()
    ct = args.ct
    if remote(SOURCE, 'hostname').strip() != 'macbookpro' or remote(TARGET, 'hostname').strip() != 'toshiba':
        raise RuntimeError('Unexpected source or target host identity')
    remote(TARGET, 'test', '!', '-e', f'/etc/pve/lxc/{ct}.conf')
    remote(TARGET, 'test', '!', '-e', '/etc/pve/corosync.conf')
    # Standalone Toshiba retained stale records from its former cluster.
    # Preserve only the reviewed source-node record before freeing this VMID.
    ghost = f'/etc/pve/nodes/macbookpro/lxc/{ct}.conf'
    saved = f'/root/usniverse-rebalance-20260930/stale-node-configs/{ct}.conf'
    remote(TARGET, 'sh', '-c', f'set -e; if test -f {ghost}; then '
           f'install -d -m 700 /root/usniverse-rebalance-20260930/stale-node-configs; '
           f'test ! -e {saved}; cp {ghost} {saved}; cmp {ghost} {saved}; rm {ghost}; fi')

    for host in [SOURCE, TARGET]:
        fs = remote(host, 'findmnt', '-n', '-o', 'FSTYPE', '--target', BASE.rsplit('/', 1)[0]).strip()
        if fs not in ['nfs', 'nfs4']:
            raise RuntimeError('Shared NAS mount missing')
    before = json.loads(remote(SOURCE, 'pct', 'exec', ct, '--', 'sh', '-c', 'docker inspect $(docker ps -q)')) if not args.resume_backup else []
    expected = {x['Name']: x['Image'] for x in before}
    if args.resume_backup:
        manifest = json.loads((Path(__file__).resolve().parents[2] / 'files/docker/versions-20260929.json').read_text())
        expected = {'/' + app['container']: app['image_id'] for apps in manifest['nodes'].values()
                    for app in apps if app['ct'] == int(ct)}
    if not expected and not args.resume_backup:
        raise RuntimeError('No running source Docker containers')
    directory = f'/var/lib/vz/usniverse-rebalance-20260930/ct{ct}'
    remote(SOURCE, 'mkdir', '-m', '0700', '-p', directory)
    if args.resume_backup:
        if remote(SOURCE, 'pct', 'status', ct).strip() != 'status: stopped':
            raise RuntimeError('Resume requires a stopped source')
        if 'onboot: 0' not in remote(SOURCE, 'pct', 'config', ct).splitlines():
            raise RuntimeError('Resume requires source automatic boot disabled')
    else:
        print(f'CT{ct}: disabling source boot, stopping cleanly, backing up', flush=True)
        remote(SOURCE, 'pct', 'set', ct, '--onboot', '0')
        remote(SOURCE, 'pct', 'shutdown', ct, '--timeout', '120')
        if remote(SOURCE, 'pct', 'status', ct).strip() != 'status: stopped':
            raise RuntimeError('Source did not stop')
        print(remote(SOURCE, 'vzdump', ct, '--mode', 'stop', '--compress', 'zstd', '--dumpdir', directory, '--tmpdir', '/var/tmp'), flush=True)
    archives = remote(SOURCE, 'find', directory, '-maxdepth', '1', '-name', '*.tar.zst', '-type', 'f').splitlines()
    if len(archives) != 1:
        raise RuntimeError('Expected exactly one fresh archive')
    archive = archives[0]
    # Read through the source host; keep restore I/O on target-local storage.
    # The durable NAS archive remains available independently of this staging copy.
    staging = '/var/lib/vz/usniverse-rebalance-20260930'
    remote(TARGET, 'mkdir', '-m', '0700', '-p', staging)
    local_archive = f'{staging}/ct{ct}.tar.zst'
    print(f'CT{ct}: transferring archive into target-local staging', flush=True)
    reader = subprocess.Popen(['ssh', '-o', 'BatchMode=yes', SOURCE, shlex.join(['cat', archive])], stdout=subprocess.PIPE)
    try:
        writer = subprocess.run(['ssh', '-o', 'BatchMode=yes', TARGET,
                                 'umask 077; cat > ' + shlex.quote(local_archive)], stdin=reader.stdout)
        reader.stdout.close()
        if reader.wait() or writer.returncode:
            raise RuntimeError('Archive transfer failed')
    finally:
        if reader.poll() is None:
            reader.terminate()
    digest = remote(SOURCE, 'sha256sum', archive).split()[0]
    if remote(TARGET, 'sha256sum', local_archive).split()[0] != digest:
        raise RuntimeError('Archive checksum mismatch')
    remote(TARGET, 'zstd', '-t', local_archive)
    print(f'CT{ct}: archive verified {digest}; restoring local-lvm', flush=True)
    remote(TARGET, 'pct', 'restore', ct, local_archive, '--storage', 'local-lvm', '--onboot', '0')
    if ct == '116':
        guard_dir = '/etc/systemd/system/pve-container@116.service.d'
        guard = ('[Unit]\nWants=network-online.target\nAfter=network-online.target\n'
                 'RequiresMountsFor=/mnt/pve/Global_Share\n\n[Service]\n'
                 'ExecStartPre=/usr/bin/findmnt -n -t nfs,nfs4 --target /mnt/pve/Global_Share\n')
        remote(TARGET, 'install', '-d', '-m', '755', guard_dir)
        remote(TARGET, 'sh', '-c', 'printf %s ' + shlex.quote(guard) +
               ' > ' + shlex.quote(guard_dir + '/usniverse-nas.conf'))
        remote(TARGET, 'chmod', '644', guard_dir + '/usniverse-nas.conf')
        remote(TARGET, 'systemctl', 'daemon-reload')
    remote(TARGET, 'pct', 'start', ct)
    deadline = time.time() + 300
    while time.time() < deadline:
        try:
            after = json.loads(remote(TARGET, 'pct', 'exec', ct, '--', 'sh', '-c', 'docker inspect $(docker ps -aq)'))
            matching = {x['Name']: x for x in after}
            if not expected:
                raise RuntimeError('Restored container has no Docker applications')
            if all(name in matching and matching[name]['Image'] == image and
                   matching[name]['State']['Running'] and not matching[name]['State']['OOMKilled'] and
                   matching[name]['State'].get('Health', {}).get('Status', 'healthy') == 'healthy'
                   for name, image in expected.items()):
                break
        except subprocess.CalledProcessError:
            pass
        time.sleep(5)
    else:
        raise RuntimeError('Target Docker health validation timed out; source remains stopped')
    remote(TARGET, 'pct', 'set', ct, '--onboot', '1')
    remote(SOURCE, 'pct', 'set', ct, '--description',
           'Retired source retained after migration to Toshiba on 2026-09-30. DO NOT START while the Toshiba copy is running.')
    print(f'CT{ct}: target healthy; retaining an additional NAS archive', flush=True)
    durable = f'{BASE}/ct{ct}'
    remote(SOURCE, 'mkdir', '-m', '0700', '-p', durable)
    remote(SOURCE, 'cp', '--no-clobber', archive, durable + '/')
    print(json.dumps({'ct': int(ct), 'source': 'pve', 'target': 'toshiba', 'containers': list(expected),
                      'archive': archive, 'sha256': digest, 'health': 'passed',
                      'source_retained_stopped': True}), flush=True)

if __name__ == '__main__':
    main()
