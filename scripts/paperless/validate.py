#!/usr/bin/env python3
"""Exercise real HTTPS upload, NAS persistence and cross-user isolation with synthetic data."""
import hashlib
import http.cookiejar
import json
import os
import re
from pathlib import Path
import secrets
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
os.umask(0o077)
BASE = 'https://edge-proxy.taildb07f.ts.net:8443'
HOST = 'root@100.69.158.73'
PREFIX = 'usniverse_validation_'+uuid.uuid4().hex[:12]
USERS = [PREFIX+'_a', PREFIX+'_b']
PASSWORDS = [secrets.token_urlsafe(24), secrets.token_urlsafe(24)]

def shell(code):
    command = ['ssh', HOST, 'pct exec 113 -- docker compose -f /opt/paperless/compose.yml exec -T webserver python manage.py shell -c "import sys; exec(sys.stdin.read())"']
    return subprocess.check_output(command, input=code.encode()).decode()

def api(path, token=None, method='GET', body=None, ctype='application/json'):
    headers = {'Content-Type': ctype}
    if token: headers['Authorization'] = 'Token '+token
    if body is not None and not isinstance(body, bytes): body = json.dumps(body).encode()
    request = urllib.request.Request(BASE+path, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=90) as r: return r.status, r.read()
    except urllib.error.HTTPError as e: return e.code, e.read()

def pdf(text):
    stream = ('BT /F1 12 Tf 60 740 Td ('+text+') Tj ET').encode()
    objects = [b'<< /Type /Catalog /Pages 2 0 R >>', b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
               b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>',
               b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>', b'<< /Length '+str(len(stream)).encode()+b' >>\nstream\n'+stream+b'\nendstream']
    data = b'%PDF-1.4\n'; offsets = []
    for n, obj in enumerate(objects, 1):
        offsets.append(len(data)); data += str(n).encode()+b' 0 obj\n'+obj+b'\nendobj\n'
    start = len(data)
    data += b'xref\n0 6\n0000000000 65535 f \n'+b''.join(f'{o:010d} 00000 n \n'.encode() for o in offsets)
    return data+b'trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n'+str(start).encode()+b'\n%%EOF\n'

report = {}
try:
    shell('from django.contrib.auth import get_user_model\nfrom django.contrib.auth.models import Group\n'+
          'group=Group.objects.get(name="Usniverse Members")\n'+
          '\n'.join('u=get_user_model().objects.create_user(username='+repr(u)+',password='+repr(p)+');u.groups.add(group)' for u,p in zip(USERS,PASSWORDS)))
    tokens = []
    for u,p in zip(USERS,PASSWORDS):
        status, body = api('/api/token/', method='POST', body={'username':u,'password':p})
        assert status == 200, ('Login failed', status)
        tokens.append(json.loads(body)['token'])
    assert api('/api/documents/')[0] in [401,403]
    cookies = http.cookiejar.CookieJar()
    browser = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookies))
    page = browser.open(BASE+'/accounts/login/', timeout=30).read().decode()
    csrf = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', page)
    assert csrf, 'Browser login form has no CSRF field'
    form = urllib.parse.urlencode({'csrfmiddlewaretoken': csrf.group(1), 'login': USERS[0],
                                  'password': PASSWORDS[0], 'next': '/'}).encode()
    browser.open(urllib.request.Request(BASE+'/accounts/login/', data=form,
                 headers={'Referer': BASE+'/accounts/login/', 'Origin': BASE}), timeout=30).read()
    with browser.open(BASE+'/api/documents/', timeout=30) as r:
        assert r.status == 200 and isinstance(json.load(r), dict), 'Browser session login failed'
    for token in tokens:
        status, body = api('/api/ui_settings/', token)
        assert status == 200, ('UI permissions', status)
    content = pdf('Usniverse private document verification '+PREFIX)
    boundary = uuid.uuid4().hex
    body = (f'--{boundary}\r\nContent-Disposition: form-data; name="title"\r\n\r\n{PREFIX}\r\n'
            f'--{boundary}\r\nContent-Disposition: form-data; name="document"; filename="{PREFIX}.pdf"\r\nContent-Type: application/pdf\r\n\r\n').encode()+content+f'\r\n--{boundary}--\r\n'.encode()
    status, response = api('/api/documents/post_document/', tokens[0], 'POST', body, 'multipart/form-data; boundary='+boundary)
    assert status in [200,202], ('Upload failed',status)
    task_response = json.loads(response)
    task_id = task_response if isinstance(task_response, str) else task_response['task_id']
    doc = None
    for _ in range(90):
        status, body = api('/api/documents/?title__icontains='+PREFIX, tokens[0])
        assert status == 200
        rows = json.loads(body)['results']
        if rows: doc = rows[0]; break
        time.sleep(3)
    assert doc, 'Synthetic document was not processed in time'
    assert doc.get('owner') is not None, 'Upload must have an owner'
    for token, visible in [(tokens[0], True), (tokens[1], False)]:
        status, task_body = api('/api/tasks/?task_id='+task_id, token)
        assert status == 200, ('Task status permission', status)
        tasks = json.loads(task_body)
        if isinstance(tasks, dict): tasks = tasks.get('results', [])
        assert bool(tasks) == visible, 'Upload task privacy mismatch'
    status, body = api(f'/api/documents/{doc["id"]}/download/?original=true', tokens[0])
    assert status == 200 and hashlib.sha256(body).digest() == hashlib.sha256(content).digest(), 'Original download checksum mismatch'
    status, body = api('/api/documents/?title__icontains='+PREFIX, tokens[1])
    assert status == 200 and json.loads(body)['count'] == 0, 'Other user can discover private document'
    for suffix in ['', 'download/', 'thumb/']:
        assert api(f'/api/documents/{doc["id"]}/'+suffix, tokens[1])[0] in [403,404], 'Cross-user document access allowed'
    assert api('/api/users/', tokens[1])[0] in [403,404], 'Member can list accounts'
    # Read the exact synthetic document path privately and verify the file resides on NAS.
    out = shell('from documents.models import Document\nimport json,os\nd=Document.objects.get(pk='+str(doc['id'])+')\nprint(json.dumps({"nas":str(d.source_path).startswith("/usr/src/paperless/media/"),"exists":os.path.isfile(d.source_path)}))')
    assert '"nas": true' in out and '"exists": true' in out
    report = {'httpsLogin': True, 'browserSessionLogin': True, 'memberUi': True, 'anonymousDenied': True, 'uploadProcessed': True,
              'originalChecksumMatched': True, 'nasMediaVerified': True, 'otherUserCannotListReadDownload': True,
              'memberCannotListAccounts': True, 'uploadTaskPrivacy': True}
finally:
    # Only synthetic documents and uniquely named users created by this run are eligible.
    shell('from documents.models import Document\nfrom django.contrib.auth import get_user_model\n'+
          'users=get_user_model().objects.filter(username__in='+repr(USERS)+')\n'+
          'Document.objects.filter(title='+repr(PREFIX)+',owner__in=users).delete()\nusers.delete()\n')
    report['testUsersAndDocumentsRemoved'] = True
    Path('/tmp/usniverse-paperless/validation.json').write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(report))
