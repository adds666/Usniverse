#!/bin/bash
set -euo pipefail
umask 077
cd /opt/immich-rehearsal
test ! -e restore-complete.json
echo 'e3f6cedf0f886b9034bb03edfcf293d85ca99b4791932c8f0417de06a93be949  recovery.dump' | sha256sum -c -
docker compose -f compose.json up -d database redis
for i in $(seq 1 60); do
 if docker compose -f compose.json exec -T database pg_isready -U postgres -d immich >/dev/null; then break; fi
 sleep 2
done
existing=$(docker compose -f compose.json exec -T database psql -U postgres -d immich -Atc "select count(*) from information_schema.tables where table_schema='public'")
test "$existing" = 0
docker compose -f compose.json exec -T database pg_restore --exit-on-error --no-owner -U postgres -d immich < recovery.dump >restore.log 2>&1
docker compose -f compose.json exec -T database psql -U postgres -d immich -Atc 'select json_build_object('\''assets'\'',(select count(*) from asset),'\''files'\'',(select count(*) from asset_file),'\''users'\'',(select count(*) from "user"),'\''albums'\'',(select count(*) from album));' > restore-complete.json
docker compose -f compose.json up -d immich-server
