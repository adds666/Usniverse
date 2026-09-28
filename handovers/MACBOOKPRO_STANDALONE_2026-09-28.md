# MacBookPro standalone conversion — 2026-09-28

> Migration is now complete. See [final cutover handover](IMMICH_CUTOVER_2026-09-28.md) for current state; observations below record preparation stages.

The user explicitly approved making MacBookPro standalone for the time being as part of Immich migration preparation.

Rollback material is private at `/root/usniverse-immich-preparation-20260928/` on MacBookPro: host configuration archive, consistent SQLite config database, CT112 configuration, complete compressed CT112 root disk with verified gzip integrity and SHA-256, and the executed conversion script. No credentials or disk archives belong in Git.

The conversion completed successfully. Corosync and HA services are disabled; pve-cluster remains enabled and runs locally. Corosync configuration and stale remote node configuration directories were archived outside `/etc/pve`. All seven existing running containers remained running. pvedaemon and pveproxy are active. This was checked against the upstream Proxmox node-separation procedure: https://github.com/proxmox/pve-docs/blob/master/pvecm.adoc#separate-a-node-without-reinstalling

All local guest root disks remain on local-lvm. The existing fstab NFS mount `192.168.1.84:/volume1/Global_Share` at `/mnt/pve/Global_Share` is unchanged. Shared NAS guest-storage registration was removed to avoid management of old cluster VM images. New backup-only storage `MacBookPro_Backups` uses `/mnt/pve/Global_Share/macbookpro-proxmox-backups`, requires the parent mount, and is restricted to MacBookPro. The existing backup job now targets this dedicated directory. Resuming the scheduler triggered an existing catch-up backup (CT110 was observed locked for backup); no manual notification was sent.

A pve-guests systemd drop-in now requires the NAS mount before guest startup. NAS access from CT110 and CT111 was checked. No host reboot has been performed, so cold-boot recovery still requires validation. Remaining offline old-cluster nodes have not been altered; their stale membership should be reconciled before any future cluster reuse. Do not restore old corosync configuration to this live standalone host or assume rejoining a cluster with existing guests is trivial.

CT112's NAS bind was changed to read-only before its startup test, protecting the live Immich source from target writes. Production Immich remains on UbuntuVM. Independent media backup on ServerNode is verified and held; final migration still requires isolated deployment rehearsal, resource validation, a fresh consistent recovery point and single-writer cutover.
