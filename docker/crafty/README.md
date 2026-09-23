# Crafty

[Crafty Controller](https://craftycontrol.com) runs the Minecraft servers. The `watcher`
service next to it puts an empty server to sleep and wakes it when a player connects:
see [`watcher/README.md`](watcher/README.md).

## Ports

Crafty uses `network_mode: host`, so it binds its ports directly on Pulsar:

| Port        | Service                 |
| ----------- | ----------------------- |
| 8443        | Crafty admin UI         |
| 25500-25599 | Minecraft servers       |
| 8098        | squaremap web map (SMP) |

It also runs as root. Taking it out of host networking and root is an open item in
[`docs/todo.md`](../../docs/todo.md) (Security, P3).

## Servers

Crafty names server and archive folders by UUID, not by name:

| UUID                                   | Crafty server        | Crafty archive schedule (2026-09-11)               |
| -------------------------------------- | -------------------- | -------------------------------------------------- |
| `9ca997b5-937f-4fbd-bf5c-95f5eb06cfb2` | Nous Deux            | paused (world unchanged since 2026-08-15), keeps 2 |
| `69dc796b-62cf-450b-a846-48893db1a6cd` | Survie 1.20.4        | paused (world unchanged since 2026-09-07), keeps 2 |
| `c5da3465-e127-4ad2-9d36-bd313bf3eebe` | Roots SMP (SMP 26.2) | daily 04:00, keeps 3                               |

## Data and backups

| Path on Pulsar                             | Content                        | Off-site copy                                                                                                   |
| ------------------------------------------ | ------------------------------ | --------------------------------------------------------------------------------------------------------------- |
| `/opt/docker-data/crafty/config/`          | Crafty's settings and database | Zerobyte job 17, plus a nightly copy of `crafty.sqlite` ([database dumps](../../docs/backup/database-dumps.md)) |
| `/opt/docker-data/crafty/servers/`         | The live worlds                | none directly: excluded from job 17, the worlds leave through Crafty's archives                                 |
| `/mnt/data/docker-volumes/crafty/backups/` | Crafty's `.zip` archives       | Zerobyte job 15 to Backblaze, daily 06:00, all three servers                                                    |
| `/mnt/data/docker-volumes/crafty/logs/`    | Logs                           | none                                                                                                            |

Job 15 runs at 06:00 because Crafty writes Roots SMP's archive at 04:00 and PBS verifies
the same drive at 05:00. Archives are compressed and taken without stopping the server, on
purpose — the reasons are in [`docs/decisions.md`](../../docs/decisions.md). No Crafty
archive has been test-restored yet.
