# VM template

VM 9000 `debian13-template` on Astra is a Debian 13 template for lab VMs (energy measurement,
bit-flip tests on a local LLM, and whatever comes next). It is built from Debian's official
**cloud image**, not from the installer ISO, and gets its identity from **cloud-init** at the
first boot of each clone. Built 2026-09-27.

## What the template holds, and what it leaves out

In the template, because every clone needs it:

| Item                                                                                         | Why                                                                             |
| -------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------- |
| Debian 13 `genericcloud` image, 20G disk on `local-lvm`                                      | Minimal, no installer leftovers, the root partition grows to the disk on boot   |
| cloud-init: user `enoal`, laptop SSH key, a console password, DNS `192.168.1.254`, `ip=dhcp` | Each clone gets its own name, IP, machine-id and SSH host keys on first boot    |
| `qemu-guest-agent`                                                                           | Clean shutdown and IP display from Proxmox                                      |
| `unattended-upgrades` and `apt-listchanges` purged                                           | Background work skews measurements; updates are manual                          |
| Timers disabled: `apt-daily`, `apt-daily-upgrade`, `man-db`, `dpkg-db-backup`, `e2scrub_all` | Same reason                                                                     |
| `fstrim.timer` **kept**                                                                      | Weekly and light; it hands freed blocks back to `local-lvm`, shared with Pulsar |
| 2 cores, 2 GiB, ballooning off (`balloon: 0`)                                                | A ballooned guest saw 1.3 GiB out of 4 and its memory moved under measurement   |

Left to each clone, because it depends on the use:

- CPU type `host`: exposes AVX2 (Ollama) and the Intel model the guest's RAPL driver needs.
- Memory, cores, and core pinning if needed (P-cores are host CPUs 0-7, E-cores 8-15).
  Clones keep the ballooning device with **minimum = memory**: the guest never loses RAM, and
  Proxmox still gets the guest's real usage through it (`balloon: 0` shows the QEMU process's
  host memory instead, cache included — 805 MiB for a guest using 311 MiB).
- Applications (Ollama…) and the virtual RAPL `args:` line.

Proxmox's cloud-init setting `ciupgrade` is left at its default: each clone installs pending
updates on its first boot. The password only serves the Proxmox console, for a guest that lost
its network: SSH stays key-only (`sshd -T` → `passwordauthentication no`), and `sudo` asks for
nothing. cloud-init reports `degraded done` on the template because Proxmox
still writes the deprecated `user:` key; the warning is harmless.

## Clone a VM

1. Proxmox UI → right-click `9000 (debian13-template)` → **Clone**.
2. **VM ID** and **Name**: the name becomes the guest's hostname (cloud-init `hostname:`),
   there is no separate hostname field. **Mode**: _Full Clone_ (a linked clone keeps depending
   on the template's disk, which then can no longer be removed).
3. On the clone → **Cloud-Init** → **IP Config (net0)** → `192.168.1.<n>/24`, gateway
   `192.168.1.254`. Then **Hardware** → **Processors** → Type `host` (not `kvm64`, which hides
   even AVX), and **Memory** → Advanced → _Minimum memory_ = _Memory_.
4. Start it. About 30 s later: `ssh enoal@192.168.1.<n>`.

Command-line equivalent on Astra (`qm` needs `sudo` for user `enoal`):

```sh
sudo qm clone 9000 110 --name comet-energy --full
sudo qm set 110 --ipconfig0 ip=192.168.1.209/24,gw=192.168.1.254 --cpu host --memory 4096 --balloon 4096
sudo qm start 110
```

Clones in use:

| VMID | Name            | IP              | Use                                       |
| ---- | --------------- | --------------- | ----------------------------------------- |
| 110  | `comet-energy`  | `192.168.1.209` | Energy measurement, virtual RAPL (below)  |
| 111  | `comet-bitflip` | `192.168.1.210` | Bit-flip tests on Ollama + `qwen3.5:0.8b` |

## Virtual RAPL

A guest cannot read the CPU's RAPL energy counters: KVM does not pass them through. QEMU can
emulate them: a root helper on Astra, `qemu-vmsr-helper` (shipped by `pve-qemu-kvm`), reads
the real package counter every second and hands each VM a share proportional to the CPU time
of its vCPU threads. The guest sees an ordinary `/sys/class/powercap/intel-rapl:0`.

- Package domain only (no DRAM, no cores), Intel hosts only.
- The guest needs CPU type `host`, or its `intel_rapl_msr` driver does not recognise the CPU.
- A **share**, not a meter. Measured 2026-09-27 on VM 110, 10 s each: idle 0.01 W in the
  guest (Astra 30 W); 4 busy vCPUs 11.7 W in the guest while Astra rose from 30 to 60 W. Fine
  to compare runs with each other; for absolute watts read Astra's own counter alongside, with
  the other lab VMs off.

Setup, on Astra:

```sh
sudo install -m 644 infra/astra/qemu-vmsr-helper.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now qemu-vmsr-helper
sudo qm set 110 --args '-accel kvm,rapl=true,rapl-helper-socket=/run/qemu-vmsr-helper.sock'
sudo qm set 110 --affinity 0-7
```

`args:` has no field in the UI; `--delete args` undoes it. The affinity (UI: Processors →
Advanced → CPU Affinity) keeps the VM on the P-cores so runs do not drift between core types.
The node's **System** page does not list the helper: it shows a fixed list of Proxmox
services; `systemctl status qemu-vmsr-helper` does. In the guest:

```sh
sudo modprobe intel_rapl_msr
sudo cat /sys/class/powercap/intel-rapl:0/energy_uj   # microjoules, grows over time
```

## Backup

Only the template is backed up; clones are rebuilt from it. VM 9000 belongs in the nightly PBS
job (Datacenter → Backup → the 03:00 job → Edit → tick 9000). A template never changes, so
PBS deduplicates every night's snapshot to nothing new.

## Rebuild the template from scratch

On Astra. The image stays in `/var/lib/vz/import/` for the next rebuild.

```sh
# 1. Download the image and check it against Debian's published SHA-512
sudo mkdir -p /var/lib/vz/import && cd /var/lib/vz/import
BASE=https://cloud.debian.org/images/cloud/trixie/latest
sudo curl -fsSLO $BASE/debian-13-genericcloud-amd64.qcow2
curl -fsSL $BASE/SHA512SUMS | grep " debian-13-genericcloud-amd64.qcow2$" | sha512sum -c -

# 2. Create the VM with the image as its disk, plus the cloud-init CD-ROM
sudo qm create 9000 --name debian13-template --ostype l26 \
  --memory 2048 --balloon 0 --cores 2 \
  --net0 virtio,bridge=vmbr0,firewall=1 \
  --scsihw virtio-scsi-single \
  --scsi0 local-lvm:0,import-from=/var/lib/vz/import/debian-13-genericcloud-amd64.qcow2,discard=on,iothread=1,ssd=1 \
  --ide2 local-lvm:cloudinit --boot order=scsi0 \
  --serial0 socket --vga serial0 --agent enabled=1
sudo qm disk resize 9000 scsi0 20G

# 3. cloud-init (the public key file is copied from the laptop first). Set the console
#    password in the UI (Cloud-Init → Password), which keeps it out of the shell history.
sudo qm set 9000 --ciuser enoal --sshkeys /tmp/enoal.pub \
  --ipconfig0 ip=dhcp --nameserver 192.168.1.254
sudo qm start 9000
```

The guest takes a DHCP address; `sudo qm agent` cannot find it yet, so ping-sweep the LAN
from Astra and read `ip neigh` for the VM's MAC (`sudo qm config 9000 | grep net0`). Then, in
the guest:

```sh
cloud-init status --wait
sudo apt-get update && sudo apt-get install -y qemu-guest-agent
sudo apt-get purge -y unattended-upgrades apt-listchanges && sudo apt-get autoremove -y
sudo systemctl disable --now apt-daily.timer apt-daily-upgrade.timer man-db.timer \
  dpkg-db-backup.timer e2scrub_all.timer
# Seal: forget this instance and its machine-id, then power off
sudo apt-get clean && sudo journalctl --rotate --vacuum-time=1s
sudo cloud-init clean --logs --machine-id
sudo poweroff
```

Back on Astra: `sudo qm template 9000`. SSH host keys need no manual removal: cloud-init's
`ssh` module runs once per instance, deletes the old keys and generates new ones
(`ssh_deletekeys` on by default).
