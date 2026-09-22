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
- [ ] Move the lab VMs to `vault-thin` (the thin pool from the Netac split below). Template 105
      is undecided, and 106 is a linked clone of it
- [x] **Split the Netac with LVM** — done 2026-09-22 with method A (staged on the WD, wiped
      and rebuilt the Netac as VG `netac`, synced back): fixed LV `pbs` for the PBS datastore,
      fixed LV `files` for the ISOs, thin pool `thin` for the cold disk. Prep work: PBS 4
      verify/GC clean (2026-09-19/20), `drive` moved off first (2026-09-21), the seven old
      `vm/100` snapshots holding `drive-scsi1` measured (349.20 GiB) and deleted by Enoal in
      the PBS UI, manual GC freed 367.491 GiB leaving the datastore at 113.238 GiB. Full
      write-up, including the same-day thin-pool overfill incident, in
      [decisions.md](decisions.md).
      **Consequence for the item below:** the ~100G reserve meant to become the future S3
      datastore's local cache was almost entirely spent same-day fixing that incident (~672M
      left) — revisit the cache plan once the wasted thin-pool space is reclaimed, or plan to
      shrink something else.
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

- [ ] **CrowdSec: block traffic that comes through Cloudflare** — bans only stop direct
      traffic today ([`docker/crowdsec/README.md`](../docker/crowdsec/README.md)).
      Cloudflare Worker Bouncer tried on 2026-09-15, then abandoned and fully removed
      (package, config, LAPI key, and everything it created at Cloudflare, checked through
      the API). Volume fits the free plan (831 730 requests over 30 days, worst day ~42 000,
      against 100 000). What stopped it: the deploy fails with `You need to enable Analytics
    Engine (10089)` although a dataset was created; the account had never deployed a
      Worker, which reportedly must happen first (untested). Also found in the v0.0.18
      source: every start and stop deletes and recreates the worker route, so a "Fail open"
      set by hand in the dashboard would be lost at each restart. Only the bouncer's local
      bans would fit anyway: 1 000 KV writes a day against 24 885 entries in the community
      list. Other paths: an IP list plus a WAF custom rule (1 list, 10 000 items on Free;
      the official `cs-cloudflare-bouncer` doing this was archived on 2026-09-02), or a
      bouncer inside NPM
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
