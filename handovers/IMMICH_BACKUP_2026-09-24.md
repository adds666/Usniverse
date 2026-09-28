# Immich independent backup — 2026-09-24

User approved a private backup of the complete Immich NAS folder onto ServerNode's actual local storage. This is a backup, not an application migration: the NAS remains live storage and UbuntuVM continues serving Immich. MacBookPro CT112 remains the proposed migration target.

## Destination and protection

- Local ZFS dataset: `rpool/immich-backup`, mounted at `/srv/immich-backup`.
- Parent permissions: 0700, accessible only to host root. Recovery files and logs are private. No photo data, database dumps or credentials belong in Git.
- Dataset uses lz4 compression, atime off and a 350 GiB quota. Pool initially had about 763 GiB available; source folder measured 221,773,712 KiB (about 212 GiB).
- `media/` receives the entire NAS Immich folder, including originals and generated/supporting content.
- `recovery/` contains the previously restore-tested preflight backup and a fresh matching database/manifest bundle.
- Scheduled 06:30 shutdown is temporarily stopped. The verifier restarts that timer only after successful verification and snapshot protection. On failure, data is retained and shutdown stays paused for investigation.

## Consistent database and original checksums

Fresh source recovery bundle: `/home/ubuntu/immich-servernode-backup-20260924` on UbuntuVM, copied into the backup's `recovery/` directory.

A read-only repeatable-read PostgreSQL transaction exported its snapshot. Both `pg_dump --snapshot` and the original-file checksum manifest used that same snapshot. The application did not need to stop. It contains 27,093 original-file records with SHA-1 checksums.

Fresh dump SHA-256, checked on both source and ServerNode:

`e3f6cedf0f886b9034bb03edfcf293d85ca99b4791932c8f0417de06a93be949`

The earlier preflight dump was fully restored successfully. The new dump has been transfer-checksummed; the photo verification job must finish before declaring the overall backup verified.

## Copy and verification jobs

The first attempt used the existing media NFS mount and did not show useful throughput. The backup now reads through a separate **read-only** NFSv3/TCP mount at `/mnt/immich-backup-source`, with `/Adam/Photos` as its source. Existing live application mounts were left unchanged. The dedicated mount's read-ahead was increased from 128 KiB to 4096 KiB for sequential WAN reads.

- `usniverse-immich-backup-copy.service`: rsync copy, preserving metadata and hard links, no `--delete`, no source changes.
- `usniverse-immich-backup-verify.service`: queued after copying. Runs a final reconciliation pass, checks every backed-up original against its recorded Immich SHA-1, and creates a SHA-256 manifest of all regular backup files.
- Only if originals have zero mismatches and zero missing files does it create `rpool/immich-backup@verified-<UTC timestamp>` and apply the ZFS hold `immich-recovery`.
- It then releases the temporary read-only source mount and resumes the original shutdown timer.

Status and evidence are stored locally on ServerNode:

- `/srv/immich-backup/status.json`
- `/srv/immich-backup/verification.json` after verification
- `/srv/immich-backup/backup-files.sha256.jsonl`
- `/srv/immich-backup/logs/`

Workers are stored at `/srv/immich-backup/copy.py` and `verify.py`. These are transient systemd jobs: they survive SSH disconnects, but should not be assumed to resume automatically after a host reboot. Leave ServerNode powered on until verification completes. If interrupted, inspect status and source mounts before restarting; preserve existing partial data and do not delete the NAS originals.

## Status at handover

Verified completion confirmed on 2026-09-28 at 00:56 UTC (01:56 UK). All 27,093 originals matched; zero missing originals and zero checksum mismatches. Hashed 78,195 files totalling 227,453,326,001 bytes. Snapshot `rpool/immich-backup@verified-20260928T005600Z` exists with the `immich-recovery` retention hold. The database and original manifest share a consistent snapshot. This completes the independent backup gate; a fresh coordinated recovery point is still needed at final cutover.
