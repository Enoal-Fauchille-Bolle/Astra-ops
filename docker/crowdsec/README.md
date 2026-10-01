# CrowdSec

CrowdSec reads Nginx Proxy Manager's access logs (mounted read-only from
`/opt/docker-data/npm/data/logs`) and the Crafty Server Watcher's log (see
[Minecraft proxy scans](#minecraft-proxy-scans)), and decides which addresses to ban. The
bans are applied by the **firewall bouncer**, installed on Pulsar itself, not in this
repository.

CrowdSec's configuration lives on Pulsar in `/opt/docker-data/crowdsec/config`, mounted as
`/etc/crowdsec`, and is backed up with the rest of `/opt/docker-data` (see
[`docs/backup/README.md`](../../docs/backup/README.md)). Only the files under
[`local/`](local/) are kept here too.

## Host configuration (not in this repository)

`/etc/crowdsec/bouncers/crowdsec-firewall-bouncer.yaml` on Pulsar lists `DOCKER-USER` under
`iptables_chains`, next to `INPUT` (since 2026-09-15). Docker-published ports, NPM's among
them, go through `FORWARD`, not `INPUT`: without `DOCKER-USER` the bans never reach the
containers.

Bans added by hand with `cscli decisions add` land in the `crowdsec-blacklists-2` ipset.

## Depends on NPM restoring the visitor's address

NPM sets `real_ip_header CF-Connecting-IP` (see [`docker/npm/README.md`](../npm/README.md)),
so its logs show the visitor, not Cloudflare. **Remove that and CrowdSec sees Cloudflare's
addresses**: the first ban would then cut every public site.

## Minecraft proxy scans

The Crafty Server Watcher holds the public Minecraft ports while servers sleep. Since 1.3.2
it writes one line per client sending something no real Minecraft client can send:

```text
2026-10-01 08:52:54 WARNING [crafty_server_watcher.proxy_listener] Rejected client 203.0.113.7 on port 25500 (server 'survival'): Packet too large: 31862890361 bytes
```

Its log file reaches CrowdSec through `/opt/docker-data/crafty/watcher/logs`, mounted
read-write in the watcher and read-only here. Three local files, copied in [`local/`](local/),
must be in place on Pulsar under `/opt/docker-data/crowdsec/config/`:

| File                                         | Role                                                                |
| -------------------------------------------- | ------------------------------------------------------------------- |
| `acquis.d/crafty-watcher.yaml`               | Reads `service.log`, labelled `type: crafty-watcher`                |
| `parsers/s01-parse/crafty-watcher-logs.yaml` | Extracts the address from `Rejected client` lines, ignores the rest |
| `scenarios/crafty-watcher-malformed.yaml`    | One rejected line → alert → the default 4 h ban                     |

`connection reset by peer` is parsed but never counted: a real client can hang up abruptly
too. Local addresses are never banned (`crowdsecurity/whitelists`), so a test from Pulsar
itself produces no alert.

The scenario starts in **simulation** (since 2026-10-01): its decisions show as `(simul)ban`
in `cscli decisions list` and block nothing. Once a week of them holds no player:

```sh
docker exec crowdsec cscli simulation disable enoal/crafty-watcher-malformed
docker restart crowdsec
```

After editing one of these files on Pulsar, copy it back to `local/` and restart the
container. `cscli explain --log "<line>" --type crafty-watcher` shows how a line is handled.

## What it does not block

Traffic proxied by Cloudflare reaches Pulsar from Cloudflare's addresses, so the firewall
bans only stop **direct** traffic (sites in DNS-only mode, such as `immich.enoal.fr`). On
2026-09-15 that was 1 488 requests against 39 949 through Cloudflare. Blocking the rest is
an open item in [`docs/todo.md`](../../docs/todo.md) (Security, P3).
