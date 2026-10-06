# Crafty

[Crafty Controller](https://craftycontrol.com) runs the Minecraft servers. The `watcher`
service next to it puts an empty server to sleep and wakes it when a player connects:
see [`watcher/README.md`](watcher/README.md).

## Ports

Crafty uses `network_mode: host`, so it binds its ports directly on Pulsar:

| Port        | Service                  |
| ----------- | ------------------------ |
| 8443        | Crafty admin UI          |
| 25500-25599 | Minecraft servers        |
| 4040        | Prism block log (SMP)    |
| 8098        | squaremap web map (SMP)  |
| 8099        | OPanel admin panel (SMP) |
| 8100        | BlueMap 3D map (SMP)     |
| 8804        | Plan player stats (SMP)  |

Only its launcher runs as root: Crafty and the Minecraft servers run as the `crafty` user
(uid 1000). Taking it out of host networking is an open item in
[`docs/todo.md`](../../docs/todo.md) (Security, P3).

The admin UI and the SMP plugin ports are open to the LAN and the VPN only; NPM serves them
by name (`crafty.enoal.fr` for the UI). See [Firewalls](../../docs/infrastructure.md#firewalls).

## Servers

Crafty names server and archive folders by UUID, not by name:

| UUID                                   | Crafty server        | Crafty archive schedule           |
| -------------------------------------- | -------------------- | --------------------------------- |
| `9ca997b5-937f-4fbd-bf5c-95f5eb06cfb2` | Nous Deux            | paused (world unchanged), keeps 2 |
| `69dc796b-62cf-450b-a846-48893db1a6cd` | Survie 1.20.4        | paused (world unchanged), keeps 2 |
| `c5da3465-e127-4ad2-9d36-bd313bf3eebe` | Roots SMP (SMP 26.2) | daily 04:00, keeps 3              |

## Data and backups

| Path on Pulsar                             | Content                        | Off-site copy                                                                                                            |
| ------------------------------------------ | ------------------------------ | ------------------------------------------------------------------------------------------------------------------------ |
| `/opt/docker-data/crafty/config/`          | Crafty's settings and database | Zerobyte Docker Data job, plus a nightly copy of `crafty.sqlite` ([database dumps](../../docs/backup/database-dumps.md)) |
| `/opt/docker-data/crafty/servers/`         | The live worlds                | none directly: excluded from the Docker Data job, the worlds leave through Crafty's archives                             |
| `/mnt/data/docker-volumes/crafty/backups/` | Crafty's `.zip` archives       | Zerobyte Crafty Backups job to Backblaze, daily 06:00, all three servers                                                 |
| `/mnt/data/docker-volumes/crafty/logs/`    | Logs                           | none                                                                                                                     |

The Crafty Backups job runs at 06:00 because Crafty writes Roots SMP's archive at 04:00 and
PBS's weekly verify reads the same drive on Saturdays at 05:00. Archives are compressed and
taken without stopping the server, on purpose; the reasons are in
[`docs/decisions.md`](../../docs/decisions.md). No Crafty archive has been test-restored yet.
