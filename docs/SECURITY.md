# Security — Hardening Tasks

> Open work from the security audit of 2026-09-08, which rated each fix P1 (urgent) to P5.
> P1 and P2 are done; what follows is P3 to P5 and the closing step. The audit report itself
> stays outside this public repository. Backup and storage tasks live in
> [`backup/README.md` §12](backup/README.md#12-pending-tasks--future-work).
>
> Items are checked only where the state was verified on the machines, not where a commit
> merely exists.

## P3 — Apps with more privileges than they need

The common risk: a container that holds host-level privileges turns a flaw in one small app
into control of Pulsar, with every app, database and backup on it.

- [x] **Remove the classic Filebrowser, hide the backups from Quantum** (2026-09-14, `f6d4527`,
      `ca56a5a`) — both apps ran as root and mounted `/mnt/data/backups` whole, dumps and
      Proxmox configuration copy included, reachable from the Internet through `drive.enoal.fr`
      ([`backup/database-dumps.md`](backup/database-dumps.md))
- [x] **Run Filebrowser Quantum as non-root** (2026-09-14, `c1b5a9e`) — uid 1000
- [x] **Run SFTPGo as non-root** (2026-09-15, `e87b3b6`) — uid 1000; as root, its account could
      read and delete the dumps
- [x] **Remove the Cloudflare tunnel** (2026-09-15, `90d75ad`) — it ran with no route at all
- [x] **dashdot without privileged mode or the host's root** (2026-09-15, `dc21b1d`; memory
      limit `b92eab9`) — it ran `privileged: true` with `/` mounted: a flaw in it was
      root on Pulsar, and it could read every file there. Now uid 1000, no capability, and
      five read-only mounts of what it reads. Tested in a throwaway pod before the commit:
      same figures as the privileged pod, except the system disk (~3.6G higher, see
      `k3s/dashdot/values.yaml`). The data-disk mount needs the empty `/mnt/data/.dashdot`.
      Also fixes 28 restarts: the speed test (every 4 h) went over the 192Mi limit
      (`OOMKilled`); now 320Mi. Checked after ArgoCD's sync: `uid=1000`, `CapEff` 0,
      `NoNewPrivs` 1, `dashdot.lan` → `200` with the host's OS, disks and traffic, and the
      startup speed test completed with 0 restarts
- [x] **portracker without ptrace or SYS_ADMIN** (2026-09-15, `dfa6af3`) — the host PID
      namespace plus `SYS_PTRACE` and `apparmor:unconfined` let it attach to any host process,
      which is root on Pulsar. `SYS_ADMIN` only serves Docker Desktop (vendor README). Tested
      with throwaway containers: without the three, it still lists every port (186 against
      188 live), but no longer names the program behind the 21 host ports — `sudo ss -tulpn`
      on Pulsar does. Docker ports keep their names through the socket proxy. Checked after
      Portainer's redeploy: no added capability, AppArmor profile `docker-default`, 185 ports
      listed, 21 of them host ports without a program name, as tested
- [ ] **CrowdSec: make the bans reach web traffic** — it runs (the README says `⏸️ Disabled`,
      wrong since at least 2026-09-08), reads NPM's logs and bans real attackers, but the
      firewall bouncer hooks `INPUT` only, and Docker-published ports go through `FORWARD`:
      its `DROP` rules had matched 0 packets. Order matters: NPM does not restore the
      visitor's address behind Cloudflare (no `real_ip`), so CrowdSec sees Cloudflare's
      addresses. Hooking the bouncer into `DOCKER-USER` first would ban Cloudflare and cut
      every public site. Configure `real_ip` in NPM, check the logs show visitors' addresses,
      then extend the bouncer. Fix the README line in the same change
  - [x] **NPM logs visitors' addresses** (2026-09-15) — `real_ip_header CF-Connecting-IP` in
        `server_proxy.conf` ([`docker/npm/README.md`](../docker/npm/README.md)). Checked after
        the reload: the 18 public sites answer the same codes as before, and the logs show no
        Cloudflare address any more (a test request shows the tester's public address)
  - [x] **Firewall bans reach the containers** (2026-09-15) — `DOCKER-USER` added under
        `iptables_chains` in `/etc/crowdsec/bouncers/crowdsec-firewall-bouncer.yaml` on Pulsar
        (host file, not in this repository; previous version kept as `.bak-2026-09-15`).
        Before: the community list (24 430 IPv4, 455 IPv6) and the local bans contained no
        Cloudflare or private address. After: the 18 public sites answer the same codes; a
        throwaway container banned with `cscli decisions add --ip` got no answer from NPM
        (`000`), then `200` once the ban was deleted. Bans added by hand land in
        `crowdsec-blacklists-2`, not `-1`. README status fixed. Blocks direct traffic only:
        on 2026-09-15, 1 488 direct requests (37 addresses, sites in DNS-only mode such as
        `immich.enoal.fr`) against 39 949 through Cloudflare, whose connections come from
        Cloudflare's addresses
  - [ ] **Block traffic that comes through Cloudflare** — Cloudflare Worker Bouncer tried on
        2026-09-15, then abandoned and fully removed (package, config, LAPI key, and everything
        it created at Cloudflare, checked through the API). Volume fits the free plan (831 730
        requests over 30 days, worst day ~42 000, against 100 000). What stopped it: the deploy
        fails with `You need to enable Analytics Engine (10089)` although a dataset was created;
        the account had never deployed a Worker, which reportedly must happen first (untested).
        Also found in the v0.0.18 source: every start and stop deletes and recreates the worker
        route, so a "Fail open" set by hand in the dashboard would be lost at each restart. Only
        the bouncer's local bans would fit anyway: 1 000 KV writes a day against 24 885 entries
        in the community list. Other paths: an IP list plus a WAF custom rule (1 list, 10 000
        items on Free; the official `cs-cloudflare-bouncer` doing this was archived on
        2026-09-02), or a bouncer inside NPM
- [ ] **Crafty out of `network_mode: host` and root** — it binds its ports on the host directly
      (8443 among them) as uid 0. Touches the sleep watcher of Roots SMP, which holds the
      server's port while it sleeps

## P4 — Reorganise VMIDs, IPs, tags and disks

- [ ] Not started. Constraint: PBS groups backups by VMID, so renumbering a guest starts its
      backup history from zero. VM 106 is a linked clone of template 105

## P5 — Documentation

- [ ] Rewrite the documentation to separate what is in place from what is planned

## Closing — last step, after P3 to P5

- [ ] Remove `/etc/sudoers.d/99-claude-audit` on Astra and on Pulsar. It gives `enoal`
      password-less `sudo` (`NOPASSWD:ALL`) for Claude's sessions, kept on purpose for the
      whole remediation
