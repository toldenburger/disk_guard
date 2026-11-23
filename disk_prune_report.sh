#!/usr/bin/env bash
# Monthly nudge: write the report and tell you to review it. Deletes nothing.
here="$(cd "$(dirname "$0")" && pwd)"
out="$HOME/.local/state/disk_guard/last_report.txt"
mkdir -p "$(dirname "$out")"
/usr/bin/python3 -I "$here/disk_prune.py" --report > "$out" 2>&1
# If the optional pacman cache archiver is installed, add its last result.
if systemctl cat pacman_cache_archive.service >/dev/null 2>&1; then
  {
    echo
    echo "== pacman cache archive (monthly root timer) =="
    systemctl show -p Result,ExecMainExitTimestamp pacman_cache_archive.service
    journalctl -u pacman_cache_archive.service -n 4 --no-pager -o cat 2>/dev/null
  } >> "$out"
fi
notify-send -a disk_guard "Monthly disk review" "Run: disk_prune   (report: $out)"
