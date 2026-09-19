"""Regression coverage for preserving user state during connection repairs."""
import copy
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts/media' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

reconcile = load('reconcile')
dashy = load('dashy')


class ConnectionTests(unittest.TestCase):
    def exercise(self, host, check=False):
        client = {'id': 4, 'implementation': 'QBittorrent', 'name': 'UbuntuVM',
                  'fields': [{'name': 'host', 'value': host}, {'name': 'port', 'value': 8080},
                             {'name': 'password', 'value': '********'}, {'name': 'tvCategory', 'value': 'existing-category'}]}
        calls = []
        def api(path, data=None, method=None):
            calls.append((path, copy.deepcopy(data), method))
            if path == 'system/status': return {'appName': 'Sonarr'}
            if path == 'rootfolder': return [{'path': '/existing/tv', 'accessible': True}]
            if path == 'downloadclient': return [copy.deepcopy(client)]
            if path == 'downloadclient/test': return None
            if path == 'indexer': return []
            if path == 'downloadclient/4':
                if method == 'PUT': client.update(copy.deepcopy(data))
                return copy.deepcopy(client)
            self.fail('Unexpected API call: ' + path)
        desired = {'roots': {'sonarr': ['/existing/tv']}, 'qbittorrent': {'host': '192.168.1.129', 'port': 8080}}
        with patch.object(reconcile.ET, 'parse') as xml, patch.object(reconcile, 'API', return_value=api), \
             patch.object(reconcile, 'db_settings', return_value={4: {'password': 'fixture-secret'}}), \
             patch.object(reconcile, 'backup_databases') as backup:
            xml.return_value.findtext.return_value = 'fixture-key'
            changes = reconcile.reconcile_arr('sonarr', desired, check)
        return changes, calls, backup

    def test_no_drift_never_saves_or_backs_up(self):
        count, calls, backup = self.exercise('192.168.1.129')
        self.assertEqual(count, 0)
        self.assertFalse(any(method == 'PUT' for _, _, method in calls))
        backup.assert_not_called()

    def test_stale_endpoint_preserves_category_and_real_secret(self):
        count, calls, backup = self.exercise('old-host')
        self.assertEqual(count, 1)
        backup.assert_called_once_with('sonarr')
        saved = next(data for _, data, method in calls if method == 'PUT')
        self.assertEqual(reconcile.fields(saved)['password']['value'], 'fixture-secret')
        self.assertEqual(reconcile.fields(saved)['tvCategory']['value'], 'existing-category')
        self.assertEqual(saved['name'], 'UbuntuVM')

    def test_check_reports_drift_without_writing(self):
        count, calls, backup = self.exercise('old-host', check=True)
        self.assertEqual(count, 1)
        self.assertFalse(any(method == 'PUT' for _, _, method in calls))
        backup.assert_not_called()


class DashyTests(unittest.TestCase):
    def test_scoped_update_and_second_run(self):
        original = {'appConfig': {'auth': {'fixture': 'preserved'}}, 'sections': [
            {'name': 'Media', 'items': [{'title': 'Sonarr', 'url': 'old', 'id': 'existing'}, {'title': 'Immich', 'url': 'unchanged'}]},
            {'name': 'Proxmox', 'items': [{'title': 'Toshiba', 'url': 'existing'}]}]}
        desired = {'media_links': {'Sonarr': 'new'}, 'servernode': {'title': 'ServerNode', 'url': 'https://node:8006'}}
        updated = dashy.update(original, desired)
        self.assertEqual(original['sections'][0]['items'][0]['url'], 'old')
        self.assertEqual(updated['appConfig'], original['appConfig'])
        self.assertEqual(updated['sections'][0]['items'][1], original['sections'][0]['items'][1])
        self.assertEqual(updated['sections'][0]['items'][0]['id'], 'existing')
        self.assertEqual(dashy.update(updated, desired), updated)

    def test_ambiguous_entries_fail_before_writing(self):
        config = {'sections': [{'name': 'Media', 'items': [{'title': 'Sonarr'}, {'title': 'Sonarr'}]}]}
        with self.assertRaises(AssertionError):
            dashy.update(config, {'media_links': {'Sonarr': 'new'}})


if __name__ == '__main__':
    unittest.main()
