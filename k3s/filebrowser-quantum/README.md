# Filebrowser Quantum

Serves the personal files on `drive.enoal.fr`. It mounts `/mnt/drive` read-write at
`/srv/drive` and the movies read-only at `/srv/Films`. It mounts nothing under
`/mnt/data/backups`: **never mount that directory whole into an app**: it holds the
database dumps and the Proxmox configuration copy.

## Sources are configured outside this repository

Quantum's list of sources lives in `/opt/k3s-data/filebrowser-quantum/config.yaml` on
Pulsar, and is read only at start-up. Change it **before** removing a mount, never after,
or the app starts in error. The same file holds the database path (`server.database.path`,
a SQLite file in the same directory) and `http.trustProxyHeaders: true`, which makes the
app read the client address and protocol from the proxy headers.

A new account's sidebar lists one source only: add the others with the pencil next to
_Navigation_.

## Logs show 10.42.0.1 as the client

With `http.trustProxyHeaders: true`, version 2.0.2 takes the **last** entry of
`X-Forwarded-For`, which it assumes is the single trusted proxy's view of the visitor.
Here two proxies sit in front (NPM, then Traefik) and Traefik appends the address it was
contacted from, `10.42.0.1`, so that is what Quantum logs and rate-limits on, although
Traefik passes the visitor's address in `X-Real-Ip`
([`docs/infrastructure.md`](../../docs/infrastructure.md#traefik-and-the-visitors-address)).
The `http.trustedProxies` setting, which skips known proxies from the right, exists only in
the 2.1 betas. Revisit when it reaches a stable release.

## Runs as uid 1000

The pod runs as uid/gid 1000 (the image's own `filebrowser` user), non-root, with no
capability. hostPath volumes ignore `fsGroup`, so the directories it writes to must be
owned by `1000:1000` on Pulsar. A file put there by root on the host (`sudo cp`), or a
restore from an older snapshot, breaks writing: re-run

```bash
sudo chown -R 1000:1000 /mnt/drive /opt/k3s-data/filebrowser-quantum
```

SFTPGo mounts the same directory and runs as uid 1000 too, so files it creates keep that
owner.
