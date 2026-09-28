# Dashy moved to MacBookPro — 2026-09-28

Dashy now runs beside Homepage in MacBookPro CT110 (`192.168.1.110`). Tailscale URL: **http://100.122.95.117:4001**. Port 4000 remains reserved for Invidious forwarding.

The original image digest was retained. All `/app/user-data` files were archived and restored to `/opt/dashy/user-data`; the served configuration matched the source exactly. ServerNode remains under Proxmox, and Immich points at `http://100.69.158.73:2283/auth/login`.

CT110 memory increased from 512 to 1024 MiB for both dashboards. Dashy has a 512 MiB limit and Docker `unless-stopped` restart policy. Enabled `dashy.service` starts Compose at boot; CT110 already has onboot enabled. Service stop/start passed, Dashy and Homepage were healthy, and configuration was verified over Tailscale after restart. CT110 was not rebooted during this migration to avoid interrupting its ingress services.

Private configuration and environment remain outside Git. Recovery archive and environment are retained at `/root/usniverse-dashy-migration` on MacBookPro and `/tmp/usniverse-dashy-migration` on the workstation (temporary). The stopped source container and original files on UbuntuVM are retained as an independent rollback copy. No user-data files were deleted.

UbuntuVM has **no running Docker containers** after the cutover. Its ordinary OS, SSH, Tailscale, Docker and desktop/printing services remain running. Dashy and the retired Immich containers have restart policy `no`. UbuntuVM itself has not been shut down or deleted.

`playbooks/dashy_ct110.yml` reconciles the pinned deployment after requiring existing private configuration and a validation marker. It preserves the live dashboard configuration. `dashy_ubuntuvm.yml` is now a compatibility redirect to the new target; the media reconciliation entry point also targets CT110. The former source-side scoped link updater is no longer used. Dashboard links can continue to be maintained through Dashy's configuration editor.

Run `ansible-playbook -i inventories/home/hosts.yml playbooks/dashy_ct110.yml`. Live reconciliation passed. For rollback, stop the target, copy back any later dashboard edits, and explicitly start the retained source container. Avoid editing both copies independently.
