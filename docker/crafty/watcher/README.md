# crafty-server-watcher

The watcher hibernates the Minecraft servers (ports 25500-25501) and wakes them
when a whitelisted player connects.

We run [`ghcr.io/enoal-fauchille-bolle/crafty-server-watcher`](https://github.com/Enoal-Fauchille-Bolle/Crafty-Server-Watcher),
a fork of [Soveticka/Crafty-Server-Watcher](https://github.com/Soveticka/Crafty-Server-Watcher).
Each change is offered upstream as its own pull request; the fork's README
tracks what diverges and why.

> This directory previously held a `Dockerfile` that patched the upstream image
> at build time. That is gone — see "Why an image, never a build" below. Only
> this README and `config.example.yaml` remain.

## Why an image, never a build

`build:` in this stack is what kept the servers running forever.

Portainer redeploys the stack from Git every ~5 minutes. A `build:` service is
rebuilt on every poll, the resulting image ID differs, and Compose therefore
*recreates* the container — while `crafty` next to it, on a fixed image tag,
is merely reported as `Running`:

```
15:33:43  Crafty Server Watcher starting
15:38:39  Crafty Server Watcher starting      <-- recreated, +4min56
15:43:37  Crafty Server Watcher starting      <-- recreated, +4min58
```

The idle countdown lives in the watcher's memory, so every recreation reset it:

```
15:42:40  idle for 240s / 600s, shutdown in 360s
15:43:37  [recreation]
15:44:10  idle for  30s / 600s, shutdown in 570s
```

A 10-minute threshold reset every 5 minutes is unreachable. Crafty's audit log
confirms the outcome: over weeks it recorded `start_server` from the `watcher`
user many times and `stop_server` **never** — the only stops were manual.

Two independent fixes, so this cannot come back:

1. **This file**: a pinned `image:` tag, never `build:`. Renovate tracks it
   through the existing `docker-compose.yml` manager.
2. **The fork**: `state.file` persists the countdown to disk, so even a genuine
   restart resumes where it left off.

## Wake-up whitelist

Any login attempt used to start a server, and a scanner (`Cornbread2100_`) was
booting both of them nightly. The Minecraft whitelist refused it — but only
after the JVM was up and holding 1.5 GB.

`access.mode: whitelist` refuses the wake-up first, reading each server's own
`whitelist.json` through the read-only `/servers` mount. Adding a friend with
`/whitelist add` in Crafty is enough; the watcher re-reads the file on change.

The player name arrives before Mojang authentication, so it is a claim rather
than a proof: someone who knows a whitelisted name can still trigger a start.
That stops scanners trying arbitrary names, which is the actual problem here.

If the whitelist cannot be read, the watcher allows everyone and logs an error
— a broken mount must not lock us out of our own servers.

## Starting a server from the Crafty console

Pressing **Start** in Crafty used to kill the server it was starting:

```
**** FAILED TO BIND TO PORT!
The exception was: ... bind(..) failed with error(-98): Address already in use
```

The watcher holds a sleeping server's port — that is how it shows the MOTD and
wakes it on connect — and it only polls Crafty every 30s. A start it did not
trigger itself therefore loses the race: the JVM asks for the port about five
seconds after being spawned, long before the next poll.

Since watcher 1.2.0 the watcher listens for Crafty's own `start_server` webhook,
which lands **0.8s** after the JVM is spawned (measured on `SMP 26.2`), and steps
off the port immediately. The start is announced on Discord like a player
wake-up, tagged `Triggered from Crafty (console or API)`.

This needs two halves, and **neither lives in this repo**:

1. In `/opt/docker-data/crafty/watcher/config.yaml`, next to the rest of the
   config:

   ```yaml
   crafty_events:
     enabled: true
     path: "/events/crafty"
     token: "<shared secret>"
   ```

2. In Crafty, per server: **Config → Webhooks → New webhook**

   | Field | Value |
   |---|---|
   | Type | `Discord` — any provider works, only the URL and body matter |
   | URL | `http://127.0.0.1:8095/events/crafty?token=<the same secret>` |
   | Triggers | `start_server` — the trigger is not called `server_start` |
   | Body | `{"server_id": "{{ server_id }}", "event": "{{ event_type }}"}` |

The secret matters even though the endpoint binds to `127.0.0.1`: `crafty` and
`crafty_watcher` both run with `network_mode: host`, so every container on that
network shares the same localhost.

Two consequences worth remembering:

- The webhook is stored in Crafty's own database, so it is one more piece of
  unversioned state — like the scheduled backups.
- **Rolling the watcher back below 1.2.0 requires disabling that webhook.** The
  older health server answers `405` to any POST, and Crafty calls
  `raise_for_status()` from inside the very call that started the server, so
  every start would raise in Crafty's start path.

## Configuration

The live config is **not** in this repo: it sits on the host at
`/opt/docker-data/crafty/watcher/config.yaml` (mounted read-only), because it
holds the Discord webhook URL and the Crafty server UUIDs. See
`config.example.yaml` for the format. The Crafty API token comes from the
`CRAFTY_API_TOKEN` environment variable.

Two host paths are mounted beyond the config:

| Host | Container | Why |
|---|---|---|
| `/opt/docker-data/crafty/watcher/state` | `/data` | Idle countdowns, survives restarts |
| `/opt/docker-data/crafty/servers` | `/servers` (ro) | Each server's `whitelist.json` |

Create the state directory before the first deploy:

```bash
mkdir -p /opt/docker-data/crafty/watcher/state
```

## Checking it works

```bash
# 1. The container is no longer recreated on every GitOps poll.
docker inspect crafty_watcher --format '{{.State.StartedAt}} {{.RestartCount}}'
# wait 10-15 min, run again: StartedAt must be unchanged
docker logs --since 15m portainer 2>&1 | grep -a crafty_watcher
# expected: "Container crafty_watcher  Running"   (never "Recreate")

# 2. The idle counter now gets past 600s.
curl -s http://127.0.0.1:8095/status
docker logs --tail 20 crafty_watcher | grep 'idle for'

# 3. The shutdown actually happens — absent from the audit log until now.
tail -5 /mnt/data/docker-volumes/crafty/logs/audit.log
# expected: "issued command stop_server ...", user_name: "watcher"
```
