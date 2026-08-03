# crafty-server-watcher (patched)

The watcher hibernates the Minecraft servers and wakes them up when a player
connects. We run the upstream image
[`ghcr.io/soveticka/crafty-server-watcher`](https://github.com/Soveticka/Crafty-Server-Watcher),
**patched at build time** because of a race condition that breaks roughly one
wake-up in six.

> This directory is temporary. Once the fix ships upstream: delete
> `Dockerfile`, `patch_start_race.py` and `test_start_race.py`, and put
> `image: ghcr.io/soveticka/crafty-server-watcher:latest` back in
> `../docker-compose.yml`.
>
> Upstream tracking: [issue #22](https://github.com/Soveticka/Crafty-Server-Watcher/issues/22)
> · [PR #23](https://github.com/Soveticka/Crafty-Server-Watcher/pull/23)

## The bug

Symptom: a player connects, the watcher does start the server, but Paper dies
immediately.

```
[13:24:36 WARN]: **** FAILED TO BIND TO PORT!
[13:24:36 WARN]: bind(..) failed with error(-98): Address already in use
```

Cause: in `_handle_login()` the watcher releases the port, **sleeps 5 seconds**,
then calls the Crafty API and only afterwards moves the state machine to
`STARTING`. But `ensure_listeners()` runs concurrently on every polling tick
(30s by default); a tick landing inside that window still sees `STOPPED`, clears
the start lockout and **re-binds the port** right under the Minecraft server
that is booting.

```
11:24:24.759  Proxy listener stopped on port 25500 for server 'server-1'
11:24:29.571  Start lockout cleared for 'server-1' (state=STOPPED)          <-- tick during the sleep
11:24:29.571  Proxy listener started on 0.0.0.0:25500 for server 'server-1' <-- port taken back
11:24:29.774  Port 25500 released and start_server sent (lockout active)    <-- the lockout is gone
11:24:36      Paper: Address already in use
```

## The fix

`patch_start_race.py` applies four replacements anchored on the upstream source:

1. `sm.transition(State.STARTING)` **before** the `sleep(5)` — `ensure_listeners()`
   then takes the `continue` branch and leaves the port alone.
2. Removal of the now-redundant transition after `start_server()`.
3. Rollback to `STOPPED` if the API call fails, so the existing recovery path
   (clear the lockout, re-bind) stays consistent.
4. Addition of the `CRASHED → STARTING` edge in the transition graph:
   `_handle_login()` also starts servers from `CRASHED`, but the graph rejected
   that transition (`invalid transition ... (ignored)`), so the bug came right
   back for a server that had just crashed.

Every anchor must match **exactly once**, otherwise the build fails with an
explicit message: if upstream changes those blocks we find out immediately
instead of silently overwriting their changes. That is also why `FROM` is
pinned by digest — Renovate will offer the bump, and the build will break if the
patch no longer applies.

## Verifying the fix

`test_start_race.py` replays the real `_handle_login()` path over a real socket,
fires a polling tick in the middle of the start window, then checks whether a
server could actually bind the port.

```bash
docker build -t crafty-watcher:test .
docker run --rm -e PYTHONPATH=/app -w /app \
  -v "$PWD/test_start_race.py:/test_start_race.py:ro" \
  --entrypoint python crafty-watcher:test /test_start_race.py STOPPED
docker run --rm -e PYTHONPATH=/app -w /app \
  -v "$PWD/test_start_race.py:/test_start_race.py:ro" \
  --entrypoint python crafty-watcher:test /test_start_race.py CRASHED
```

Expected: `port 25500 free for MC : True` and exit code 0. Both scenarios fail
against the unpatched upstream image.

## Configuration

The config does not live in this repo: it sits on the host at
`/opt/docker-data/crafty/watcher/config.yaml` (mounted read-only), because it
holds the Discord webhook URL and the Crafty server UUIDs. See
`config.example.yaml` for the format. The Crafty API token comes from the
`CRAFTY_API_TOKEN` environment variable.
