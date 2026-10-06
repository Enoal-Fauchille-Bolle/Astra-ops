#!/bin/bash
# Watches the two thin pools of Astra, local-lvm (pve/data) and vault-thin (netac/thin).
# Installed as /usr/local/sbin/thin-pool-check, triggered every 5 min by thin-pool-check.timer.
# Why: docs/monitoring.md, "local-lvm and vault-thin".
#
# A thin pool cannot fill while the disks it holds add up to no more than its size, since no
# disk outgrows its own size. Proxmox still lets that sum go above, silently, through one
# snapshot or one new disk too many. Hence the main check, and two safety nets: the real fill,
# for the day overbooking is kept on purpose, and the metadata, which fills on its own.
#
# Reports to an Uptime Kuma push monitor when PUSH_URL is set (by the service, from
# /etc/default/thin-pool-check, so the token stays out of this repository). The monitor
# alerts on a "down" push, and when no push arrives in time.

set -euo pipefail

# --- CONFIGURATION ---
# Proxmox storage name = volume group/thin pool
POOLS=(
    "local-lvm=pve/data"
    "vault-thin=netac/thin"
)
MAX_PROVISIONED=100
MAX_DATA=90
MAX_META=80
# Kuma displays the URL with "?status=up&msg=OK&ping=" appended: keep only the part before "?"
PUSH_URL="${PUSH_URL:-}"
PUSH_URL="${PUSH_URL%%\?*}"
# ---------------------

push() {
    [ -n "$PUSH_URL" ] || return 0
    curl -fsS -m 10 --retry 3 -o /dev/null -G "$PUSH_URL" \
        --data-urlencode "status=$1" --data-urlencode "msg=$2" \
        || echo "WARNING: could not reach Uptime Kuma" >&2
}

# True when $1 > $2; awk because the percentages have decimals
over() {
    awk -v v="$1" -v m="$2" 'BEGIN {exit !(v > m)}'
}

join() {
    local sep="$1" out="$2"
    shift 2
    for item in "$@"; do out+="$sep$item"; done
    echo "$out"
}

# A failed read must not look like a healthy pool: report it, whatever the step
trap 'status=$?; [ "$status" -eq 0 ] || push down "Check failed with exit code $status, see journalctl -u thin-pool-check on astra"' EXIT

summary=()
problems=()
for entry in "${POOLS[@]}"; do
    name="${entry%%=*}"
    vg="${entry#*=}"; vg="${vg%/*}"
    pool="${entry#*/}"

    stats=$(lvs --noheadings --nosuffix --units b \
        -o lv_size,data_percent,metadata_percent "$vg/$pool")
    read -r size data meta <<< "$stats"
    # Every thin volume of the pool counts at its full size: disks, snapshots, saved RAM
    provisioned=$(lvs --noheadings --nosuffix --units b -o lv_size \
        -S "vg_name=$vg && pool_lv=$pool" | awk '{s += $1} END {print s + 0}')
    prov_pct=$(awk -v p="$provisioned" -v s="$size" 'BEGIN {printf "%.1f", 100 * p / s}')

    summary+=("$name provisioned ${prov_pct}% data ${data}% meta ${meta}%")
    if over "$prov_pct" "$MAX_PROVISIONED"; then
        problems+=("$name provisioned ${prov_pct}% > ${MAX_PROVISIONED}%")
    fi
    if over "$data" "$MAX_DATA"; then
        problems+=("$name data ${data}% > ${MAX_DATA}%")
    fi
    if over "$meta" "$MAX_META"; then
        problems+=("$name meta ${meta}% > ${MAX_META}%")
    fi
done

msg=$(join " | " "${summary[@]}")
echo "$msg"
if [ "${#problems[@]}" -eq 0 ]; then
    push up "$msg"
else
    alert=$(join ", " "${problems[@]}")
    echo "ALERT: $alert" >&2
    push down "$alert"
fi
