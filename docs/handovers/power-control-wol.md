# USniverse Power Control / WOL Handover

## Current Architecture

Homepage users access only edge-proxy:

- edge-proxy Tailscale IP: 100.122.95.117

edge-proxy proxies WOL/shutdown requests over Tailscale to:

- earls-edge01 / Earls relay: 100.91.80.105

earls-edge01 is on the same LAN as servernode and sends the actual LAN WOL packet.

Flow:

Homepage -> edge-proxy:8787 -> earls-edge01:8787 over Tailscale -> LAN etherwake -> servernode

## ServerNode

- LAN IP: 192.168.1.104
- WOL MAC: 0c:c4:7a:ca:24:2b
- WOL NIC: eno2

## Important Rule

WOL packets must be sent from a device on the same LAN as servernode.

Remote users should never call earls-edge01 directly. They call edge-proxy, which relays the request.

## Homepage

Homepage buttons should point to:

- http://100.122.95.117:8787/wol?token=<token>
- http://100.122.95.117:8787/shutdown?token=<token>

Do not template the whole Homepage services.yaml destructively. Patch only the Server Control block.

## Ansible Roles

Relevant roles/playbooks:

- roles/edge_wol_proxy/
- roles/edge_wol_webhook/
- roles/homepage_services/
- playbooks/power_control_proxy.yml
- group_vars/all/power_control.yml

## Secrets

The webhook token must not be committed in plaintext.

Use this variable in an encrypted Ansible Vault file, or pass via -e:

vault_wol_webhook_token: <secret>

## Cleanup Done

Removed stale Homepage entries for:

- ComfyUI
- Open WebUI
- Ollama

## Known Pitfalls

- Do not point user-facing Homepage buttons directly at earls-edge01.
- Do not overwrite full Homepage services file.
- Do not commit webhook tokens.
- /bin/sh on ct110 does not support set -o pipefail.
- WOL must be emitted locally on the same LAN as servernode.

## Final Intended Request Flow

User browser -> Homepage on edge-proxy -> edge-proxy WOL proxy -> earls-edge01 WOL relay -> servernode LAN WOL/shutdown

