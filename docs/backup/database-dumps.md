# Database Dump Strategy

> Section numbers (§) refer to the [backup overview](README.md); each numbered section there
> is either in place or points to where it moved.

Live databases cannot be safely copied at the file level while running — doing so risks backing up a partially-written, corrupt state. Instead, a dump script runs **before** Zerobyte jobs and writes cold, consistent export files to `/mnt/data/backups/dumps/`. Zerobyte then backs up this directory as part of the existing **Backups** job (13, 02:00). A dump is a copy, so its place is the Netac (§12, disk layout).

> **In service since 2026-09-14.** First run by hand at 14:27 Paris: 16 dumps, 156 MB, 8 s,
> Kuma push `up`. First nightly run on 2026-09-15: 01:00:00 → 01:00:08 Paris, 16/16, 157 MB,
> push `up`; job 13 picked the 16 files up at 02:00 (81 files instead of 65, `success`), and
> the restore was tested end to end the same day (see _Restoring_ below). Zerobyte's own
> database joined on 2026-09-15 afternoon: run by hand, 17/17, push `up`; the copy holds the
> same 13 schedules, 6 repositories and 12 volumes as the original.

| Piece       | Where                                                                                       | What it does                                                                                        |
| ----------- | ------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| Script      | `infra/pulsar/dump-databases.sh` → `/usr/local/sbin/dump-databases` on Pulsar (root, `755`) | dumps each database on its own, checks the result, then replaces the previous dump                  |
| Timer       | `infra/pulsar/dump-databases.{service,timer}`                                               | daily at **01:00 Europe/Paris**, `Persistent=true` (catches up at boot)                             |
| Destination | `/mnt/data/backups/dumps/`                                                                  | root, directory `700`, files `600`; one file per database, replaced every night                     |
| Alerting    | Uptime Kuma push monitor **Database Dumps** (id 38)                                         | `up` when all 17 succeed, `down` naming the failed ones, alert on Discord if no push for 25 h (§10) |

The push URL lives in `/etc/default/dump-databases` (root, `600`), outside this repository.

**Who else can read the dumps.** Root, and any container running as root that mounts
`/mnt/data/backups` — the `700`/`600` modes stop users, not root. Until 2026-09-14 both
Filebrowser apps (`runAsUser: 0`) mounted that whole directory: the dumps and the Proxmox
configuration copy (§4.2) could be browsed and downloaded, from the Internet through
`drive.enoal.fr` for the classic one. Since commit `f6d4527` both mount
`/mnt/data/backups/OnePlus-10T` only; checked after ArgoCD's sync, neither pod sees `dumps/`
or `proxmox-configs/` any more. The classic app was removed the same day (`ca56a5a`) and
`drive.enoal.fr` now reaches Quantum, which runs as uid 1000 since `c1b5a9e` (§12). Since
`c9e98e1` (2026-09-20) neither app mounts anything under `/mnt/data/backups`: the phone backup
moved to `/mnt/drive` (§8.1). **Never mount
`/mnt/data/backups` whole into an app.**
The script is installed by copy, not run from `/opt/ops`: that clone is updated by hand (last
pull 2026-08-31) and owned by `enoal`, and root must not run a file a user account can edit.

## What is dumped

| Dump                | Source                                                                                                                                                               | Engine                    | How                                                                                                                                                                                                               |
| ------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `umami.sql`         | deployment `analytics/umami-postgres`                                                                                                                                | PostgreSQL 16.14          | `pg_dump` inside the pod, as `$POSTGRES_USER` on `$POSTGRES_DB`                                                                                                                                                   |
| `infisical.sql`     | deployment `infisical/infisical-postgres`                                                                                                                            | PostgreSQL 16.14          | same                                                                                                                                                                                                              |
| `uptimekuma.sql`    | deployment `monitoring/uptimekuma`, socket `/app/data/run/mariadb.sock`                                                                                              | embedded MariaDB 10.11.14 | `mariadb-dump -u root --single-transaction --databases kuma` — its 28 tables are all InnoDB, so the dump is consistent without locking                                                                            |
| `<app>.sqlite` × 12 | Vaultwarden, n8n, SFTPGo, ntfy `user.db`, Jellyfin, NPM, Homarr, Wallos, Crafty `crafty.sqlite`, Beszel `data.db`, Speedtest Tracker, Loandash — paths in the script | SQLite                    | Python's online backup API (no `sqlite3` binary on Pulsar), run as the file's owner                                                                                                                               |
| `zerobyte.sqlite`   | `/var/lib/zerobyte/data/zerobyte.db` (since 2026-09-15)                                                                                                              | SQLite                    | same. Its only off-site copy: `/var/lib/zerobyte` lies outside both app roots, so jobs 16 and 17 never see it. It keeps the 13 jobs, their exclusions and the repositories, which §9.3 otherwise rebuilds by hand |

Not dumped, on purpose:

- **Immich** — `postgres:14-vectorchord…`: a plain `pg_dump` cannot be restored on vanilla
  PostgreSQL. Immich dumps itself into `library/backups/` (job 8).
- **Scanopy, AppFlowy** — not running; their cold raw files are copied by job 16.
- **The other SQLite files** — caches (ntfy `cache.db`), statistics (Crafty's
  `crafty_server_stats.sqlite`, 132 MB for Roots SMP), indexes, CrowdSec, Scrutiny, ConvertX,
  Portracker and old copies. Jobs 16 and 17 copy them raw. Decided 2026-09-14: any dump can
  raise the alert, so the script only lists data worth one.
- **Filebrowser Quantum** — no SQLite: its `database.db` is a BoltDB file, copied raw by
  job 16. The removed classic app's `filebrowser/filebrowser.db` (BoltDB, 64K) was deleted on
  2026-09-14; job 16's snapshots still hold it.
- **Redis** (Infisical, Homarr) — caches and queues.
- **CouchDB** (Obsidian notes, §9.5) — decided 2026-09-14. The CouchDB documentation
  (_Maintenance → Backing up CouchDB_) states that copying `.couch` files while the server runs
  is safe, the format being append-only, so job 16's raw copy is consistent. The order it
  recommends, secondary indexes before databases, does not apply: `courses` has no design
  document, hence no `data/.shards`. A replication to a backup database was rejected:
  replication never copies `_local` documents, and LiveSync keeps half of its encryption key
  there (§9.5). The content is end-to-end encrypted either way.

A new app with a database needs a line in the script; jobs 16 and 17 already copy its raw files.

## How a dump is checked

- **One database at a time.** A failure keeps that database's previous dump, lets the others
  through, and reports `down` with the failed names.
- **Written aside, renamed once checked.** Each dump goes to `.<name>.tmp` first:
  - SQL dumps must end with the tool's marker (`-- PostgreSQL database dump complete`,
    `-- Dump completed`) and contain a `CREATE TABLE`. A crash or a timeout (15 min per dump)
    leaves no marker; an empty database has no table.
  - SQLite copies must pass `PRAGMA integrity_check` and hold a table. They are opened with
    `mode=rw`, so a wrong path fails instead of creating an empty database.
- **SQLite copies run as the file's owner** (`setpriv`). Opening a WAL database may create its
  `-wal` and `-shm` files, and root-owned ones would lock the app out of its own database.
  Checked on 2026-09-14: every companion file kept its owner.
- **No compression.** restic deduplicates plain dumps from one night to the next and compresses
  them itself; a `.gz` would be uploaded whole every night.
- **Pulsar's clock is UTC**, Zerobyte's schedules are Paris time: the timer pins
  `Europe/Paris`. Without it the dumps ran at 03:00 Paris, after job 13.

## Restoring

- **PostgreSQL:** `psql -U <user> -d <empty database> -f <app>.sql`, with **`psql` 16.10 / 17.6
  or newer**: the dumps open with `\restrict` and close with `\unrestrict`, which older clients
  reject. Dawarich needs a PostGIS image (`postgis/postgis:17-3.5-alpine`). Into a fresh server,
  create the owner role first (`umami`, `infisical`): the dumps set every object's owner with
  `OWNER TO <role>`. Restore into a new, empty database (`createdb -T template0`), not the
  image's default one: PostGIS's image preinstalls its extensions in `postgres` and
  `template_postgis`, and the Dawarich dump creates them itself.
- **Uptime Kuma:** `mariadb -u root < uptimekuma.sql` into the same MariaDB; the dump creates
  database `kuma`. Its first line, `/*M!999999\- enable the sandbox mode */`, is only
  understood by recent MariaDB clients.
- **SQLite:** stop the app, replace its database file with the copy (same owner and mode),
  delete any leftover `-wal` and `-shm`, start the app. Six copies keep their original's WAL
  flag (Beszel, Crafty, Jellyfin, Loandash, n8n, Vaultwarden) — harmless in place; to read one
  elsewhere, open it with `?immutable=1`.

**Tested end to end on 2026-09-15.** Job 13's snapshot `fd07fcc1` (02:00), folder `dumps`,
restored from Backblaze into `/restore/dumps-2026-09-15` (§9.6), then loaded into throwaway
containers on Pulsar (`--network none`, `--rm`):

| Check                                      | Result                                                                                                                                                                                   |
| ------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Restored files vs the originals            | 16/16 identical in content (SHA-256), owner, mode and modification time                                                                                                                  |
| 12 SQLite copies                           | `integrity_check` ok for all; e.g. Vaultwarden 2 users, 888 ciphers; NPM 75 proxy hosts                                                                                                  |
| Umami (`postgres:16`, psql 16.15)          | imported with `ON_ERROR_STOP`, 0 errors; 25/25 tables, 128 rows, same as the dump's `COPY` blocks                                                                                        |
| Infisical (`postgres:16`)                  | 0 errors, 9 s; 770 tables, 1 247 rows, all equal to the dump                                                                                                                             |
| Dawarich (`postgis/postgis:17-3.5-alpine`) | 0 errors, 3 s; the dump's 39 tables of data equal, 136 064 points; the 4 other differences are rows PostGIS ships itself (`spatial_ref_sys`, `tiger.pagc_*`), which `pg_dump` leaves out |
| Uptime Kuma (`mariadb:10.11`, 10.11.19)    | 0 errors, 2 s; 28 tables, 187 898 rows, all equal to the dump                                                                                                                            |

Counting a Kuma dump's rows: `mariadb-dump` 10.11 writes `INSERT INTO … VALUES` and then one
row per line up to the `;`, not a whole statement on one line.
