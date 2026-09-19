#!/bin/sh
# Run with sudo on DS920. Stops only Radarr/Lidarr and archives config, not media.
set -eu
umask 077
[ "$(id -u)" = 0 ] || { echo 'Run this script with sudo.' >&2; exit 1; }
for app in radarr lidarr; do
    case "$app" in radarr) title=Radarr ;; lidarr) title=Lidarr ;; esac
    test -s "/volume1/@appdata/$app/.config/$title/$app.db"
done
backup_dir=$(mktemp -d /volume1/@tmp/usniverse-arr-migration.XXXXXX)
echo "Backup directory: $backup_dir"
echo 'If interrupted, sources may remain stopped; backups and source configs are retained.'
for app in radarr lidarr; do
    /usr/syno/bin/synopkg stop "$app"
done
sleep 3
for app in radarr lidarr; do
    case "$app" in radarr) title=Radarr ;; lidarr) title=Lidarr ;; esac
    if ps aux | grep -F "/share/$title/bin/$title" | grep -v grep >/dev/null; then
        echo "$title still running; refusing to copy live config." >&2
        exit 1
    fi
    tar -C "/volume1/@appdata/$app/.config/$title" -cf "$backup_dir/$app.tar" .
    tar -tf "$backup_dir/$app.tar" >/dev/null
done
cd "$backup_dir"
sha256sum radarr.tar lidarr.tar > SHA256SUMS
chown adds666:users radarr.tar lidarr.tar SHA256SUMS "$backup_dir"
chmod 600 radarr.tar lidarr.tar SHA256SUMS
chmod 700 "$backup_dir"
echo 'Archives ready; original configs untouched, packages left stopped:'
ls -lh "$backup_dir"
echo "$backup_dir"
