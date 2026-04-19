# USniverse

Usniverse is an Ansible-managed homelab for running Proxmox LXC workloads with a bias toward one service per container, unprivileged LXCs, and repeatable CLI-first operations.

## Current Intent

- Run services as individual LXC containers on Proxmox.
- Use Debian 12 as the baseline LXC OS where practical.
- Install Docker only on containers that need it.
- Keep external access centralized on `ct110` (`edge-proxy`) via Tailscale and iptables DNAT.
- Mount NAS storage on Proxmox, then bind-mount it into containers. Do not mount NFS directly inside LXCs.

## Environment Model

There are two Proxmox nodes in scope:

| Inventory Alias | Actual Proxmox Node | Purpose |
| --- | --- | --- |
| `pve` | `macbookpro` | primary Proxmox node |
| `servernode` | `servernode` | secondary Proxmox node |

The inventory uses host aliases (`pve`, `servernode`) for Ansible. The actual Proxmox node name `macbookpro` still appears in Proxmox-specific settings such as `proxmox_node`.

## Current Managed Estate

| CT | Hostname | Node | IP | Docker | Dedicated app playbook |
| ---: | --- | --- | --- | --- | --- |
| 110 | edge-proxy | `pve` | `192.168.1.110` | no | no |
| 111 | jellyfin | `pve` | `192.168.1.111` | yes | yes |
| 112 | immich | `pve` | `192.168.1.112` | yes | no |
| 113 | ollama | `servernode` | `192.168.1.113` | yes | yes |
| 114 | invidious | `pve` | `192.168.1.114` | yes | no |
| 115 | openwebui | `servernode` | `192.168.1.115` | yes | yes |
| 116 | n8n | `pve` | `192.168.1.116` | yes | yes |
| 117 | synapse | `pve` | `192.168.1.117` | yes | no |
| 118 | ombi | `pve` | `192.168.1.118` | yes | no |
| 120 | comfyui | `servernode` | `192.168.1.120` | yes | yes |
| 121 | openclaw | `servernode` | `192.168.1.121` | yes | yes |
| 219 | immich-ml | `servernode` | `192.168.1.219` | yes | no |

Notes:

- `ct219` intentionally still uses `219`; it has not yet been renumbered into the `1xx` scheme.
- A separate `7dtd` container exists in Proxmox but is not represented in this repo.
- Not every running service has a dedicated app deployment playbook yet. The repo currently mixes full deployment playbooks with infrastructure-only representation.

## Inventory Model

The inventory lives at `inventories/home/hosts.yml` and defines three important groups:

- `lxc`: every managed LXC container
- `docker_lxc`: LXC containers expected to run Docker workloads
- `proxmox`: the Proxmox nodes themselves

`inventories/home/group_vars/lxc.yml` is the logical CT map. Each CT entry can carry:

- `id`: the logical CT number used in naming and IP conventions
- `proxmox_vmid`: the live VMID on Proxmox
- `node`: the Ansible alias of the node that owns the CT
- `hostname`, `ip`, `cores`, `memory`, `disk_gb`, `features`

In normal steady state, `id` and `proxmox_vmid` should match. If they differ during a renumbering, the repo should treat that as temporary debt and clean it up once the live CT has been migrated.

## Playbook Catalog

### Core lifecycle

- `playbooks/lxc_ssh.yml`: create LXCs on Proxmox via `pct` and `pveam`
- `playbooks/ct_bootstrap.yml`: bootstrap brand-new CTs so Ansible can log in
- `playbooks/base_lxc.yml`: baseline Debian LXC config
- `playbooks/docker_host.yml`: install Docker on the `docker_lxc` group
- `playbooks/pve_docker_lxc_fix.yml`: Proxmox-side fixes for Docker inside unprivileged LXCs

### Infrastructure and support

- `playbooks/pve_global_share_mount.yml`: ensure `Global_Share` is mounted on Proxmox
- `playbooks/nas_mount.yml`: bind-mount `Global_Share` into selected LXCs
- `playbooks/pve_ct110_global_share_bind.yml`: ensure CT110 gets its dedicated `Global_Share` bind mount
- `playbooks/pve_docker_egress.yml`: configure Docker subnet egress rules on `pve`
- `playbooks/docker_update_all.yml`: update Docker Compose projects across `docker_lxc`
- `playbooks/edge_proxy_dnat.yml`: variable-driven DNAT management for `ct110` via Proxmox `pct exec`
- `playbooks/ct110_ingress.yml`: direct-on-CT110 DNAT playbook with an inline rules list

### App and service deployment

- `playbooks/app_jellyfin_ct111.yml`
- `playbooks/app_ollama_ct113.yml`
- `playbooks/app_openwebui_ct115.yml`
- `playbooks/app_n8n_ct116.yml`
- `playbooks/comfyui.yml`
- `playbooks/app_openclaw_ct121.yml`

### Convenience wrappers

- `playbooks/base_lxc_ct110.yml`
- `playbooks/docker_host_ct110.yml`

These are small helpers for CT110 only. They are not the canonical path for general repo operations.

## Canonical Workflows

Always use the file inventory:

```bash
ansible-playbook -i inventories/home/hosts.yml ...
```

### Create one or more CTs

`lxc_ssh.yml` accepts `lxc_target_ids`, which may be logical CT IDs or live VMIDs:

```bash
ansible-playbook -i inventories/home/hosts.yml playbooks/lxc_ssh.yml --limit servernode -e "{\"lxc_target_ids\":[115]}"
```

### Bootstrap a new CT

`ct_bootstrap.yml` takes Proxmox VMIDs, not inventory hostnames:

```bash
ansible-playbook -i inventories/home/hosts.yml playbooks/ct_bootstrap.yml --limit servernode -e "{\"ct_ids\":[115]}"
```

### Apply baseline and Docker

```bash
ansible-playbook -i inventories/home/hosts.yml playbooks/base_lxc.yml --limit ct115
ansible-playbook -i inventories/home/hosts.yml playbooks/docker_host.yml --limit ct115
ansible-playbook -i inventories/home/hosts.yml playbooks/pve_docker_lxc_fix.yml --limit servernode
```

### Deploy an app

```bash
ansible-playbook -i inventories/home/hosts.yml playbooks/app_openwebui_ct115.yml
```

## Networking and Ingress

`ct110` (`edge-proxy`) owns published service access through Tailscale and iptables DNAT.

The parameterized ingress rule source in the repo is:

- `group_vars/all/edge_proxy_dnat.yml`

That rule set currently publishes:

- Jellyfin `8096`
- Ombi `3579`
- Synapse `8008`
- n8n `5678`
- OpenWebUI `8081 -> 192.168.1.115:3000`
- Ollama `11435 -> 192.168.1.113:11434`
- Invidious `4000`
- ComfyUI `8188`
- OpenClaw `18789`

## Storage Model

`Global_Share` is mounted on Proxmox, not inside LXCs.

- `playbooks/pve_global_share_mount.yml` ensures the host mount exists
- `playbooks/nas_mount.yml` bind-mounts it into selected LXCs
- `playbooks/pve_ct110_global_share_bind.yml` gives CT110 its dedicated Homepage-facing bind path

This is a hard rule for the repo: no direct NFS mounts inside unprivileged LXCs.

## Documentation Policy

The current authoritative docs are:

- this `README.md`
- `handovers/USNIVERSE_MASTER_HANDOVER.md`

Older files under `handovers/` are historical snapshots. They are useful for root-cause history and migration context, but they are not the current source of truth. If an older handover conflicts with the README or the master handover, the current docs win.
