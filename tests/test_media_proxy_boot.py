"""Guard the socket ordering that caused the first post-migration reboot outage."""
from pathlib import Path
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[1]


class ProxyBootTests(unittest.TestCase):
    def test_socket_can_start_before_network_is_online(self):
        play = yaml.safe_load((ROOT / 'playbooks/media_proxy_routes.yml').read_text())[0]
        content = play['tasks'][0]['ansible.builtin.copy']['content']
        directives = {}
        for line in content.splitlines():
            if '=' in line and not line.lstrip().startswith('#'):
                key, value = line.strip().split('=', 1)
                directives.setdefault(key, []).extend(value.split())
        # Socket units implicitly precede sockets.target, which precedes basic.target.
        # Waiting on a normal network service/target closes that boot ordering loop.
        forbidden = {'network-online.target', 'network.target', 'tailscaled.service',
                     'basic.target', 'multi-user.target'}
        self.assertFalse(forbidden.intersection(directives.get('After', [])))
        self.assertFalse(forbidden.intersection(directives.get('Wants', [])))
        self.assertEqual(directives['FreeBind'], ['true'])
        self.assertEqual(directives['WantedBy'], ['sockets.target'])


if __name__ == '__main__':
    unittest.main()
