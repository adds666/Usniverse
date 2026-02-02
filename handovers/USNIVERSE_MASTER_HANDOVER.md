# USNIVERSE — AUTHORITATIVE MASTER HANDOVER (CANON)
**Canonical date:** 2026-01-21 (Europe/London)  
**Audience:** future AI agents + human operators  
**Intent:** *single source of truth* for architecture, methodology, current state, and “don’t repeat the pain”.

> **Rule of interpretation:**  
> If an older handover conflicts with this file, **this file wins**.  
> If this file says “planned/target”, it is *aspirational*; everything labelled **CURRENT** is ground truth.

---

## 0) Read-first rules for future agents

### 0.1 Operational rules (do not break)
1. **CLI only**: do not use nano/vim/editors or Proxmox UI clicking in instructions.  
2. **Commands must be provided in a single unbroken code block** (ChatGPT UI truncation/buffer issues).  
3. **Terminal buffer friendly (especially when remote)**: prefer **small, paste-safe command chunks** (each chunk self-contained) over one massive block; avoid long heredocs unless explicitly requested.
4. **Assume remote execution** unless explicitly stated.  
5. **Idempotency first**: check before mutating state.  
6. **Proxmox is authoritative** for mounts, backups, snapshots.  
7. **One service per LXC** (separation of concerns).

### 0.2 Design constraints (non-negotiable)
1. **LXCs (not VMs)**
2. **Unprivileged LXCs**
3. **Debian 12 is the target LXC OS baseline**  
   - Some containers may currently be Ubuntu due to earlier migration timing; see “History / Changes”.
4. **Single ingress point**: **CT110 edge-proxy** owns Tailscale + forwarding.
5. **No NFS mounts inside LXCs**: NFS is mounted on Proxmox and bind-mounted into LXCs.

---

## 1) What Usniverse is (project definition)

Usniverse is a homelab migration + IaC project to move from a few “heavy” Ubuntu VMs running many Docker Compose apps into:

- **One Debian 12 LXC per app**
- Fully reproducible lifecycle via **Ansible**
- Clear network topology:
  - LAN-only services by default
  - A single ingress point for friends/external access via **Tailscale**

This is a **re-platform** (not a tidy-up).

---

## 2) Current architecture (CURRENT)

### 2.1 Platform
- **Proxmox host:** `pve`
- All services run as **unprivileged LXCs**
- Docker runs **inside** LXCs when needed

### 2.2 Network
- LAN: `192.168.1.0/24`
- Convention: **CT ID == last octet of IP**
  - CT111 → `192.168.1.111`
  - CT118 → `192.168.1.118`

### 2.3 Ingress & external access
- **CT110 = edge-proxy**
  - Runs **Tailscale**
  - Owns **iptables DNAT** for exposed services
- **UbuntuVM2** (older “jump host / ingress”) is **deprecated** for ingress.
  - It may still exist as a *data source* for configs until migrations complete.

---

## 3) Current service inventory (CURRENT)

> **Note about CT numbering conflicts in older docs:**  
> Some older handovers accidentally list CT115/CT116 roles incorrectly.  
> The DNAT rules and the n8n handover confirm **n8n is on CT116**.

| CT | Hostname / Role | Service(s) | Status |
|---:|------------------|------------|--------|
| 110 | edge-proxy | Tailscale + iptables DNAT | **CURRENT ingress** |
| 111 | jellyfin | Jellyfin (Docker) | Running |
| 112 | immich | Immich | Running |
| 113 | ollama | Ollama backend | Running |
| 114 | invidious | Invidious + Postgres + Companion | Running |
| 115 | openwebui | OpenWebUI frontend | Running |
| 116 | n8n | n8n (Docker) | Running |
| 117 | synapse | Matrix Synapse | Running |
| 118 | ombi | Ombi (Docker) | Running (login currently broken; see §9.2) |

Special:
- A **7 Days to Die** LXC exists and must not be disturbed.

---

## 4) Repository / IaC layout (CURRENT)

### 4.1 Golden playbooks (authoritative)
- `playbooks/lxc_ssh.yml`  
  Creates LXCs using **pct/pveam via SSH on Proxmox** (stable & proven).
- `playbooks/ct_bootstrap.yml`  
  Fixes “new CT not ready” problems (sudo missing, SSH keys/users missing).
- `playbooks/base_lxc.yml`  
  Baseline config for LXCs.
- `playbooks/docker_host.yml`  
  Installs/configures Docker on LXCs that need it.
- `playbooks/pve_docker_lxc_fix.yml`  
  Proxmox-side LXC config changes required for Docker inside **unprivileged** LXCs.

### 4.2 Deprecated / forbidden
- Proxmox API module provisioning (`community.proxmox.proxmox` etc.)  
  **Why:** repeated token weirdness and module behavior inconsistencies.
- Legacy playbook: `playbooks/lxc.yml`  
  **Do not use**.

---

## 5) Lifecycle runbook (MANDATORY ORDER)

### 5.1 Creating a new LXC (repeatable)
1) **Create** (Proxmox-side, via SSH `pct`):
```bash
ansible-playbook -i inventories/home/hosts.yml playbooks/lxc_ssh.yml --limit pve
```

2) **Bootstrap** (ONE TIME per CT; fixes sudo/SSH/admin user):
```bash
ansible-playbook -i inventories/home/hosts.yml playbooks/ct_bootstrap.yml --limit ctXXX
```

3) **Baseline** (packages, hardening, etc.):
```bash
ansible-playbook -i inventories/home/hosts.yml playbooks/base_lxc.yml --limit ctXXX
```

4) **Docker host** (only for Docker-based services):
```bash
ansible-playbook -i inventories/home/hosts.yml playbooks/docker_host.yml --limit ctXXX
```

### 5.2 Inventory hygiene rules (prevents Ansible parsing failures)
- Always use file inventory:
```bash
ansible-playbook -i inventories/home/hosts.yml ...
```
- Do **not** pass the directory (`-i inventories/home`) because Ansible will try to parse random backup files.
- Do **not** store backups inside `inventories/home/`  
  Put them in something like `inventories/_backups/`.

---

## 6) Remote access / ProxyJump (CURRENT + GOTCHAS)

### 6.1 Current topology intent
When remote:
- You must be able to reach **pve** and **ct110** reliably.
- **Do not ProxyJump “pve through pve”** (loop bug seen previously).

### 6.2 ProxyJump file (where to look first when SSH breaks)
A ProxyJump configuration has been stored at:
- `inventories/home/group_vars/lxc/ssh.yml`

Older content used:
- `ansible_ssh_common_args: "-o ProxyJump=ubuntu@100.122.95.117,root@100.69.158.73"`

**Important evolution:** the **Tailscale IP `100.122.95.117` is now CT110 (edge-proxy)**, not UbuntuVM2.  
If SSH “mysteriously” fails, verify:
- which host currently owns `100.122.95.117`
- the usernames (ubuntu/admin/root) used for jump hops

**Golden rule:** pve must be reachable directly; jump-host settings must not create loops.

---

## 7) Docker inside unprivileged LXC (MOST IMPORTANT TECHNICAL GOTCHA)

### 7.1 Symptoms (what you will see)
- `OCI runtime create failed`
- `permission denied: sysctl net.ipv4.ip_unprivileged_port_start`
- `fuse-overlayfs: device not found`
- Containers “create” but won’t “start”
- `docker info` looks fine but runtime fails

### 7.2 Root cause (what is actually happening)
Unprivileged LXC restricts:
- overlayfs
- sysctl/proc/sys interactions
- device access

Docker falls back to **fuse-overlayfs**, which requires `/dev/fuse` and host module support.

### 7.3 The canonical fix (Proxmox-side)
On Proxmox:
- Ensure `fuse` module is loaded and persistent
- Modify CT config to allow `/dev/fuse` and relax AppArmor/proc/sys
- **Stop/start the CT** (reboot inside CT is insufficient)

This is automated by:
```bash
ansible-playbook -i inventories/home/hosts.yml playbooks/pve_docker_lxc_fix.yml --limit pve
```

### 7.4 Critical operator requirement
Every Docker-based CT must be listed in `docker_lxc_ct_ids` in `pve_docker_lxc_fix.yml`.  
If you forget, Docker will break later and it will look “random”.

---

## 8) Storage model (CRITICAL)

### 8.1 NAS / Global_Share rule
- NFS mount lives **on Proxmox only**:
  - `/mnt/pve/Global_Share`
- LXCs get access via **bind mounts**:
```bash
pct set <CTID> -mp0 /mnt/pve/Global_Share,mp=/mnt/Global_Share
```

### 8.2 Absolutely forbidden
- Mounting NFS inside an LXC (`/etc/fstab` entries, `mount -t nfs`, etc.)

**Why this rule exists (past failures):**
- permission chaos
- unstable services
- Proxmox backup hangs / snapshot pain

---

## 9) Edge-proxy (CT110) — ingress source of truth

### 9.1 What CT110 does
- Runs Tailscale (`tailscaled`)
- Owns external access via iptables DNAT
- Replaces older “UbuntuVM2 forwarding” approach

### 9.2 Current DNAT mapping (AUTHORITATIVE)
Exposed on CT110’s Tailscale IP (`100.122.95.117`):

| External port | Internal destination | Notes |
|---:|---|---|
| 8096 | `192.168.1.111:8096` | Jellyfin |
| 3579 | `192.168.1.118:3579` | Ombi |
| 8008 | `192.168.1.117:8008` | Synapse (Matrix) |
| 5678 | `192.168.1.116:5678` | n8n |
| 8081 | `192.168.1.115:3000` | OpenWebUI (NOT :8080) |
| 11435 | `192.168.1.113:11434` | Ollama |
| 4000 | `192.168.1.114:3000` | Invidious |

### 9.3 Verification pattern
Use:
- `curl http://100.122.95.117:<port>`
- service-specific health endpoints where available

---

## 10) Service runbooks + pitfalls

### 10.1 Jellyfin (CT111)
**CURRENT:** running and reachable on `:8096`.

**Key lesson:** Jellyfin metadata exploded (~160GB+) and broke backups and migrations.

**Do migrate (from old host):**
- `config/`
- `data/data/`

**Do NOT migrate:**
- `data/metadata`
- `cache/`
- `transcodes/`

**Docker-in-LXC note:** Jellyfin Docker only worked after applying the unprivileged-LXC Docker fix (fuse/AppArmor/proc/sys).

---

### 10.2 Ombi (CT118)
**CURRENT:** UI loads but **login fails**.

**Most likely root cause:** config DB set not fully restored; DBs were recreated.

**Required files to restore from old host (copy entire config dir):**
- `Ombi.db`
- `OmbiSettings.db`
- `OmbiExternal.db`
- `.aspnet/DataProtection-Keys/` (or equivalent)

**Ownership requirement:**
- UID/GID `1000:1000` (linuxserver conventions used elsewhere)

Until restored properly, login will not succeed.

---

### 10.3 n8n (CT116)
**CURRENT:** running on `:5678`.

**Canonical URL rule (CRITICAL):**  
n8n must be accessed consistently via one URL that matches:
- `N8N_HOST`
- `N8N_EDITOR_BASE_URL`
- `WEBHOOK_URL`
- `N8N_PROTOCOL`

**Common failure symptom:**
- `Cannot GET /setup`

**HTTP testing rule:**
- If using HTTP temporarily:
  - `N8N_PROTOCOL=http`
  - `N8N_SECURE_COOKIE=false`

**If using HTTPS later (edge proxy):**
- switch to `N8N_PROTOCOL=https`
- `N8N_SECURE_COOKIE=true`

---

### 10.4 Ollama (CT113) + OpenWebUI (CT115)
**CURRENT:**
- Ollama listens on `ct113:11434`
- OpenWebUI maps container `8080` → host `ct115:3000`
- Edge-proxy forwards `8081` → `ct115:3000`
- Edge-proxy forwards `11435` → `ct113:11434`

**Port confusion is the #1 failure:**
- Do NOT forward to `ct115:8080` (that’s container-internal).
- Forward to `ct115:3000`.

**Determinism choice:**
- `ENABLE_PERSISTENT_CONFIG=false` so the UI doesn’t override env config.

**Model policy:**
- No models installed by default
- TinyLlama is a small test model (if needed later)

---

### 10.5 Invidious (CT114)
**CURRENT:** running; docker-compose stack at `/opt/invidious`.

**#1 pitfall:** YAML corruption when patching multi-line compose with sed/escaping via multiple shells.

**Rule:**
- Never patch multi-line YAML with sed one-liners through ansible/pct layers.
- Use a Python rewrite in-place (deterministic).

**Policy chosen:**
- `login_enabled: true`
- `registration_enabled: true`
- `captcha_enabled: false`
- `admins: ["adds666"]`
- `statistics_enabled: true`

**Extra Ansible gotcha:**
- `docker ps --format '{{.Names}}'` breaks because `{{ }}` gets parsed as Jinja.

---

### 10.6 Synapse (CT117)
**CURRENT:** running; exposed on `:8008` through edge-proxy.

Earlier migration had permission issues on data volume; resolved by fixing ownership/permissions.

---

## 11) Proxmox backups (lessons learned)

### 11.1 Jellyfin backup hang
A Jellyfin backup hung for many hours due to:
- snapshot method
- large bind mounts / metadata explosion / I/O

**Recommendation:**
- Avoid backing up huge metadata caches
- Consider separate volumes or exclude patterns if/when implemented
- Treat media data as NAS responsibility; back up configs and DBs intentionally

---

## 12) “We keep failing on this” — explicit anti-footguns

### 12.1 New CT bootstrap
**Failure:** `sudo: not found`, `Permission denied (publickey)`  
**Fix:** always run `ct_bootstrap.yml` before `base_lxc.yml`.

### 12.2 Directory inventory parsing
**Failure:** Ansible tries to parse backups as inventory → warnings/errors  
**Fix:** always pass `-i inventories/home/hosts.yml` and keep backups out of `inventories/home/`.

### 12.3 Docker in unprivileged LXC
**Failure:** OCI errors even though Docker looks installed  
**Fix:** apply `pve_docker_lxc_fix.yml` and ensure CT IDs are listed.

### 12.4 YAML patching via sed
**Failure:** compose breaks with `yaml.scanner.ScannerError` due to collapsed newlines/tabs  
**Fix:** use Python rewrites or full-file heredocs.

### 12.5 ProxyJump loops
**Failure:** “pve through pve” or wrong jump host after TS move  
**Fix:** verify current TS owner of `100.122.95.117` (should be CT110 now) and avoid loops.

### 12.6 Jellyfin blind rsync
**Failure:** moved huge caches/metadata → time + backup pain  
**Fix:** migrate only minimal config/data; exclude metadata/cache/transcodes.

### 12.7 n8n canonical URL
**Failure:** Cannot GET /setup, cookie/security errors  
**Fix:** one canonical URL; set N8N_* accordingly; disable secure cookie on HTTP.

### 12.8 Homepage NAS disk widget (“API error” / “Drive not found”)

**Symptom**
- Homepage web UI shows an API error or empty values for the NAS disk widget.
- Logs contain repeated warnings:
warn: <resources> Drive not found for target: /home/ubuntu/Global_Share


**Root cause (IMPORTANT)**
This was caused by confusing a **Proxmox Storage definition** with an **active Linux filesystem mount**.

- Seeing `Global_Share` under *Datacenter → Storage* in the Proxmox UI **does NOT guarantee** that
`/mnt/pve/Global_Share` is mounted at all times on the host.
- Proxmox may mount NFS storage **on demand** (e.g. during backups) and unmount it afterwards.
- Homepage’s Resources/Disk widget does a normal Linux filesystem check on the target path inside the container.
If the path is just an empty directory (not an NFS mount), Homepage cannot map it to a drive and warns.

**Canonical working configuration (CURRENT – do not diverge)**

- Proxmox storage:
nfs: Global_Share
server 192.168.1.84
export /volume1/Global_Share
path /mnt/pve/Global_Share


- Proxmox host (`/etc/fstab`) MUST contain:
192.168.1.84:/volume1/Global_Share /mnt/pve/Global_Share nfs vers=3,rw,hard,timeo=600,retrans=2,_netdev 0 0


- CT110 bind mount (`/etc/pve/lxc/110.conf`):
mp0: /mnt/pve/Global_Share,mp=/home/ubuntu/Global_Share,backup=0


- Homepage docker-compose (on CT110):
volumes:
- /home/ubuntu/Global_Share:/home/ubuntu/Global_Share:ro


**Verification checklist (in order)**
1. On Proxmox host:
findmnt -T /mnt/pve/Global_Share

Must show `nfs` (not ext4, not empty).

2. Inside CT110:
df -hT /home/ubuntu/Global_Share

Must show NAS size (≈10.5T), not the CT root disk.

3. Inside Homepage container:
docker exec homepage df -hT /home/ubuntu/Global_Share

Must show the same NFS filesystem.

**Operational notes / gotchas**
- `docker logs --tail` includes historical warnings. Use:
docker logs --since 3m homepage

to confirm whether the issue is still occurring.
- Restart CTs using:
pct stop <id>; pct start <id>

Do NOT assume `pct restart` exists on all Proxmox versions.
- When running remote SSH commands from `rog_ubuntu`, avoid local variable expansion.
Use a heredoc pattern:
ssh root@PVE 'bash -s' <<'BASH'
...
BASH


**Design rule (do not break)**
- NAS mounts belong to **Proxmox**, not inside LXCs.
- LXCs receive NAS access ONLY via bind mounts (`mpX:`).
- Containers receive NAS access ONLY via docker bind mounts.

---

## 13) History of major changes (why earlier docs differ)

### 13.1 Proxmox API provisioning → SSH pct provisioning
Earlier attempts used Proxmox API modules and failed repeatedly (token mangling / inconsistent module behavior).  
**Final decision:** use `pct` + `pveam` via SSH. Stable and proven.

### 13.2 UbuntuVM2 ingress → CT110 edge-proxy ingress
Earlier setup forwarded ports on UbuntuVM2.  
**Final decision:** move Tailscale + DNAT to CT110 to:
- reduce device count issues
- simplify topology
- centralise ingress

### 13.3 CT role naming drift
Some handovers list CT114 as “homepage” or CT115 as “n8n”.  
**Final correction:** CT114 is **Invidious**, CT115 is **OpenWebUI**, CT116 is **n8n**, matching service-specific handovers and DNAT mappings.

### 13.4 Debian 12 target vs current reality
Original design constraint: Debian 12 LXCs.  
Some CTs may have been created as Ubuntu during early migration pressure (e.g., Jellyfin handover explicitly notes Ubuntu inside CT111).  
**Target remains:** converge to Debian 12 over time, but do not destabilise working services just to “standardise”.

---

## 14) Current priority TODOs (safe next steps)

1. **Fix Ombi login** by restoring the full config directory DB set + keys.
2. **Migrate Homepage** (still pending; decide CT target and integrate behind edge-proxy).
3. **Plan Jellyfin minimal config migration** (LAN-only, deliberate excludes).
4. Add missing baseline packages (e.g., rsync) to `base_lxc` if still needed.
5. Remove any remaining reliance on deprecated UbuntuVM2 once data migrations are done.

---

## 15) Appendix — quick reference snippets

### 15.1 “If Docker is broken in an LXC”
Checklist:
- Is CT listed in `docker_lxc_ct_ids`?
- Did we run `pve_docker_lxc_fix.yml`?
- Did we **stop/start** the CT after config change?
- Does `/dev/fuse` exist inside CT?
- Is Docker using `fuse-overlayfs` (expected)?

### 15.2 “If Ansible can’t SSH to a CT”
Checklist:
- Is ProxyJump correct and not looping?
- Did `ct_bootstrap.yml` run?
- Is the admin user created and key installed?
- Is `sudo` installed?

### 15.3 “If YAML/compose broke after a ‘small patch’”
Assume sed/newline corruption.  
Prefer:
- full-file rewrite with heredoc, or
- Python script rewrite in-place.

---

# END
This file is the canonical handover for Usniverse.

---

## Jellyfin – Playback Failure Root Cause & Fix (CT111)

### Symptoms
- Jellyfin UI loads
- Libraries visible
- Playback fails immediately
- Logs show ffmpeg errors (e.g. “FFmpeg exited with code 254” and/or “No such file or directory”)

### Root Cause
This was NOT an ffmpeg, permissions, or transcode issue.

It was a PATH MISMATCH between Jellyfin library paths and the actual NAS directory layout.

Actual NAS layout:
- /mnt/Global_Share/Media/
  - Movies/
    - Feature Film/
    - TV Series/
  - Music/

Broken configuration (old):
- Mounted /mnt/Global_Share/Media -> /media
- Jellyfin TV library pointed at /media/TV Series
- But /media/TV Series does NOT exist
- Actual TV path was /media/Movies/TV Series

Result:
- Jellyfin tried to play files at /media/TV Series/... that were not present
- ffmpeg then fails opening input (looks like “ffmpeg problem”, but it’s just wrong paths)

### Correct & Durable Fix
Mount directories to match Jellyfin’s expected library paths.
Do NOT use nested mounts or symlinks as the permanent solution.

Final container mounts (read-only):
- /mnt/Global_Share/Media/Movies -> /media:ro
- /mnt/Global_Share/Media/Music  -> /music:ro

This provides:
- /media/TV Series/... ✅
- /media/Feature Film/... ✅
- /music/... ✅

### Explicit Warnings (Do NOT Do This)
- Do NOT mount /mnt/Global_Share/Media directly to /media if Jellyfin expects /media/TV Series
- Do NOT mount a subpath into a directory that is already a read-only mount (Docker cannot create mountpoints inside RO FS)
- Do NOT rely on symlinks inside read-only mounts except as a temporary diagnostic step

### Verification Commands (remote-safe)
- docker exec jellyfin ls -lah /media
- docker exec jellyfin ls -lah "/media/TV Series"
- docker exec jellyfin ls -lah "/media/Feature Film"
- docker exec jellyfin ls -lah /music
- docker logs jellyfin --tail=200

Playback should succeed immediately after container recreation.

---

## Operational Rule – Remote / Buffer-Safe CLI Usage (MANDATORY)

When operating remotely or over SSH with limited terminal buffers:

- Use single, self-contained command blocks
- Do NOT use interactive editors (nano/vi)
- Avoid complex nested quoting; prefer robust patterns (e.g. env vars, simple awk extraction)
- Prefer Python+YAML for deterministic config edits
- Avoid nested mounts and implicit directory creation inside containers

All future handover instructions MUST follow this rule.


### (Fix) Correct media paths this configuration provides
With the final mounts:
- /mnt/Global_Share/Media/Movies -> /media:ro
- /mnt/Global_Share/Media/Music  -> /music:ro

The container paths provided are:
- /media/TV Series/...          (maps to NAS: Media/Movies/TV Series)
- /media/Feature Film/...       (maps to NAS: Media/Movies/Feature Film)
- /music/...                    (maps to NAS: Media/Music)


---

## CT111 – Startup failure after resizing (mp1 host path missing)

### Symptom
`pct start 111 --debug` failed with:
- `Failed to run lxc.hook.pre-start`
- `directory '/opt/jellyfin/config/cache' does not exist`

### Root Cause
CT111 had:
- `mp1: /opt/jellyfin/config/cache,mp=/opt/jellyfin/config/cache,backup=0`

The source path is on the Proxmox host. If it does not exist, the pre-start hook aborts and the container will not start.

### Fix
mp1 was removed (it was not present in IaC repo sources, only in /etc/pve/lxc/111.conf).

If mp1 is ever reintroduced, ensure the host source directory exists first:
- `mkdir -p /opt/jellyfin/config/cache`


---

## Jellyfin (CT111) – Media mounts + metadata egress (Jan 2026)

### Playback fix: make library paths match NAS layout
Symptoms:
- Jellyfin attempted to open files under `/media/TV Series/...`
- ffmpeg failed because `/media/TV Series` didn’t exist in-container

Root cause:
- NAS layout is nonstandard: TV Series lives under:
  `/mnt/Global_Share/Media/Movies/TV Series/`

Fix:
- Mount Movies to `/media` and Music to `/music`:
  - `/mnt/Global_Share/Media/Movies:/media:ro`
  - `/mnt/Global_Share/Media/Music:/music:ro`
- Do NOT mount `/mnt/Global_Share/Media:/media:ro` (breaks expected layout)

Repo source-of-truth:
- `files/ct111/jellyfin/docker-compose.yml`

### Metadata/posters fix: container had no internet
Symptoms:
- Library scan finds items but no posters/metadata
- `docker exec jellyfin curl https://api.themoviedb.org` timed out

Root cause:
- Docker-in-LXC egress required NAT/forward rules on the *Proxmox host*
  that runs CT111 (not CT110 / edge proxy)

Fix on Proxmox host:
- Enable `net.ipv4.ip_forward=1`
- Enable `br_netfilter` and bridge sysctls:
  - `net.bridge.bridge-nf-call-iptables=1` (and ip6/arptables)
- Add nftables rules (example docker subnet was `172.18.0.0/16`):
  - NAT postrouting masquerade out `vmbr0`
  - Forward allow `172.18.0.0/16` and established/related return

Validation:
- After fix, container `curl -4 -I https://api.themoviedb.org` returned HTTP 301.

### After internet restored: force artwork refresh
Jellyfin UI:
- Dashboard → Libraries → (each library) → Refresh metadata
  - Replace all metadata
  - Replace existing images
  - Search for missing metadata
- Dashboard → Scheduled Tasks → run library/metadata tasks as needed

### Resource notes
Artwork/cache can grow `/opt/jellyfin/config` (esp cache).
CT111 at time of debug:
- rootfs: 256G
- memory: 2G

# Power Control & Usage Visibility (Edge‑Proxy ↔ ServerNode)

> **Purpose**
> This document captures the *current, working* implementation for:

* Wake‑on‑LAN (WOL)
* Remote shutdown
* Homepage UI controls (Wake / Shutdown)
* LAN + Tailscale–restricted webhook

This exists **before Ansible** so future automation does not re‑discover solved problems.

---

## Architecture Overview

```
[ Homepage UI ]
       |
       v
[ Edge‑Proxy ]
  - wol‑webhook (python + systemd)
  - nftables (LAN + tailscale0)
       |
       v
[ ServerNode ]
  - WOL enabled on NIC (eno2)
  - SSH forced command for shutdown
```

---

## Nodes

| Host       | Role         | IP            |
| ---------- | ------------ | ------------- |
| edge‑proxy | Control      | 192.168.1.110 |
| servernode | Power Target | 192.168.1.104 |

---

## Wake‑on‑LAN (ServerNode)

### NIC

* Interface: `eno2`
* MAC: `0c:c4:7a:ca:24:2b`
* WOL mode: `g`

### Persistent systemd unit

File:

```
/etc/systemd/system/wol-eno2.service
```

Purpose: ensure WOL survives reboot / shutdown.

---

## Shutdown Mechanism (ServerNode)

### User

* `edge-shutdown`
* Shell: `/bin/bash` (shell disabled by sshd ForceCommand)

### sshd Match block

File:

```
/etc/ssh/sshd_config.d/99-edge-shutdown.conf
```

```
Match User edge-shutdown
    ForceCommand sudo /sbin/poweroff
    PermitTTY no
    AllowTcpForwarding no
    X11Forwarding no
```

### sudoers

File:

```
/etc/sudoers.d/edge-shutdown
```

```
edge-shutdown ALL=(root) NOPASSWD: /sbin/poweroff
```

> **Why:** polkit blocks non‑root shutdown; sudo is the clean escalation.

---

## Edge‑Proxy Webhook

### Location

```
/opt/wol-webhook/server.py
```

### Endpoints

| Path        | Method   | Function        |
| ----------- | -------- | --------------- |
| `/wol`      | GET/POST | Send WOL packet |
| `/shutdown` | GET/POST | SSH → poweroff  |

### Environment

File:

```
/etc/wol-webhook/env
```

```
WOL_PORT=8787
WOL_TOKEN=***
```

### systemd service

```
/etc/systemd/system/wol-webhook.service
```

---

## Firewall (Edge‑Proxy)

### nftables table

```
/etc/nftables.d/wol-webhook.nft
```

Allows:

* localhost
* LAN: `192.168.1.0/24`
* Tailscale: `iifname "tailscale0"`

Blocks everything else to port `8787`.

---

## Homepage Integration

### Config path

Host path:

```
/opt/homepage/config/services.yaml
```

### Server Control tiles

```
- Server Control:
    - Wake ServerNode:
        icon: mdi-power
        href: http://192.168.1.110:8787/wol?token=...
        ping: 192.168.1.104

    - Shutdown ServerNode:
        icon: mdi-power-off
        href: http://192.168.1.110:8787/shutdown?token=...
        ping: 192.168.1.104
```

---

## Known Pitfalls (DO NOT REPEAT)

* ❌ Editing Homepage YAML with duplicate groups breaks UI silently
* ❌ Relying on `authorized_keys command=` alone (sshd ignored it)
* ❌ Using `nologin` shell for forced‑command users
* ❌ Forgetting sudo for shutdown → polkit denial
* ❌ Binding webhook without firewall rules

---

## Next Steps (Ansible)

This setup is now **stable** and ready to be automated.

Recommended Ansible split:

1. `role: wol_servernode`

   * enable WOL
   * install systemd unit

2. `role: shutdown_servernode`

   * user + sudoers
   * sshd Match block

3. `role: wol_webhook_edge`

   * python script
   * systemd service
   * env file

4. `role: firewall_edge`

   * nftables rules

5. `role: homepage_services`

   * render services.yaml

---

> **Status:** Working, tested end‑to‑end (LAN + Tailscale)
