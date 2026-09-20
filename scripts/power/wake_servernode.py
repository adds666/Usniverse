#!/usr/bin/env python3
"""Use CT110's existing authenticated proxy to send WOL through Earls-edge."""
import pathlib
import urllib.parse
import urllib.request

values = {}
for line in pathlib.Path('/etc/wol-webhook/env').read_text().splitlines():
    if '=' in line and not line.lstrip().startswith('#'):
        key, value = line.split('=', 1)
        values[key.strip()] = value.strip().strip('"').strip("'")

query = urllib.parse.urlencode({'token': values['WOL_TOKEN']})
url = 'http://127.0.0.1:' + values.get('WOL_PORT', '8787') + '/wol?' + query
try:
    with urllib.request.urlopen(url, timeout=20) as response:
        # Do not print response bodies or exception URLs, which could contain tokens.
        if response.status != 200:
            raise RuntimeError('Unexpected relay status')
        print('Earls-edge wake relay accepted request')
except Exception as error:
    raise SystemExit('Wake relay failed: ' + type(error).__name__) from None
