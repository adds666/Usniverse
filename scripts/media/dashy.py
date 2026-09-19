#!/usr/bin/env python3
"""Update only the migrated links in the existing Dashy configuration."""
import argparse
import copy
import datetime
import json
import os
from pathlib import Path
import subprocess
import yaml


def update(config, desired):
    result = copy.deepcopy(config)
    for title, url in desired['media_links'].items():
        matches = [item for section in result['sections'] for item in section.get('items', [])
                   if item.get('title', '').lower() == title.lower()]
        assert len(matches) == 1, 'Expected one existing Dashy media entry: ' + title
        matches[0]['url'] = url
    sections = [section for section in result['sections'] if section['name'] == 'Proxmox']
    assert len(sections) == 1, 'Expected a Proxmox section'
    matches = [item for item in sections[0]['items'] if item['title'].lower() == 'servernode']
    assert len(matches) <= 1, 'Duplicate ServerNode entries'
    if matches:
        matches[0].update(desired['servernode'])
    else:
        sections[0]['items'].append(desired['servernode'])
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('specification')
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    os.umask(0o077)
    desired = json.loads(Path(args.specification).read_text())
    path = Path(desired['config_path'])
    raw = path.read_text()
    current = yaml.safe_load(raw)
    updated = update(current, desired)
    changed = updated != current
    if changed and not args.check:
        backup = Path(str(path) + '.pre-ansible-' + datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
        backup.write_text(raw)
        # The single-file mount is owned by the container. Preserve its inode.
        subprocess.run(['docker', 'exec', '-i', '--user', '0', desired['container'],
                        'node', '-e', "require('fs').writeFileSync('/app/user-data/conf.yml',require('fs').readFileSync(0))"],
                       input=yaml.safe_dump(updated, sort_keys=False).encode(), check=True)
        assert yaml.safe_load(path.read_text()) == updated
        subprocess.run(['docker', 'restart', desired['container']], check=True, stdout=subprocess.DEVNULL)
    print(json.dumps({'changed': changed, 'check': args.check}))


if __name__ == '__main__':
    main()
