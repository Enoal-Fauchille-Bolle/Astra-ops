# Filebrowser Quantum

Serves the personal files on `drive.enoal.fr`. It mounts `/mnt/drive` read-write at
`/srv/drive` and the movies read-only at `/srv/Films`. It mounts nothing under
`/mnt/data/backups`: **never mount that directory whole into an app** — it holds the
database dumps and the Proxmox configuration copy.

## Sources are configured outside this repository

Quantum's list of sources lives in `/opt/k3s-data/filebrowser-quantum/config.yaml` on
Pulsar, and is read only at start-up. Change it **before** removing a mount, never after,
or the app starts in error.

A new account's sidebar lists one source only: add the others with the pencil next to
*Navigation*.

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
