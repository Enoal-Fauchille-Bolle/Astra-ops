#!/bin/bash
# Dumps the live databases of Pulsar into /mnt/data/backups/dumps/, where Zerobyte job 13
# ("Backups") ships them off-site to Backblaze every night at 02:00.
# Installed as /usr/local/sbin/dump-databases, triggered by dump-databases.timer.
# Why it exists and how to restore from it: docs/backup/database-dumps.md.
#
# Reports to an Uptime Kuma push monitor when PUSH_URL is set (by the service, from
# /etc/default/dump-databases — the token stays out of this repository). The monitor alerts
# when no push arrives in time, which also covers a timer that never fires.
#
# Each database is dumped on its own: a failure keeps that database's last good dump, lets
# the others through, and reports "down". A dump replaces the previous one only once checked.

set -euo pipefail
# The dumps hold password hashes and encrypted secrets: root only
umask 077

# --- CONFIGURATION ---
DUMP_DIR="${DUMP_DIR:-/mnt/data/backups/dumps}"
# PostgreSQL in k3s, as "<dump name>=<namespace>/<deployment>". User and database are the
# container's own POSTGRES_USER and POSTGRES_DB.
K3S_POSTGRES=(
    "umami=analytics/umami-postgres"
    "infisical=infisical/infisical-postgres"
)
# Uptime Kuma 2 runs an embedded MariaDB; root reaches it over the socket without a password
KUMA_DEPLOYMENT="monitoring/uptimekuma"
KUMA_SOCKET="/app/data/run/mariadb.sock"
KUMA_DATABASE="kuma"
# SQLite databases worth a guaranteed copy. The others (caches, statistics, indexes) are only
# copied raw by Zerobyte jobs 16 and 17, like these ones too — except Zerobyte's own, which
# lies outside both app roots: this dump is its only off-site copy.
SQLITE=(
    "zerobyte=/var/lib/zerobyte/data/zerobyte.db"
    "vaultwarden=/opt/k3s-data/vaultwarden/db.sqlite3"
    "n8n=/opt/k3s-data/n8n/data/database.sqlite"
    "sftpgo=/opt/k3s-data/sftpgo/sftpgo.db"
    "ntfy-user=/opt/k3s-data/ntfy/data/user.db"
    "jellyfin=/opt/k3s-data/jellyfin/config/data/jellyfin.db"
    "npm=/opt/docker-data/npm/data/database.sqlite"
    "homarr=/opt/docker-data/homarr/db/db.sqlite"
    "wallos=/opt/docker-data/wallos/db/wallos.db"
    "crafty=/opt/docker-data/crafty/config/db/crafty.sqlite"
    "beszel=/opt/docker-data/beszel/data.db"
    "speedtest-tracker=/opt/docker-data/speedtest-tracker/database.sqlite"
    "loandash=/opt/docker-data/loandash/loandash.db"
)
# Per dump: a stuck one must not run into job 13 at 02:00
DUMP_TIMEOUT="15m"
# Kuma displays the URL with "?status=up&msg=OK&ping=" appended: keep only the part before "?"
PUSH_URL="${PUSH_URL:-}"
PUSH_URL="${PUSH_URL%%\?*}"
# ---------------------

# Copies a live SQLite database through the online backup API (consistent while the app
# writes), checks the copy in memory, and writes it to stdout. mode=rw makes a wrong path fail
# instead of creating an empty database.
SQLITE_COPY='
import sqlite3, sys
src = sqlite3.connect(f"file:{sys.argv[1]}?mode=rw", uri=True, timeout=60)
copy = sqlite3.connect(":memory:")
src.backup(copy)
src.close()
check = copy.execute("PRAGMA integrity_check").fetchone()[0]
tables = copy.execute("SELECT count(*) FROM sqlite_master WHERE type = ?", ("table",)).fetchone()[0]
if check != "ok" or tables == 0:
    sys.exit(f"integrity_check: {check}, tables: {tables}")
sys.stdout.buffer.write(copy.serialize())
'

push() {
    [ -n "$PUSH_URL" ] || return 0
    curl -fsS -m 10 --retry 3 -o /dev/null -G "$PUSH_URL" \
        --data-urlencode "status=$1" --data-urlencode "msg=$2" \
        || echo "WARNING: could not reach Uptime Kuma" >&2
}

# Single exit point: every failure, `set -e` included, ends here and reports "down"
FAILED=()
DONE=0
finish() {
    local status=$?
    rm -f "$DUMP_DIR"/.*.tmp
    if [ "$status" -eq 0 ] && [ "${#FAILED[@]}" -eq 0 ]; then
        push up "OK, $DONE dumps"
    else
        push down "Failed: ${FAILED[*]:-script error $status}, see journalctl -u dump-databases on pulsar"
    fi
}
trap finish EXIT

# The functions below run as `if` conditions, where `set -e` does not apply: every step
# checks its own result.

# $1 dump name, $2 the file written so far, $3 its end-of-dump marker. A dump cut short by a
# crash or a timeout lacks the marker; an empty database has no table.
check_sql() {
    if ! tail -n 5 "$2" | grep -q "$3"; then
        echo "ERROR: $1: no \"$3\" at the end, dump incomplete" >&2
        return 1
    fi
    if ! grep -q '^CREATE TABLE ' "$2"; then
        echo "ERROR: $1: no CREATE TABLE in the dump" >&2
        return 1
    fi
}

# $1 dump name, then the command that runs a program inside the database container
dump_postgres() {
    local name=$1 tmp="$DUMP_DIR/.$1.sql.tmp"
    shift
    # Plain SQL, uncompressed: restic deduplicates it night after night, and compresses it
    timeout "$DUMP_TIMEOUT" "$@" sh -c 'exec pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB"' \
        > "$tmp" || return 1
    check_sql "$name" "$tmp" '^-- PostgreSQL database dump complete$' || return 1
    mv -f "$tmp" "$DUMP_DIR/$name.sql"
}

dump_kuma() {
    local tmp="$DUMP_DIR/.uptimekuma.sql.tmp"
    # All tables are InnoDB: --single-transaction reads a consistent state without locking
    timeout "$DUMP_TIMEOUT" k3s kubectl -n "${KUMA_DEPLOYMENT%%/*}" exec "deploy/${KUMA_DEPLOYMENT#*/}" -- \
        mariadb-dump --socket="$KUMA_SOCKET" -u root --single-transaction \
        --routines --triggers --events --databases "$KUMA_DATABASE" \
        > "$tmp" || return 1
    check_sql uptimekuma "$tmp" '^-- Dump completed' || return 1
    mv -f "$tmp" "$DUMP_DIR/uptimekuma.sql"
}

# Run as the database's owner: opening a WAL database may create its -wal and -shm files,
# and root-owned ones would lock the app out of its own database.
dump_sqlite() {
    local name=$1 src=$2 tmp="$DUMP_DIR/.$1.sqlite.tmp" owner
    owner=$(stat -c '%u:%g' "$src") || return 1
    timeout "$DUMP_TIMEOUT" setpriv --reuid="${owner%:*}" --regid="${owner#*:}" --clear-groups \
        python3 -c "$SQLITE_COPY" "$src" > "$tmp" || return 1
    mv -f "$tmp" "$DUMP_DIR/$name.sqlite"
}

# $1 dump name, then the dump command
run() {
    local name=$1
    shift
    if "$@"; then
        DONE=$((DONE + 1))
        echo "$name: OK"
    else
        FAILED+=("$name")
        echo "ERROR: $name failed, its previous dump is kept" >&2
    fi
}

install -d -m 700 "$DUMP_DIR"

for entry in "${K3S_POSTGRES[@]}"; do
    target=${entry#*=}
    run "${entry%%=*}" dump_postgres "${entry%%=*}" \
        k3s kubectl -n "${target%%/*}" exec "deploy/${target#*/}" --
done
run uptimekuma dump_kuma
for entry in "${SQLITE[@]}"; do
    run "${entry%%=*}" dump_sqlite "${entry%%=*}" "${entry#*=}"
done

echo "$DONE dumps written to $DUMP_DIR, ${#FAILED[@]} failed"
[ "${#FAILED[@]}" -eq 0 ]
