#!/usr/bin/env bash
# Read-only size report for the parts of the internal disk a normal user can't read.
# Run it with:  sudo ./disk_sudo_report.sh
# It only measures. It never deletes or changes anything; the "to clean" commands are printed as suggestions.

if [ "$EUID" -ne 0 ]; then
  echo "Run this with sudo: sudo $0" >&2
  exit 1
fi

hr() { printf '\n===== %s =====\n' "$1"; }

hr "Filesystem overview"
df -h /
btrfs filesystem usage -h / 2>/dev/null | sed -n '1,16p'

hr "Docker (/var/lib/docker) by folder"
du -xh --max-depth=1 /var/lib/docker 2>/dev/null | sort -rh | head -10
echo
docker system df 2>/dev/null

hr "Btrfs snapshots (/.snapshots)"
if [ -d /.snapshots ]; then
  ls /.snapshots | head -30
  echo "snapshot count: $(ls /.snapshots | wc -l)"
  btrfs subvolume list / 2>/dev/null | grep -i snapshot | head -30
  command -v snapper >/dev/null && snapper list 2>/dev/null | tail -30
else
  echo "no /.snapshots folder"
fi

hr "Pacman cache"
du -sh /var/cache/pacman/pkg 2>/dev/null
echo "packages cached: $(ls /var/cache/pacman/pkg 2>/dev/null | grep -c '\.pkg\.')"
if command -v paccache >/dev/null; then
  echo "--- dry run: what 'paccache -rk2' would remove (keeps 2 versions per package)"
  paccache -dk2 2>/dev/null | tail -4
fi

hr "System journal and crash dumps"
journalctl --disk-usage 2>/dev/null
du -sh /var/lib/systemd/coredump 2>/dev/null

hr "Swap file"
ls -lh /swap/swapfile 2>/dev/null
swapon --show 2>/dev/null

hr "Biggest folders under /var, /usr and /opt"
du -xh --max-depth=2 /var 2>/dev/null | sort -rh | head -12
echo
du -xh --max-depth=2 /usr 2>/dev/null | sort -rh | head -10
echo
du -xh --max-depth=1 /opt 2>/dev/null | sort -rh | head -8

hr "Suggestions (NOT run; discuss first)"
cat <<'EOF'
  paccache -rk2            # trim pacman cache to 2 versions per package
  journalctl --vacuum-size=500M
  docker image prune       # only dangling images
  btrfs balance start -dusage=50 /   # releases half-empty data chunks (can take a while)
EOF
