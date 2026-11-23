#!/usr/bin/env python3
"""Monthly disk review. Shows exactly what would go, asks y/N per item.

  disk_prune             interactive review (nothing is deleted without a y)
  disk_prune --report    list candidates only (used by the monthly timer)

Safety rules baked in:
  * Never removes containers, volumes, or locally built Docker images.
  * Never touches photos, music, documents, backups or any bind mount.
  * Only things that regenerate on their own are candidates.
"""
import argparse, datetime, glob, os, shutil, subprocess

H = os.path.expanduser("~")
PROTECTED = [
    "all Docker containers, volumes and locally built images",
    "your files, and everything on external disks",
]
HAVE_DOCKER = shutil.which("docker") is not None


def run(*cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def human(n):
    return f"{n/1e9:.1f} GB" if n >= 1e9 else f"{n/1e6:.0f} MB"


def du(rel):
    p = os.path.join(H, rel)
    if not os.path.isdir(p):
        return 0
    out = run("du", "-sk", p).stdout.split()
    return int(out[0]) * 1024 if out else 0


# ---- Docker: only registry images that no container (even stopped) uses ----
def docker_images():
    used = set(run("docker", "ps", "-aq", "--no-trunc").stdout.split())
    used_img = set()
    for cid in used:
        used_img.add(run("docker", "inspect", "--format", "{{.Image}}", cid).stdout.strip())
    rows = []
    for line in run("docker", "image", "ls", "-a", "--no-trunc",
                    "--format", "{{.ID}}|{{.Repository}}:{{.Tag}}|{{.Size}}").stdout.splitlines():
        iid, name, size = line.split("|")
        if iid in used_img:
            continue  # a container (running or stopped) needs it
        digests = run("docker", "image", "inspect", "--format", "{{len .RepoDigests}}", iid).stdout.strip()
        if digests == "0":
            continue  # locally built: cannot be re-pulled, so never offered
        rows.append((iid, name, size))
    return rows


def prune_images(rows):
    for iid, name, size in rows:
        if input(f"    remove image {name} ({size})? [y/N] ").strip().lower() == "y":
            run("docker", "image", "rm", iid)


# ---- Trash: only things binned more than 30 days ago ----
def old_trash(days=30):
    info = os.path.join(H, ".local/share/Trash/info")
    files = os.path.join(H, ".local/share/Trash/files")
    cutoff = datetime.datetime.now() - datetime.timedelta(days=days)
    out = []
    for f in glob.glob(info + "/*.trashinfo"):
        try:
            for line in open(f):
                if line.startswith("DeletionDate="):
                    when = datetime.datetime.fromisoformat(line.strip().split("=", 1)[1])
                    if when < cutoff:
                        out.append((f, os.path.join(files, os.path.basename(f)[:-10])))
        except Exception:
            pass
    return out


def trash_size(items):
    total = 0
    for _, p in items:
        r = run("du", "-sk", p).stdout.split() if os.path.exists(p) else []
        total += int(r[0]) * 1024 if r else 0
    return total


def clean_trash(items):
    for info, p in items:
        if os.path.isdir(p) and not os.path.islink(p):
            shutil.rmtree(p, ignore_errors=True)
        elif os.path.lexists(p):
            os.remove(p)
        os.remove(info)


def rm_dir(rel):
    return lambda: shutil.rmtree(os.path.join(H, rel), ignore_errors=True)


def journal_size():
    out = run("journalctl", "--disk-usage").stdout
    return out.strip().split("take up")[-1].split("in the")[0].strip() if "take up" in out else "?"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args()
    u = shutil.disk_usage("/")
    print(f"/ is {u.used*100/u.total:.0f}% full, {u.free/1e9:.1f} GB free\n")

    imgs = docker_images() if HAVE_DOCKER else []
    trash = old_trash()
    items = [
        ("Docker images no container uses",
         f"{len(imgs)} images" if imgs else "none",
         "Registry images only (Docker re-downloads them if you ever start that app again). "
         "Locally built images and anything a container, even a stopped one, uses is skipped.",
         lambda: prune_images(imgs) if imgs else None, bool(imgs)),
        ("Docker build cache", None,
         "Leftover layers from image builds. Rebuilt automatically when you build again.",
         lambda: run("docker", "builder", "prune", "-af"), HAVE_DOCKER),
        ("yay (AUR) build cache", human(du(".cache/yay")),
         "Downloaded AUR sources and build folders. yay re-fetches on the next AUR install/update.",
         rm_dir(".cache/yay"), du(".cache/yay") > 0),
        ("debuginfod cache", human(du(".cache/debuginfod_client")),
         "Debug symbols downloaded when analysing crashes. Re-downloaded only if you analyse a crash.",
         rm_dir(".cache/debuginfod_client"), du(".cache/debuginfod_client") > 0),
        ("Trash older than 30 days", human(trash_size(trash)) + f" ({len(trash)} items)",
         "Only items you deleted over 30 days ago. Newer items stay in the Trash.",
         lambda: clean_trash(trash), bool(trash)),
        ("System journal (logs)", journal_size(),
         "Old log history; keeps the last 30 days and at most 1 GB. Asks for your sudo password. "
         "Logs are only useful for troubleshooting past events.",
         lambda: subprocess.run(["sudo", "journalctl", "--vacuum-time=30d", "--vacuum-size=1G"]), True),
    ]

    for name, size, why, _, avail in items:
        if not avail and not name.startswith(("Docker images", "Trash")):
            continue  # tool not installed / nothing there
        s = size if size is not None else "see docker"
        print(f"  {s:>22}  {name}")
        print(f"  {'':>22}  {why}\n")
    print("  NEVER touched:", "; ".join(PROTECTED))
    if a.report:
        return
    print()
    for name, size, why, act, avail in items:
        if not avail:
            continue
        if name.startswith("Docker images"):
            print(f"{name}:")
            act()
            continue
        if input(f"Clean '{name}' ({size or 'cache'})? [y/N] ").strip().lower() == "y":
            act()
    u = shutil.disk_usage("/")
    print(f"\nNow {u.used*100/u.total:.0f}% full, {u.free/1e9:.1f} GB free")


if __name__ == "__main__":
    main()
