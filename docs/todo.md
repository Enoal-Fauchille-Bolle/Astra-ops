# To do

> Section numbers (§) refer to the [backup overview](backup/README.md); each numbered section there
> is either in place or points to where it moved.

Open work only. Finished items move to [decisions.md](decisions.md).

## Backups and storage

### Layer 2 — Zerobyte

- [ ] **Fix Zerobyte → Discord notifications**: a message over ~5,970 characters loses its
      first 6,000 with HTTP 400 — Shoutrrr does not count the title against Discord's
      6,000-character embed cap (§10). Accepted as is for now (2026-09-12)
- [ ] Revisit `Mega D` about 2026-12-15 — kept as is for three months (decided 2026-09-15):
      job disabled, 7 dormant Nous Deux snapshots

### Storage

- [ ] Decide the fate of LXC 102 (`wireguard`, stopped since 2026-05-04) in the vzdump job

### Disk layout — decided 2026-09-13

- [ ] Delete job 12 and its snapshots, remove `Mega A` from Zerobyte and drop the unused
      per-app mounts from `docker-compose.yml` — **about 2026-12-13**, once jobs 16 and 17
      hold three months of history (§5.4)
- [ ] Once jobs 10 and 14 are no longer wanted: delete them and their snapshots, then drop
      the `/data/filebrowser` and `/data/media/photos` mounts from `docker-compose.yml` and the
      two empty host folders. Their snapshots hold the off-site history of the personal files
      before 2026-09-21
- [ ] Bring Termix (`/opt/ops/docker/termix/data`, 15M) under the app roots — it is outside
      them and has no off-site copy. Not urgent (2026-09-15): Termix is a test, started by
      hand outside Portainer, no backup wanted yet. Dawarich's file volumes were on the same
      list until Dawarich was removed on 2026-09-21
- [ ] Move the lab VMs to `vault`. Template 105 is undecided, and 106 is a linked clone of it
- [ ] **Split the Netac with LVM** — a fixed LV for the PBS datastore, a thin pool for the
      rest. Today both share one ext4 filesystem, and the cold disk (500G declared) plus the
      datastore (476G after the GC of 2026-09-20, 113G since 2026-09-21) could exceed the 938G
      drive. **Plan approved by
      Enoal on 2026-09-15**, in this order:
      1. ~~after the first verify and GC under PBS 4~~ — both `OK` on 2026-09-19 and 20;
      2. ~~**`drive` first**~~ — done 2026-09-21 (above). This changed the 2026-09-13 order
         (LVM, then tidy up): the Netac now holds only copies and replaceable data, so the
         worst accident during the split destroys nothing unique;
      3. ~~measure what the datastore weighs without the `vm/100` snapshots that still hold
         `drive-scsi1`~~ — measured 2026-09-21, read-only. Only **7** were left, not 13: the
         dailies had expired (3 monthlies 2026-05-31, 06-28, 07-26; 4 weeklies 08-16, 08-23,
         08-30, 09-06, UTC). A script read every index of the datastore and summed the chunks
         that no other snapshot references: **349.20 GiB** for the seven, but only 72.41 GiB
         for the monthlies alone and 84.21 GiB for the weeklies alone — they share the cold
         disk's chunks, so it is all or nothing. The other 44 snapshots reference
         **113.40 GiB**;
      4. ~~Enoal decides whether to delete those snapshots~~ — **deleted 2026-09-21** by Enoal
         in the PBS web UI (the history of Pulsar's system disk before 2026-09-12 went with
         them; app data has Backblaze history since 2026-09-13, dumps since 2026-09-14, the
         Crafty archives since 2026-09-11). Proxmox's `pvesm free` could not do it:
         `backup_user@pbs` only holds `DatastoreBackup` on the datastore, which cannot delete —
         kept that way on purpose, so a compromised Astra cannot erase its backups. A manual GC
         right after: `TASK OK`, **367.491 GiB** and 174 402 chunks removed (the 349 GiB plus
         chunks already orphaned by the nightly prunes); the datastore holds **113.238 GiB**
         (76 290 chunks, deduplication 18.87), and the Netac went from 62 % to **22 %** — 199G
         used of 938G, 730G free;
      5. **method A** if the snapshots go and the datastore falls under ~250G: copy it to the
         WD with a PBS sync job (the `local-lvm` thin pool stays under ~55 %), wipe the Netac,
         build the LVM, sync back. **Otherwise method B**: move the cold disk `scsi1` and the
         ISOs to the WD online (*Move disk*), shrink the datastore's ext4 and partition in
         place with PBS stopped, build the thin pool in the freed space, move `scsi1` back.
         Never park the whole 489G on the WD: a full thin pool freezes every guest, Pulsar
         included.
      Reserve an LV for the 64–128 GiB local cache a future S3 datastore needs (below), so the
      disk is not split twice
- [ ] Later: a PBS 4 datastore on Backblaze (S3 backend) to restore whole VMs after losing
      Astra. It needs a 64–128 GiB local cache; support status and B2 compatibility unchecked

### Phase 3 — Secrets sync

- [ ] Record where the Infisical bootstrap values and the hand-applied `secrets.yaml` files
      are kept off Astra. [secrets.md](secrets.md) says to fetch them from Vaultwarden, which
      is lost with Astra (found 2026-09-22)
- [ ] Configure `rclone crypt` on the workstation for a `mega-a-crypt` remote
- [ ] Create `~/astra-secrets/` and consolidate all secrets
- [ ] Write rclone sync script with versioned backup dir
- [ ] Create systemd timer on the workstation (daily sync)
- [ ] First restore test: decrypt and apply secrets on a clean machine

### Long-term

- [ ] Decide whether to migrate the remaining MEGA jobs to B2 — Mega A's four jobs moved to
      jobs 16 and 17 on 2026-09-13; Mega C's job 10 (Filebrowser) was replaced by job 18 to
      Backblaze on 2026-09-20 and is disabled, its snapshots frozen. What to do with Mega A
      and Mega C themselves is still open
- [ ] `Mega B` is **retired**: removed from Zerobyte on 2026-09-09, its 10 snapshots left
      intact on MEGA, neither copied nor purged. Still readable with `restic --no-lock`.

## Security

> Open work from the security audit of 2026-09-08, which rated each fix P1 (urgent) to P5.
> P1 and P2 are done; what follows is P3 to P5 and the closing step. The audit report itself
> stays outside this public repository.
>
> Items are checked only where the state was verified on the machines, not where a commit
> merely exists.

### P3 — Apps with more privileges than they need

The common risk: a container that holds host-level privileges turns a flaw in one small app
into control of Pulsar, with every app, database and backup on it.

- [ ] **CrowdSec: make the bans reach web traffic** — it runs (the README says `⏸️ Disabled`,
      wrong since at least 2026-09-08), reads NPM's logs and bans real attackers, but the
      firewall bouncer hooks `INPUT` only, and Docker-published ports go through `FORWARD`:
      its `DROP` rules had matched 0 packets. Order matters: NPM does not restore the
      visitor's address behind Cloudflare (no `real_ip`), so CrowdSec sees Cloudflare's
      addresses. Hooking the bouncer into `DOCKER-USER` first would ban Cloudflare and cut
      every public site. Configure `real_ip` in NPM, check the logs show visitors' addresses,
      then extend the bouncer. Fix the README line in the same change
  - [x] **NPM logs visitors' addresses** (2026-09-15) — `real_ip_header CF-Connecting-IP` in
        `server_proxy.conf` ([`docker/npm/README.md`](../docker/npm/README.md)). Checked after
        the reload: the 18 public sites answer the same codes as before, and the logs show no
        Cloudflare address any more (a test request shows the tester's public address)
  - [x] **Firewall bans reach the containers** (2026-09-15) — `DOCKER-USER` added under
        `iptables_chains` in `/etc/crowdsec/bouncers/crowdsec-firewall-bouncer.yaml` on Pulsar
        (host file, not in this repository; previous version kept as `.bak-2026-09-15`).
        Before: the community list (24 430 IPv4, 455 IPv6) and the local bans contained no
        Cloudflare or private address. After: the 18 public sites answer the same codes; a
        throwaway container banned with `cscli decisions add --ip` got no answer from NPM
        (`000`), then `200` once the ban was deleted. Bans added by hand land in
        `crowdsec-blacklists-2`, not `-1`. README status fixed. Blocks direct traffic only:
        on 2026-09-15, 1 488 direct requests (37 addresses, sites in DNS-only mode such as
        `immich.enoal.fr`) against 39 949 through Cloudflare, whose connections come from
        Cloudflare's addresses
  - [ ] **Block traffic that comes through Cloudflare** — Cloudflare Worker Bouncer tried on
        2026-09-15, then abandoned and fully removed (package, config, LAPI key, and everything
        it created at Cloudflare, checked through the API). Volume fits the free plan (831 730
        requests over 30 days, worst day ~42 000, against 100 000). What stopped it: the deploy
        fails with `You need to enable Analytics Engine (10089)` although a dataset was created;
        the account had never deployed a Worker, which reportedly must happen first (untested).
        Also found in the v0.0.18 source: every start and stop deletes and recreates the worker
        route, so a "Fail open" set by hand in the dashboard would be lost at each restart. Only
        the bouncer's local bans would fit anyway: 1 000 KV writes a day against 24 885 entries
        in the community list. Other paths: an IP list plus a WAF custom rule (1 list, 10 000
        items on Free; the official `cs-cloudflare-bouncer` doing this was archived on
        2026-09-02), or a bouncer inside NPM
- [ ] **Crafty out of `network_mode: host` and root** — it binds its ports on the host directly
      (8443 among them) as uid 0. Touches the sleep watcher of Roots SMP, which holds the
      server's port while it sleeps

### P4 — Reorganise VMIDs, IPs, tags and disks

- [ ] Not started. Constraint: PBS groups backups by VMID, so renumbering a guest starts its
      backup history from zero. VM 106 is a linked clone of template 105

### P5 — Documentation

- [ ] Rewrite the documentation to separate what is in place from what is planned

### Closing — last step, after P3 to P5

- [ ] Remove `/etc/sudoers.d/99-claude-audit` on Astra and on Pulsar. It gives `enoal`
      password-less `sudo` (`NOPASSWD:ALL`) for Claude's sessions, kept on purpose for the
      whole remediation
