# Proxmox configuration copy

A nightly job on Astra copies both configurations to Pulsar, where Zerobyte job 13
(**Backups**) ships them to Backblaze at 02:00 — no new Zerobyte volume was needed.
First unattended night, 2026-09-12: copy sent at 01:30:05, Kuma push `up`, and job 13 went
from 12 to 62 files (50 new) in `succeeded`.

| Piece | Where | What it does |
| --- | --- | --- |
| Script | `infra/astra/proxmox-config-backup.sh` → `/usr/local/sbin/proxmox-config-backup` on Astra | stages the copy in `/run` (tmpfs), then rsyncs it to Pulsar with `--delete` |
| Timer | `infra/astra/proxmox-config-backup.{service,timer}` | daily at **01:30**, `Persistent=true` (catches up at boot) |
| Destination | `/mnt/data/backups/proxmox-configs/` on Pulsar | owned by `astra-configs`, directories `700`, files `600` |
| Alerting | Uptime Kuma push monitor **Proxmox Config Backup** | `up` on success, `down` on any failure, alert on Discord if no push for 25 h (§10) |

What the copy holds (~70 KB):

| Folder | Content | Used for |
| --- | --- | --- |
| `pve/` | `/etc/pve` as readable files (runtime dotfiles and `priv/lock/` skipped) | reading or re-creating a single setting |
| `pmxcfs/config.db` | the pmxcfs database, copied with `sqlite3 .backup` and integrity-checked | the official full recovery (§9.4) |
| `pbs/proxmox-backup/` | `/etc/proxmox-backup` from LXC 103 (lock files skipped) | rebuilding PBS (§9.4) |
| `host/` | `/etc/hostname`, `/etc/hosts`, `/etc/network/interfaces`, `/etc/fstab`, `mnt-pve-vault.mount` | identity, network and `vault` mount of Astra |
| `MANIFEST.txt` | date, `pveversion -v`, `proxmox-backup-manager versions` | reinstalling the same versions first |

**Transport.** Astra pushes; Pulsar never gets any access to Astra. Root on Astra uses a
dedicated key (`/root/.ssh/proxmox-config-backup_ed25519`) and a pinned host key
(`/root/.ssh/proxmox-config-backup_known_hosts`). On Pulsar, the system account
`astra-configs` (shell `dash`, root-owned home and `authorized_keys`) accepts that key only as:

```
restrict,from="192.168.1.200",command="rrsync -wo /mnt/data/backups/proxmox-configs" ssh-ed25519 …
```

Verified on 2026-09-11: an interactive shell, an arbitrary command, reading back, a path
outside the directory (`..`) and both port-forwarding directions are refused; writing works.
This does not protect Pulsar from a compromised Astra (the hypervisor owns the VM anyway); it
confines a script mistake or a leaked key to one directory.

**Secrets.** The copy contains private keys, password hashes, the PBS storage password and
the Resend API key. They are protected by file permissions on Pulsar and by restic encryption
off-site — no second encryption layer, since Zerobyte on Pulsar already holds the keys to
every repository. File permissions do not stop a container running as root: both Filebrowser
apps could browse this copy until 2026-09-14 (§6, *Who else can read the dumps*). The push URL lives in `/etc/default/proxmox-config-backup` (root, `600`),
outside this repository.

**Failure behaviour.** Every step runs under `set -e` and the transfer comes last: if one step
fails (integrity check, LXC 103 stopped…), nothing is sent and Pulsar keeps the last good copy.

## Reinstalling this mechanism from scratch

Nothing here is deployed by ArgoCD or Portainer — after a fresh Astra or Pulsar (§9.3), both
sides must be rebuilt by hand, in this order. Verified against the live setup on 2026-09-22.

**1. On Pulsar — the receiving account.** Root-owned home and `.ssh`, so a compromised
`rrsync` command cannot rewrite its own restriction:

```bash
sudo useradd --system --home-dir /var/lib/astra-configs --create-home --shell /usr/bin/dash astra-configs
sudo chown root:root /var/lib/astra-configs
sudo chmod 755 /var/lib/astra-configs
sudo mkdir -p /var/lib/astra-configs/.ssh
sudo chown root:root /var/lib/astra-configs/.ssh
sudo chmod 755 /var/lib/astra-configs/.ssh
sudo touch /var/lib/astra-configs/.ssh/authorized_keys
sudo chown root:root /var/lib/astra-configs/.ssh/authorized_keys
sudo chmod 644 /var/lib/astra-configs/.ssh/authorized_keys

sudo install -d -o astra-configs -g astra-configs -m 700 /mnt/data/backups/proxmox-configs
```

`rrsync` ships inside the `rsync` package, already installed by default on Ubuntu Server —
nothing extra to install for it.

**2. On Astra — the key pair and pinned host key.**

```bash
sudo ssh-keygen -t ed25519 -f /root/.ssh/proxmox-config-backup_ed25519 \
  -C "root@astra proxmox-config-backup" -N ""
sudo ssh-keyscan -t ed25519 192.168.1.201 | sudo tee /root/.ssh/proxmox-config-backup_known_hosts
```

> [!CAUTION]
> `ssh-keyscan` trusts whatever answers on the network the first time (TOFU). On a LAN this is
> usually fine, but for real confidence compare its output against Pulsar's actual host key,
> read directly on its console: `ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub`.

**3. Authorize that key on Pulsar.** Append one line to
`/var/lib/astra-configs/.ssh/authorized_keys` (still root-owned — edit it as root, not as
`astra-configs`), pasting the public key just generated after `command="..."`. The full line,
with its `restrict` and `rrsync -wo` restriction, is shown above under *Transport*.

**4. On Astra — install the script and the timer**, from a clone of this repository:

```bash
sudo install -o root -g root -m 755 infra/astra/proxmox-config-backup.sh /usr/local/sbin/proxmox-config-backup
sudo install -o root -g root -m 644 infra/astra/proxmox-config-backup.service /etc/systemd/system/proxmox-config-backup.service
sudo install -o root -g root -m 644 infra/astra/proxmox-config-backup.timer /etc/systemd/system/proxmox-config-backup.timer
```

**5. Recreate the push URL**, from the **Proxmox Config Backup** monitor in Uptime Kuma
(§10) — copy its push URL and keep only the part before `?`:

```bash
printf 'PUSH_URL=%s\n' '<push URL from the Uptime Kuma monitor>' | sudo tee /etc/default/proxmox-config-backup
sudo chmod 600 /etc/default/proxmox-config-backup
```

**6. Enable and test:**

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now proxmox-config-backup.timer
sudo systemctl start proxmox-config-backup.service   # first run, on demand
journalctl -u proxmox-config-backup --no-pager -n 30
```

A successful run leaves the four folders (`pve/`, `pmxcfs/`, `pbs/`, `host/`) and
`MANIFEST.txt` under `/mnt/data/backups/proxmox-configs/` on Pulsar (owned by
`astra-configs`, `700`/`600`, as in §4.2) and turns the Kuma monitor green.

## 9.4 Restoring the Proxmox configuration

**Where to get it:** `/mnt/data/backups/proxmox-configs/` on Pulsar if it survived, otherwise
Zerobyte job 13 (**Backups**, repository **Backblaze**) — pick a snapshot from before the
incident, since the nightly copy mirrors the current state with `--delete`.

**Proxmox VE — full recovery** (`pmxcfs` documentation, section *Recovery*), on a fresh
install with nothing running:

1. Install the Proxmox VE version listed in `MANIFEST.txt`.
2. `systemctl stop pve-cluster`
3. Copy `pmxcfs/config.db` to `/var/lib/pve-cluster/config.db` and set it to `0600`, owned by root.
4. Adapt `/etc/hostname` and `/etc/hosts` from `host/`, and `/etc/network/interfaces` if the
   hardware (NIC names) is the same.
5. Reboot, then check storage, VMs and LXCs — the disks themselves come from PBS or Layer 2.

For a single setting, read the matching file under `pve/` instead.

**Proxmox Backup Server** — in a fresh LXC with the same PBS version, stop
`proxmox-backup-proxy` and `proxmox-backup`, copy `pbs/proxmox-backup/*` into
`/etc/proxmox-backup/`, and restore the original ownership, which the copy does not keep
(every file arrives as `600`):

| Files | Owner | Mode |
| --- | --- | --- |
| `authkey.key`, `notifications-priv.cfg`, `shadow.json` | `root:root` | `600` |
| every other file (`*.cfg`, `authkey.pub`, `csrf.key`, `proxy.key`, `proxy.pem`) | `root:backup` | `640` |
| the directory `/etc/proxmox-backup` | `backup:backup` | `700` |

Then start both services again. The datastore itself is self-describing (§4.2).
