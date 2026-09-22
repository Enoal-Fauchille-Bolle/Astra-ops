# Decisions and completed work

Finished work and the decisions behind it, kept for the _why_. One short entry each; the
full measurements and checks are in the git history of this file and of
`docs/backup/README.md`. Open work lives in [todo.md](todo.md).

## Rules that must not be undone

- **Never mount `/mnt/data/backups` whole into an app.** It holds the database dumps and
  the Proxmox configuration copy. Until 2026-09-14 both Filebrowser apps and SFTPGo did,
  and the dumps could be downloaded from the Internet through `drive.enoal.fr`.
- **Restore Pulsar from PBS to a new VMID.** Snapshots taken after `backup=0` hold no
  `scsi1`, and what an in-place restore does to an excluded disk is undocumented.
- **Keep off Astra what a restore of Astra needs.** The B2 key, Zerobyte's restic password
  and the Obsidian LiveSync secrets are in the official Bitwarden cloud, and Zerobyte's
  `APP_SECRET` is saved outside Astra too — Vaultwarden runs on Astra and goes down with it.
- **Address drives by model or UUID, never `nvmeXn1`.** The two NVMe drives swapped kernel
  names on the reboot of 2026-09-13.
- **`backup_user@pbs` cannot delete backups, on purpose.** It only holds `DatastoreBackup`,
  so a compromised Astra cannot erase its own backups; deleting snapshots is done by hand in
  the PBS web UI.
- **Do not install `grub-efi-amd64` in LXC 103.** `pbs3to4 --full` warns about it, but a
  container never boots through GRUB.

## Backups

- **2026-09-09 — Backblaze B2 adopted as the off-site target.** Immich first, then every
  other job; bucket `astra-pulsar-backup`, lifecycle `daysFromHidingToDeleting: 1`. MEGA A
  and C are frozen, MEGA B retired (see [todo.md](todo.md)).
- **2026-09-11 — Cold disk out of PBS (`backup=0` on `scsi1`).** A copy on the same Netac
  never survived its failure; the Tier 2 content goes to Backblaze instead. Accepted
  because every Tier 2 path on the Netac had an off-site copy by then.
- **2026-09-11 — One Crafty job for all three servers (job 15).** Job 9 only covered Nous
  Deux, so Survie Gay and Roots SMP had no off-site copy until then.
- **2026-09-11 — Nightly copy of the Proxmox configuration.** Nothing else kept `/etc/pve`
  or `/etc/proxmox-backup` off the host ([proxmox-config-copy.md](backup/proxmox-config-copy.md)).
- **2026-09-13 — Whole app roots instead of per-app jobs.** Jobs 16 and 17 copy
  `/opt/k3s-data` and `/opt/docker-data` whole, so a new app is covered without a new job.
  Live database directories are excluded: their dumps are the copy.
- **2026-09-13 — No separate Zerobyte job for the dumps.** `/mnt/data/backups/dumps/` is
  already inside job 13.
- **2026-09-14 — Nightly database dumps.** A file-level copy of a running database may be
  corrupt; the dumps are consistent. Installed by copy in `/usr/local/sbin`, not run from
  `/opt/ops`, because that clone is editable by a user account. Restore tested end to end on
  2026-09-15 ([database-dumps.md](backup/database-dumps.md)).
- **2026-09-14 — Immich is not in the dump script.** Its PostgreSQL carries vector
  extensions, so a plain `pg_dump` cannot be restored on a vanilla server; Immich dumps
  itself into `library/backups/`, which Backblaze covers.
- **2026-09-14 — CouchDB is not dumped.** Its files are copied raw by job 16 and the notes
  are end-to-end encrypted by LiveSync; a restore was tested on 2026-09-14.
- **2026-09-14 — Zerobyte restores to `/mnt/data/restore` only.** Every data mount is
  read-only, so a backup can never damage its source.
- **2026-09-15 — `zerobyte.db` joins the dumps.** `/var/lib/zerobyte` lies outside every
  Zerobyte volume, so only PBS held it.
- **2026-09-15 — Zerobyte notifies Discord only.** No ntfy webhook wanted. Messages over
  ~5,970 characters still fail (open in [todo.md](todo.md)).
- **2026-09-15 — Crafty archives stay compressed and taken live (`compress=1`,
  `shutdown=0`).** The watcher already stops Roots SMP when empty, so the 04:00 archive
  usually copies a stopped server; `shutdown=1` would restart a sleeping server while the
  watcher holds its port. Compression saves 3.3G on the Netac.
- **2026-09-15 — Passwords from the deleted Google export rotated.** The export survives in
  PBS snapshots of VM 100 for up to ~6 months.
- **Films are not backed up.** 47G, re-downloadable.

## Storage

- **2026-09-09 — Space reclaimed on the Netac.** `fstrim -av` in Pulsar returned 137G of
  dead space left by the deleted Kiwix library; `tune2fs -m 1` released 38G of ext4 reserve
  that PBS could never use; AdGuard's query log went from 90 to 7 days.
- **2026-09-11 — Crafty growth cut at the source.** Survie Gay and Nous Deux archive
  schedules paused (worlds no longer played); only Roots SMP archives daily.
- **2026-09-13 — Data placed by value, not by service.** Irreplaceable data (databases,
  configs, photos, worlds) lives on the WD Blue with three copies: the disk, PBS, Backblaze.
  Replaceable data or copies (films, ISOs, lab VMs, Crafty archives, the PBS datastore) live
  on the Netac with no backup required. No hardware purchase (both M.2 slots taken, no room
  for a SATA drive); no ZFS mirror — a dead disk is handled by restoring within hours.
- **2026-09-15 — Personal files on their own virtual disk, `drive`.** A dedicated 64G thin
  disk on the WD Blue (`scsi2`), not a folder of the system disk: a full `drive` must not
  stop the apps. Filled on 2026-09-20 with `rsync -a` as root to keep the `1000:1000` owner
  both apps need; the originals on the Netac were deleted on 2026-09-21 after a second
  checksum comparison. Films stay on the Netac, shown read-only.
- **2026-09-21 — Old PBS snapshots of `vm/100` deleted.** The seven snapshots that still
  held the cold disk weighed 349 GiB together; the datastore went from 476G to 113G and the
  Netac from 62 % to 22 %. The history of Pulsar's system disk before 2026-09-12 went with
  them.
- **2026-09-22 — Netac split into LVM compartments (method A of the disk plan).** One ext4
  filesystem holding the PBS datastore, the Pulsar cold disk and the ISOs let any of them
  starve the others. Everything was staged on the WD Blue, the Netac wiped and repartitioned
  as VG `netac`: LV `pbs` (300G ext4, fixed, `/mnt/pbs-datastore`, `nofail` in `fstab`), LV
  `files` (32G ext4, fixed, mounted at `/mnt/pve/vault` — kept that name and path so the
  105–108 lab VMs' CD-ROM references needed no change — Proxmox storage `vault`, content
  restricted to `iso,vztmpl,backup,snippets`), and a thin pool `thin` (Proxmox storage
  `vault-thin`) for Pulsar's cold disk. Chunk size forced to 64 KiB (`lvcreate -c 64k`) to
  match the existing `pve/data` pool — LVM's own default for a pool this size picked 512 KiB
  and warned about slow zeroing. ~100G left unallocated as reserve.
  Names, the 32G `files` size and leaving the lab-VM move as a separate decision were all
  confirmed with Enoal before the irreversible step (wiping the Netac).
  **Incident, same day:** moving the cold disk from its temporary WD copy into the new thin
  pool (`qm disk move 100 scsi1 vault-thin`) physically wrote all 500G of the declared virtual
  disk, not just the ~76G of real guest data — unlike the initial Netac→WD move, which had
  correctly skipped empty regions from the source `.qcow2` file. This filled the pool to
  96.15%. Two `fstrim` attempts inside Pulsar (including one after `mount -o remount`)
  reclaimed only ~57 MiB combined — ext4 most likely still believes it already reported that
  free space as trimmed from before the disk move, and a real unmount (not just a remount)
  would probably be needed to force a full re-trim, which was not attempted same-day since it
  would require briefly stopping Crafty, Zerobyte, Filebrowser Quantum and SFTPGo. Mitigated
  by growing `thin` from 520G to 620G using nearly all of the ~100G reserve (`lvextend -L
  +100G netac/thin`), bringing real usage down to ~80.65%. The ~400G of wasted space and the
  now-exhausted reserve remain open — see [monitoring.md](monitoring.md) for why Beszel could
  not have caught this on its own (thin pools have no file system to watch).

## PBS (LXC 103)

- **2026-09-12 — PBS upgraded to 3.4.9, then to 4 on 2026-09-13.** `proxmox-backup-manager
versions` prints the APT _candidate_, not the installed version: check with `dpkg`. The
  root disk was grown from 8G to 16G first, as the upgrade guide asks for 10G free.
- **2026-09-12 — `nesting=1` on LXC 103.** Without it, every unit that asks systemd for
  sandboxing died with `226/NAMESPACE` — `logrotate` had never run since install.
- **2026-09-13 — LXC 103 on the host's time zone.** Its jobs ran two hours late in UTC.
- **2026-09-13 — Astra rebooted onto kernel `7.0.14-16-pve`.** Every guest came back on its
  own (`onboot: 1`).

## Monitoring

- **2026-09-11 — Alerts on `vault` at 75 %, on LXC 101 and on LXC 103**, through Beszel,
  plus a Kuma DNS monitor for AdGuard ([monitoring.md](monitoring.md)).

## Security

Fixes from the security audit of 2026-09-08 (P3: apps with more privileges than they need).
A container that holds host-level privileges turns a flaw in one small app into control of
Pulsar.

- **2026-09-14 — Classic Filebrowser removed (`ca56a5a`).** The project was archived on
  2026-09-01 and gets no security fixes; `drive.enoal.fr` now reaches Filebrowser Quantum.
- **2026-09-14 — Filebrowser Quantum as uid 1000 (`c1b5a9e`)** and **2026-09-15 — SFTPGo
  as uid 1000 (`e87b3b6`).** As root, SFTPGo's account could read and delete the dumps. See
  [`k3s/filebrowser-quantum/README.md`](../k3s/filebrowser-quantum/README.md) for what
  undoes the ownership.
- **2026-09-15 — Cloudflare tunnel removed (`90d75ad`).** It ran with no route at all.
- **2026-09-15 — dashdot without privileged mode (`dc21b1d`).** It ran `privileged: true`
  with `/` mounted: a flaw in it was root on Pulsar. Now uid 1000 with five read-only
  mounts; the data-disk mount needs the empty `/mnt/data/.dashdot`.
- **2026-09-15 — portracker without ptrace or `SYS_ADMIN` (`dfa6af3`).** The host PID
  namespace with `SYS_PTRACE` let it attach to any host process. It still lists every port,
  but no longer names the program behind host ports — `sudo ss -tulpn` on Pulsar does.
- **2026-09-15 — CrowdSec bans reach the containers.** NPM restores the visitor's address
  behind Cloudflare, then the bouncer was hooked into `DOCKER-USER` — in that order, or the
  first ban would have cut every public site
  ([`docker/crowdsec/README.md`](../docker/crowdsec/README.md)).
