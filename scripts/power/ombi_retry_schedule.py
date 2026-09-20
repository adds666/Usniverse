#!/usr/bin/env python3
"""Reconcile only Ombi's failed-request retry schedule via its supported API."""
import json
import os
import pathlib
import sqlite3
import urllib.request

os.umask(0o077)
with sqlite3.connect('file:/opt/ombi/config/OmbiSettings.db?mode=ro', uri=True) as database:
    content = database.execute(
        "select Content from GlobalSettings where SettingsName='OmbiSettings'"
    ).fetchone()[0]
key = json.loads(content)['ApiKey']


def jobs_api(data=None):
    request = urllib.request.Request(
        'http://127.0.0.1:3579/api/v1/Settings/jobs',
        data=json.dumps(data).encode() if data is not None else None,
        headers={'ApiKey': key, 'Content-Type': 'application/json'},
    )
    with urllib.request.urlopen(request, timeout=40) as response:
        return json.load(response)


jobs = jobs_api()
field = next(name for name in jobs if name.lower() == 'retryrequests')
previous = jobs[field]
backup = pathlib.Path('/opt/ombi/config/pre-overnight-jobs-20260920.json')
if not backup.exists():
    backup.write_text(json.dumps(jobs))
jobs[field] = '0 15 0-6 * * ?'
changed = previous != jobs[field]
if changed:
    result = jobs_api(jobs)
    if result.get('result') is not True:
        raise SystemExit('Ombi rejected the retry schedule')
if jobs_api()[field] != jobs[field]:
    raise SystemExit('Ombi retry schedule did not persist')
print(json.dumps({'changed': changed, 'previous': previous, 'retryRequests': jobs[field]}))
