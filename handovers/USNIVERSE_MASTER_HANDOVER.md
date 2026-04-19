# USNIVERSE MASTER HANDOVER

Canonical date: 2026-04-19  
Audience: human operators and future AI agents  
Status: current source of truth for the repo as it exists today

If an older handover conflicts with this file, this file wins.

## 1. Project Definition

Usniverse is a Proxmox homelab managed primarily with Ansible. The repo is focused on:

- unprivileged LXC containers rather than VMs
- one service per container where practical
- Debian 12 as the preferred LXC baseline
- Docker inside selected LXCs only
- CLI-first, repeatable operations
- centralized external access through `ct110` (`edge-proxy`)
- Proxmox-owned storage mounts with bind mounts into LXCs

This repo is both infrastructure-as-code and an operations repo. Not every currently running service is fully represented by a dedicated app deployment playbook yet.

## 2. Environment Model

### 2.1 Inventory aliases vs actual Proxmox node names

The repo uses Ansible host aliases for Proxmox nodes:

| Inventory alias | Actual Proxmox node name | Purpose |
| --- | --- | --- |
| `pve` | `macbookpro` | primary Proxmox node |
| `servernode` | `servernode` | secondary Proxmox node |

Important:

- `inventories/home/group_vars/lxc.yml` uses `node: pve` or `node: servernode`, meaning the Ansible alias.
- `inventories/home/group_vars/proxmox.yml` still contains `proxmox_node: macbookpro`, which is the actual Proxmox node name used in Proxmox-specific contexts.

### 2.2 Network conventions

- LAN: `192.168.1.0/24`
- Most managed CTs follow `CT ID == last octet of IP`
- `ct219` is the intentional exception that still lives in the `2xx` range

### 2.3 Access model

- `ct110` is the edge proxy and Tailscale ingress point
- LXC SSH may be routed through ProxyJump when working remotely
- Proxmox remains authoritative for CT config, bind mounts, stop/start, backup, and restore

## 3. Current Managed Estate

| CT | Hostname | Node | VMID | IP | Docker | Dedicated app playbook | Notes |
| ---: | --- | --- | ---: | --- | --- | --- | --- |
| 110 | edge-proxy | `pve` | 110 | `192.168.1.110` | yes | no | ingress, Tailscale, DNAT, existing Homepage Docker host |
| 111 | jellyfin | `pve` | 111 | `192.168.1.111` | yes | yes | app playbook plus static compose asset |
| 112 | immich | `pve` | 112 | `192.168.1.112` | yes | no | infra represented, app playbook absent |
| 113 | ollama | `servernode` | 113 | `192.168.1.113` | yes | yes | renumbered from `213` |
| 114 | invidious | `pve` | 114 | `192.168.1.114` | yes | no | service known, playbook absent |
| 115 | openwebui | `servernode` | 115 | `192.168.1.115` | yes | yes | renumbered from `215` |
| 116 | n8n | `pve` | 116 | `192.168.1.116` | yes | yes | playbook writes compose inline |
| 117 | synapse | `pve` | 117 | `192.168.1.117` | yes | no | service known, playbook absent |
| 118 | ombi | `pve` | 118 | `192.168.1.118` | yes | no | service known, playbook absent |
| 119 | searxng | `pve` | 119 | `192.168.1.119` | yes | yes | dedicated web search backend for Open WebUI and Homepage |
| 120 | comfyui | `servernode` | 120 | `192.168.1.120` | yes | yes | GPU-enabled workload |
| 121 | openclaw | `servernode` | 121 | `192.168.1.121` | yes | yes | builds local image from upstream repo |
| 219 | immich-ml | `servernode` | 219 | `192.168.1.219` | yes | no | still intentionally `219` |

Outside this repo:

- A `7dtd` container exists in Proxmox and should not be disturbed by repo cleanup work.

## 4. Repository Structure and Semantics

### 4.1 Core top-level files

- `ansible.cfg`: default inventory path, roles path, SSH pipelining, interpreter detection
- `README.md`: current operator-facing summary
- `handovers/USNIVERSE_MASTER_HANDOVER.md`: this file

### 4.2 Inventories and variables

- `inventories/home/hosts.yml`
  - `lxc`: all managed CTs
  - `docker_lxc`: CTs expected to run Docker workloads
  - `proxmox`: Proxmox nodes
- `inventories/home/group_vars/lxc.yml`
  - logical CT map with sizing, IPs, features, and `proxmox_vmid`
- `inventories/home/group_vars/proxmox.yml`
  - Proxmox API and network defaults
- `inventories/home/host_vars/pve.yml`
  - node-specific rootfs storage and live Docker CT VMIDs on `pve`
- `inventories/home/host_vars/servernode.yml`
  - node-specific rootfs storage and live Docker CT VMIDs on `servernode`
- `inventories/home/host_vars/ct110.yml`
  - assumptions about the existing Homepage container on CT110
- `inventories/home/group_vars/lxc/base_lxc.yml`
  - shared authorized key and admin baseline values
- `inventories/home/group_vars/lxc/ssh.yml`
  - ProxyJump settings for LXC access
- `inventories/home/group_vars/lxc/python.yml`
  - explicit Python interpreter path for LXCs

### 4.3 Roles

- `roles/base_lxc`
  - Debian 12 baseline, packages, admin user, SSH hardening, standard directories
- `roles/docker_host`
  - Docker CE repo + packages + docker group membership
- `roles/docker_compose_app`
  - reusable helper for rendering compose files and bringing apps up/down
- `roles/nas_mount`
  - bind-mount `Global_Share` from Proxmox into selected LXCs
- `roles/proxmox_docker_egress`
  - nft/sysctl-based outbound egress support for Docker subnets on Proxmox

### 4.4 Static payloads

- `files/ct111/jellyfin/docker-compose.yml`
  - historical or alternate Jellyfin compose asset
- `files/ct120/comfyui/`
  - ComfyUI Dockerfile and compose payload copied into CT120

## 5. Playbook Catalog

### 5.1 Canonical lifecycle playbooks

- `playbooks/lxc_ssh.yml`
  - creates CTs on the Proxmox node itself via `pct` and `pveam`
  - accepts `lxc_target_ids`
  - supports targeting by logical CT ID or current VMID
- `playbooks/ct_bootstrap.yml`
  - bootstraps a brand-new CT via Proxmox `pct exec`
  - takes `ct_ids`, which are Proxmox VMIDs
- `playbooks/base_lxc.yml`
  - applies the `base_lxc` role to the full `lxc` group
- `playbooks/docker_host.yml`
  - applies the `docker_host` role to the `docker_lxc` group
- `playbooks/pve_docker_lxc_fix.yml`
  - patches Proxmox LXC config for Docker inside unprivileged LXCs
  - uses node-scoped `docker_lxc_ct_ids` from `host_vars`

### 5.2 Infrastructure and support playbooks

- `playbooks/pve_global_share_mount.yml`
  - ensures `Global_Share` is mounted on `pve`
- `playbooks/nas_mount.yml`
  - uses `roles/nas_mount` to bind `Global_Share` into selected CTs on `pve`
- `playbooks/pve_ct110_global_share_bind.yml`
  - ensures CT110 has `/home/ubuntu/Global_Share` bind-mounted from Proxmox
- `playbooks/pve_docker_egress.yml`
  - applies Docker egress support on `pve`
- `playbooks/docker_update_all.yml`
  - scans `docker_lxc` containers for compose files and runs pull/up
- `playbooks/homepage_ct110.yml`
  - updates the existing Homepage config on CT110 with SearXNG search and AI links

### 5.3 Ingress playbooks

Two ingress playbooks exist:

- `playbooks/edge_proxy_dnat.yml`
  - parameterized
  - runs on `pve`
  - manages CT110 rules via `pct exec`
  - takes rules from `group_vars/all/edge_proxy_dnat.yml`
- `playbooks/ct110_ingress.yml`
  - runs directly against `ct110`
  - carries its own inline `dnat_rules`

Operationally, `edge_proxy_dnat.yml` is the better source for rule data because it externalizes the rules into `group_vars/all/edge_proxy_dnat.yml`. If both playbooks are kept, their rule sets must stay synchronized.

### 5.4 Application and service playbooks

- `playbooks/app_jellyfin_ct111.yml`
- `playbooks/app_ollama_ct113.yml`
- `playbooks/app_openwebui_ct115.yml`
- `playbooks/app_n8n_ct116.yml`
- `playbooks/app_searxng_ct119.yml`
- `playbooks/comfyui.yml`
- `playbooks/app_openclaw_ct121.yml`

### 5.5 Convenience helper playbooks

- `playbooks/base_lxc_ct110.yml`
- `playbooks/docker_host_ct110.yml`

These are convenience wrappers for CT110 only. They are not the canonical general pattern for the repo.

## 6. Canonical Operational Workflows

Always use the file inventory:

```bash
ansible-playbook -i inventories/home/hosts.yml ...
```

Do not point Ansible at the inventory directory itself.

### 6.1 Create a CT

Example:

```bash
ansible-playbook -i inventories/home/hosts.yml playbooks/lxc_ssh.yml --limit servernode -e "{\"lxc_target_ids\":[115]}"
```

Key semantics:

- `lxc_target_ids` may be logical CT IDs or live VMIDs
- `lxc_ssh.yml` executes on the owning Proxmox node alias (`pve` or `servernode`)
- CT sizing, IP, features, and placement come from `inventories/home/group_vars/lxc.yml`

### 6.2 Bootstrap a CT for Ansible

Example:

```bash
ansible-playbook -i inventories/home/hosts.yml playbooks/ct_bootstrap.yml --limit servernode -e "{\"ct_ids\":[115]}"
```

Important:

- `ct_ids` are Proxmox VMIDs
- this step is mandatory before `base_lxc.yml` if the CT is truly new

### 6.3 Baseline and Docker

```bash
ansible-playbook -i inventories/home/hosts.yml playbooks/base_lxc.yml --limit ct115
ansible-playbook -i inventories/home/hosts.yml playbooks/docker_host.yml --limit ct115
ansible-playbook -i inventories/home/hosts.yml playbooks/pve_docker_lxc_fix.yml --limit servernode
```

### 6.4 Deploy apps

Examples:

```bash
ansible-playbook -i inventories/home/hosts.yml playbooks/app_ollama_ct113.yml
ansible-playbook -i inventories/home/hosts.yml playbooks/app_openwebui_ct115.yml
ansible-playbook -i inventories/home/hosts.yml playbooks/app_searxng_ct119.yml
ansible-playbook -i inventories/home/hosts.yml playbooks/homepage_ct110.yml
ansible-playbook -i inventories/home/hosts.yml playbooks/app_openclaw_ct121.yml
```

### 6.5 Update all Docker workloads

```bash
ansible-playbook -i inventories/home/hosts.yml playbooks/docker_update_all.yml
```

## 7. Docker Inside Unprivileged LXC

This remains the biggest technical gotcha in the repo.

### 7.1 What the repo does

- `playbooks/docker_host.yml`
  - installs Docker Engine and Compose plugin inside the CT
- `playbooks/pve_docker_lxc_fix.yml`
  - patches `/etc/pve/lxc/<vmid>.conf` on the Proxmox host
  - enables `/dev/fuse`, AppArmor relaxation, proc/sys mount relaxation
  - restarts the affected CTs

### 7.2 Source of truth for which CTs need the Proxmox fix

The live Docker CT VMIDs are stored per node in:

- `inventories/home/host_vars/pve.yml`
- `inventories/home/host_vars/servernode.yml`

Those values must reflect real Proxmox VMIDs, not just logical CT names.

### 7.3 GPU-specific handling

CT120 is the only GPU-designated CT in the repo today.

- `playbooks/pve_docker_lxc_fix.yml` applies extra NVIDIA passthrough lines for CT120
- `playbooks/comfyui.yml` configures the NVIDIA container toolkit inside CT120

### 7.4 Docker egress

`playbooks/pve_docker_egress.yml` currently targets `pve` only and configures:

- `br_netfilter`
- IPv4 forwarding
- nftables NAT and forward rules for Docker subnet `172.18.0.0/16`

That is the repo's current implementation, not a generic cluster-wide abstraction.

## 8. Storage Model

### 8.1 Hard rule

Do not mount NFS directly inside unprivileged LXCs.

The intended pattern is:

1. mount `Global_Share` on Proxmox
2. bind-mount it into selected LXCs
3. bind-mount subpaths into Docker containers as needed

### 8.2 Repo implementation

- `playbooks/pve_global_share_mount.yml`
  - ensures the `Global_Share` NFS mount exists on `pve`
- `playbooks/nas_mount.yml`
  - bind-mounts the host path into selected LXCs
  - currently driven by `roles/nas_mount/defaults/main.yml`
- `playbooks/pve_ct110_global_share_bind.yml`
  - separately ensures CT110 gets `/home/ubuntu/Global_Share`

### 8.3 Known semantic debt

`roles/nas_mount/defaults/main.yml` still hardcodes `nas_lxc_ct_ids`. That is current behavior, but it is inventory-like data living in role defaults.

## 9. Current Ingress State

`ct110` owns external access.

The parameterized DNAT rules in `group_vars/all/edge_proxy_dnat.yml` currently publish:

| External port | Internal target | Service |
| ---: | --- | --- |
| 8096 | `192.168.1.111:8096` | Jellyfin |
| 3579 | `192.168.1.118:3579` | Ombi |
| 8008 | `192.168.1.117:8008` | Synapse |
| 5678 | `192.168.1.116:5678` | n8n |
| 8081 | `192.168.1.115:3000` | OpenWebUI |
| 11435 | `192.168.1.113:11434` | Ollama |
| 4000 | `192.168.1.114:3000` | Invidious |
| 8188 | `192.168.1.120:8188` | ComfyUI |
| 18789 | `192.168.1.121:18789` | OpenClaw |

The repo also contains a direct CT110 ingress playbook with the same intent.

Homepage itself is assumed to already exist on CT110. The repo does not currently claim to own its full deployment; it only owns the SearXNG-oriented config injected by `playbooks/homepage_ct110.yml`.

## 10. Service-Specific Semantics That Matter

### 10.0 Edge Proxy / Homepage (CT110)

- CT110 is now a Docker host in repo terms and is included in `docker_lxc`
- Homepage is assumed to already exist there as a Docker container
- `playbooks/homepage_ct110.yml` injects the managed SearXNG search widget and AI service links
- `inventories/home/host_vars/ct110.yml` is where to change:
  - `homepage_config_dir`
  - `homepage_container_name`

### 10.1 SearXNG (CT119)

- Docker-based
- deployed with `playbooks/app_searxng_ct119.yml`
- listens on `192.168.1.119:8080`
- settings explicitly enable JSON search results for Open WebUI
- intended as the dedicated web-search backend for Open WebUI and Homepage

### 10.2 Jellyfin (CT111)

- Docker-based
- deployed with `docker_compose_app`
- also has a static compose asset at `files/ct111/jellyfin/docker-compose.yml`
- currently uses host paths under `/opt/jellyfin`, `/data/media`, `/data/transcode`

### 10.3 Ollama (CT113)

- Docker-based
- listens on `192.168.1.113:11434`
- no models are pulled by the playbook

### 10.4 OpenWebUI (CT115)

- Docker-based
- maps `3000:8080`
- depends on `OLLAMA_BASE_URL=http://192.168.1.113:11434`
- now enables built-in web search against `http://192.168.1.119:8080/search?q=<query>`
- `ENABLE_PERSISTENT_CONFIG=false` is an intentional determinism choice
- because the relevant web-search settings are PersistentConfig values in Open WebUI, keeping persistent config disabled is what makes the Ansible-managed environment authoritative

### 10.5 n8n (CT116)

- Docker-based
- current playbook writes compose inline rather than using `docker_compose_app`
- current playbook sets `N8N_SECURE_COOKIE=false`

### 10.6 ComfyUI (CT120)

- Docker-based GPU workload
- uses local payload from `files/ct120/comfyui/`
- configures NVIDIA toolkit inside the CT before bringing the compose project up

### 10.7 OpenClaw (CT121)

- Docker-based
- clones upstream source into the CT
- builds a local image named `openclaw:local`
- points at Ollama on `192.168.1.113:11434`
- publishes `18789` and `18790`, with `18789` exposed through edge-proxy

### 10.8 Services without dedicated deployment playbooks

These services are clearly part of the environment but are not fully codified as dedicated app playbooks in this repo yet:

- Immich (`ct112`)
- Invidious (`ct114`)
- Synapse (`ct117`)
- Ombi (`ct118`)
- Immich ML (`ct219`)

That is current repo reality, not a documentation omission.

## 11. Current Documentation Policy

The current source of truth is:

- `README.md`
- this master handover

The other files under `handovers/` are historical snapshots. They are still useful for deep debugging and migration history, but they are not the operational contract for the current repo.

## 12. Known Current Gaps and Tradeoffs

These are intentional or known aspects of the current repo state:

- `ct219` has not yet been renumbered into the `1xx` convention
- two ingress playbooks exist and represent the same intent in different styles
- CT110 helper playbooks still exist as convenience wrappers
- `roles/nas_mount/defaults/main.yml` still stores environment-specific CT IDs
- `ansible.cfg` currently sets `host_key_checking = False`
- `ansible.cfg` currently sets `deprecation_warnings = False`
- older handovers contain valuable history but may be stale on current semantics

## 13. Anti-Footguns

- Always pass `-i inventories/home/hosts.yml`
- `ct_bootstrap.yml` takes Proxmox VMIDs, not `ctXXX` inventory names
- `docker_host.yml` now targets `docker_lxc`, not all LXCs
- `pve_docker_lxc_fix.yml` must be rerun after adding or renumbering Docker CTs
- after `pve_docker_lxc_fix.yml`, do not assume a guest reboot is enough; the playbook itself stop/starts the CTs
- keep edge-proxy published ports aligned with `group_vars/all/edge_proxy_dnat.yml`
- keep `docker_lxc_ct_ids` aligned with live VMIDs in node `host_vars`

## 14. Historical Troubleshooting Depth

If a service-specific issue needs migration history or old root-cause details, consult the older handovers:

- Jellyfin migration and config history
- Synapse / proxyjump history
- n8n bootstrap history
- Invidious patching notes
- Ollama / OpenWebUI migration history

Use those as historical references only. Do not treat them as the current state contract.
