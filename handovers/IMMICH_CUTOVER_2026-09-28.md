# Immich migration completed — 2026-09-28

Immich v2.7.5 now runs on **MacBookPro CT112**. New browser/phone address: **http://100.69.158.73:2283** while connected to Tailscale. Existing accounts and library were retained. Photos remain on the NAS at `/volume1/Global_Share/Adam/Photos`; the application sees the unchanged `/usr/src/app/upload` path.

## Deployment

- MacBookPro: `root@100.69.158.73`, standalone Proxmox. CT112: `192.168.1.112`, 4 vCPU, 4 GiB RAM, 32 GiB local root disk, unprivileged.
- CT112 NAS bind: `/mnt/pve/Global_Share` → `/mnt/Global_Share`, writable, `backup=0`. Photo ownership was not changed.
- Production directory: `/opt/immich`, Compose project `immich`, enabled `immich.service`. PostgreSQL data, persistent Redis data and model cache are local under that directory.
- `immich-tailscale.socket` on MacBookPro listens only on `100.69.158.73:2283`; `systemd-socket-proxyd` forwards to CT112 port 2283. Socket enabled for boot.
- Server/ML image digests and PostgreSQL/Redis versions are pinned to the source deployment. Normal NAS mount checks are enabled; rehearsal-only bypasses are absent.
- Restored ML endpoint changed from unreachable `192.168.1.219:3003` to local `immich-machine-learning:3003`. Enabled features preserved. Job concurrency is 1, FFmpeg threads 2 and ML threads limited for host capacity.
- CT112 onboot enabled, startup order 20. Host pve-guests requires the NAS mount. MacBookPro full reboot recovered all eight guests; the actual production stack also passed a subsequent CT112 reboot.

## Verification

Final frozen database: **27,095 assets, 49,844 generated-file records, two users, zero albums**. Target restore matched these counts exactly.

All **27,095 original checksums matched** the final manifest. **78,048 database-referenced media files** were hashed, including derivatives, sidecars, person thumbnails and profile images. No references were missing and no originals needed repair. The full-folder warm backup had completed; a redundant final NAS directory scan was stopped in favour of direct database-referenced verification to avoid prolonged metadata traversal over the remote link.

Five recent originals downloaded through the production API matched their checksums. A synthetic image uploaded, downloaded and was deleted successfully; asset count returned to 27,095. Rehearsal ML inference passed. Production server and ML are healthy, with no OOM kills or restart loops observed. Final host check showed about 3.6 GiB available and no swap use. This is not a guarantee for arbitrary simultaneous bulk workloads.

Web UI HTTP 200, API ping and v2.7.5 version were verified from the workstation over Tailscale after restart. Dashy's existing link was changed to the new URL and verified in its served configuration. Homepage had no Immich entry to update.

## Recovery

ServerNode's **local ZFS** retains these held snapshots:

- `rpool/immich-backup@verified-20260928T005600Z` — original full-folder backup, earlier consistent DB/manifest.
- `rpool/immich-cutover-backup@verified-20260928T140500Z` — final 27,095-original recovery point, final DB/manifest and Redis state. Hold: `immich-recovery`.

- `rpool/immich-cutover-backup@deployed-20260928` — final deployed configuration and credentials archive, protected by the same hold. Archive SHA-256: `6be658bcb4fe436f31ae5ceb124b9aea1db7eb96e44da860beb4dd1029d52091`.

Final recovery directory: `/srv/immich-cutover-backup/recovery/cutover-20260928`. Final DB SHA-256: `7312305b71e69d7e86ed6e495ed4cc29a2272f33ec5bdf62e19adb6b1f6aaced`. Frozen Redis SHA-256: `a70c1f755804b0effdbe89b5a808c80eedf265c829ae1d8b33b2819b4e39177b`. Redis was restored to preserve pending jobs. Final reports: `/srv/immich-cutover-backup/status.json`, `cutover-verification.json`, `cutover-files.sha256.jsonl`.

Private host rollback/staging directory: `/root/usniverse-immich-preparation-20260928` on MacBookPro. Includes pre-change host configuration, validated original CT112 disk image, final source bundle and deployed configuration archive. Source bundle also remains at `/home/ubuntu/immich-cutover-20260928` on UbuntuVM. Workstation `/tmp/usniverse-immich-preflight` is temporary, not durable recovery storage. Credentials, DB dumps, file manifests and photos must never enter Git.

ServerNode's temporary read-only backup mount was released and its normal shutdown timer restored. The independent media backups are migration recovery points, not a newly configured recurring photo-backup schedule. Existing Immich and Proxmox backup schedules remain separate.

## Retired source and rollback

All four old Immich containers on UbuntuVM are stopped with restart policy `no`; their data/configuration remain intact. **Dashy remains running on UbuntuVM.** Retirement note: `/home/ubuntu/IMMICH_MOVED_20260928.md`.

Never start the stale source application against the shared NAS while CT112 is running. After accepting target uploads, rollback requires stopping target writes and transferring a current target database recovery point; simply starting the old database would omit later changes. Do not delete the source data or held snapshots during acceptance.

## Automation

`playbooks/immich_ct112.yml` reconciles an already restored and production-validated deployment through MacBookPro's `pct` commands. It refuses to operate without validation, private environment files and an existing PostgreSQL data directory. It does not initialize, overwrite or automatically restore a database. Pinned Compose/systemd configuration is under `files/immich`; guarded migration/check scripts are under `scripts/immich`.

Run: `ansible-playbook -i inventories/home/hosts.yml playbooks/immich_ct112.yml`.

Syntax check and a live reconciliation passed with zero failures. Secrets stay in private `server.env`/`database.env` files on CT112 and in private recovery archives, not in the repository.
