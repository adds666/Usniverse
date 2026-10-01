# Toshiba resource rebalance — 2026-09-30

## UbuntuVM retired

User authorized shutdown and redistribution of services between the always-on hosts.
VM100 is stopped on Toshiba and `onboot=0`. Two graceful shutdown attempts timed out;
the second used Proxmox's `--forceStop 1` fallback. Its old application containers
were stopped before shutdown. No VM disk or application data was deleted. The weekly backup job now excludes
VM100 while retaining its existing VM111 exclusion; the immutable source no longer
triggers another 900 GiB scan. `playbooks/ubuntuvm_retired.yml` reconciled with zero changes.

The 900 GiB virtual disk lives on NAS storage `Global_Share`, not Toshiba local-lvm.
Deleting it would reclaim NAS capacity; stopping it already released host RAM.
Proxmox reported its scheduled full backup completed at 07:52 on September 30,
with a 628.10 GB archive. Archive contents have not yet been independently verified
or restore-tested. Do not delete the source disk on the strength of the task log alone.

After shutdown Toshiba had 3.9 GiB available RAM (5.7 GiB total), compared with
about 800 MiB beforehand. KaliVM was normally stopped; the backup job temporarily
started its QEMU process to read its disk. CT102 remains running and unchanged.

## Container cutovers

Selected: CT114 Invidious, CT116 n8n and CT119 SearXNG. Keep Immich, Jellyfin,
Homepage/Dashy, Paperless, Synapse and Ombi on MacBookPro for this first pass.
All three cutovers completed successfully; final validation was repeated on 2026-10-01.

`playbooks/lxc_rebalance_toshiba.yml -e ct_id=119` (or 114/116) wraps the one-time
controller script. It requires existing SSH keys to both standalone hosts.
The source is cleanly stopped and boot-disabled before backup; a checksum-tested
zstd archive is staged on Toshiba local storage and restored to local-lvm.
Source local staging is under `/var/lib/vz/usniverse-rebalance-20260930`; `vzdump`
uses `/var/tmp` for its unprivileged scratch directory. Private NAS copies are also retained. IP and MAC stay unchanged. Target
Docker image IDs and health must match before automatic boot is enabled.
Archives are private under NAS `/volume1/Global_Share/usniverse-rebalance-20260930`.
NAS bind mounts are retained; their contents are not included in the CT archive.

On failure the source stays stopped. For rollback first stop and boot-disable the
target. Account for any new target writes before starting the retained source.
Never run both copies with the same network identity or shared writable data.
The script refuses to overwrite an existing target CT.

## Host and network findings

Toshiba's Ethernet adapter supports and advertises gigabit, but its link partner
advertises only 10/100 Mbps; the negotiated link is 100 Mbps full duplex.
Check the upstream switch/port or intermediate adapter. Toshiba uses a rotating
Toshiba MK5075GSX disk; MacBookPro uses a Crucial SSD. This limits NAS throughput;
keep media streaming and photo workloads on MacBookPro in this first split.
The scheduled KaliVM backup is still active and was not cancelled. Its live task
log showed normal progress (29% after about 2h11m), competing for the same 100 Mbps
link. Per-VM summary logs lagged behind the live task log.

Toshiba has no Corosync configuration and its Corosync service is inactive, but it
retains stale node records from its former cluster. For each moved CT, the old
`nodes/macbookpro/lxc/<id>.conf` is preserved in
`/root/usniverse-rebalance-20260930/stale-node-configs` before removing that stale
Toshiba-local record. No live MacBookPro configuration is removed.

## Final validation

CT119 SearXNG: restored successfully, exact reviewed image ID matched, local/LAN
and frontend HTTP 200, a real search returned 20 results, outbound Docker HTTPS 204, Ansible ping passed through
Toshiba. Target `onboot=1`, source stopped with `onboot=0`.
Archive SHA-256: `3e995f2d70aa36c9e5b8b7bf6e47f1d08ac5e22e0d9f3ab3d06130e48be0e62a`.
CT114 Invidious: all three reviewed images matched, companion healthy, application
and database running, frontend root redirected normally and its destination
returned HTTP 200. Ansible ping through Toshiba passed.
Archive SHA-256: `daf2bd76eab5b6d3327dce97237aab581589ada3966ddd6b2ef4465dc1201c34`.
CT116 n8n: exact reviewed image matched, Docker running for about 18 hours at
final inspection, health and database-readiness endpoints HTTP 200 from the
frontend. The original NAS export remains mounted inside the guest. Target
startup checks for real NFS before binding it. Archive SHA-256:
`34abc6f8a60abae0ba3d3db6a0ac41f72941925b424b8c8811f0ac82f791eb99`.

All target containers have automatic boot enabled; all retained source copies
remain stopped with automatic boot disabled. Inventory, SSH jump hosts, logical
CT ownership, Docker/NAS host lists and image manifests reflect Toshiba ownership.
`playbooks/toshiba_rebalance_reconcile.yml` preserves the n8n NAS startup guard
and verifies retirement states.

Final available memory was about 2.8 GiB on MacBookPro and 2.7 GiB on Toshiba.
This is an observed snapshot, not a load benchmark. MacBookPro retains CT110,
111, 112, 113, 117 and 118. Toshiba runs CT102 plus 114, 116 and 119.

KaliVM's backup finished and it is stopped again. On October 1 the user approved
manual startup only: both KaliVM and UbuntuVM now have `onboot=0`.
`playbooks/toshiba_vm_autostart.yml` records this policy and is included in the
rebalance reconciliation. Kali's disk and backup coverage are retained.


## Jellyfin memory finding and mitigation

The final reviewed-image check passed for all Toshiba containers and matched all
MacBookPro images and running/health states. Its strict OOM check still reports
Jellyfin's historical event. Kernel logs show a **global** OOM on September 30 at
08:57, before these moves: FFmpeg used about 3 GiB RSS and was killed. Jellyfin
itself remained running; its health endpoint returns HTTP 200.

CT111 previously allowed 8000 MiB RAM with no swap on a 7.7 GiB host. It now has a
4096 MiB RAM ceiling and 1024 MiB swap allowance, applied live while actual cgroup
usage was about 1.1 GiB. The reconciliation playbook and logical CT map record
these limits. Generic CT creation now honors optional `swap_mb` (default zero).
This bounds Jellyfin's impact; it is not a guarantee that every future transcode
will fit. No playback-quality or application configuration was changed.

Jellyfin was not restarted to erase the historical Docker OOM flag. An attempt
to check active sessions with the dashboard credential was rejected by automatic
approval review after authentication failed; no credential workaround was used.
The ordinary unauthenticated health check and resource limits were verified.
Consequently the strict full-host version checker still returns failure for that
known historical OOM flag; the checker was not weakened to hide it.


## Reboot validation — 2026-10-01

User requested Kali manual startup and a Toshiba reboot to test link negotiation.
Ansible verified the reboot completed (196 seconds). UbuntuVM and KaliVM both
remained stopped; CT102, 114, 116 and 119 started automatically. The applications
needed additional cold-start time on the rotating disk. Final frontend checks
returned HTTP 200 for Invidious, n8n database readiness and SearXNG. n8n's NAS
bind was mounted from the expected Synology export. Autostart reconciliation
passed with zero changes after reboot.

Ethernet remained **100 Mbps full duplex** with autonegotiation enabled. Toshiba
supports and advertises gigabit, but its link partner advertises only 10/100 Mbps.
A reboot did not change this. Check the upstream port/intermediate network device
and cable; no unsupported forced-gigabit setting was applied.
