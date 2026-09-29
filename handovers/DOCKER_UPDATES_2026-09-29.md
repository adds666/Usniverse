# Docker application updates — 2026-09-29

Updates cover Docker applications on standalone MacBookPro and ServerNode. Existing network addresses, application data directories, NAS photo/media paths and the qBittorrent VPN namespace were retained. ServerNode was woken via Earls-edge for maintenance; its shutdown timer was held during the work and restored afterwards. The next shutdown is 2026-09-30 at 06:30 BST.

## Reviewed deployments

The exact image references and platform image IDs are recorded in `files/docker/versions-20260929.json`. Image pins were applied to the live Compose configurations and existing repository deployment definitions where present. The private live Compose files for otherwise unmanaged applications remain in their host recovery directory; they are not published to Git.

| Host | CT | Container | Version |
| --- | --- | --- | --- |
| pve | 110 | Dashy | 4.7.0 |
| pve | 110 | homepage | v2.4.0 |
| pve | 111 | jellyfin | 12.1ubu2604-ls50 |
| pve | 112 | immich-immich-server-1 | v3.2.4 |
| pve | 112 | immich-immich-machine-learning-1 | v3.2.4 |
| pve | 112 | immich-redis-1 | 9.1.2 |
| pve | 112 | immich-database-1 | 14.19; VectorChord 0.4.3; pgvector 0.8.1 |
| pve | 114 | invidious_invidious_1 | 2.20260804.1 |
| pve | 114 | invidious_postgres_1 | 14.24 |
| pve | 114 | invidious_companion_1 | latest |
| pve | 116 | n8n | 2.40.7 |
| pve | 117 | synapse | 1.161.0 |
| pve | 118 | ombi | v4.53.10-ls270 |
| pve | 119 | searxng | 2026.9.25-12f8b6515 |
| servernode | 121 | openclaw-cli | 2026.9.6 |
| servernode | 121 | openclaw-gateway | 2026.9.6 |
| servernode | 122 | sonarr | 4.0.20.3014-ls326 |
| servernode | 123 | radarr | 6.4.4.10685-ls318 |
| servernode | 124 | lidarr | 3.1.0.4875-ls42 |
| servernode | 125 | readarr | 0.4.18.2805-ls157 |
| servernode | 126 | bazarr | v1.6.2-ls366 |
| servernode | 127 | prowlarr | 2.6.5.5623-ls162 |
| servernode | 128 | flaresolverr | v3.5.2 |
| servernode | 129 | qbittorrent | 5.2.3_v2.0.15-ls478 |
| servernode | 129 | gluetun | latest |

Readarr is deprecated upstream. Its pinned 0.4.18.2805-ls157 image was retained and its API checked. The moving `develop` tag no longer provides a matching amd64 manifest. No replacement application was installed. See [LinuxServer's deprecation notice](https://docs.linuxserver.io/deprecated_images/docker-readarr/).

CT204 (7 Days to Die) does not run Docker and was not modified. CT120 was not present on ServerNode. No Docker daemon or Proxmox package upgrades were part of this work.

## Database and compatibility work

Immich moved from v2.7.5 to v3.2.4 in stages. A fresh stopped-application database dump and cold PostgreSQL/Redis archive were captured immediately before migration. PostgreSQL remains major 14. The official compatible database image migrated pgvecto.rs to VectorChord 0.4.3 while still on v2.7.5, followed by another database dump, then the v3 application/ML images and Valkey 9. Photos remain on the NAS with the same application media path. The longer migration briefly exceeded the initial health-check window; no restart was forced during index rebuilding. Final API health, five original checksum downloads, synthetic upload/download/removal, ML inference, and the unchanged 27,095 asset count passed. Phone clients should use Immich 3.x.

Jellyfin moved from 10.11.8 to 12.1.0 after a full cold configuration/data archive. There were no conflicting case-insensitive usernames. All nine users remained. Official Webhook 22.0.0.0 and TheTVDB 24.0.0.0 packages were checksum-verified, installed and confirmed active. The required full library scan was started after schema migration and subsequently finished (no running scheduled tasks). Original plugin directories were retained under `/opt/jellyfin/pre-update-plugins-20260928`.

Invidious uses legacy Docker Compose v1. Its stack was stopped and recreated without deleting named volumes, preserving PostgreSQL major 14. Its web endpoint passed. SearXNG, Homepage, Dashy, n8n, Synapse and Ombi endpoints passed after updates. Synapse had no experimental auth delegation, workers or custom modules requiring separate migration.

ServerNode's Sonarr, Radarr, Lidarr and Prowlarr APIs responded with the new versions. Each of Sonarr/Radarr/Lidarr retained its enabled download client. qBittorrent retained 30 torrents; API access from the trusted Sonarr CT passed. Its network namespace still exactly matches the healthy Gluetun container.

## Recovery and verification

Private recovery directory on **each host**: `/root/usniverse-docker-update-20260928/<CT>/`. `application-data.tgz` contains `/opt` and persistent Docker volumes captured while that CT's application containers were stopped. Archives passed gzip validation. NAS media was not copied into these archives. Old Docker images were retained. Proxmox snapshots were unavailable with the guests' bind-mount setup; cold archives were used instead.

MacBookPro has an additional NAS recovery copy at `/mnt/pve/Global_Share/macbookpro-proxmox-backups/docker-update-20260929`. SHA-256 comparisons passed for all eight application archives and all three additional Immich recovery files. The matching verification record is `nas-copy-sha256.json` in both the host recovery directory and the NAS copy. Immich has additional fresh pre-upgrade and post-VectorChord dumps in CT112's host recovery subdirectory. Do not roll back only an image after a database upgrade: restore its matching database/configuration while the application is stopped, accounting for any writes accepted after the backup. Do not delete existing Immich migration recovery snapshots or retired UbuntuVM data during acceptance.

`ansible-playbook -i inventories/home/hosts.yml playbooks/docker_versions_check.yml` performs a read-only check of running image IDs, health and OOM state on both hosts. It does not upgrade or restart anything. The updated Immich and Dashy reconciliation playbooks also passed live runs without restarting those applications. Credentials, database archives and user configuration are excluded from Git.

## OpenClaw local build and migration

OpenClaw 2026.9.6 was built locally from the upstream stable tag and deployed to both gateway and CLI containers, preserving mounted configuration and workspace data. The original source checkout and old image are retained. The fresh source is `/opt/openclaw/update-src-2026.9.6`. The Dockerfile uses `--config.package-import-method=copy` for pnpm to work around filesystem linking restrictions in nested Docker. CT121 root disk was increased from 32 to 48 GiB for retained images/build cache. Compilation required a temporary 16 GiB memory allocation; normal 4 GiB memory was restored after deployment.

The built-in `doctor --fix --non-interactive` migrated configuration and credentials to the new schema. Both containers passed health checks with zero restarts and no OOM state. UI and `/healthz` responded HTTP 200 at both the existing direct Tailscale endpoint `http://100.72.13.78:18789` and the actual Homepage HTTPS link `https://openclaw.taildb07f.ts.net`. The new release initially rejected the externally managed Tailscale Serve proxy with `proxy_attribution_required`. After explicit user approval, only the observed Docker bridge address `172.18.0.1` was added to `gateway.trustedProxies` in the existing private JSON configuration. Token authentication and the existing allowed origins were retained. This follows the [externally managed Serve compatibility instructions](https://docs.openclaw.ai/gateway/tailscale#externally-managed-serve-and-funnel). A private pre-change configuration copy is retained in CT121 under `/root/usniverse-openclaw-update-recovery/`.

One historical, unregistered JSONL transcript has a header ID that differs from its filename. The migration explicitly deferred that file; its 184,024-byte original is retained under `agents/main/session-sqlite-import-archive` and in the pre-upgrade archive. This historical transcript is not confirmed imported into the new SQLite history. No transcript was renamed, deleted or rewritten to suppress the warning. Diagnose with `openclaw doctor --session-sqlite dry-run --session-sqlite-all-agents` before any separate history repair. The gateway runs normally; no test messages were sent to external chat channels.

The Ansible build recipe now pins the stable release and records the pnpm compatibility patch. Its syntax check passed; the full provisioning playbook was not reapplied over existing user configuration. The new cross-host version verification playbook checks the deployed image independently.

## Homepage Jellyfin widget correction

The Jellyfin 12 upgrade requires `version: 2` in Homepage's Jellyfin widget ([Homepage documentation](https://gethomepage.dev/widgets/services/jellyfin/)). The default v1 widget called retired `/emby/Items/Counts` and `/emby/Sessions` routes and received HTTP 404. Added version 2 to the live CT110 widget and the Ansible service template, retaining the existing API key and URL. Both `CountV2` and `SessionsV2` returned HTTP 200 through Homepage's widget proxy. The Homepage playbook syntax check passed. A private pre-change configuration backup remains in CT110 at `/root/homepage-services-before-jellyfin-v2-20260929.yaml`.
