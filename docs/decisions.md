# Decisions and completed work

> Section numbers (§) refer to the [backup overview](backup/README.md); each numbered section there
> is either in place or points to where it moved.

Finished work and the decisions behind it, kept for the *why*. Open work lives in
[todo.md](todo.md).

## Backups and storage

> **Reviewed against the machines on 2026-09-11.** Items are checked only where the state was
> actually verified, not where it was merely planned.

### Layer 2 — Zerobyte

- [x] Configure rclone remotes on Pulsar — `mega-a`, `mega-b`, `mega-c`, `mega-d`, `backblaze-test`
- [x] Deploy Zerobyte via Docker Compose (`docker/zerobyte/docker-compose.yml`, v0.42)
- [x] Create Zerobyte repositories — `Mega A`, `Mega C`, `Mega D`, `Backblaze`
- [x] Add `zerobyte.lan` DNS entry in AdGuard Home
- [x] Add NPM proxy host for `zerobyte.lan`
- [x] Move Immich off-site to Backblaze B2 (2026-09-09) — 7/7 schedules now `success`
- [x] **Declare the three mounted-but-undeclared volumes** (2026-09-10) — `/mnt/data/backups`
      triaged first (8.8G → 102M), then volumes 11, 12, 13 and jobs 12, 13, 14 to Backblaze.
      First nightly run 2026-09-11: all `success`.
- [x] **Send every Crafty server off-site** (2026-09-11) — job 9 (Mega D) only covered Nous
      Deux; replaced by job 15 to Backblaze covering all three servers, retention 7/4/3.
- [x] **Give Zerobyte a writable restore target** (2026-09-14) — `/mnt/data/restore` (root
      `700`) mounted at `/restore`; restore from Backblaze tested, identical to the original (§9.6)
- [x] **Send `zerobyte.db` off-site** (2026-09-15) — `/var/lib/zerobyte` lies outside every
      Zerobyte volume, so only PBS held it (found 2026-09-14). Added to the nightly dumps (§6),
      which job 13 ships to Backblaze; first run by hand: 17/17, the copy matches the original
      (13 schedules, 6 repositories, 12 volumes)
- [x] **Keep Zerobyte's `APP_SECRET` off Astra** (2026-09-20) — saved by Enoal outside Astra;
      the database copy above is only usable with it ([restore.md](backup/restore.md#93-scenario-c--total-loss-of-astra), step 6). It stays set in
      Portainer's stack 11 environment
- [x] ~~Set up ntfy webhook in Zerobyte settings~~ — not wanted: Discord only (decided 2026-09-15)
- [x] Create `/mnt/data/backups/dumps/` directory — created by the dump script on its first run
      (2026-09-14), root `700`
- [x] **Back up the Proxmox configuration** (2026-09-11) — nightly copy of `/etc/pve`,
      `config.db`, `/etc/proxmox-backup` and host files to `/mnt/data/backups/proxmox-configs/`,
      picked up by job 13; Uptime Kuma push monitor (§4.2). The `Permission denied` of
      2026-09-09 did not reproduce: the files are `root:www-data 640`, so any read without
      `sudo` fails — most likely the second half of a `sudo a; b` command.
- [x] **Put the B2 key and Zerobyte's restic password somewhere off Astra** — both kept in
      the official Bitwarden cloud, not the self-hosted Vaultwarden ([restore.md](backup/restore.md#93-scenario-c--total-loss-of-astra)); recorded 2026-09-12

### Storage — reclaimed 2026-09-09

- [x] Resize Pulsar `sda` from 100G → 200G
- [x] Move `/mnt/data/k3s-pvc/immich/` → `/opt/k3s-data/immich/library/`
- [x] Move `/mnt/data/k3s-pvc/homer/` → `/opt/k3s-data/homer/`
- [x] Move `/mnt/data/k3s-pvc/criteri-fresque/` → `/opt/k3s-data/criteri-fresque/`
- [x] Delete residue `/opt/k3s-data/crafty/`
- [x] **`fstrim -av` on Pulsar** — returned **137G** of dead space to `vault` (79 % → 63 %)
- [x] **`tune2fs -m 1 /dev/nvme1n1p1`** — released **38G** of ext4 root reserve (63 % → 61 %).
      `nvme1n1` was the Netac then; the name now points at the WD Blue (§2.1)
- [x] **AdGuard query log** — retention 90d → 7d and log cleared; LXC 101 went 95 % → 11 %
- [x] **Second `fstrim -av` on Pulsar** (2026-09-11) — **20.25 GiB** returned after the
      `/mnt/data/backups` triage (65 % → 63 %)
- [x] **Cut the growth at the source** (2026-09-11) — Survie Gay and Nous Deux Crafty archive
      schedules paused (worlds no longer played); only Roots SMP still archives daily.

### Storage

- [x] **Apply `backup=0` on `scsi1`** — applied 2026-09-11 at 11:21 (§4.2); the 2026-09-12
      03:00 snapshot of VM 100 holds `drive-scsi0` only
- [x] Delete the three surplus Nous Deux archives in Crafty (2026-09-11) — 2 remain
- [x] **Upgrade PBS to 3.4.9** (2026-09-12) — this item used to say 3.4.9-2 was installed and
      only a restart was missing. Wrong: `dpkg` still had `3.4.8-3`, and
      `proxmox-backup-manager versions` prints the APT *candidate*, not the installed version.
      `apt full-upgrade` in LXC 103, the first since install on 2026-04-16 (78 packages);
      `running version: 3.4.9` afterwards
- [x] Delete the safety backup `vzdump-lxc-103-2026_09_12-16_26_15.tar.zst` from `local`
      (888 MB) once the first nights after the upgrade are checked — deleted 2026-09-13
- [x] **Upgrade PBS to 4** (2026-09-13) — Debian 12 → 13, PBS 3.4.9 → 4.2.5. Safety net
      first: `vzdump-lxc-103-2026_09_13-15_12_10.tar.zst` (1.07 GB). Local versions kept for
      `/etc/pam.d/common-session`, `/etc/issue`, `/etc/crontab` and `/etc/cron.d/e2scrub_all`.
      Root disk grown 8G → 16G beforehand (UI: Resources → Root Disk → Volume Action →
      Resize): the guide asks for 10 GB free and there were 3.9, eaten by kernel packages the
      container never boots. 11G free afterwards. `pbs3to4 --full` still warns about NTP and
      `grub-efi-amd64`; both are moot in a container, which uses the host's clock and never
      boots through GRUB — do not install `grub-efi-amd64`
- [x] **Put LXC 103 on Paris time** (2026-09-13) — `pct set 103 --timezone host`. Prune
      "04:00" had been running at 06:00 Paris, verify and GC "05:00" at 07:00
- [x] Delete the safety backup `vzdump-lxc-103-2026_09_13-15_12_10.tar.zst` from `local`
      once the first night on PBS 4 is checked — deleted 2026-09-14. That night: vzdump 03:00
      `OK` (VM 100, CT 101, CT 102 in PBS), prune at **04:00** Paris, logrotate at 00:00,
      `systemctl --failed` empty
- [x] **First verify and GC under PBS 4** (2026-09-19 and 20) — both fired at 05:00 Paris as
      scheduled, where the last runs (12 and 13 September) had drifted to 07:00 under PBS 3.
      Verify: `TASK OK` in 10 min 55 s, 21 snapshots read with 0 errors; the 30 others were
      skipped as `recently verified` (the job carries `ignore-verified` with a 30-day window,
      so the snapshots last checked under PBS 3 come back one by one over the next month).
      GC: `TASK OK` in 9 s, **36.797 GiB** and 33 617 chunks removed, 0 bad chunks, 0 chunks
      left pending. Afterwards the datastore holds **476.314 GiB** for 7.297 TiB of original
      data (deduplication 15.69, average chunk 1.982 MiB), and the Netac is at **62 %** —
      571G used of 938G, 358G free. The week's nightly jobs were all `OK` as well (backups
      03:00, prune 04:00), and `systemctl --failed` is empty in LXC 103
- [x] **Reboot Astra onto kernel `7.0.14-16-pve`** (2026-09-13, 15:38) — installed with
      PVE 9.2.11 → 9.2.18 on 2026-09-12. Pulsar, AdGuard and PBS came back on their own
      (`onboot: 1`), `systemctl --failed` empty on the host, `pvesm list pbs-local` lists the
      51 snapshots. The two NVMe drives swapped kernel names on this boot (§2.1)
- [x] ~~Crafty backups use `compress=1` and `shutdown=0`~~ — kept as is (decided 2026-09-15).
      Crafty's documentation recommends stopping the server during backups and warns
      compression can damage chunk data. But the watcher already stops Roots SMP 10 minutes
      after the last player leaves (on 2026-09-15 it had slept since 22:29), so the 04:00
      archive, done in 45 s, copies a stopped server unless someone plays at that moment;
      `shutdown=1` would make Crafty restart a sleeping server while the watcher holds its
      port (untested). Compression takes each archive from 2.8G to 1.7G, 3.3G saved on the
      Netac for the three kept. No Crafty archive has been test-restored yet
- [x] Rotate the passwords from the deleted Google export — it survives in PBS snapshots of
      VM 100 for up to ~6 months; passwords changed by Enoal (recorded 2026-09-15)

### Disk layout — decided 2026-09-13

Data is placed by its value, not by the service it belongs to. Inside Pulsar:

- **Irreplaceable** (databases, configs, photos, Minecraft worlds) → `/opt/k3s-data` or
  `/opt/docker-data`, on the WD Blue. Three copies: the disk, PBS on the Netac, Backblaze.
- **Replaceable, or already a copy** (films, ISOs, lab VMs, Crafty archives, the PBS
  datastore) → `/mnt/data` or `vault`, on the Netac. No backup required.

No hardware purchase: both M.2 slots are taken and the case has no room for a SATA drive.
Backblaze carries the off-site copy of 3-2-1. A dead disk is handled by restoring within
hours, not by a mirror, so ZFS was ruled out.

- [x] **Send every app directory off-site** (2026-09-13) — jobs 16 and 17 copy
      `/opt/k3s-data` and `/opt/docker-data` whole to Backblaze, with 9 exclusions (§5.4); the
      five per-app jobs they replace (4, 6, 7, 11, 12) are disabled. The live PostgreSQL and
      MariaDB directories are excluded; their dumps (Phase 2, since 2026-09-14) are the copy.
      First nightly run 2026-09-14 at 01:00: both `success`, same file counts as the manual run
- [x] **Remove the classic Filebrowser and serve `drive.enoal.fr` from Filebrowser Quantum**
      (2026-09-14, `ca56a5a`) — the classic project was archived on 2026-09-01 and gets no
      security fixes. Both apps shared `/mnt/data/k3s-pvc/filebrowser`, so no file moved; the
      classic app had no share links, and its `test` account (an empty folder) was not
      recreated. Checked after ArgoCD's sync: no classic Deployment, Service, Ingress or VPA
      left, `drive.enoal.fr` answers with Quantum, whose pod sees `OnePlus-10T/` and no
      `dumps/`. Login is a personal account (`enoal`) created by Enoal; `filebrowser.lan`
      now gets NPM's default 404 page (proxy host 34 removed). Kuma: Enoal deleted monitor 13
      and pointed monitor 15 ("Filebrowser Quantum") at `https://drive.enoal.fr`; no monitor
      probes `filebrowser-quantum.lan` any more (checked 2026-09-14)
- [x] **Run Filebrowser Quantum as non-root** (2026-09-14, `c1b5a9e`) — `runAsUser`/`runAsGroup`
      1000, `runAsNonRoot`, no privilege escalation, every capability dropped. 1000 is the
      image's own `filebrowser` user and already owned `/mnt/data/media` (`enoal` on Pulsar).
      hostPath volumes ignore `fsGroup`, so Enoal chowned `/mnt/data/k3s-pvc/filebrowser`,
      `/mnt/data/backups/OnePlus-10T` and `/opt/k3s-data/filebrowser-quantum` to `1000:1000`
      by hand; SFTPGo, which mounts the same directories and still runs as root, got uid/gid
      1000 on its `enoal` user so that it chowns every file it creates (checked with an
      upload: `enoal:enoal 644`). Port 80 binds without root (`ip_unprivileged_port_start=0`
      in the pod). Checked after ArgoCD's sync: `id` → `uid=1000(filebrowser)`, `CapEff` 0,
      `NoNewPrivs` 1, no error in the logs, Kuma monitor 15 stayed `up`, no file outside
      `1000:1000` in the four directories. Enoal created, edited and deleted a file in
      `files` and browsed `Media` and `Backups`. **Undone by**: a file put there by root on
      the host (`sudo cp`), or a restore from a snapshot older than the night of 2026-09-15 —
      re-run the `chown -R 1000:1000`. A new account's sidebar lists one source only: add
      the others with the pencil next to *Navigation*
- [x] **Run SFTPGo as non-root** (2026-09-15, `e87b3b6`) — same settings as Quantum: uid/gid
      1000 (the image's own `sftpgo` user), `runAsNonRoot`, no privilege escalation, every
      capability dropped. Found that morning: as root, SFTPGo mounted `/mnt/data/backups` whole
      and its only account (`enoal`, home `/data`, every permission) could read, change and
      delete the database dumps and the Proxmox configuration copy — the leak closed on
      2026-09-14 for Filebrowser, LAN and VPN only here. Only `/opt/k3s-data/sftpgo` (its
      database and host keys) was still root's; Enoal chowned it to `1000:1000`. Checked after
      ArgoCD's sync: `id` → `uid=1000(sftpgo)`, `CapEff` 0, `NoNewPrivs` 1, `dumps/` and
      `proxmox-configs/` → `Permission denied` from the pod, phone backups and media still
      readable, both listeners up with no error, `sftpgo.lan` → `200`, Kuma monitor up; Enoal
      uploaded and deleted a file. The mount itself goes away with `drive` (below)
- [x] **Delete `/opt/k3s-data/filebrowser`** (64K, the removed app's database, 2026-09-14) —
      no pod, container or open file used it; job 16 had already copied it to Backblaze
- [x] **Gather personal files into one `drive`** (decided 2026-09-15, after the first verify and
      GC under PBS 4) — replaces "move `/mnt/data/media/photos` and `/mnt/data/k3s-pvc/filebrowser`
      under `/opt/k3s-data`". Personal files are the only thing SFTPGo and Filebrowser Quantum
      may mount; everything else on Pulsar is system. Decided:
      - a dedicated virtual disk for Pulsar on the WD Blue (`local-lvm`, thin), not a folder of
        the system disk: a full `drive` must not stop the apps and their databases. PBS backs
        it up with VM 100, and it gets its own Backblaze job
      - one account, a plain tree — `Documents/`, `Photos/`, `Téléphone/` (today
        `backups/OnePlus-10T`), `Archives/` (`Nexus Backup`, `Snapchat`)
      - films stay on the Netac (replaceable, 47G), shown read-only as a second folder in both
        apps
      Measured 2026-09-15: 5.7G to move without the films; `local-lvm` 657G free, Pulsar's
      system disk 81G free. Keep the owner `1000:1000` (`rsync -a` as root), or both apps lose
      write access

      **Done 2026-09-20 and 21** (§2.2, §8.1):
      - 2026-09-20: `scsi2`, 64G on `local-lvm`, created by Enoal in the UI and hot-plugged
        (`sdc`); ext4 labelled `drive`, `-m 1`, mounted by UUID at `/mnt/drive`. 5.7G copied,
        216 files, checksums identical, no file outside `1000:1000`. Both apps switched to
        `/mnt/drive` + read-only movies (`c9e98e1`), Zerobyte given `/data/drive` read-only
        (`646c539`); Enoal created volume and job 18 **Drive** (Backblaze, 02:00, 7/4/3) and
        disabled jobs 10 and 14 (§5.4)
      - 2026-09-21: job 18 `success`, 216 files; PBS snapshot of VM 100 holds
        `drive-scsi2.img.fidx` (§4.2). The checksums were compared once more (0 difference,
        45 + 128 + 12 + 30 + 1 = 216 files), then the originals on the Netac were deleted:
        `/mnt/data` 78G → 72G. `k3s-pvc/filebrowser/` and `media/photos/` were emptied but
        kept, as Zerobyte still mounts them for the frozen jobs 10 and 14
- Films (`/mnt/data/media/movies`, 47G) are replaceable: no backup, by decision

### Phase 2 — Database dumps

- [x] **Write the dump script** (2026-09-14) — `infra/pulsar/dump-databases.sh`, installed as
      `/usr/local/sbin/dump-databases`, not run from `/opt/ops` as first planned (§6)
- [x] **Exclude Immich from the script** — its database runs on
      `postgres:14-vectorchord0.4.3-pgvectors0.2.0`, and a plain `pg_dump` produces a file no
      vanilla PostgreSQL can restore. Immich already dumps itself into `library/backups/`,
      which Backblaze covers.
- [x] **Add Umami, Infisical and Dawarich** (2026-09-14)
- [x] **Dump Uptime Kuma with `mariadb-dump`** (2026-09-14) — present in the image, root reaches
      the embedded MariaDB over its socket without a password
- [x] **Choose the SQLite databases** (2026-09-14) — the 12 worth a guaranteed copy, out of the
      25 SQLite files found by their header under the app roots (§6)
- [x] Confirm whether Scanopy still runs before scripting its dump — not running on
      2026-09-13 (nor AppFlowy): no dump, their cold raw files are copied by job 16
- [x] Test each dump command individually (2026-09-14) — a test run into `/tmp`, then checked:
      every SQL dump ends with its marker, Umami's table row counts equal the dump's `COPY`
      rows, every SQLite copy passes `integrity_check`, no `-wal`/`-shm` changed owner
- [x] Set up systemd timer on Pulsar to run dumps at 01:00 daily, with an Uptime Kuma push
      monitor on full success (2026-09-14) — 01:00 **Europe/Paris**, monitor 38; first run by
      hand: 16/16, push `up`
- [x] **Check the first nightly run** (2026-09-15) — dumps 01:00:00 → 01:00:08 Paris, 16/16,
      Kuma monitor 38 `up` "OK, 16 dumps"; job 13 at 02:00 `success`, 16 new files (81
      instead of 65), 104.8 MB added, 16.8 MB after compression
- [x] ~~Add `tier2-db-dumps` job in Zerobyte~~ — not needed: `/mnt/data/backups/dumps/` is
      inside job 13 (decided 2026-09-13)
- [x] **Validate end to end** (2026-09-15): dump → Zerobyte backup → restore dump → import to
      DB — snapshot `fd07fcc1` from Backblaze, 16/16 identical to the originals, the 4 SQL dumps
      imported with 0 errors and the same row counts, the 12 SQLite copies pass
      `integrity_check` (§6, *Restoring*)
- [x] **Hide the dumps from Filebrowser** (2026-09-14, `f6d4527`) — both apps run as root and
      mounted `/mnt/data/backups` whole, dumps and Proxmox configuration copy included (§6).
      They now mount `OnePlus-10T/` only. Side effects: `Nexus Backup/` and `Snapchat/`, which
      the old mount hid in `/mnt/data/k3s-pvc/filebrowser/Backups/`, show again (kept there,
      decided 2026-09-14), and an empty `OnePlus-10T/` mount point was created there

### Obsidian notes (CouchDB)

- [x] **Check that job 16 carries the CouchDB files** (2026-09-14) — snapshot `4bcb4081`
      (01:00) holds `couchdb/data/shards/*/courses.1789121873.couch`, 336 and 824 KiB
- [x] **Put the LiveSync passphrase, the Setup URI and the CouchDB account in the official
      Bitwarden cloud** (2026-09-14) — Vaultwarden alone would go down with Astra (§9.5)
- [x] **Test a restore of the notes end to end** (2026-09-14) — Backblaze → throwaway
      CouchDB on the workstation → test vault: 8 files of 8 decrypted, content as of 01:00 (§9.5)

### Monitoring

- [x] **Alert on `vault` at 75 %** — Beszel, 2026-09-11 (§10); tested by lowering the
      threshold to 60 %, which fired at 61.6 %
- [x] Alert on LXC 101 (`adguard`) — Beszel agent and Kuma DNS monitor, 2026-09-11 (§10)
- [x] Alert on LXC 103 (`pbs`) — Beszel agent, 2026-09-11 (§10)
- [x] **Fix the failed units in LXC 103** (2026-09-12) — without `nesting=1`, every unit that
      asks systemd for sandboxing died with `226/NAMESPACE`: `logrotate` (every night, since
      install), `man-db`, `systemd-logind`, `systemd-networkd` and its socket. `nesting=1`
      set and the container rebooted: `systemctl --failed` is empty, `is-system-running`
      says `running`, and a `systemd-run` with `logrotate`'s sandbox exits 0. `zfs-mount`
      and `zfs-share` disabled, as `zfs-zed` was. The journal needs nothing: 797.5M is
      journald's default cap of 10 % of the 7.8G root. First real `logrotate` run: 2026-09-13
      at 00:00 UTC. Since the root went to 16G (2026-09-13), that cap is ~1.6G

### Long-term

- [x] Evaluate Backblaze B2 as a scalable Tier 2 alternative — **adopted** for Immich
      (2026-09-09), then Portainer, personal backups, photos (2026-09-10) and Crafty backups
      (2026-09-11). Bucket `astra-pulsar-backup`, 43.4 GiB, lifecycle
      `daysFromHidingToDeleting: 1`

### How `drive` was filled (2026-09-20)

`rsync -a` as root, which keeps the owner
`1000:1000` that both apps need to write; then `rsync -anic` (compare every file's
checksum, change nothing) returned no line on any pair, 216 files on each side. Not carried
over on purpose: a 6-byte test file (`filebrowser/a/b`) and the empty mount points `Media/`
and `Backups/OnePlus-10T/`. `lost+found` was removed from `/mnt/drive`: it showed among the
personal folders and made Filebrowser Quantum log an error at start-up; `e2fsck` recreates
it if a repair ever needs it.

| Before (Netac) | After (`/mnt/drive`) |
| --- | --- |
| `/mnt/data/k3s-pvc/filebrowser/Documents` | `Documents/` |
| `/mnt/data/media/photos` | `Photos/` |
| `/mnt/data/backups/OnePlus-10T` | `Téléphone/` |
| `/mnt/data/k3s-pvc/filebrowser/Backups/Nexus Backup` and `Snapchat` | `Archives/` |

## Security

### P3 — Apps with more privileges than they need

- [x] **Remove the classic Filebrowser, hide the backups from Quantum** (2026-09-14, `f6d4527`,
      `ca56a5a`) — both apps ran as root and mounted `/mnt/data/backups` whole, dumps and
      Proxmox configuration copy included, reachable from the Internet through `drive.enoal.fr`
      ([`backup/database-dumps.md`](backup/database-dumps.md))
- [x] **Run Filebrowser Quantum as non-root** (2026-09-14, `c1b5a9e`) — uid 1000
- [x] **Run SFTPGo as non-root** (2026-09-15, `e87b3b6`) — uid 1000; as root, its account could
      read and delete the dumps
- [x] **Remove the Cloudflare tunnel** (2026-09-15, `90d75ad`) — it ran with no route at all
- [x] **dashdot without privileged mode or the host's root** (2026-09-15, `dc21b1d`; memory
      limit `b92eab9`) — it ran `privileged: true` with `/` mounted: a flaw in it was
      root on Pulsar, and it could read every file there. Now uid 1000, no capability, and
      five read-only mounts of what it reads. Tested in a throwaway pod before the commit:
      same figures as the privileged pod, except the system disk (~3.6G higher, see
      `k3s/dashdot/values.yaml`). The data-disk mount needs the empty `/mnt/data/.dashdot`.
      Also fixes 28 restarts: the speed test (every 4 h) went over the 192Mi limit
      (`OOMKilled`); now 320Mi. Checked after ArgoCD's sync: `uid=1000`, `CapEff` 0,
      `NoNewPrivs` 1, `dashdot.lan` → `200` with the host's OS, disks and traffic, and the
      startup speed test completed with 0 restarts
- [x] **portracker without ptrace or SYS_ADMIN** (2026-09-15, `dfa6af3`) — the host PID
      namespace plus `SYS_PTRACE` and `apparmor:unconfined` let it attach to any host process,
      which is root on Pulsar. `SYS_ADMIN` only serves Docker Desktop (vendor README). Tested
      with throwaway containers: without the three, it still lists every port (186 against
      188 live), but no longer names the program behind the 21 host ports — `sudo ss -tulpn`
      on Pulsar does. Docker ports keep their names through the socket proxy. Checked after
      Portainer's redeploy: no added capability, AppArmor profile `docker-default`, 185 ports
      listed, 21 of them host ports without a program name, as tested
