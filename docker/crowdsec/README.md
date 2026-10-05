# CrowdSec

CrowdSec reads Nginx Proxy Manager's access logs (mounted read-only from
`/opt/docker-data/npm/data/logs`) and the Crafty Server Watcher's log (see
[Minecraft proxy scans](#minecraft-proxy-scans)), and decides which addresses to ban. The
bans are applied by the **firewall bouncer**, installed on Pulsar itself, not in this
repository, and, for traffic proxied by Cloudflare, by a Cloudflare rule (see
[Bans behind Cloudflare](#bans-behind-cloudflare)).

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

## Web UI

[CrowdSec Web UI](https://github.com/TheDuffman85/crowdsec-web-ui) (`web-ui` service) shows
the alerts, the active and expired decisions, simulated ones included, and the metrics; it
can add and remove bans. It answers on `crowdsec.lan` through NPM (port 3000, LAN only) and
keeps its own login: the administrator account is created on the first visit.

It reaches the LAPI as the machine `crowdsec-web-ui`, whose password is the Portainer
variable `CROWDSEC_WEB_UI_PASSWORD`. To create or replace that account:

```sh
docker exec crowdsec cscli machines delete crowdsec-web-ui  # replacing only
docker exec crowdsec cscli machines add crowdsec-web-ui --password '<password>' -f /dev/null
```

`-f /dev/null` keeps cscli from overwriting the container's own credentials file.

Deleting alerts fails with `403 Forbidden`, on purpose: CrowdSec only allows it from the
addresses in `api.server.trusted_ips`, still `127.0.0.1` and `::1` alone. Removing a ban
works. Its cache, in `/opt/docker-data/crowdsec/web-ui`, keeps seven days of history and is
backed up with the rest of the directory.

## Bans behind Cloudflare

Traffic proxied by Cloudflare reaches Pulsar from Cloudflare's addresses, so the firewall
bans only stop **direct** traffic (sites in DNS-only mode, such as `immich.enoal.fr`). On
2026-09-15 that was 1 488 requests against 39 949 through Cloudflare.

For the rest, the `cloudflare-sync` service runs
[`cloudflare-sync/cloudflare_sync.py`](cloudflare-sync/cloudflare_sync.py) once a minute:
it reads the active bans from the LAPI and, when they changed, writes them into the
expression of the WAF custom rule _CrowdSec bans_ on `enoal.fr`, such as
`(ip.src in {203.0.113.7 198.51.100.0/24})`. The rule blocks them before the request leaves
Cloudflare. An expired ban leaves the rule at the next pass; with no ban at all, the
expression holds `192.0.2.1`, an address reserved for documentation.

**The script owns the expression**: an edit made by hand is overwritten at the next change.
It only writes the expression, so the rule's action and whether it is enabled stay as set
in the dashboard.

**Why not a Cloudflare IP list**: the first version filled the list `crowdsec_bans`, which
the rule referenced. From 2026-10-04 23:11, every write to the account's lists answered
`429` with code `10040` ("you have been ratelimited"), from the dashboard too, still after
eleven hours of tries spaced up to 30 minutes apart, and even on a list created the next
morning. Cloudflare does not document that code; other accounts on its community forum
report the same lock lasting days.

**Only CrowdSec's own bans are copied** (origins `crowdsec` and `cscli`), not the community
list: its ~27 000 addresses would never fit in an expression, limited to 4 096 characters
(about 250 IPv4 addresses). Measured over 2026-09-16 → 2026-10-04, the community list would
have stopped 1 754 of 1 207 055 requests through NPM, 1 657 of them crawlers and 97 attack
attempts. The firewall bouncer still applies the whole community list to direct traffic.

| Piece            | Where                                                                                    |
| ---------------- | ---------------------------------------------------------------------------------------- |
| Script           | `/opt/docker-data/crowdsec/cloudflare-sync/cloudflare_sync.py` on Pulsar, copy here      |
| CrowdSec access  | Bouncer `cloudflare-sync`, key in the Portainer variable `CROWDSEC_CLOUDFLARE_SYNC_KEY`  |
| Cloudflare token | `CLOUDFLARE_SYNC_TOKEN`: _Zone WAF: Edit_ on `enoal.fr`, limited to Pulsar's public IPv4 |
| Cloudflare zone  | `CLOUDFLARE_ZONE_ID`, the zone ID of `enoal.fr`                                          |
| Rule             | _CrowdSec bans_ on `enoal.fr`, action _Block_, found by that name                        |
| Alerting         | Kuma push monitor _CrowdSec Cloudflare Sync_, URL in `CLOUDFLARE_SYNC_KUMA_PUSH_URL`     |

The token can edit every WAF rule of `enoal.fr`, but only from Pulsar's address. The rule
was created by hand.

**If the service stops, the rule freezes**: expired bans stay blocked and new ones never
arrive. The Kuma monitor catches it. To undo everything, disable the rule in Cloudflare
first (instant), then remove the service.

To create or replace the bouncer key:

```sh
docker exec crowdsec cscli bouncers delete cloudflare-sync  # replacing only
docker exec crowdsec cscli bouncers add cloudflare-sync
```

The container's log (`docker logs crowdsec_cloudflare_sync`) has one line per change of the
rule and one per failure.
