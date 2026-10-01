#!/usr/bin/env python3
"""Cold application snapshot + PostgreSQL dump; private recovery copy on the NAS."""
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
os.umask(0o077)
lock = open('/run/lock/usniverse-paperless-backup.lock', 'w')
fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
root = Path('/mnt/pve/Global_Share/Paperless')
subprocess.run(['findmnt', '-n', '-t', 'nfs,nfs4', '--target', str(root)], check=True, stdout=subprocess.DEVNULL)
assert (root/'media/.usniverse-paperless-nas').is_file()
stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
backup = root/'backups'/stamp
backup.mkdir(parents=True, mode=0o700)
compose = ['pct', 'exec', '113', '--', 'docker', 'compose', '-f', '/opt/paperless/compose.yml']
try:
    subprocess.run(compose+['stop', '--timeout', '180', 'webserver', 'broker'], check=True, stdout=subprocess.DEVNULL)
    with (backup/'database.dump').open('wb') as output:
        subprocess.run(compose+['exec', '-T', 'db', 'pg_dump', '-U', 'paperless', '-d', 'paperless', '-Fc'], stdout=output, check=True)
    with (backup/'application.tgz').open('wb') as output:
        subprocess.run(['pct', 'exec', '113', '--', 'tar', '-C', '/opt/paperless', '-czf', '-', '.env', 'initial-credentials.json', 'compose.yml', 'data', 'redis', 'consume', 'manage_users.py'], stdout=output, check=True)
    subprocess.run(['tar', '-C', str(root), '-czf', str(backup/'media.tgz'), 'media'], check=True)
    for name in ['application.tgz', 'media.tgz']:
        subprocess.run(['gzip', '-t', str(backup/name)], check=True)
    hashes = {}
    for name in ['database.dump', 'application.tgz', 'media.tgz']:
        h = hashlib.sha256()
        with (backup/name).open('rb') as source:
            for block in iter(lambda: source.read(1024*1024), b''): h.update(block)
        hashes[name] = h.hexdigest()
    (backup/'verified.json').write_text(json.dumps({'created': stamp, 'sha256': hashes}, indent=2)+'\n')
finally:
    subprocess.run(compose+['up', '-d', '--wait', '--wait-timeout', '600'], check=True, stdout=subprocess.DEVNULL)
print('Paperless recovery snapshot completed: '+stamp)
