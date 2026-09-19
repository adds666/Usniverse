#!/usr/bin/env python3
"""Reconcile migrated settings in place. Secrets stay on the application host.

Requires restored application databases; this deliberately does not bootstrap empty
libraries. --check validates connections and reports drift without writing settings.
"""
import argparse
import copy
import datetime
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

APP = {'sonarr': (8989, 3), 'radarr': (7878, 3), 'lidarr': (8686, 1), 'prowlarr': (9696, 1)}


class API:
    def __init__(self, base, key):
        self.base, self.key = base, key

    def __call__(self, path, data=None, method=None):
        request = urllib.request.Request(
            self.base + path, data=None if data is None else json.dumps(data).encode(),
            method=method or ('GET' if data is None else 'POST'),
            headers={'X-Api-Key': self.key, 'ApiKey': self.key, 'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                body = response.read()
                return json.loads(body) if body else None
        except urllib.error.HTTPError as error:
            raise RuntimeError(f'API {path.split("?")[0]} returned HTTP {error.code}') from None
        except urllib.error.URLError:
            raise RuntimeError('Application endpoint is unreachable') from None


def backup_databases(app):
    root = Path('/opt') / app
    dest = root / ('pre-ansible-connections-' + datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
    dest.mkdir(mode=0o700)
    for path in (root / 'config').glob('*.db'):
        with sqlite3.connect(f'file:{path}?mode=ro', uri=True) as source:
            with sqlite3.connect(dest / path.name) as target:
                source.backup(target)
    return dest


def fields(record):
    return {field['name']: field for field in record['fields']}


def db_settings(app, table):
    if table not in ('DownloadClients', 'Applications', 'Indexers'):
        raise ValueError('Unexpected settings table')
    with sqlite3.connect(f'file:/opt/{app}/config/{app}.db?mode=ro', uri=True) as db:
        return {row[0]: json.loads(row[1]) for row in db.execute(f'SELECT Id, Settings FROM {table}')}


def restore_secrets(record, settings):
    # Arr APIs mask credentials; never save the masked representation back.
    for field in record['fields']:
        name = field['name']
        if name.lower() in ('apikey', 'username', 'password') and name in settings:
            field['value'] = settings[name]


def reconcile_arr(app, desired, check):
    port, version = APP[app]
    key = ET.parse(f'/opt/{app}/config/config.xml').findtext('ApiKey')
    api = API(f'http://127.0.0.1:{port}/api/v{version}/', key)
    assert api('system/status')['appName'].lower() == app
    changes = []
    if app != 'prowlarr':
        roots = api('rootfolder')
        for path in desired['roots'][app]:
            assert any(r['path'] == path and r.get('accessible') for r in roots), 'Required migrated root unavailable'
    clients = [c for c in api('downloadclient') if c['implementation'].lower() == 'qbittorrent']
    assert len(clients) == 1, 'Expected one restored qBittorrent client'
    secrets = db_settings(app, 'DownloadClients')
    client = clients[0]
    before = copy.deepcopy(client)
    values = fields(client)
    values['host']['value'] = desired['qbittorrent']['host']
    values['port']['value'] = desired['qbittorrent']['port']
    changed = client != before
    restore_secrets(client, secrets[client['id']])
    api('downloadclient/test', client)
    if changed:
        changes.append(('downloadclient', client, False))
    if app == 'prowlarr':
        apps = api('applications')
        secrets = db_settings(app, 'Applications')
        for name, endpoint in desired['applications'].items():
            matches = [a for a in apps if a['implementation'].lower() == name]
            assert len(matches) == 1, 'Expected one restored Prowlarr application'
            record = matches[0]
            before = copy.deepcopy(record)
            values = fields(record)
            values['baseUrl']['value'] = endpoint
            values['prowlarrUrl']['value'] = desired['prowlarr_url']
            record['syncLevel'] = 'addOnly'
            changed = record != before
            restore_secrets(record, secrets[record['id']])
            api('applications/test', record)
            if changed:
                changes.append(('applications', record, False))
        proxies = [p for p in api('indexerProxy') if p['implementation'] == 'FlareSolverr']
        assert len(proxies) == 1, 'Expected restored FlareSolverr proxy'
        proxy = proxies[0]
        if fields(proxy)['host']['value'].rstrip('/') != desired['flaresolverr_url'].rstrip('/'):
            fields(proxy)['host']['value'] = desired['flaresolverr_url']
            changes.append(('indexerProxy', proxy, False))
    else:
        secrets = db_settings(app, 'Indexers')
        for record in api('indexer'):
            if '(Prowlarr)' not in record['name']:
                continue
            values = fields(record)
            if 'baseUrl' not in values:
                continue
            old = urllib.parse.urlsplit(values['baseUrl']['value'])
            base = urllib.parse.urlsplit(desired['prowlarr_url'])
            new = urllib.parse.urlunsplit((base.scheme, base.netloc, old.path, old.query, old.fragment))
            if new != values['baseUrl']['value']:
                values['baseUrl']['value'] = new
                restore_secrets(record, secrets[record['id']])
                changes.append(('indexer', record, True))
    if changes and not check:
        backup_databases(app)
        for resource, record, force in changes:
            path = resource + '/' + str(record['id'])
            api(path + ('?forceSave=true' if force else ''), record, 'PUT')
            saved = api(path)
            # Compare only managed non-secret fields; the API masks credentials.
            keys = {'downloadclient': ['host', 'port'], 'applications': ['baseUrl', 'prowlarrUrl'],
                    'indexer': ['baseUrl'], 'indexerProxy': ['host']}[resource]
            assert all(fields(saved)[k]['value'] == fields(record)[k]['value'] for k in keys)
    return len(changes)


def reconcile_ombi(desired, check):
    with sqlite3.connect('file:/opt/ombi/config/OmbiSettings.db?mode=ro', uri=True) as db:
        key = json.loads(db.execute("SELECT Content FROM GlobalSettings WHERE SettingsName='OmbiSettings'").fetchone()[0])['ApiKey']
    api = API('http://127.0.0.1:3579/api/v1/', key)
    sonarr, radarr = api('Settings/sonarr'), api('Settings/radarr')
    old_s, old_r = copy.deepcopy(sonarr), copy.deepcopy(radarr)
    for name, config in [('sonarr', sonarr), ('radarr', radarr['radarr'])]:
        config['ip'] = desired['ombi_host']
        config['port'] = APP[name][0]
        config['ssl'] = False
        if config.get('subDir'):
            config['subDir'] = ''
        assert api('Tester/' + name, config)['isValid'], 'Ombi connection test failed'
        roots = api(name.capitalize() + '/RootFolders', config)
        target = desired['ombi_roots'][name]
        matches = [r for r in roots if r['path'] == target]
        assert len(matches) == 1, 'Ombi root folder missing'
        if name == 'sonarr':
            config['rootPath'] = str(matches[0]['id'])
        else:
            config['defaultRootPath'] = target
        profiles = api(name.capitalize() + '/Profiles', config)
        profile = config['qualityProfile' if name == 'sonarr' else 'defaultQualityProfile']
        assert any(str(p['id']) == str(profile) for p in profiles), 'Existing quality profile no longer exists'
    changes = [('sonarr', sonarr, old_s), ('radarr', radarr, old_r)]
    changes = [(name, new, old) for name, new, old in changes if new != old]
    if changes and not check:
        backup_databases('ombi')
        for name, new, old in changes:
            assert api('Settings/' + name, new) is True, 'Ombi settings save failed'
            saved = api('Settings/' + name)
            assert saved == new, 'Ombi settings readback differs'
    return len(changes)


def reconcile_qbit(desired, check):
    base = 'http://127.0.0.1:8080/api/v2/'
    def get():
        return json.loads(subprocess.check_output(['docker', 'exec', 'gluetun', 'wget', '-qO-', base + 'app/preferences']))
    prefs = get()
    assert prefs['bypass_auth_subnet_whitelist_enabled'], 'Expected migrated host trust configuration'
    trusted = prefs['bypass_auth_subnet_whitelist'].splitlines()
    trusted = [h for h in trusted if h not in desired['qbittorrent']['retired_trust']]
    for host in desired['qbittorrent']['trusted_hosts']:
        if host not in trusted:
            trusted.append(host)
    wanted = {'bypass_auth_subnet_whitelist': '\n'.join(trusted),
              'save_path': '/downloads/radarr/', 'temp_path': '/incomplete/', 'temp_path_enabled': True}
    changed = {k: v for k, v in wanted.items() if (prefs[k].rstrip('/') if k in ('save_path', 'temp_path') else prefs[k]) != (v.rstrip('/') if k in ('save_path', 'temp_path') else v)}
    if changed and not check:
        dest = Path('/opt/qbittorrent') / ('preferences.pre-ansible-' + datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '.json')
        dest.write_text(json.dumps(prefs))
        payload = urllib.parse.urlencode({'json': json.dumps(changed)})
        subprocess.run(['docker', 'exec', 'gluetun', 'wget', '-qO-', '--header=Content-Type: application/x-www-form-urlencoded', '--post-data=' + payload, base + 'app/setPreferences'], check=True, stdout=subprocess.DEVNULL)
        saved = get()
        assert all(saved[k] == v for k, v in changed.items()), 'qBittorrent readback differs'
    return len(changed)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('app', choices=list(APP) + ['ombi', 'qbittorrent'])
    parser.add_argument('config')
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    os.umask(0o077)
    desired = json.loads(Path(args.config).read_text())
    if args.app in APP:
        count = reconcile_arr(args.app, desired, args.check)
    elif args.app == 'ombi':
        count = reconcile_ombi(desired, args.check)
    else:
        count = reconcile_qbit(desired, args.check)
    print(json.dumps({'app': args.app, 'changed': bool(count), 'changes': count, 'check': args.check}))


if __name__ == '__main__':
    main()
