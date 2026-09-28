# Immich migration preflight — 2026-09-24

> Migration is now complete. See [final cutover handover](IMMICH_CUTOVER_2026-09-28.md) for current state; observations below record preparation stages.

Destination requested: MacBookPro CT112, for daytime access. ServerNode remains excluded as the production destination because of its overnight power schedule. No cutover or guest start has been performed.

## Read-only inventory

- UbuntuVM source is healthy, running Immich server and machine-learning v2.7.5. Deployment uses floating `release` tags; migration must pin the inspected image digests rather than pulling a potentially newer release.
- Database: PostgreSQL 14 / tensorchord pgvecto-rs pg14-v0.2.0, approximately 439 MB. Database is local to UbuntuVM's filesystem, not the photo bind mount.
- NAS media source: `/home/ubuntu/Global_Share/Adam/Photos`, exposed inside Immich at `/usr/src/app/upload`.
- All 27,093 original asset records and 49,840 generated-file records reference `/usr/src/app/upload`. There are two user records, zero album records and no external-library import paths in the baseline.
- An anonymous Docker volume is also mounted at `/data`, but is empty (4 KiB). Do not assume current upstream Compose paths match this installation: preserve the existing application-visible paths during migration.
- CT112 is stopped, `onboot: 0`, 4 vCPU, 4 GiB RAM, 32 GiB local-lvm root disk, and already has the NAS bind mount. Read-only debugfs inspection found no existing Docker containers or application volume directories; do a complete target backup before modifications.
- MacBookPro has 7.7 GiB total RAM and about 3.7 GiB available during inspection, with seven other running containers. Current Immich idle memory was about 1 GiB, but that does not establish adequate headroom for concurrent indexing, transcoding and machine learning. The saved machine-learning enable flags are unset, so they must not be assumed disabled; current upstream requirements call for 6 GiB for a smooth full-feature deployment (4 GiB with machine learning disabled).
- MacBookPro still has no quorum: only its own two votes are present out of six expected. No HA resources or replication jobs were configured. CT112 cannot be treated as a reliable always-on destination until startup/quorum is resolved.
- Toshiba is standalone and hosts UbuntuVM (VM100). It has only 5.7 GiB physical RAM, is heavily swapping, and has UbuntuVM configured with 7 GiB; this constrains restore-test throughput.

## Recovery work

A live, transaction-consistent PostgreSQL custom-format dump and private configuration/container metadata backup were created at `/home/ubuntu/immich-migration-preflight-20260924-143007` on UbuntuVM. The dump is 165,271,267 bytes. This is a preflight backup, not a coordinated final cutover snapshot.

The user explicitly approved an off-host copy, including credentials, to `/tmp/usniverse-immich-preflight/` on the ROG-Ubuntu workstation. This directory is private and must never be committed. `/tmp` is temporary storage, not a durable long-term backup destination.

A restore rehearsal uses only the separate database `immich_migration_restore_check_20260924`; the live database is not overwritten. Its script removes only that temporary database after a successful restore and count verification. Original-file readability verification passed: 27,093 of 27,093 originals readable, zero missing and zero other errors; total original bytes 186,956,058,770 (about 187 GB). This checks existence and access, not a content-checksum comparison. The copied dump matches the source SHA-256: `2f66a3b75d929a17742f0936323e7099daa481a74c45765cdb9678ac13f6bee0`. Both backup directory and parent are mode 0700; the dump is mode 0600. The full restore rehearsal passed: 27,093 assets, 49,840 generated-file records, two users, zero albums and zero libraries, matching the preflight baseline. The temporary restore-test database was then dropped; the live database and backup were retained.

## Remaining gates

- Database backup, full restore rehearsal, off-host dump checksum and original-file readability checks have passed. These do not replace an independent photo backup or final coordinated cutover snapshot.
- User confirmed there was no separate photo backup and approved creating one on ServerNode local ZFS. Copy and checksum verification passed on 2026-09-28; see IMMICH_BACKUP_2026-09-24.md. All 27,093 originals matched, with zero missing or mismatched originals and a held ZFS snapshot.
- Decide a sustainable RAM budget for CT112 and other MacBookPro workloads, accounting for peak jobs rather than idle use.
- Back up and resolve MacBookPro cluster membership/startup, preserve NAS mounts and existing services, and test reboot recovery.
- Rehearse the complete destination deployment against isolated storage before granting it write access to the live NAS paths.
- Only then arrange final consistent backup, single-writer cutover, URL preservation, functional/integrity verification and rollback retention.

Additional observations: Synology reports HyperBackup and SnapshotReplication packages not installed; this does not exclude another backup method. During the restore rehearsal, PostgreSQL used about 856 MiB and the live Immich server about 650 MiB. This is not a peak machine-learning or upload capacity test.

## Resumed preparation — 2026-09-28

MacBookPro still has two of six votes and no quorum; CT112 remains stopped. About 3.7 GiB RAM is available. The user has been asked to choose standalone operation versus repairing the remaining cluster. Private configuration archives and a SQLite configuration backup were created under `/root/usniverse-immich-preparation-20260928` on MacBookPro. A complete compressed backup of the stopped CT112 root disk has been started as `usniverse-ct112-preflight-backup.service`; confirm its successful completion before changes. The workstation temporary recovery directory is no longer present, so use the durable private recovery bundles on ServerNode. No cutover has occurred.

## Subsequent state

MacBookPro standalone conversion and CT112 startup succeeded; see MACBOOKPRO_STANDALONE_2026-09-28.md. CT112 root-disk backup integrity and SHA-256 passed. The isolated Immich rehearsal database restore and authenticated sample-original checks have passed; see IMMICH_REHEARSAL_2026-09-28.md for remaining checks. Earlier stopped/quorum-blocked observations above are historical.
