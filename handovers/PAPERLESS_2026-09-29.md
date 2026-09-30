# Paperless deployment — 2026-09-29

Deployment completed and validated on 2026-09-30.

Paperless is intended for private collections per person, reached through the existing Usniverse Tailscale frontend. Administrators can access every collection; this is application-level separation, not encryption against the system administrator.

- MacBookPro CT113: unprivileged Debian 12, 192.168.1.113, 2 CPUs, 2 GiB RAM, 512 MiB swap, 24 GiB local disk.
- Frontend: https://edge-proxy.taildb07f.ts.net:8443 through CT110 Tailscale Serve, forwarding to a loopback-only socket on port 8013 and then CT113:8000. No Funnel/public-internet route.
- Branding: Usniverse Documents; links on Homepage and Dashy.
- Documents: Synology `/volume1/Global_Share/Paperless/media`, mounted through MacBookPro at `/mnt/pve/Global_Share/Paperless/media`, CT113 `/mnt/paperless-media`, Docker `/usr/src/paperless/media`.
- Database, broker and search data: local `/opt/paperless` in CT113. Paperless-ngx 3.2.1, PostgreSQL 18 and Valkey 9; all three images are pinned by digest.
- NAS directory permissions are 0700. Existing NAS export maps client UIDs to NAS UID1024; the mapped application UID was explicitly tested for write access. No export-policy or other NAS-directory changes were made.
- Web application runs as UID1000 without root. OCR uses one worker and one thread to fit the always-on host.
- Host LXC boot and application startup require the NAS marker. They must not silently create a local substitute media store.

## Deployment and reconciliation

```
ansible-playbook -i inventories/home/hosts.yml playbooks/paperless_deploy.yml
```

This provisions CT113, installs Docker and the application, configures the existing frontend, schedules backups, and adds dashboard links. It preserves existing passwords, documents, dashboards and unrelated Tailscale routes. Existing CT113 must identify as Paperless; an unrelated CT is rejected. The dashboard helper changes only the Paperless entries.

Private credentials are generated on CT113, not in Git. `/opt/paperless/.env` holds the application/database credentials. `/opt/paperless/initial-credentials.json` contains initial administrator and personal-account logins. Do not add these files, database dumps, document contents or live dashboard configurations to Git.

## Accounts and privacy

Initial administrator: `usniverse-admin`. Personal account: `adam`, in `Usniverse Members`.

Use the personal account for ordinary document work. Create friends through the administrator's Users & Groups screen: give each person a unique username/password, leave staff and superuser disabled, and add them to `Usniverse Members`. The group permits document management and UI settings, but not user/group administration, global configuration, workflows, shared mail rules or global monitoring. Permissions on individual documents remain owner-scoped.

Anonymous signup and social signup are disabled. The shared consumption-folder watcher is disabled: browser/API uploads belong to the uploader rather than producing ownerless documents. Users should retain the default private permissions unless deliberately sharing. NAS and Paperless administrators can still access documents. Friends need Tailscale access to the existing edge-proxy node and HTTPS port 8443.

## Recovery

Nightly backup at 03:15 Europe/London on MacBookPro. The script briefly stops Paperless and its broker, dumps PostgreSQL in custom format, and archives local application state/configuration plus NAS media. It always attempts to restart the application afterwards. Recovery copies are private under `/mnt/pve/Global_Share/Paperless/backups/<UTC timestamp>/` and have gzip validation and SHA-256 records. The duration of the maintenance interval grows with document volume.

These copies protect against application/host problems and document deletion; they are on the same NAS as the originals and do not cover NAS failure. Retention is not automatically destructive; review capacity as the collection grows. Keep an independent NAS backup for hardware-loss recovery.

For restoration, stop the application, preserve current files, restore the matching application and media archives and PostgreSQL dump together, and use the archived Compose image versions. PostgreSQL data itself stays local; never place its live directory on NFS. Restore ownership for local application directories to UID1000; retain the existing NAS UID mapping. Validate login, permissions and original-file checksums before reopening access.

## Validation

Passed: healthy application/database/broker; HTTPS token and browser-session login; member UI; anonymous API denied; synthetic PDF upload and OCR consumption; original download SHA-256 matched; NAS-backed source file present; a second member could neither list, read, download nor view the first member's upload task; member account administration denied. Temporary test users and documents were removed.

The complete deployment playbook was rerun successfully with **zero changed tasks** on CT110, CT113 and MacBookPro. The first scheduled recovery snapshot is `20260930T021501Z`; both compressed archives passed integrity checks and all three files have SHA-256 records in `verified.json`. PostgreSQL `pg_restore --list` also read the database dump successfully.

The user approved a private workstation credential copy at `/tmp/usniverse-paperless/initial-credentials.json`, mode 0600. This is temporary delivery storage, not a durable backup.
