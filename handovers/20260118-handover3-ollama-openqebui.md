# Handover 3 — Ollama + OpenWebUI (AI Services)

Date: 2026-01-18  
Scope: AI services (Ollama backend + OpenWebUI frontend), networking, security decisions  
Audience: Future ChatGPT agents or humans continuing this repo

---

## 1. Purpose of this handover

This document captures the final, working state of the Ollama + OpenWebUI setup, including:
- LXC layout
- Docker configuration
- Network and port-forwarding logic
- Security decisions
- Known pitfalls and “gotchas”

This setup works. Deviating from the documented ports or assumptions will likely break access.

---

## 2. High-level architecture

### Containers (LXCs)

| CT ID | Name       | Purpose |
|------:|------------|---------|
| 113   | ollama     | Ollama backend (CPU-only, no GPU) |
| 115   | openwebui  | OpenWebUI frontend |
| 110   | edge-proxy | Not used for OpenWebUI yet |
| jump host | UbuntuVM2 | External access via DNAT |

OpenWebUI and Ollama are intentionally deployed in separate LXCs for isolation.

---

## 3. Ollama (ct113)

- CPU-only deployment
- No models installed by default
- Service port: 11434
- Internal IP: 192.168.1.113

Safe validation endpoints (no downloads):
- /api/version
- /api/tags

External forwarding:
100.122.95.117:11435 → 192.168.1.113:11434

---

## 4. OpenWebUI (ct115)

- Docker-based deployment via Ansible
- Container port: 8080
- Host port on ct115: 3000
- Internal IP: 192.168.1.115

CRITICAL:
Do NOT forward traffic directly to 192.168.1.115:8080.
OpenWebUI is exposed on ct115:3000.

Correct path:
container:8080 → ct115:3000 → jump-host:8081

---

## 5. Environment configuration

The following environment variables are set intentionally:

- OLLAMA_BASE_URL=http://192.168.1.113:11434
- ENABLE_PERSISTENT_CONFIG=false

Persistent config is disabled to ensure deterministic behaviour and prevent UI-stored config from overriding env vars.

---

## 6. User registration & security

Default OpenWebUI behaviour allows open user registration.

Recommended for public or semi-public exposure:
- REGISTRATION_ENABLED=false

This prevents untrusted users from consuming CPU/RAM.

---

## 7. Jump host networking (UbuntuVM2)

DNAT rules:
- 8081 → 192.168.1.115:3000 (OpenWebUI)
- 11435 → 192.168.1.113:11434 (Ollama)

FORWARD rules must allow:
- tcp dpt:3000 → 192.168.1.115
- tcp dpt:11434 → 192.168.1.113

Other FORWARD rules (e.g. dpt:8080) belong to unrelated services and should not be removed without verification.

---

## 8. Homepage integration

OpenWebUI is exposed in Homepage under a GPTs section.

URL:
http://100.122.95.117:8081

Optional Ollama health endpoint:
http://100.122.95.117:11435/api/version

---

## 9. Hardware constraints

Host machine:
- MacBook Pro (2011)
- 8 GB RAM
- Multiple LXCs

Implications:
- CPU-only inference is slow but functional
- RAM is the primary constraint
- Avoid running all heavy services simultaneously

Recommended memory caps:
- ct113 (ollama): ~2 GB
- ct115 (openwebui): ~1–1.5 GB

---

## 10. Model policy

- No models installed by default
- System is ready but unloaded

TinyLlama (~637 MB) is the smallest practical test model if needed later.

---

## 11. Known pitfalls

1. Port confusion (8080 vs 3000) is the most common failure
2. OpenWebUI may appear disconnected when no models exist — this is normal
3. DNAT can be correct but still fail if the target port is wrong
4. Persistent config must be disabled for automation
5. Registration defaults are unsafe for public exposure

---

## 12. Current status

- Ollama reachable
- OpenWebUI reachable
- Frontend ↔ backend connectivity verified
- External access via jump host verified
- Repository state committed

This setup is stable within current hardware constraints.
