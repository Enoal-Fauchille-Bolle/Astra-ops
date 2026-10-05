# To do

> Section numbers (§) refer to the [backup overview](backup/README.md); each numbered section there
> is either in place or points to where it moved.

Open work only. Finished items move to [decisions.md](decisions.md).

## Backups and storage

### Layer 2 — Zerobyte

- [ ] **Fix Zerobyte → Discord notifications**: a message over ~5,970 characters loses its
      first 6,000 with HTTP 400: Shoutrrr does not count the title against Discord's
      6,000-character embed cap ([monitoring.md](monitoring.md)). Accepted as is for now
- [ ] **Purge `Mega A`, `Mega B`, `Mega C` and `Mega D`, about 2027-03-23**, all four on
      the same day ([decisions.md](decisions.md)): delete their frozen snapshots on MEGA,
      remove `Mega A`, `Mega C` and `Mega D` from Zerobyte (`Mega B` is already out), then
      drop the now-unused per-app mounts from `docker-compose.yml`. Once done, drop
      `mega-a`/`mega-c`/`mega-d` from the rclone remotes step of the disaster-recovery
      runbook ([restore.md](backup/restore.md), §9.3 step 7)

### Disk layout

- [ ] Delete the Portainer job (Backblaze) and its snapshots, then drop the unused mount
      from `docker-compose.yml`, **about 2026-12-13**, once Docker Data holds three months of
      history covering the same path (§5.4). It was never on MEGA, so the purge above does
      not cover it
- [ ] Once the Photos job (Backblaze) is no longer wanted: delete it and its snapshots,
      then drop the `/data/media/photos` mount from `docker-compose.yml` and the empty host
      folder. Its snapshots hold the off-site history of the photos from before the move to
      `drive`. The Filebrowser Files job (`Mega C`) is **not** part of this cleanup: it is
      handled by the MEGA purge above instead
- [ ] Bring Termix (`/opt/ops/docker/termix/data`) under the app roots: it is outside them
      and has no off-site copy. Not urgent: Termix is a test, started by hand outside
      Portainer, no backup wanted yet
- [ ] Move the lab VMs to `vault-thin` (the thin pool on the Netac). Template 105 is
      undecided, and 106 is a linked clone of it
- [ ] `local-lvm` is provisioned close to its size, and no alert watches it
      ([monitoring.md](monitoring.md)). Either add an alert on provisioning, or free space:
      the old snapshots of VMs 101 (`Before_update`) and 108 (`Before-Dotfiles`), or the lab
      VMs (item above)
- [ ] Later: a PBS 4 datastore on Backblaze (S3 backend) to restore whole VMs after losing
      Astra. It needs a 64–128 GiB local cache. The ~100G reserve meant for it went into the
      `thin` pool, so that space has to be found elsewhere. Support status and B2
      compatibility unchecked

### Phase 3 — Secrets sync

Official Bitwarden only for now. Whether to add the automated copy below, possibly to
Backblaze instead of Mega A, is to be decided later.

- [ ] Configure `rclone crypt` on the workstation for a `mega-a-crypt` remote
- [ ] Create `~/astra-secrets/` and consolidate all secrets
- [ ] Write rclone sync script with versioned backup dir
- [ ] Create systemd timer on the workstation (daily sync)
- [ ] First restore test: decrypt and apply secrets on a clean machine

## Security

> Open work from the security audit of 2026-09-08, which rated each fix P1 (urgent) to P5.
> P1 and P2 are done; what follows is P3 to P5. The audit report itself stays
> outside this public repository.
>
> Items are checked only where the state was verified on the machines, not where a commit
> merely exists.

### P3 — Apps with more privileges than they need

The common risk: a container that holds host-level privileges turns a flaw in one small app
into control of Pulsar, with every app, database and backup on it.

- [ ] **Crafty out of `network_mode: host` and root**: it binds its ports on the host directly
      (8443 among them) as uid 0. Touches the sleep watcher of Roots SMP, which holds the
      server's port while it sleeps

### P4 — Reorganise VMIDs, IPs, tags and disks

- [ ] Not started. Constraint: PBS groups backups by VMID, so renumbering a guest starts its
      backup history from zero. VM 106 is a linked clone of template 105

### P5 — Documentation

- [ ] Rewrite the documentation to separate what is in place from what is planned
