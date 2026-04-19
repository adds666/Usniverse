# Invidious (CT114) Handover

Scope: This file documents ONLY the CT114 Invidious deployment + fixes (no other handovers).

> Historical snapshot: superseded by `handovers/USNIVERSE_MASTER_HANDOVER.md`.
> Keep for migration/debug history only. If it conflicts with current docs, the master handover wins.

Location in CT114: /opt/invidious
Service: Invidious + Postgres + Invidious Companion via docker-compose

## Key pitfall: YAML indentation + newline collapsing

We hit repeated failures where attempts to insert multiple config keys via sed inside:
- host -> ansible -> pct exec -> bash -lc -> sed

caused newlines to collapse into a single long line, or introduced a TAB.
This breaks YAML and docker-compose fails.

Symptom:
    docker-compose up -d
    yaml.scanner.ScannerError: mapping values are not allowed here

Avoid writing multi-line YAML via sed one-liners.
Use a Python rewrite inside the LXC instead.

## Selected login/registration policy

User requirements:
- Anyone can create a login: registration enabled
- No captcha: captcha disabled
- Admin user: adds666
- Statistics: enabled

Invidious config keys:
    login_enabled: true
    registration_enabled: true
    captcha_enabled: false
    admins: ["adds666"]
    statistics_enabled: true

## Safe patch method (recommended)

Run from host (ROG-Ubuntu) to patch CT114 without YAML corruption.

1) Backup compose file and patch with python3:
    ansible pve -i inventories/home -b -m shell -a "pct exec 114 -- bash -lc 'cd /opt/invidious && cp -av docker-compose.yml docker-compose.yml.bak.$(date +%F_%H%M%S) && python3 - <<\"PY\"
from pathlib import Path
import re

p = Path(\"docker-compose.yml\")
txt = p.read_text()

# Keys we manage (we remove any existing occurrences to avoid duplicates)
keys = [
  \"login_enabled\",
  \"registration_enabled\",
  \"captcha_enabled\",
  \"admins\",
  \"statistics_enabled\",
]

# Strip existing managed keys
txt = \"\\n\".join(
    line for line in txt.splitlines()
    if not re.match(r\"^[\\t ]*(%s):\" % \"|\".join(map(re.escape, keys)), line)
) + \"\\n\"

lines = txt.splitlines(True)
out = []
inserted = False

# Insert right after the first hmac_key line inside INVIDIOUS_CONFIG block
for line in lines:
    out.append(line)
    m = re.match(r\"^(\\s*)hmac_key:\\s*.*$\", line)
    if m and not inserted:
        indent = m.group(1)
        out += [
            f\"{indent}login_enabled: true\\n\",
            f\"{indent}registration_enabled: true\\n\",
            f\"{indent}captcha_enabled: false\\n\",
            f\"{indent}admins: [\\\"adds666\\\"]\\n\",
            f\"{indent}statistics_enabled: true\\n\",
        ]
        inserted = True

if not inserted:
    raise SystemExit(\"ERROR: Could not find hmac_key line to anchor insertion\")

p.write_text(\"\".join(out))
print(\"OK: patched docker-compose.yml\")
PY'"

2) Validate config parses:
    ansible pve -i inventories/home -b -m shell -a "pct exec 114 -- bash -lc 'cd /opt/invidious && docker-compose config >/dev/null && echo OK'"

3) Restart stack:
    ansible pve -i inventories/home -b -m shell -a "pct exec 114 -- bash -lc 'cd /opt/invidious && docker-compose down && docker-compose up -d && docker-compose ps'"
## Operations

Check status (run inside CT114):
    cd /opt/invidious
    docker-compose ps
    docker-compose logs --tail=120 invidious
    docker-compose logs --tail=120 companion

API sanity check (jq not installed):
    curl -fsS http://127.0.0.1:3000/api/v1/stats | head -c 800; echo

## Ansible/Jinja gotcha
Do not use docker --format strings containing:
    {{.Names}}
via ansible -m shell, because Jinja tries to template {{ ... }} and errors.
