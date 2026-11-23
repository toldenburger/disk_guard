#!/usr/bin/env bash
# Installs the root-owned pacman cache archiver and its monthly system timer (Arch only).
# Usage: sudo system/install.sh /path/to/backup/disk/pacman_cache
set -euo pipefail
[ "$EUID" -eq 0 ] || { echo "run with sudo" >&2; exit 1; }
dest="${1:?usage: sudo $0 /path/to/backup/disk/pacman_cache}"
[ -d "$dest" ] || { echo "$dest does not exist; create it on the backup disk first" >&2; exit 1; }
case "$dest" in *[[:space:]]*) echo "please use a path without spaces" >&2; exit 1;; esac
here="$(cd "$(dirname "$0")" && pwd)"
install -o root -g root -m 0755 "$here/pacman_cache_archive.sh" /usr/local/bin/pacman_cache_archive
sed "s|DEST\$|$dest|" "$here/pacman_cache_archive.service" > /etc/systemd/system/pacman_cache_archive.service
install -o root -g root -m 0644 "$here/pacman_cache_archive.timer" /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now pacman_cache_archive.timer
systemctl list-timers pacman_cache_archive.timer --no-pager
