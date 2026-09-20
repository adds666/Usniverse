# ServerNode standalone operation and overnight schedule

ServerNode was separated from the fragmented Universe cluster on 2026-09-20 using the official Proxmox non-reinstall procedure. All ten local container definitions and ZFS disks were preserved. No HA resources or replication jobs were configured. Corosync and unused HA daemons are disabled; pve-cluster remains enabled to provide the local Proxmox configuration filesystem.

Configuration archives and consistent config.db backups exist on ServerNode at `/root/usniverse-standalone-20260920-083525/` and MacBookPro at `/root/usniverse-standalone-20260920-083528/`. An additional ServerNode archive was copied to the administration workstation's `/tmp/usniverse-standalone/`. These archives contain credentials and must not be committed.

ServerNode membership was removed from MacBookPro's cluster configuration (version 6). The remaining old cluster still lacks quorum; repairing its other members is a separate task. Do not copy its old corosync configuration back to ServerNode.

## Storage and boot

All guest root disks use local-zfs. The NAS remains at `100.84.166.81:/volume1/Global_Share`, mounted at `/mnt/pve/Global_Share_Servernode`; existing container bind paths are unchanged. The NAS root is no longer registered as Proxmox guest storage on ServerNode. This prevents the standalone host from managing the old cluster's NAS VM images.

The media mount is now managed through fstab and Ansible, with a readiness service checking that the NAS NFS listener is reachable through tailscale0. The first reboot test caught a race where tailscaled had started but the tailnet route was not ready. Guest startup requires the actual NAS mount, preventing downloads into an empty local mount directory.

`Servernode_Backups` is a backup-only directory storage at `/mnt/pve/Global_Share_Servernode/servernode-proxmox-backups`, protected by an `is_mountpoint` check on the parent NFS mount. The existing weekly backup job now targets this dedicated directory, Tuesday 00:30 UK time. Other nodes' copied guest definitions were removed only from ServerNode, after backup.

## Overnight automation

Deploy or reconcile with:

```sh
ansible-playbook -i inventories/home/hosts.yml playbooks/servernode_overnight.yml
```

- CT110 timer: midnight Europe/London calls the existing authenticated local wake proxy, which asks Earls-edge to emit the LAN magic packet.
- Ombi CT118: failed-request retries hourly at 00:15 through 06:15 (`0 15 0-6 * * ?`). Existing unrelated job schedules are preserved. Ombi currently uses Europe/London.
- ServerNode timer: graceful systemd poweroff at 06:30 Europe/London, using Proxmox's normal guest shutdown handling.
- Both power timers use `Persistent=false`, so starting a timer later in the day does not unexpectedly execute a missed shutdown or wake.

The wake client reads `/etc/wol-webhook/env` locally; no token is stored in Git. Wake scheduling currently depends on CT110 and its host being up. Earls-edge handles the actual LAN wake packet, but direct SSH administration was unavailable, so no timer was installed there. Any pre-existing independent Earls-edge schedule could not be audited.

The overnight schedule stops **all ServerNode workloads**, including OpenClaw and 7DTD, not just media services. Containers retain their existing onboot settings.

To suspend scheduled shutdown for daytime maintenance:

```sh
systemctl stop usniverse-servernode-shutdown.timer
# Restore after maintenance:
systemctl start usniverse-servernode-shutdown.timer
```

The nightly wake relay was tested successfully while ServerNode was already on. This confirms the relay accepted and sent the magic packet, but is not a power-off/wake test.

## Validation

The second full reboot passed on 2026-09-20: NAS readiness completed at 08:45:16 BST, NFS mounted at 08:45:17, and all ten containers had started automatically by 08:45:26. No quorum override or manual guest start was used. Sonarr, Radarr, Lidarr, Prowlarr and qBittorrent user-facing proxy URLs all returned HTTP 200. Both timer schedules and the installed wake service were checked. Six existing media regression tests and Ansible syntax checks passed. The first reboot exposed the NAS readiness race and was followed by the fix described above.
