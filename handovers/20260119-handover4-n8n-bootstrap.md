# Handover 4 — New CT Bootstrap Fix + n8n (CT116)

Date: 2026-01-19  
Project: Usniverse  
Context: Repeated failures when onboarding new LXCs (SSH + sudo), fixed permanently.

---

## Purpose of this handover

This document exists to prevent **recurring bootstrap failures** that occur every time a new LXC (CT) is created.

Specifically:
- SSH access fails (`Permission denied (publickey,password)`)
- Ansible fails immediately with (`sudo: not found`)
- Inventory parsing warnings caused by backups inside inventory directories
- Confusion about when a CT is actually "ready" for `base_lxc`

This handover documents:
- The root causes
- The permanent fix
- The **correct, repeatable order of operations**
- Hard rules for future chats / agents

---

## Non-negotiable operator rules (READ FIRST)

### 1) CLI ONLY — no editors
- No nano/vim/interactive editors
- Files must be created/modified using CLI (cat heredocs / sed / awk)
- This avoids terminal buffer corruption and broken YAML

### 2) Commands must be delivered in SMALL copy/paste-safe blocks
- Large blocks often fail in chat UI
- Always split into logical steps

### 3) Always use file-based inventory
Bad:
  ansible-playbook -i inventories/home ...

Correct:
  ansible-playbook -i inventories/home/hosts.yml ...

Reason: directory inventory makes Ansible try to parse backups as inventory sources.

### 4) Never store backups inside inventories/home/
- Backups must go to inventories/_backups/
- Keep inventory dir clean (otherwise parse warnings/errors)

### 5) A CT is NOT ready until bootstrapped
New CTs may lack:
- SSH key for admin
- sudo package
- admin user
Therefore base_lxc/docker_host can fail before they can fix anything.


---

## Root cause of repeated new-CT failures

Every new CT initially failed with one or more of the following:

- SSH access failure:
  Permission denied (publickey,password)

- Privilege escalation failure:
  sudo: not found

### Why this happens

- Debian LXC templates often do NOT include sudo
- The admin user may not exist yet
- SSH public keys are not reliably injected at CT creation time
- base_lxc assumes:
  - SSH access already works
  - admin exists
  - sudo exists

Because of this, Ansible fails BEFORE it can fix the system.

This is not an Ansible bug.
It is a missing bootstrap step.


---

## Permanent fix implemented

A dedicated bootstrap playbook was created:

- playbooks/ct_bootstrap.yml

This playbook runs via Proxmox using pct exec, and makes a brand-new CT immediately usable by Ansible.

### What ct_bootstrap.yml does (per CT)

1) Installs required packages:
   - sudo
   - openssh-server

2) Ensures admin user exists:
   - creates admin if missing
   - adds admin to sudo group

3) Configures passwordless sudo:
   - writes /etc/sudoers.d/010-admin-nopasswd

4) Injects controller SSH key:
   - /home/admin/.ssh/authorized_keys
   - /root/.ssh/authorized_keys (fallback)

Result: no more "Permission denied" and no more "sudo: not found".


---

## Mandatory run order for every new CT (runbook)

1) Create CT via Proxmox (SSH-based pct)
   ansible-playbook -i inventories/home/hosts.yml playbooks/lxc_ssh.yml --limit pve

2) Bootstrap CT for Ansible (ONE TIME per CT)
   ansible-playbook -i inventories/home/hosts.yml playbooks/ct_bootstrap.yml

3) Apply baseline role
   ansible-playbook -i inventories/home/hosts.yml playbooks/base_lxc.yml --limit ctXXX

4) Apply docker role (if needed)
   ansible-playbook -i inventories/home/hosts.yml playbooks/docker_host.yml --limit ctXXX

If step 2 is skipped, steps 3-4 may fail immediately.


---

## Mandatory run order for every new CT (runbook)

1) Create CT via Proxmox (SSH-based pct)
   ansible-playbook -i inventories/home/hosts.yml playbooks/lxc_ssh.yml --limit pve

2) Bootstrap CT for Ansible (ONE TIME per CT)
   ansible-playbook -i inventories/home/hosts.yml playbooks/ct_bootstrap.yml

3) Apply baseline role
   ansible-playbook -i inventories/home/hosts.yml playbooks/base_lxc.yml --limit ctXXX

4) Apply docker role (if needed)
   ansible-playbook -i inventories/home/hosts.yml playbooks/docker_host.yml --limit ctXXX

If step 2 is skipped, steps 3-4 may fail immediately.


---

## Inventory parsing gotcha (recurring warnings)

Problem:
- Using "-i inventories/home" (directory) makes Ansible parse every file in that folder as inventory.
- Backup files like hosts.yml.bak.TIMESTAMP inside inventories/home trigger parse warnings/errors.

Permanent rules:
- Always use file inventory:
  ansible-playbook -i inventories/home/hosts.yml ...
- Store backups outside inventories/home:
  inventories/_backups/


---

## CT116 (n8n) notes

- CT ID: 116
- Purpose: n8n service container + repeatable Ansible lifecycle test target
- Fresh install (no migration)
- Intended exposure: behind edge proxy (CT110)

CT116 was used to:
- reproduce the new-CT failures reliably
- validate ct_bootstrap.yml solves them
- establish a repeatable pattern for future service LXCs

## n8n deployment (CT116)

- CT ID: 116
- Service: n8n
- Runtime: Docker inside unprivileged LXC
- Compose path: /opt/n8n/docker-compose.yml
- Data path: /opt/n8n/data  ->  /home/node/.n8n (inside container)
- Default port: 5678

The n8n container runs as user `node` (UID 1000).

**Important:** the host bind-mounted data directory MUST be owned by UID 1000:
chown -R 1000:1000 /opt/n8n/data
If permissions are wrong, n8n will crash-loop with:
`EACCES: permission denied, open '/home/node/.n8n/config'`.

---

## n8n canonical URL rule (CRITICAL)

n8n **must be accessed via a single canonical URL** that matches ALL of:
- N8N_HOST
- N8N_EDITOR_BASE_URL
- WEBHOOK_URL
- N8N_PROTOCOL

Mixing access paths (e.g. LAN IP + forwarded IP + HTTPS hostname) WILL break:
- /setup
- /signin
- cookie handling
- SPA routing

Example failure symptom:
- Browser shows: `Cannot GET /setup`

Rule:
> One n8n instance = one canonical URL at a time.

When testing on LAN:
- Use LAN IP in all N8N_* vars
- Access only via LAN IP

When forwarding or proxying:
- Switch all N8N_* vars to the forwarded/proxied hostname
- Access only via that hostname

## HTTP vs HTTPS and secure cookies

n8n defaults to **secure cookies**, which REQUIRE HTTPS.

If accessing over HTTP (temporary / internal / port-forwarded):

N8N_PROTOCOL=http
N8N_SECURE_COOKIE=false

If accessing over HTTPS (recommended, via edge proxy):

N8N_PROTOCOL=https
N8N_SECURE_COOKIE=true

If misconfigured, browser error will say:
"Your n8n server is configured to use a secure cookie..."



---

## Ansible / Docker gotchas encountered (n8n)

1) Ansible shell defaults to /bin/sh  
   - `set -o pipefail` will FAIL unless wrapped in:
     ```
     bash -lc '...'
     ```

2) Docker in unprivileged LXC requires Proxmox-side config  
   - Handled by: playbooks/pve_docker_lxc_fix.yml
   - CT must be STOPPED and STARTED (reboot is insufficient)

3) ProxyJump must NOT apply to LAN LXCs  
   - ProxyJump scoped to proxmox group only
   - LXCs connect directly over LAN

