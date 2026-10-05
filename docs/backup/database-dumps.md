# Database Dump Strategy

> Section numbers (§) refer to the [backup overview](README.md); each numbered section there
> is either in place or points to where it moved.

Live databases cannot be safely copied at the file level while running: doing so risks backing up a partially-written, corrupt state. Instead, a dump script runs **before** Zerobyte jobs and writes cold, consistent export files to `/mnt/data/backups/dumps/`. Zerobyte then backs up this directory as part of the existing **Backups** job (02:00). A dump is a copy, so its place is the Netac ([infrastructure.md](../infrastructure.md#disks)).

| Piece       | Where                                                                                       | What it does                                                                                             |
| ----------- | ------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| Script      | `infra/pulsar/dump-databases.sh` → `/usr/local/sbin/dump-databases` on Pulsar (root, `755`) | dumps each database on its own, checks the result, then replaces the previous dump                       |
| Timer       | `infra/pulsar/dump-databases.{service,timer}`                                               | daily at **01:00 Europe/Paris**, `Persistent=true` (catches up at boot)                                  |
| Destination | `/mnt/data/backups/dumps/`                                                                  | root, directory `700`, files `600`; one file per database, replaced every night                          |
| Alerting    | Uptime Kuma push monitor **Database Dumps** (id 38)                                         | `up` when every dump succeeds, `down` naming the failed ones, alert on Discord if no push for 25 h (§10) |

The push URL lives in `/etc/default/dump-databases` (root, `600`), outside this repository.
Its host is `https://kuma-probe.enoal.fr`, not the `http://uptime.lan` Kuma displays: Pulsar
does not resolve `.lan` names ([monitoring.md](../monitoring.md#uptime-kuma)).

**Who else can read the dumps.** Root, and any container running as root that mounts
`/mnt/data/backups`; the `700`/`600` modes stop users, not root. No app mounts anything under
`/mnt/data/backups`: Filebrowser Quantum (`drive.enoal.fr`, uid 1000) and SFTPGo mount only
`/mnt/drive` and the movies (§8.1). **Never mount `/mnt/data/backups` whole into an app.**
The script is installed by copy, not run from `/opt/ops`: that clone is updated by hand and
owned by `enoal`, and root must not run a file a user account can edit.

## What is dumped

| Dump                | Source                                                                                                                                                               | Engine                    | How                                                                                                                                                                                                                                  |
| ------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `umami.sql`         | deployment `analytics/umami-postgres`                                                                                                                                | PostgreSQL 16.14          | `pg_dump` inside the pod, as `$POSTGRES_USER` on `$POSTGRES_DB`                                                                                                                                                                      |
| `infisical.sql`     | deployment `infisical/infisical-postgres`                                                                                                                            | PostgreSQL 16.14          | same                                                                                                                                                                                                                                 |
| `uptimekuma.sql`    | deployment `monitoring/uptimekuma`, socket `/app/data/run/mariadb.sock`                                                                                              | embedded MariaDB 10.11.14 | `mariadb-dump -u root --single-transaction --databases kuma` — its tables are all InnoDB, so the dump is consistent without locking                                                                                                  |
| `<app>.sqlite` × 12 | Vaultwarden, n8n, SFTPGo, ntfy `user.db`, Jellyfin, NPM, Homarr, Wallos, Crafty `crafty.sqlite`, Beszel `data.db`, Speedtest Tracker, Loandash — paths in the script | SQLite                    | Python's online backup API (no `sqlite3` binary on Pulsar), run as the file's owner                                                                                                                                                  |
| `zerobyte.sqlite`   | `/var/lib/zerobyte/data/zerobyte.db`                                                                                                                                 | SQLite                    | same. Its only off-site copy: `/var/lib/zerobyte` lies outside both app roots, so the K3s Data and Docker Data jobs never see it. It keeps the 13 jobs, their exclusions and the repositories, which §9.3 otherwise rebuilds by hand |

Not dumped, on purpose:

- **Immich**: `postgres:14-vectorchord…`: a plain `pg_dump` cannot be restored on vanilla
  PostgreSQL. Immich dumps itself into `library/backups/` (Immich Library job).
- **Scanopy, AppFlowy**: not running; their cold raw files are copied by the K3s Data job.
- **The other SQLite files**: caches (ntfy `cache.db`), statistics (Crafty's
  `crafty_server_stats.sqlite`), indexes, CrowdSec, Scrutiny, ConvertX, Portracker and old
  copies. The K3s Data and Docker Data jobs copy them raw. Any dump can raise the alert, so the
  script only lists data worth one.
- **Filebrowser Quantum**: no SQLite: its `database.db` is a BoltDB file, copied raw by the
  K3s Data job.
- **Redis** (Infisical, Homarr): caches and queues.
- **CouchDB** (Obsidian notes, §9.5): the CouchDB documentation
  (_Maintenance → Backing up CouchDB_) states that copying `.couch` files while the server runs
  is safe, the format being append-only, so the K3s Data job's raw copy is consistent. The order it
  recommends, secondary indexes before databases, does not apply: `courses` has no design
  document, hence no `data/.shards`. A replication to a backup database was rejected:
  replication never copies `_local` documents, and LiveSync keeps half of its encryption key
  there (§9.5). The content is end-to-end encrypted either way.

A new app with a database needs a line in the script; the K3s Data and Docker Data jobs already copy its raw files.

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
  Checked: every companion file kept its owner.
- **No compression.** restic deduplicates plain dumps from one night to the next and compresses
  them itself; a `.gz` would be uploaded whole every night.
- **Pulsar's clock is UTC**, Zerobyte's schedules are Paris time: the timer pins
  `Europe/Paris`. Without it the dumps ran at 03:00 Paris, after the Backups job.

## Restoring

- **PostgreSQL:** `psql -U <user> -d <empty database> -f <app>.sql`, with **`psql` 16.10 / 17.6
  or newer**: the dumps open with `\restrict` and close with `\unrestrict`, which older clients
  reject. Into a fresh server, create the owner role first (`umami`, `infisical`): the dumps
  set every object's owner with `OWNER TO <role>`. Restore into a new, empty database
  (`createdb -T template0`).
- **Uptime Kuma:** `mariadb -u root < uptimekuma.sql` into the same MariaDB; the dump creates
  database `kuma`. Its first line, `/*M!999999\- enable the sandbox mode */`, is only
  understood by recent MariaDB clients.
- **SQLite:** stop the app, replace its database file with the copy (same owner and mode),
  delete any leftover `-wal` and `-shm`, start the app. Six copies keep their original's WAL
  flag (Beszel, Crafty, Jellyfin, Loandash, n8n, Vaultwarden), harmless in place; to read one
  elsewhere, open it with `?immutable=1`.

**Tested end to end on 2026-09-15.** The Backups job's snapshot `fd07fcc1` (02:00), folder
`dumps`, restored from Backblaze into `/restore/dumps-2026-09-15` (§9.6), then loaded into
throwaway containers on Pulsar (`--network none`, `--rm`):

| Check                                   | Result                                                                                            |
| --------------------------------------- | ------------------------------------------------------------------------------------------------- |
| Restored files vs the originals         | 16/16 identical in content (SHA-256), owner, mode and modification time                           |
| 12 SQLite copies                        | `integrity_check` ok for all                                                                      |
| Umami (`postgres:16`, psql 16.15)       | imported with `ON_ERROR_STOP`, 0 errors; 25/25 tables, 128 rows, same as the dump's `COPY` blocks |
| Infisical (`postgres:16`)               | 0 errors, 9 s; 770 tables, 1 247 rows, all equal to the dump                                      |
| Uptime Kuma (`mariadb:10.11`, 10.11.19) | 0 errors, 2 s; 28 tables, 187 898 rows, all equal to the dump                                     |

Counting a Kuma dump's rows: `mariadb-dump` 10.11 writes `INSERT INTO … VALUES` and then one
row per line up to the `;`, not a whole statement on one line.
