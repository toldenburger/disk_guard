#!/usr/bin/env bash
# Monthly (Arch): move old pacman package versions from the internal disk to a backup disk,
# so you can still roll back a package without keeping every version on the system disk.
# Keeps the newest version of each installed package in /var/cache/pacman/pkg.
# Usage: pacman_cache_archive DEST   (DEST = an existing folder on the backup disk)
# Runs as root from pacman_cache_archive.timer; install.sh copies it to /usr/local/bin.
set -euo pipefail

dest="${1:?usage: pacman_cache_archive DEST}"

if [ "$EUID" -ne 0 ]; then
  echo "must run as root" >&2; exit 1
fi
# If the backup disk is not mounted, DEST does not exist: skip instead of filling the system disk.
if [ ! -d "$dest" ]; then
  echo "$dest does not exist (disk not mounted?), skipped" >&2; exit 1
fi
# Don't race a running pacman/yay update.
if [ -e /var/lib/pacman/db.lck ]; then
  echo "pacman is running (db.lck present), skipped" >&2; exit 1
fi

echo "before: $(du -sh /var/cache/pacman/pkg | cut -f1) internal, $(du -sh "$dest" | cut -f1) archived"
paccache --nocolor -k1 -m "$dest"      # old versions of installed packages
paccache --nocolor -uk0 -m "$dest"     # all versions of uninstalled packages
echo "after: $(du -sh /var/cache/pacman/pkg | cut -f1) internal, $(du -sh "$dest" | cut -f1) archived"
