# Advent-Calendar

Password-protected advent calendar, served on `https://avent.enoal.fr` through Nginx Proxy
Manager. The image is private: `ghcr.io/enoal-fauchille-bolle/advent-calendar`. The
surprises are files on Pulsar, never in git.

## First install, on Pulsar

These steps are done once, before the first sync.

1. Create the content folder. The pod mounts it read-only and runs as uid 1000 (the
   image's `node` user), so every file must be readable by others. The volume uses
   `hostPathType: Directory`, so the pod waits for this folder instead of starting on an
   empty one:

   ```bash
   sudo install -d -m 755 /opt/k3s-data/advent-calendar
   ```

   Copy `calendar.json` and the `days/` folder into it (the format is in the
   Advent-Calendar README), then make them readable:

   ```bash
   sudo chmod -R a+rX /opt/k3s-data/advent-calendar
   ```

2. Add three keys in Infisical (`infisical.lan` → project `astra-yrel` → env `prod`), read
   by the `ExternalSecret` in `values.yaml` ([secrets.md](../../docs/secrets.md)). The
   hashes come from `pnpm make-hash` in the Advent-Calendar repository:

   | Key                           | Value                                                  |
   | ----------------------------- | ------------------------------------------------------ |
   | `ADVENT_PASSWORD_HASH`        | Hash of the shared password                            |
   | `ADVENT_AUTHOR_PASSWORD_HASH` | Hash of the author password, which opens every door    |
   | `ADVENT_SESSION_SECRET`       | At least 32 characters, from `openssl rand -base64 48` |

   Changing `ADVENT_SESSION_SECRET` logs everyone out.

3. Create the pull secret named in `values.yaml` ([secrets.md](../../docs/secrets.md)):

   ```bash
   ../generate-regcred.sh web regcred-advent-calendar   # prompts for GitHub username + PAT
   kubectl apply -f regcred.yaml
   rm regcred.yaml
   ```

4. In Nginx Proxy Manager, add the proxy host `avent.enoal.fr` → `http://192.168.1.201:9080`
   (Traefik) with a Let's Encrypt certificate and "Force SSL".

## Updating the content

The days (`days/NN/`) are read on each request: copying new files in is enough.
`calendar.json` is read once at startup, so a change to it needs a restart:

```bash
kubectl rollout restart -n web deploy/advent-calendar
```
