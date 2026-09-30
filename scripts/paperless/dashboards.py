#!/usr/bin/env python3
"""Add Paperless to existing Homepage and Dashy without replacing other entries."""
import copy
import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import yaml
os.umask(0o077)
url = sys.argv[1]
changed = []
for kind, filename, container in [('homepage', '/opt/homepage/config/services.yaml', 'homepage'),
                                   ('dashy', '/opt/dashy/user-data/conf.yml', 'Dashy')]:
    path = Path(filename)
    raw = path.read_text()
    original = yaml.safe_load(raw)
    data = copy.deepcopy(original)
    if kind == 'homepage':
        sections = [x['Documents'] for x in data if 'Documents' in x]
        if not sections:
            data.append({'Documents': []})
            sections = [data[-1]['Documents']]
        matches = [entry['Paperless'] for group in data for values in group.values() if isinstance(values, list)
                   for entry in values if 'Paperless' in entry]
        assert len(matches) <= 1
        desired = {'icon': 'paperless-ngx', 'href': url, 'siteMonitor': url+'/accounts/login/',
                   'description': 'Private document collections — individual logins'}
        if matches: matches[0].update(desired)
        else: sections[0].append({'Paperless': desired})
    else:
        sections = [s for s in data['sections'] if s['name'] == 'Documents']
        if not sections:
            data['sections'].append({'name': 'Documents', 'icon': 'fas fa-file-alt', 'items': []})
            sections = [data['sections'][-1]]
        matches = [item for section in data['sections'] for item in section.get('items', [])
                   if item.get('title', '').lower() == 'paperless']
        assert len(matches) <= 1
        desired = {'title': 'Paperless', 'url': url, 'icon': 'hl-paperless-ngx',
                   'description': 'Private document collections — individual logins'}
        if matches: matches[0].update(desired)
        else: sections[0]['items'].append(desired)
    if data != original:
        backup = Path('/root/usniverse-paperless-dashboard-backups')
        backup.mkdir(mode=0o700, exist_ok=True)
        (backup/(kind+'-'+datetime.datetime.now().strftime('%Y%m%d%H%M%S')+'.yaml')).write_text(raw)
        encoded = yaml.safe_dump(data, sort_keys=False, allow_unicode=True).encode()
        if kind == 'dashy':
            subprocess.run(['docker', 'exec', '-i', '--user', '0', container, 'node', '-e',
                            "require('fs').writeFileSync('/app/user-data/conf.yml',require('fs').readFileSync(0))"], input=encoded, check=True)
        else: path.write_bytes(encoded)
        assert yaml.safe_load(path.read_text()) == data
        subprocess.run(['docker', 'restart', container], check=True, stdout=subprocess.DEVNULL)
        changed.append(kind)
print(json.dumps({'changed': changed}))
