# Media automation and recovery

The September 2026 cutover is now represented by deployment playbooks, connection reconciliation,
private network routes and dashboard configuration. App databases and media are separate recovery
assets; a checkout of this repository alone does not recreate libraries, torrent state or requests.

## Entry points

Run from the repository root with the normal Ansible Vault credentials configured:

```bash
ansible-playbook -i inventories/home/hosts.yml playbooks/media_migration_reconcile.yml
```

This maintains private socket proxies on ServerNode and CT110, then reconciles qBittorrent,
Sonarr, Radarr, Lidarr, Prowlarr, Ombi, Homepage and Dashy. It does not deploy/upgrade images,
copy media, approve requests, start downloads, or start the deferred Readarr/Bazarr containers.
Existing Homepage widgets and power links are retained. Arr/qBittorrent entries are absent
from Homepage by request; Dashy retains them and the ServerNode Proxmox link.

Individual entry points:

| Playbook | Responsibility |
| --- | --- |
| `app_arr_suite_servernode.yml` | App deployment, compatibility volumes and VPN; restored `/opt/<app>/config` must already exist to retain data |
| `media_proxy_routes.yml` | Private routes across overlapping site subnets |
| `media_connections.yml` | Existing app connections, qBittorrent trust/download paths, Prowlarr app/indexer URLs and Ombi root mapping |
| `homepage_ct110.yml` | Homepage layout, existing widgets and generated-page refresh |
| `dashy_ubuntuvm.yml` | Five media links and Proxmox ServerNode entry in existing Dashy configuration |
| `media_stack_link_servernode.yml` | Compatibility entrypoint importing routes and connection reconciliation; replaces the obsolete bootstrap |

Readarr and Bazarr deployment requires explicit `-e media_deploy_deferred=true`. Source data
for those applications was not found; they remain stopped. The migration playbook does not
manage Immich or the 7DTD workload.

## Desired state and credentials

- Non-secret connection specification: `inventories/home/group_vars/all/media_connections.yml`.
- Dashy specification: `inventories/home/host_vars/ubuntuvm.yml`.
- Site-specific SSH jump configuration lives in the `lxc_macbookpro` and `lxc_servernode` groups.
- ServerNode's NAS mount is PVE-managed `Global_Share_Servernode`; the storage playbook verifies
  the existing mount instead of creating a second fstab-managed mount.
- API keys are read locally from restored XML/SQLite settings. Masked API passwords are replaced
  with the existing local values before saving. No API secrets are embedded in the new scripts.
- Existing quality profiles, download categories, request approval policy and unrelated Dashy settings
  are preserved. Prowlarr remains `addOnly`; existing generated indexer endpoints are reconciled directly.
- qBittorrent retains its existing WebUI password. Only the four app `/32` addresses replace the retired
  NAS trust entries; other existing trust entries remain. No LAN-wide authentication bypass is enabled.

## Validation and drift checks

```bash
python3 -m unittest discover -s tests -p 'test_media_reconcile.py' -v
ansible-playbook -i inventories/home/hosts.yml playbooks/media_migration_reconcile.yml --syntax-check
ansible-playbook -i inventories/home/hosts.yml playbooks/media_connections.yml -e media_connections_check=true
ansible-playbook -i inventories/home/hosts.yml playbooks/dashy_ubuntuvm.yml -e media_connections_check=true
```

The last two commands install/update non-secret helper files, then validate/report settings drift
without changing application settings. Connection tests use the apps' test APIs, not test downloads.
Standard Ansible `--check` validates helper-file deployment but skips executing helpers, since a fresh
host might not yet contain them. It is not a substitute for the explicit drift checks above.

Reconciliation fails if migrated roots, expected clients/applications or required credentials are
missing. It does not guess a replacement library or initialize blank request databases.

## Backups and recovery boundary

Before settings writes, the connection helper takes consistent SQLite backups on the application
host under `/opt/<app>/pre-ansible-connections-*`; qBittorrent preference backups use
`/opt/qbittorrent/preferences.pre-ansible-*.json`. Dashy keeps a private sibling `.pre-ansible-*`
backup. Homepage uses Ansible's destination backup feature.

The [cutover handover](MEDIA_MIGRATION_2026-09-18_PROGRESS.md) records the original full configuration
archives, torrent snapshot, checksums and rollback paths. Keep those assets and the Ansible Vault
password/SSH credentials available separately from GitHub. Restoring a host requires restoring the
matching application data and NAS access before deploying/reconciling services. Stop a target before
reactivating its old source to avoid duplicate automation or torrent clients.

GitHub stores code, non-secret configuration, encrypted Vault values and documentation. It does not
store application database archives, media, private keys or the Vault password. Automatic off-site
application-data backups and a full disaster-recovery restore drill are not implemented by this change.
