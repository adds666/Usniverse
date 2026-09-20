#!/usr/bin/env python3
"""Wait for the tailnet route and NFS listener before the boot-time mount."""
import json
import socket
import subprocess
import time

NAS = '100.84.166.81'
deadline = time.monotonic() + 180
while time.monotonic() < deadline:
    try:
        routes = json.loads(subprocess.check_output(['ip', '-j', 'route', 'get', NAS], timeout=5))
        if routes and routes[0].get('dev') == 'tailscale0':
            with socket.create_connection((NAS, 2049), timeout=5):
                print('NAS NFS listener reachable through tailscale0')
                break
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    time.sleep(2)
else:
    raise SystemExit('NAS not reachable through Tailscale within 180 seconds')
