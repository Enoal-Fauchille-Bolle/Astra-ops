# Restoring the Obsidian notes (CouchDB)

> Section numbers (§) refer to the [backup overview](../../docs/backup/README.md); each numbered section there
> is either in place or points to where it moved.

The course notes (Obsidian vault `~/Documents/Courses` on the laptop, also on the phone) sync
through Self-hosted LiveSync and the CouchDB of `k3s/couchdb` (namespace `productivity`,
`couchdb.enoal.fr`), in a single database, `courses`. Job 16 copies `/opt/k3s-data/couchdb/`
(`data/` and `etc/`) to Backblaze every night at 01:00. Nothing else does: no dump (§6), no
readable export (below).

**What it takes to read the copy** — all three in the official Bitwarden cloud since
2026-09-14, because Vaultwarden runs on Astra:

| Secret | Needed for |
| --- | --- |
| LiveSync end-to-end encryption passphrase | reading anything — without it the copy stays unreadable |
| Setup URI and its own passphrase | reconnecting a device in one step |
| CouchDB account (`enoal`) | reconnecting the devices to a restored server |

**The passphrase is only half of the key.** Every chunk is encrypted (`encrypt: true`,
`E2EEAlgorithm: v2`, paths obfuscated — read from `_local/obsydian_livesync_milestone` on
2026-09-14). The key is derived from the passphrase **and** a salt kept in
`_local/obsidian_livesync_sync_parameters`. `_local` documents live in the `.couch` files, so
the raw copy has the salt. CouchDB replication never copies them: a replicated copy decrypts
to garbage, with an error that reads exactly like a wrong passphrase (livesync-bridge issue
#72).

**CouchDB is not a history.** CouchDB 3 compacts its databases on its own (default `smoosh`
settings) and drops old revisions on the way. An older version of a note comes from an older
job 16 snapshot.

## Reading the notes from a backup — tested 2026-09-14

For a partial loss (a note deleted or damaged): restore into a throwaway CouchDB on the
workstation, read the note in a test vault, copy it back by hand into the real vault. Leave
the production database alone: a deletion made on any device is a newer revision and would
win again.

1. Zerobyte → repository **Backblaze** → a **K3s Data** snapshot from before the incident →
   folder `couchdb` → **Download**. The archive holds `couchdb/data/` (`_dbs.couch`,
   `_nodes.couch`, `shards/*/courses.<n>.couch`) and `couchdb/etc/`.
2. Load it into Docker volumes — the image `chown`s its data directory, which would hand
   files in a home directory over to uid 5984:

   ```bash
   docker volume create restore-test-couchdb-data
   docker volume create restore-test-couchdb-etc
   docker run --rm -v restore-test-couchdb-data:/data -v restore-test-couchdb-etc:/etc-out \
     -v ~/Downloads/snapshot-<id>.tar:/in.tar:ro couchdb:3.5.2.1 sh -c \
     'tar -xf /in.tar -C /data --strip-components=2 couchdb/data &&
      tar -xf /in.tar -C /etc-out --strip-components=2 couchdb/etc/10-livesync.ini'
   ```

3. Start a throwaway CouchDB bound to the workstation only, with a throwaway admin (the
   production admin lives in `etc/docker.ini`, left out on purpose):

   ```bash
   docker run -d --name restore-test-couchdb -p 127.0.0.1:15984:5984 \
     -e COUCHDB_USER=restoretest -e COUCHDB_PASSWORD=<throwaway> \
     -v restore-test-couchdb-data:/opt/couchdb/data \
     -v restore-test-couchdb-etc:/opt/couchdb/etc/local.d couchdb:3.5.2.1
   curl -s -u restoretest:<throwaway> http://127.0.0.1:15984/courses
   curl -s -u restoretest:<throwaway> \
     http://127.0.0.1:15984/courses/_local/obsidian_livesync_sync_parameters   # must exist
   ```

4. Build a test vault in its own folder (`~/restore-test-courses`):
   - copy the plugin's `main.js`, `manifest.json` and `styles.css` from the real vault —
     **not** `data.json`, whose connection points at production and is encrypted per device;
   - list `obsidian-livesync` in `.obsidian/community-plugins.json`;
   - write a `data.json` with the throwaway connection in plain fields (`couchDB_URI`
     `http://127.0.0.1:15984`, `couchDB_USER`, `couchDB_PASSWORD`, `couchDB_DBNAME` `courses`,
     `isConfigured: true`) — LiveSync turns them into a remote on first load — plus
     `encrypt: true`, `E2EEAlgorithm: "v2"`, `usePathObfuscation: true`, an empty
     `passphrase`, every automatic sync off, and the chunk settings of the milestone's
     `tweak_values` (`customChunkSize` 60, `minimumChunkSize` 20, `hashAlg` `xxhash64`,
     `chunkSplitterVersion` `v3-rabin-karp`).

   **Never use the Setup URI in a test vault: it points at production.**
5. In Obsidian: *Manage vaults → Open folder as vault*, trust the plugin, type the
   passphrase, then run **Fetch everything from the remote**.
6. Clean up: close the window and *Remove from list* in *Manage vaults*, then
   `docker rm -f restore-test-couchdb`,
   `docker volume rm restore-test-couchdb-data restore-test-couchdb-etc`, and delete the test
   folder and the archive.

**Result on 2026-09-14.** Snapshot `4bcb4081` (01:00, 1.3 MB archive). CouchDB 3.5.2.1
recognised `courses` — 51 documents, the salt document present, every chunk still encrypted.
Obsidian 1.13.7 with LiveSync 1.0.28 decrypted all **8 files** that existed at 01:00 (seven
Markdown files and `Courses.base`). Compared with the live vault by `diff`: the four
*Advanced Project* notes were identical except for a front-matter property renamed later that
day (`to_review` → `processed`); the other four were their 01:00 versions, lacking only what
was added or changed after. Notes created after 01:00 were absent, as expected (RPO ≤ 24 h).

## Losing the server

Not tested. The devices hold the whole vault, so losing Astra does not lose the notes.
Putting job 16's copy back into `/opt/k3s-data/couchdb/` (deployment scaled to 0 first, owner
`5984:5984`) returns the server to its 01:00 state; check LiveSync's documentation of the day
for how the devices then catch up.

## Why there is no readable copy

Decided 2026-09-14. A Markdown export on Pulsar would need the passphrase on Astra, and would
leave the notes in plain text on Pulsar and in Backblaze — exactly what the end-to-end
encryption is there to prevent. The LiveSync CLI, the tool such an export would use, was
also assessed: no published release, a daemon mode that deleted documents at startup (issue
#1143, open), and a `sync` that writes checkpoints into the remote database (issue #846). A
copy made from the laptop was offered and declined. The readable copies are the devices.
