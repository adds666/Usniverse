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

