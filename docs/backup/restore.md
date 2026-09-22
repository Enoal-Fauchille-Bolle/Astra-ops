# Restoration Runbooks

> Section numbers (§) refer to the [backup overview](README.md); each numbered section there
> is either in place or points to where it moved.

## 9.1 Scenario A — Logical Corruption (service-level)

**Trigger:** A service is broken, a database is corrupted, or files were accidentally deleted. The Astra host and Netac NVMe are healthy.

**Recovery via Layer 1 (PBS):**

1. Access PBS web UI at `pbs.enoal.fr` (or directly at the LXC IP).
2. Navigate to the relevant datastore → find the most recent healthy snapshot of Pulsar (VM 100).
3. If restoring the entire VM: Proxmox UI → VM 100 → Backups → Restore — **to a new VMID**.
   Snapshots taken after `backup=0` do not contain `scsi1`, and the documentation does not say
   what an in-place restore does to an excluded disk (§4.2).
4. If restoring individual files: use `proxmox-backup-client` to mount the snapshot and extract specific paths.

```bash
# Mount a specific PBS snapshot on Astra
proxmox-backup-client mount \
  --repository user@pbs-host:datastore \
  <snapshot-id> /mnt/restore-point

# Extract specific directory
cp -r /mnt/restore-point/opt/k3s-data/immich/ /opt/k3s-data/immich-restored/
```

5. Restart the affected service.
6. Validate service health.

**Files under `/mnt/data`** are no longer in PBS since `backup=0` (2026-09-11): restore them from
Zerobyte (§5.4) through its restore directory (§9.6).

**Estimated time:** 15 min – 1 hour depending on restore scope.

---

## 9.2 Scenario B — Netac NVMe Failure

**Trigger:** The Netac NVMe fails. Both Pulsar's cold disk (`/mnt/data`) and the PBS datastore are lost simultaneously.

**What is lost:**

- `/mnt/data/` contents (cold PVCs, media, backups)
- All Layer 1 PBS snapshots

**What survives:**

- Pulsar OS disk (`sda`, on the WD Blue) — `/opt/k3s-data/`, `/opt/docker-data/`, running services
- Layer 2 cloud backups (Backblaze B2, MEGA)

**Recovery steps:**

1. Replace Netac NVMe with a new drive.
2. In Proxmox, create a new storage pool on the new drive (e.g., `vault`).
3. Create a new PBS LXC (ID 103) and point it to the new datastore — no historical backups, but PBS is operational again.
   Restore its configuration (users, retention, verify job, notifications) from the Proxmox config copy (§9.4).
4. Add the new drive as a second disk to Pulsar (Proxmox UI → VM 100 → Hardware → Add → Hard Disk).
5. Inside Pulsar, format and mount the new disk at `/mnt/data`.
6. Restore Tier 2 data via Zerobyte:
   - Recreate the restore directory first: `sudo install -d -m 700 -o root -g root /mnt/data/restore`
   - Access Zerobyte UI at `zerobyte.lan`
   - Pick the repository that holds the path (§5.4): **Backblaze** for `backups/` and Crafty
     backups. Personal files are not on the Netac since 2026-09-21: `/mnt/drive` is on the WD
     Blue and survives this scenario
   - Restore each path into its own subfolder of `/restore`, then move it into `/mnt/data/` (§9.6)
   - Movies and Crafty logs are not backed up anywhere: re-download or accept the loss
7. Restore directory structure (`k3s-pvc/`, `backups/`, `media/`, etc.).
8. Restart services that depend on `/mnt/data/` mounts.

**Estimated time:** 4–24 hours (depends on total data size ~35G for `/mnt/data` and bandwidth).

---

## 9.3 Scenario C — Total Loss of Astra

**Trigger:** Complete hardware failure, theft, fire, or similar. The entire Astra node is gone.

**What survives:**

- Layer 2 cloud backups (Backblaze B2, MEGA) — all Tier 2 data
- The `astra-ops` GitOps repository (GitHub) — all manifests, Helm charts, configurations
- The secrets kept off Astra ([secrets.md](../secrets.md))

**Recovery steps:**

1. Provision a new server (or reinstall on repaired hardware).
2. Install Proxmox VE — the version recorded in the config copy's `MANIFEST.txt`.
3. Recreate the VM/LXC structure from the Proxmox config copy (§9.4). That copy sits in
   Backblaze, and opening it takes the B2 key and Zerobyte's restic password. Both are kept
   in the **official Bitwarden cloud** — not in the self-hosted Vaultwarden, which runs on
   Astra and would be lost with it.
4. Create Pulsar VM (Ubuntu Server), install K3s and Docker.
5. Reinstall the Proxmox config backup mechanism
   ([proxmox-config-copy.md](proxmox-config-copy.md), _Reinstalling this mechanism from
   scratch_) so nightly copies of the new Proxmox configuration resume.
6. Install Zerobyte (Docker Compose in `docker/zerobyte/`). To get its 13 jobs back instead of
   re-creating them, fetch `dumps/zerobyte.sqlite` from job 13's latest snapshot with the
   `restic` command line (B2 key and restic password as above) and put it at
   `/var/lib/zerobyte/data/zerobyte.db` before the first start. Zerobyte encrypts the secrets
   it stores with `APP_SECRET`: the new stack needs the **same** value, or those secrets are
   lost. It is set in Portainer's stack 11 environment, on Astra, and a copy is kept off
   Astra since 2026-09-20.
7. Configure rclone remotes (`mega-a`, `mega-c`, `mega-d`) on the new Pulsar, and re-create
   the Backblaze S3 repository in Zerobyte with the B2 key (skip the latter with the
   database of step 6).
8. Restore Tier 2 data from Backblaze and MEGA via Zerobyte, through `/mnt/data/restore` (§9.6).
9. Apply the K3s secrets: the two Infisical bootstrap files, the hand-applied `secrets.yaml`
   and the registry credentials ([secrets.md](../secrets.md)).

10. Bootstrap ArgoCD and the App-of-Apps:

    ```bash
    kubectl apply -f /opt/ops/infra/argocd/root-app.yaml
    ```

11. ArgoCD will deploy all K3s services automatically from GitHub.
12. Restore Docker Compose stacks via Portainer.
13. Validate all services via Uptime Kuma and Homer dashboard.

**Estimated time:** 1–3 days for full restoration.

---

## 9.4 Restoring the Proxmox configuration

Moved to [proxmox-config-copy.md](proxmox-config-copy.md#94-restoring-the-proxmox-configuration).

---

## 9.5 Restoring the Obsidian notes (CouchDB)

Moved to [`k3s/couchdb/README.md`](../../k3s/couchdb/README.md).

## 9.6 Restoring files with Zerobyte

Every data mount of the Zerobyte container is read-only, so a backup can never damage its
source — and Zerobyte cannot restore to the _original location_ either. Since 2026-09-14 it
has one writable directory for that: `/mnt/data/restore` on Pulsar (root, `700`), mounted at
**`/restore`** in the container. Restore there, check, then copy into place by hand.

1. Open `http://zerobyte.lan/backups/<job short id>/<snapshot short id>/restore` (page
   _Restore Snapshot_). A job's short id is in `zerobyte.db` (`backup_schedules_table.short_id`,
   `2JsgS07p` for job 13 _Backups_); a snapshot's is the first 8 hex characters of its id.
2. Under _Select Files to Restore_, tick the folders wanted.
3. Under _Restore Location_, choose **Custom location** and give a **subfolder per restore**,
   e.g. `/restore/crafty`. Zerobyte writes the _contents_ of the ticked folder straight into
   the target, without the `/data/...` path above it, so two restores into `/restore` itself
   end up mixed together.
4. Wait for **Restore completed**, then from Pulsar compare and move the files into place,
   for example `sudo diff -r /mnt/data/restore/crafty <destination>`. Owners, modes and
   modification times are kept (uid `1000` for Quantum and SFTPGo, root for the rest), so no
   `chown` is needed after the copy.
5. Empty the directory afterwards: `sudo find /mnt/data/restore -mindepth 1 -delete`. A plain
   `sudo rm -rf /mnt/data/restore/*` removes nothing — the `*` is expanded by the user's shell,
   which cannot read a root-only directory.

Where it lives, and why: on the Netac with the data it usually restores (a move into
`/mnt/data` is then instant), 390 GB free on 2026-09-14, and outside PBS (`scsi1`,
`backup=0`), so a forgotten restore is not kept for months in Layer 1. It is not a Zerobyte
volume, so nothing restored there is ever backed up again. After a Netac failure (§9.2),
recreate it on the new disk before Zerobyte starts: `sudo install -d -m 700 -o root -g root
/mnt/data/restore`.

Zerobyte refuses only its own directories as a target (read in v0.42's code): its database
and repository directories under `/var/lib/zerobyte`, the restic cache, the rclone
configuration, `/app` and the temporary directory.

**Tested on 2026-09-14.** Job 13's snapshot `156b3871` (02:00), folder `proxmox-configs`,
restored from Backblaze into `/restore` in 2.5 s: 53 files, 70 KB, identical to
`/mnt/data/backups/proxmox-configs` in content (`diff -r`) and in owner, mode and
modification time. Second test on 2026-09-15: the database dumps of snapshot `fd07fcc1`, into
`/restore/dumps-2026-09-15`, then imported into throwaway databases (§6, _Restoring_). The
subfolder Zerobyte creates is `755`; the files keep their `600`, and `/mnt/data/restore` itself
stays `700`.

## 11. Restore Testing

Backups that have never been tested are assumptions, not guarantees.

### Recommended Testing Schedule

| Frequency         | Test                                                      | Priority    |
| ----------------- | --------------------------------------------------------- | ----------- |
| **Quarterly**     | Full restore of Vaultwarden from Layer 2 snapshot         | 🔴 Critical |
| **Quarterly**     | Full restore of Immich photos (sample) from Layer 2       | 🔴 Critical |
| **Semi-annually** | Restore single Pulsar service from Layer 1 PBS snapshot   | High        |
| **Annually**      | Full Scenario C simulation (new VM, restore from scratch) | High        |

### Restore Validation Checklist

For each tested restore:

- [ ] Service starts without errors
- [ ] Data integrity verified (spot-check files, query DB)
- [ ] No data loss beyond expected RPO window
- [ ] Service accessible via expected URL (`.lan` or `.enoal.fr`)
- [ ] Dependent services unaffected
- [ ] Restore duration recorded (baseline for RTO estimates)
