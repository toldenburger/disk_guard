#!/usr/bin/env python3
"""Warn early when the root disk is filling up. Notify only, never deletes.

Levels (whichever trips first):
  warn   used >= 85%  or  free < 30 GB      (once a day)
  crit   used >= 93%  or  free < 12 GB      (once every 2 hours)
  fast   at the last hour's growth rate the disk fills in < 4 h
         and it grew > 1 GB/h               (once every 3 hours)

Also keeps ~/.local/state/disk_guard/usage.csv (time, used, free) for 14 days,
so next time there is a record of what happened and when.

The warning lists the biggest folders in your home. To also list specific
folders (a big app cache, say), set DISK_GUARD_EXTRA to a colon-separated list:
  DISK_GUARD_EXTRA="~/.cache/some-app:~/Downloads"
"""
import argparse, json, os, shutil, subprocess, time

DIR = os.path.expanduser("~/.local/state/disk_guard")
STATE, HIST = os.path.join(DIR, "watch.json"), os.path.join(DIR, "usage.csv")
GB = 1e9
COOLDOWN = {"warn": 86400, "crit": 7200, "fast": 10800}


def history(now, used, free):
    os.makedirs(DIR, exist_ok=True)
    rows = []
    try:
        rows = [tuple(map(float, l.split(","))) for l in open(HIST) if l.strip()]
    except Exception:
        pass
    rows.append((now, used, free))
    rows = [r for r in rows if now - r[0] < 14 * 86400]
    with open(HIST, "w") as f:
        f.writelines(f"{int(t)},{int(u)},{int(fr)}\n" for t, u, fr in rows)
    return rows


def growth_gb_per_h(rows, now):
    """Average growth over roughly the last hour (needs >= 30 min of data)."""
    recent = [r for r in rows if now - r[0] <= 3900]
    if len(recent) < 2 or recent[-1][0] - recent[0][0] < 1800:
        return 0.0
    dt = (recent[-1][0] - recent[0][0]) / 3600
    return (recent[-1][1] - recent[0][1]) / GB / dt


def sh(*cmd, t=60):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=t).stdout
    except Exception:
        return ""


def culprits():
    """Biggest folders in $HOME, any DISK_GUARD_EXTRA folders, and Docker, for the message."""
    home = os.path.expanduser("~")
    rows = []
    for line in sh("du", "-xk", "--max-depth=1", home, t=120).splitlines():
        if "\t" in line:
            k, p = line.split("\t")
            rows.append((int(k), p))
    rows.sort(reverse=True)
    out = [f"{os.path.basename(p)} {k/1048576:.0f}G" for k, p in rows[1:4]]
    for extra in filter(None, os.environ.get("DISK_GUARD_EXTRA", "").split(":")):
        path = os.path.expanduser(extra)
        k = sh("du", "-sk", path).split()
        if k:
            out.append(f"{os.path.basename(path.rstrip('/'))} {int(k[0])/1048576:.0f}G")
    df = sh("docker", "system", "df", "--format", "{{.Type}} {{.Size}}").splitlines() if shutil.which("docker") else []
    if df:
        out.append("docker " + df[0].replace("Images ", "images "))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="print, don't notify or record cooldowns")
    a = ap.parse_args()
    now = time.time()
    u = shutil.disk_usage("/")
    pct, free = u.used * 100 / u.total, u.free / GB
    rows = history(now, u.used, u.free)
    rate = growth_gb_per_h(rows, now)
    hours_left = free / rate if rate > 1 else None

    level = None
    if pct >= 93 or free < 12:
        level = "crit"
    elif pct >= 85 or free < 30:
        level = "warn"
    if level != "crit" and hours_left is not None and hours_left < 4:
        level = "fast"
    print(f"/ {pct:.0f}% full, {free:.1f} GB free, growth {rate:+.1f} GB/h, level={level}")
    if not level:
        return

    try:
        state = json.load(open(STATE))
    except Exception:
        state = {}
    if not a.dry_run and now - state.get(level, 0) < COOLDOWN[level]:
        return

    title = {"crit": "DISK ALMOST FULL", "warn": "Disk filling up", "fast": "Disk filling FAST"}[level]
    body = f"{pct:.0f}% used, {free:.1f} GB free."
    if rate > 0.5:
        body += f" Growing {rate:.1f} GB/h" + (f", full in ~{hours_left:.1f} h." if hours_left else ".")
    body += "\nBiggest: " + "; ".join(culprits()) + "\nRun: disk_prune"
    if a.dry_run:
        print(title + "\n" + body)
        return
    subprocess.run(["notify-send", "-u", "critical" if level != "warn" else "normal",
                    "-a", "disk_guard", title, body])
    state[level] = now
    json.dump(state, open(STATE, "w"))


if __name__ == "__main__":
    main()
