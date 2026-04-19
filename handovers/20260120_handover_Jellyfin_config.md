# Handover 3 – Proxmox / Ansible / LXC / Service Migration State

Date: 2026-01-20

> Historical snapshot: superseded by `handovers/USNIVERSE_MASTER_HANDOVER.md`.
> Keep for migration/debug history only. If it conflicts with current docs, the master handover wins.

This document **supersedes and extends** handover1 + handover2. It is written so that a *fresh agent* can take over without any prior context.

---

## GLOBAL RULES (DO NOT BREAK)

1. **CLI ONLY** – never suggest nano/vim/editors. All changes must be via shell commands.
2. **Single unbroken code blocks** when providing commands (ChatGPT UI truncates otherwise).
3. **Assume remote execution** unless explicitly stated local.
4. **Idempotency matters** – always check before mutating state.
5. **Proxmox is authoritative** for mounts, snapshots, backups.

---

## NETWORK & ACCESS MODEL (CRITICAL)

### Topology

```
[ You ]
   │
   │ (SSH)
   ▼
UbuntuVM2 (Tailscale)
   │
   │ ProxyJump
   ▼
Proxmox (pve) – 100.69.158.73
   │
   └── LXC LAN (192.168.1.0/24)
        ├─ ct110 edge-proxy
        ├─ ct111 jellyfin
        ├─ ct112 immich
        ├─ ct113 ollama
        ├─ ct114 invidious
        ├─ ct115 openwebui
        ├─ ct116 n8n
        └─ ct117 synapse
```

### SSH ProxyJump (MANDATORY WHEN REMOTE)

Defined in:
```
inventories/home/group_vars/lxc/ssh.yml
```

```yaml
---
ansible_ssh_common_args: "-o ProxyJump=ubuntu@100.122.95.117,root@100.69.158.73"
```

If CTs suddenly become unreachable → **this file is the first thing to check**.

---

## LXC CREATION MECHANISM

LXCs are **only** created via:

```
playbooks/lxc_ssh.yml
```

Backed by:

```
inventories/home/group_vars/lxc.yml
```

### NEVER manually `pct create` outside Ansible.

If a CT exists but is not in inventory → inventory is wrong.
If inventory exists but CT missing → rerun `lxc_ssh.yml`.

---

## BASE LXC BOOTSTRAP FAILURES (COMMON PITFALL)

### Problem 1: `sudo: not found`

Fresh Debian LXCs **do not ship sudo**.

Fix (first run only):

```bash
apt-get update -y && apt-get install -y sudo openssh-server
```

This is now handled inside the bootstrap flow.

---

### Problem 2: SSH works as root but not admin

Cause: admin user + SSH key not yet provisioned.

Resolution used on ct117 (synapse):

- create admin user
- install sudo
- install SSH key
- enable ssh

This MUST be automated later (role candidate).

---

## DOCKER IN UNPRIVILEGED LXC (VERY IMPORTANT)

### Symptom

```
OCI runtime create failed
open sysctl net.ipv4.ip_unprivileged_port_start: permission denied
```

### Cause

Unprivileged LXC missing fuse + apparmor relaxations.

### Canonical Fix Playbook

```
playbooks/pve_docker_lxc_fix.yml
```

This:
- loads fuse
- bind-mounts /dev/fuse
- relaxes apparmor
- enables proc/sys rw
- restarts affected CTs

### IMPORTANT

You must **add new Docker LXCs** to:

```yaml
docker_lxc_ct_ids:
```

Failure to do so WILL break Docker later.

---

## NAS / GLOBAL_SHARE HANDLING (DO NOT MOUNT NFS IN LXC)

### Source of Truth

- NAS mounted **ON PROXMOX ONLY**:

```
/mnt/pve/Global_Share
```

### Correct LXC Access Pattern

Bind-mount from Proxmox into LXC:

```bash
pct set <CTID> -mp0 /mnt/pve/Global_Share,mp=/mnt/Global_Share
```

### DO NOT

- ❌ mount NFS inside LXC
- ❌ add fstab entries inside LXC

### Services using Global_Share

- ct111 jellyfin (media)
- ct112 immich
- ct113 ollama
- ct116 n8n (future workflows)

---

## SERVICE STATE (AS OF NOW)

### ct110 – edge-proxy
- Running
- Will later absorb all port-forwarding

### ct111 – jellyfin
- Running
- **Config migration NOT COMPLETE**
- UbuntuVM2 Jellyfin config is ~170GB (!!)
- Only *minimal* config should be migrated:
  - users/
  - plugins/
  - data/root
  - NOT metadata cache

### ct112 – immich
- Running
- Uses Global_Share bind mount

### ct113 – ollama
- Running
- Docker-in-LXC fixes applied

### ct114 – invidious
- Running

### ct115 – openwebui
- Running

### ct116 – n8n
- Running
- Uses Docker Compose in `/opt/n8n`
- `N8N_SECURE_COOKIE=false` applied for HTTP
- Edge-proxy TLS to be added later

### ct117 – synapse

- Newly created
- Docker Compose at `/opt/synapse`
- Data migrated imperfectly (permissions need cleanup)
- Currently listening on **8008**
- Restart loops previously caused by `/data` permissions

---

## PORT FORWARDING (TEMPORARY – UBUNTUVM2)

Jellyfin is currently exposed via UbuntuVM2 using **iptables DNAT**.

### Active Rules (UbuntuVM2)

```bash
iptables -t nat -A PREROUTING -p tcp --dport 8096 \
  -j DNAT --to-destination 192.168.1.111:8096

iptables -A FORWARD -p tcp -d 192.168.1.111 --dport 8096 -j ACCEPT
iptables -A FORWARD -p tcp -s 192.168.1.111 --sport 8096 -j ACCEPT

iptables -t nat -A POSTROUTING -s 192.168.1.111 -j MASQUERADE
```

### This will be REMOVED once edge-proxy takes over.

---

## PROXMOX BACKUPS (KNOWN ISSUE)

### Jellyfin Backup Hung for ~19 Hours

Cause:
- Snapshot backup
- Large bind mounts
- Jellyfin metadata explosion

Resolution:
- Job interrupted manually
- Proxmox later skipped bind mounts correctly

### Lesson

- Jellyfin CT should eventually:
  - exclude metadata cache
  - or move metadata to separate volume

---

## CURRENT PRIORITIES (NEXT AGENT)

1. **Finish Jellyfin config migration** (selective, not full)
2. Fix Synapse data permissions cleanly
3. Move all port forwarding into edge-proxy
4. Remove UbuntuVM2 from serving path
5. Convert remaining manual fixes into Ansible roles

---

## FINAL NOTE

If something "mysteriously" breaks:

1. Check ProxyJump
2. Check Docker LXC fix applied
3. Check Proxmox bind mounts
4. Assume permissions, not networking

This system is stable **when treated declaratively**.
