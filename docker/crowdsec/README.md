# CrowdSec

CrowdSec reads Nginx Proxy Manager's access logs (mounted read-only from
`/opt/docker-data/npm/data/logs`) and decides which addresses to ban. The bans are applied
by the **firewall bouncer**, installed on Pulsar itself, not in this repository.

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

## What it does not block

Traffic proxied by Cloudflare reaches Pulsar from Cloudflare's addresses, so the firewall
bans only stop **direct** traffic (sites in DNS-only mode, such as `immich.enoal.fr`). On
2026-09-15 that was 1 488 requests against 39 949 through Cloudflare. Blocking the rest is
an open item in [`docs/todo.md`](../../docs/todo.md) (Security, P3).
