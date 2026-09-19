# Media migration — verified state on 2026-09-19

This replaces the earlier in-progress notes in this file. Existing unrelated workspace changes were preserved. The automation closeout is recorded below.

## Running services

| Service | Target | Verified data / state |
| --- | --- | --- |
| Sonarr | CT122, 192.168.1.122:8989 | 37 series; TV Series and Kids TV roots accessible |
| Radarr | CT123, 192.168.1.123:7878 | 504 movies; all five library roots accessible; version 6.4.4.10685 |
| Lidarr | CT124, 192.168.1.124:8686 | 275 artists; music root accessible; version 3.1.0.4875 |
| Prowlarr | CT127, 192.168.1.127:9696 | Application connection tests passed for all three Arr apps; manual download client also redirected |
| FlareSolverr | CT128, 192.168.1.128:8191 | Existing Prowlarr proxy URL retained |
| qBittorrent + Gluetun | CT129, 192.168.1.129:8080 | All 24 original torrent identities verified; 23 completed/seeding and one incomplete; no missing-file/error states; VPN healthy and connection status connected |

All four download-client tests (Sonarr, Radarr, Lidarr and Prowlarr) passed against CT129:8080. Their old display name `UbuntuVM` remains, but the endpoint is now CT129.

## Storage and paths

Servernode uses PVE-managed `Global_Share_Servernode`: `100.84.166.81:/volume1/Global_Share` at `/mnt/pve/Global_Share_Servernode`.

CT122/123/124/129 have verified live NFS-backed mounts at `/mnt/Global_Share`. CT123/124/129 were restarted only after preventing placeholder app startup.

Compatibility Docker mounts preserve the original database paths without moving library media:

- Sonarr and Radarr: `/mnt/Global_Share/Media/Movies` to `/volume1/Global_Share/Media/Movies`.
- Lidarr: `/mnt/Global_Share/Media/Music` to `/volume1/Global_Share/Media/Music`.
- Existing `/tv`, `/movies` and `/music` aliases remain.
- qBittorrent `/downloads` maps to NAS `Media/Torrents_Unsorted`; default save path remains `/downloads/radarr`.
- qBittorrent `/incomplete` maps to NAS `Media/Torrents_Unsorted/incomplete-ct129`.

Only the incomplete download data was copied from UbuntuVM's local disk to the new NAS folder. It was 239 MB allocated / 1.3 GB logical; a GNU sparse archive preserved empty regions. Original files on UbuntuVM remain intact.

NAS ownership appears unmapped (`nobody`) inside the unprivileged CT. The new incomplete directory uses 0777 and its restored files 0666; qBittorrent UMASK is 000 so new shared files remain writable under this mapping. Existing library media permissions were not changed. Application UID 1000 passed read/write checks for both download paths.

## Integrations

Prowlarr applications now use the target app URLs and advertise `http://192.168.1.127:9696`. All connection tests passed and ApplicationIndexerSync command 365542 completed.

The existing sync mode is `addOnly`, which did not update previously created indexer URLs. Updated those directly through each app's API: 12 Sonarr, 12 Radarr, 11 Lidarr entries now point at CT127 rather than localhost. Preserved indexer IDs, settings and sync mode. Knaben passed an indexer test from all three apps; 1337x failed its test.

The old NAS bypassed qBittorrent password authentication through an existing host allowlist, hiding stale Arr credentials. Migrated that trust by replacing old NAS entries `100.84.166.81/32` and `192.168.1.84/32` with individual CT122/123/124/127 addresses. Retained the other existing trusted addresses and the existing WebUI password. Verified the new entries persisted in qBittorrent config. No LAN-wide bypass was added.

qBittorrent shares Gluetun's network namespace. Verified VPN health, internet routes through tun0 and OUTPUT DROP firewall policy with a tunnel allow rule. No simulated VPN-outage test was performed.

## Backups and rollback

Source Synology apps remain installed and stopped. Source qBittorrent is stopped with restart policy `no` (verified), preventing duplicate startup. Immich and 7DTD were untouched.

Synology complete config archives:

- `/volume1/@tmp/usniverse-arr-migration.SDLLE7/radarr.tar`
- `/volume1/@tmp/usniverse-arr-migration.SDLLE7/lidarr.tar`
- Matching `SHA256SUMS` in that directory.
- Local copies: `/tmp/usniverse-migration/SDLLE7/`.
- Target archive copies: `/tmp/radarr-SDLLE7.tar` on CT123 and `/tmp/lidarr-SDLLE7.tar` on CT124.

Both archive checksums were verified locally and on targets. SQLite integrity checks passed before startup. Original source configs were not altered.

Target placeholder config/compose backups:

- Sonarr compose: `/opt/sonarr/docker-compose.yml.pre-path-compat-20260918-202912` (earlier source-migration config backup also retained).
- Radarr: `/opt/radarr/config.pre-synology-migration-20260918-205652` and corresponding compose backup.
- Lidarr: `/opt/lidarr/config.pre-synology-migration-20260918-205804` and corresponding compose backup.
- qBittorrent: `/opt/qbittorrent/config.pre-migration-20260919-061048` and corresponding compose backup.
- qBittorrent environment: `/opt/qbittorrent/.env.pre-nas-permissions-20260919-061341`.

qBittorrent source backup: `/home/ubuntu/usniverse-qbit-migration-20260918-214821/` on UbuntuVM. Use `config.tar.gz`, `incomplete.tar` and `SHA256SUMS`. The abandoned partial `incomplete.tar.gz` is NOT a valid backup. Full source container inspection is retained in `container-inspect.json` there. Local copies are in `/tmp/usniverse-migration/qbit-20260918/`; target staging copies are in `/tmp/qbit-20260918/` on CT129. Config and sparse archive checksums were verified on both sides.

Private API-settings backups live under each app's `/opt/<app>/` directory:

- `migration-downloadclients-*.json`
- `indexers.pre-url-migration-20260919-062357.json` for Sonarr/Radarr/Lidarr
- Prowlarr `migration-apps-20260918-205926.json`
- qBittorrent `preferences.pre-host-migration-20260919-061704.json` contains the original trust entries; `...061949.json` captures the intermediate state.

Rollback requires stopping the target before restarting its source. For qBittorrent, also account for downloads made after cutover: source incomplete data is a retained snapshot, not an automatically synchronized rollback copy. Restore the old Arr endpoint/settings if reverting qBittorrent. The old source container's original restart policy is in its saved inspection JSON.

## Infrastructure-as-code validation

- App playbooks now preserve the migrated library paths and qBittorrent incomplete mount/permissions.
- Servernode host vars set `nas_host_mount_src` to `Global_Share_Servernode` and `global_share_managed_by_pve: true`.
- The host-mount playbook verifies PVE-managed NFS and ends that host's play before legacy fstab tasks.
- NAS bind role now verifies an actual NFS mount, refuses conflicting duplicate destinations, and correctly reports unchanged mappings.
- Both storage playbooks ran against servernode successfully with `changed=0`.
- Relevant Ansible syntax checks and whitespace checks passed. A pre-existing trailing-whitespace warning remains in the unrelated master handover.

## Remaining follow-up

- Prowlarr reports obsolete/missing definitions for Badass Torrents, YourBittorrent, TheRARBG, Torlock, TorrentGalaxyClone, Pirate's Paradise and Demonoid Clone. These were not deleted. Some other indexers fail tests; Knaben is verified working through each Arr app.
- Final health checks still show indexer backoff warnings, including all-indexers-unavailable warnings in Radarr/Lidarr despite the successful Knaben tests. No missing-root or download-client connectivity errors remained.
- Sonarr/Prowlarr have update notices. Radarr also reports two TMDb-removed movie records and an Allowed Hosts notice. These are separate from path/download-client migration and were not changed.
- No Readarr or Bazarr source was identified in the Synology package or UbuntuVM Docker audits. CT125/126 remain stopped pending source identification or a fresh-deployment decision. Their configured mount points are correct, but the live old mount still requires an LXC restart; prevent placeholder startup first.
- Temporary local/target archives were retained; no source uninstalls or backup cleanup were performed.

## Ombi, Homepage and Dashy connections — 2026-09-19

Both sites use `192.168.1.0/24`. Old-site apps cannot reach new-site containers by LAN address directly. `playbooks/media_proxy_routes.yml` now installs persistent systemd socket proxies:

- ServerNode listens only on Tailscale `100.74.248.75`, forwarding to the new media containers.
- CT110 listens on `100.122.95.117` and old-site LAN `192.168.1.110`, forwarding over Tailscale to ServerNode.
- Ports: Sonarr 8989, Radarr 7878, Lidarr 8686, Prowlarr 9696, qBittorrent 8086 (target 8080).
- Existing edge DNAT chains and unrelated services were not modified. Use `Type=simple` for compatibility with CT110's systemd-socket-proxyd.

Ombi CT118 now connects to Sonarr at `192.168.1.110:8989` and Radarr at `192.168.1.110:7878`. Existing API keys and quality profiles were valid and retained. Sonarr's obsolete root ID 3 was corrected to ID 1 (`/volume1/Global_Share/Media/Movies/TV Series`); Radarr retains its Feature Film root. Settings were saved through Ombi's API. Both saved connections passed Ombi's tester; profile and root-folder discovery also succeeded. No synthetic requests or bulk approvals were submitted. Counts before/after: 147 movie requests, 41 TV requests, 42 child requests, 30 queue entries.

Ombi SQLite backups (including requests) are in `/opt/ombi/config/pre-media-connections-20260919-113647/` on CT118. An earlier pre-save backup is also retained.

Homepage CT110 now includes all five media links under Media, using `http://100.122.95.117:<port>`. Its repository template matches. Existing widgets, power actions and other links were retained. Live backup: `/opt/homepage/config/services.yaml.pre-media-connections-20260919-063740`.

Dashy's five obsolete NAS/UbuntuVM media URLs now use the same edge endpoints. ServerNode was added under **Proxmox** at `https://100.74.248.75:8006/`. Its status polling is disabled because Proxmox uses its own TLS certificate; the HTTPS navigation link was verified. Configuration: `/home/ubuntu/DockerContainers/dashy/my-config.yml`; a sibling `.pre-media-connections-*` backup contains the original. Changes were made in place through the file-owning Dashy container and the container restarted.

All five media URLs, Homepage and ServerNode's Proxmox page returned HTTP 200 during verification (Proxmox checked with certificate verification disabled). Dashy's YAML parsed successfully with five corrected media links and ServerNode in the Proxmox section.

The historical `media_stack_link_servernode.yml` contained stale direct-LAN mappings and guessed settings. The automation closeout replaced it with imports of the private-route and restored-settings reconciliation playbooks. It is now the safe compatibility entrypoint.

Final Dashy verification: container healthy after restart; `/`, `/conf.yml` and `/user-data/conf.yml` returned HTTP 200. Both served configuration paths include ServerNode.

User-requested adjustment: removed Sonarr, Radarr, Lidarr, Prowlarr and qBittorrent from Homepage's live services and repository template. Homepage was restarted. Backup: `/opt/homepage/config/services.yaml.pre-remove-media-20260919-113905`. Dashy entries and the routes supporting Ombi remain in place.

## Automation and GitHub closeout — 2026-09-19

- Added `media_migration_reconcile.yml` to maintain the private routes, restored application connections, Homepage and Dashy. `media_stack_link_servernode.yml` now imports the safe route/connection playbooks instead of its historical hard-coded credentials and bootstrap defaults.
- Non-secret desired state lives in `media_connections.yml` group vars and `ubuntuvm.yml` host vars. Helpers read credentials only on the application host and back up databases/settings before changes. No request approvals or downloads are submitted.
- App deployment retains migrated library paths, qBittorrent NAS incomplete storage, VPN setup, site-specific SSH routing and PVE-managed storage. Readarr/Bazarr are excluded by default.
- Fixed Homepage's repeated-quote bug by parsing existing YAML values instead of extracting quoted URLs with regex. Added pre-write rendered-YAML validation and generated-page refresh. The valid original configuration was restored during verification; Homepage's media entries remain absent.
- Validation: 13 changed/new playbooks passed syntax checks; five regression tests passed; the full live reconciliation completed. Application settings needed no changes, and Dashy reported no drift. Homepage's corrected repeat run reported zero changes. Both dashboard APIs were verified afterward.
- Reviewed the publication file set for credential literals: Vault additions are encrypted, new code contains no embedded API keys, and local archives/configuration snapshots are excluded. The unrelated local 7DTD commit was kept out of the migration branch.
- Publication branch: `migration/media-stack-20260919` in `adds666/Usniverse`, prepared in an isolated worktree at `/tmp/usniverse-media-publish`. The original working directory and its pre-existing branch were preserved.

See [Media automation and recovery](MEDIA_AUTOMATION.md) for the run commands and recovery boundary. GitHub contains configuration/code; application-data archives remain on the documented hosts and have not been uploaded to GitHub.
