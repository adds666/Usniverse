#!/usr/bin/env python3
"""Read-only verification of reviewed image IDs and container health via Proxmox."""
import argparse
import json
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('manifest')
parser.add_argument('node')
args = parser.parse_args()
manifest = json.load(open(args.manifest))
results = []
for app in manifest['nodes'][args.node]:
    command = ['pct', 'exec', str(app['ct']), '--', 'docker', 'inspect', app['container']]
    current = json.loads(subprocess.check_output(command))[0]
    state = current['State']
    health = state.get('Health', {}).get('Status', 'not configured')
    valid = current['Image'] == app['image_id'] and state['Running'] and health in ['healthy', 'not configured']
    results.append({'ct': app['ct'], 'container': app['container'], 'matches': valid,
                    'health': health, 'restarts': current['RestartCount'], 'oom': state['OOMKilled']})
print(json.dumps(results, indent=2))
raise SystemExit(0 if all(r['matches'] and not r['oom'] for r in results) else 1)
