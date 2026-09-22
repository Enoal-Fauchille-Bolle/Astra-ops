# Monitoring & Alerts

> Section numbers (§) refer to the [backup overview](backup/README.md); each numbered section there
> is either in place or points to where it moved.

| Component                              | Monitoring Method                                                                      | Alert Channel                                                                                      |
| -------------------------------------- | -------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| Zerobyte job failures                  | Zerobyte built-in notifications                                                        | Discord webhook — ⚠️ **broken for long messages** (below)                                          |
| PVE backup job (vzdump)                | PVE notifications, `default-matcher`                                                   | Email, **errors only**: target `mail-to-root` → root@pam's address, sent by Postfix through Resend |
| PBS jobs (GC, verify, prune)           | PBS notifications, `default-matcher`                                                   | Email, **errors only**: SMTP target `resend` (configured 2026-09-09)                               |
| Proxmox config copy                    | Uptime Kuma push monitor (§4.2)                                                        | Discord (`APS #monitoring`): `down` pushed on failure, or no push for 25 h                         |
| Database dumps                         | Uptime Kuma push monitor **Database Dumps**, id 38 (§6)                                | Discord (`APS #monitoring`): `down` pushed on failure, naming the databases, or no push for 25 h   |
| Disk usage — `vault` + `pbs-datastore` | Beszel agent on Astra, drop-in below                                                   | Discord (`APS #monitoring`, Beszel webhook): above 75 %                                            |
| Disk usage — Pulsar sda                | Beszel agent on Pulsar                                                                 | Discord (Beszel): above 85 %                                                                       |
| LXC 101 `adguard`                      | Beszel agent in the container                                                          | Discord (Beszel): disk or memory above 80 %                                                        |
| AdGuard DNS answers                    | Uptime Kuma DNS monitor **AdGuard DNS**: resolves `beszel.lan` through `192.168.1.202` | Discord (`APS #monitoring`)                                                                        |
| LXC 103 `pbs`                          | Beszel agent in the container                                                          | Discord (Beszel): disk above 80 %, memory above 80 % for 10 min                                    |
| Cloud storage usage                    | MEGA web UI · B2 _Caps & Alerts_                                                       | Manual quarterly check · B2 spending cap                                                           |

> **PVE and PBS mail only failures since 2026-09-13.** Each `default-matcher` keeps a single
> rule, `match-severity error`: every job success is `info`, every failure `error`, so success
> mails stop — and so do the _package updates available_ ones, also `info`. Both matchers are
> now `modified-builtin`; _Reset_ in the GUI brings back the built-in one, which sends
> everything. A job that never starts sends nothing either: silence does not prove the backup
> ran.

> **Until 2026-09-11 no disk alert existed.** Dashdot only draws graphs: `vault` reached 79 %
> and LXC 101 95 % without a single message. The Beszel alerts above replace it.

> **Beszel keeps one disk alert per machine, and it fires on the fullest disk.** The agent on
> Astra only reports `/` until told otherwise; the drop-in
> [`infra/astra/beszel-agent.service.d/extra-filesystems.conf`](../infra/astra/beszel-agent.service.d/extra-filesystems.conf)
> adds `/mnt/pve/vault` and, since the 2026-09-22 Netac split,
> `/mnt/pbs-datastore` (the PBS vault's new, separate mount). With `/` at 14 %, `vault` at 17 %
> and `pbs-datastore` at 44 % (2026-09-22), the 75 % rule is in practice a `pbs-datastore` rule.
> The alert message names the machine, not the disk.

> **`local-lvm` and `vault-thin` have no alert, on purpose — and this already bit once.** A
> thin pool has no file system, so Beszel cannot see it, and its `Data%` counts every block
> ever written, not what the guests use. Measured 2026-09-11 on `local-lvm`: 378G provisioned
> on a 794G pool, `Data` 20 %, `Meta` 0.93 %. The pool cannot fill while provisioning stays
> below its size; add an alert before it goes above. **`vault-thin` (created 2026-09-22) is the
> same story, minus the safety margin**: a same-day disk move filled it to 96 % real usage
> (500G physically written for ~76G of real guest data — see `decisions.md`), invisible to
> Beszel the whole time. It was grown to 620G by hand; nothing would have caught it filling
> further on its own.

> **The agents in LXC 101 and 103 log `lookup beszel.lan on 1.1.1.1:53: no such host`.** Not a
> failure: both containers resolve through `1.1.1.1`, which does not know `beszel.lan`, so the
> hub falls back to reaching the agent over SSH on port 45876. Left as is — AdGuard must not
> depend on itself to resolve. Beszel's _Status_ alert only proves the agent answers; the
> Kuma DNS monitor proves AdGuard actually serves.

> **⚠️ Zerobyte → Discord loses the start of long messages (HTTP 400).** Diagnosed on
> 2026-09-12 from the source of Zerobyte v0.42.0 and of Shoutrrr v0.17.0, the sender inside
> the image; not reproduced against Discord. Zerobyte always sends a title and
> `splitLines=false`. Shoutrrr then cuts the body into batches of up to 6,000 characters, each
> sent as one message of embeds. Discord caps the text of all embeds in a message at 6,000
> characters **including the title**, so every full batch is rejected. A body under ~5,970
> characters arrives whole; a longer one loses each full 6,000-character batch and only its
> tail arrives. The failure messages of 2026-09-09 (9,741 and 13,379 characters) hit this —
> the earlier explanation, Discord's 2,000-character limit, was wrong: Shoutrrr already
> splits at 2,000. The loudest failures are exactly the ones that lose their beginning.
> **Accepted as is on 2026-09-12:** the title and the tail of the error still arrive, and the
> full error stays readable in the Zerobyte UI.

> **No ntfy webhook, by decision (2026-09-15):** Zerobyte notifies Discord only.
