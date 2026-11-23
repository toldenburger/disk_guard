# disk_guard

Small scripts that stop a Linux system disk from quietly filling up. They **warn early** and help you
**clean up safely**. Nothing is ever deleted automatically.

```text
$ python3 disk_watch.py --dry-run
/ 86% full, 32.8 GB free, growth +0.2 GB/h, level=warn
Disk filling up
86% used, 32.8 GB free.
Biggest: .local 22G; Projects 10G; .cache 9G; docker images 40.84GB
Run: disk_prune
```

| Script | What it does | Deletes? |
|---|---|---|
| `disk_watch.py` | checks the disk every 10 minutes and shows a notification when it is getting full, or filling unusually fast | no |
| `disk_prune.py` | shows what can be cleaned, explains each item, asks **y/N** for each | only what you say **y** to |
| `disk_prune_report.sh` | monthly reminder with a written report | no |
| `disk_sudo_report.sh` | read-only size report of the parts a normal user can't see (Docker, snapshots, swap, journal…) | no |
| `system/` | optional, Arch only: moves old pacman package versions to a backup disk once a month | moves, doesn't delete |

## When it warns

| Level | Trigger | Repeats |
|---|---|---|
| warn | 85% used or less than 30 GB free | once a day |
| critical | 93% used or less than 12 GB free | every 2 hours |
| filling fast | at the last hour's speed, full in less than 4 hours (and growing over 1 GB/h) | every 3 hours |

The message names the biggest folders in your home and Docker's disk use, so you know where to look.
It also keeps two weeks of usage history in `~/.local/state/disk_guard/usage.csv`.

## What `disk_prune` offers

Only things that come back on their own when needed:

- Docker images from a registry that **no container uses, not even a stopped one**. Images you built
  yourself are never offered, because they can't be downloaded again.
- Docker build cache
- yay (AUR) build cache and debuginfod cache, if present
- Trash items older than 30 days
- The system journal, trimmed to 30 days / 1 GB (asks for sudo)

It never touches containers, volumes, your own files or other disks.

## Install

Needs Python 3.9+ and `notify-send` (package `libnotify`). Docker, yay and paccache are optional.

```bash
git clone https://github.com/toldenburger/disk_guard ~/disk_guard
cd ~/disk_guard
python3 disk_watch.py --dry-run        # try it: prints, doesn't notify

mkdir -p ~/.config/systemd/user
cp units/* ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now disk_watch.timer disk_prune_report.timer
```

The services expect the repo at `~/disk_guard`; edit the `ExecStart` lines if you put it elsewhere.

Make `disk_prune` a command:

```bash
mkdir -p ~/.local/bin
ln -s ~/disk_guard/disk_prune.py ~/.local/bin/disk_prune
disk_prune              # interactive review
disk_prune --report     # list only
```

### Options

- **Name extra folders in the warning**: set `DISK_GUARD_EXTRA` (colon-separated), for example in
  `units/disk_watch.service`:
  `Environment=DISK_GUARD_EXTRA=%h/.cache/some-app:%h/Downloads`
- **Change the limits**: edit the numbers in `disk_watch.py` (`main()` and `COOLDOWN`).

### Optional: archive old pacman packages (Arch)

```bash
mkdir /path/to/backup/disk/pacman_cache
sudo system/install.sh /path/to/backup/disk/pacman_cache
```

Once a month it moves old package versions off the system disk with `paccache`, keeping the newest version
of every installed package. If the backup disk isn't mounted, it does nothing.

## License

MIT, see [LICENSE](LICENSE).

---

Made by Claude 🤖
