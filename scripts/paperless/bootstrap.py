#!/usr/bin/env python3
"""Create private credentials once, on the application CT only."""
import json
import os
from pathlib import Path
import secrets
os.umask(0o077)
root = Path('/opt/paperless')
p = root / 'initial-credentials.json'
env = root / '.env'
if env.exists() and not p.exists():
    raise SystemExit('Existing environment has no credential record; refusing to invent replacement credentials')
if not p.exists():
    p.write_text(json.dumps({'admin_username': 'usniverse-admin', 'admin_password': secrets.token_urlsafe(30),
                            'member_username': 'adam', 'member_password': secrets.token_urlsafe(30)}, indent=2)+'\n')
c = json.loads(p.read_text())
env = root / '.env'
if not env.exists():
    env.write_text('\n'.join(['PAPERLESS_SECRET_KEY='+secrets.token_urlsafe(64),
                              'PAPERLESS_DBPASS='+secrets.token_urlsafe(40),
                              'PAPERLESS_ADMIN_USER='+c['admin_username'],
                              'PAPERLESS_ADMIN_PASSWORD='+c['admin_password']])+'\n')
    print('Created private application environment')
