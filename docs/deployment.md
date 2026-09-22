# Deployment

## GitOps workflow

### ArgoCD

ArgoCD watches this repository and automatically syncs changes to the K3s cluster.

This repository uses the **App-of-Apps** pattern: a single root application defined in
`infra/argocd/root-app.yaml` points to `apps/` and manages all other applications.

- **Sync policy**: automated with `prune: true` and `selfHeal: true`
- **Namespace creation**: via `CreateNamespace=true`
- **Disabled apps**: placed in `apps/.disabled/` — present in the repo but not synced

### Renovate

[Renovate](https://renovatebot.com) monitors this repository for dependency updates:

- Docker image versions in `docker-compose.yml` files
- Helm chart `values.yaml` image tags
- Kubernetes manifest image references
- Private GHCR images (`ghcr.io/enoal-fauchille-bolle/*`) via `GHCR_PAT` secret

### Helm migration

Services remaining to migrate from raw manifests to Helm: `immich`, `n8n`, `scanopy`,
`zerobyte`. Migrated services use this structure:

```text
k3s/<service>/
├── Chart.yaml
├── values.yaml
├── generate-regcred.sh    # (if GHCR access needed)
└── templates/
    ├── _helpers.tpl
    ├── deployment.yaml
    ├── service.yaml
    ├── ingress.yaml
    └── ...
```

### Vertical Pod Autoscaler (VPA)

[VPA](https://github.com/kubernetes/autoscaler/tree/master/vertical-pod-autoscaler) is
deployed via the `cowboysysop/vertical-pod-autoscaler` Helm chart and runs in **Off mode**
(recommendations only — pods are never automatically evicted or modified).

The recommender watches all application deployments and builds CPU/memory usage histograms
over time using `metrics-server`. After 24-48 h of observation, it produces per-container
recommendations (`Lower Bound`, `Target`, `Upper Bound`) that inform manual updates to
`values.yaml` resource fields.

```bash
# Read recommendations for a service
kubectl describe vpa <service> -n <namespace>
# or browse all at once in k9s
:vpa
```

VPA objects live in `infra/vpa/` (one file per deployment) and are deployed by the
`vpa-objects` ArgoCD Application. The operator itself (`vpa-system`) is managed separately
as a Helm chart Application pointing to the cowboysysop registry.

### Hooks and commit convention

The local git hooks (secret scan, Compose/Helm/ArgoCD checks) and the commit convention
are described in [CONTRIBUTING.md](../CONTRIBUTING.md).

## Prerequisites

### Hardware

- A server or mini PC (e.g., NiPoGi CK10)
- 2 NVMe drives recommended (system + cold storage)

### Software — server

- [Proxmox VE](https://www.proxmox.com/) — hypervisor
- Linux VM with [K3s](https://k3s.io/), [Docker](https://docs.docker.com/engine/install/), [Helm](https://helm.sh/docs/intro/install/)
- LXC container with [AdGuard Home](https://adguard.com/adguard-home.html)

### Software — workstation

- [kubectl](https://kubernetes.io/docs/tasks/tools/) — Kubernetes CLI
- [Helm](https://helm.sh/docs/intro/install/) — chart management
- [k9s](https://k9scli.io/) — terminal-based K8s UI (recommended)
- [lazydocker](https://github.com/jesseduffield/lazydocker) — Docker terminal UI (optional)

### Networking

- A domain name with DNS records pointing to your public IP
- Port forwarding on your router (80, 443 → server IP)
- Static IPs for server, VM, and LXC

## Getting started

### 1. Clone the repository

```bash
git clone https://github.com/Enoal-Fauchille-Bolle/Astra-ops.git /opt/ops
cd /opt/ops
```

### 2. Start Docker infrastructure (Layer A)

Portainer manages all Docker Compose stacks. Start it first, then deploy the others
from its web UI at `http://<server-ip>:9444`:

```bash
cd docker/portainer && docker compose up -d
# Then deploy via Portainer: npm, crowdsec, dozzle
# (crafty is deployed manually for now)
```

Or deploy manually:

```bash
cd docker/npm && docker compose up -d
cd ../crowdsec && docker compose up -d
cd ../dozzle && docker compose up -d
```

### 3. Install ArgoCD

```bash
kubectl create namespace argocd
kubectl apply -n argocd \
  -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
kubectl apply -f infra/argocd/argocd-ingress.yaml
```

### 4. Bootstrap all K3s services

Apply the root App-of-Apps once — ArgoCD then deploys and manages everything in `apps/`:

```bash
kubectl apply -f infra/argocd/root-app.yaml
```

### 5. Bootstrap secrets

Application secrets are managed by ESO + Infisical. Two files must be applied manually
(copy from the `.example` templates in `infra/eso/`, fill in values, then apply):

```bash
# Infisical bootstrap (ENCRYPTION_KEY, AUTH_SECRET, DB credentials)
kubectl apply -f infra/eso/infisical-bootstrap.yaml

# Infisical service token (generated in the Infisical UI after first login)
kubectl apply -f infra/eso/infisical-token.yaml
```

All other application secrets are created automatically by ESO once the cluster is synced.

For services using GHCR private images, apply the registry credentials:

```bash
cd k3s/<service>
./generate-regcred.sh   # prompts for GitHub username + PAT
kubectl apply -f regcred.yaml
```

### 6. Configure Nginx Proxy Manager

Access NPM at `http://<server-ip>:81` and configure:

- Let's Encrypt SSL certificates
- Proxy hosts for each public service pointing to `192.168.1.201` (Traefik)

### 7. Install host-level files on Astra

`infra/astra/` is not deployed automatically by ArgoCD or Portainer — it must be copied to the
Proxmox host by hand after any fresh install of Astra:

```bash
scp infra/astra/disable-subscription-nag.sh astra:/tmp/
scp infra/astra/89no-subscription-nag astra:/tmp/
ssh astra "sudo install -o root -g root -m 755 /tmp/disable-subscription-nag.sh /usr/local/sbin/disable-subscription-nag && \
  sudo install -o root -g root -m 644 /tmp/89no-subscription-nag /etc/apt/apt.conf.d/89no-subscription-nag && \
  rm /tmp/disable-subscription-nag.sh /tmp/89no-subscription-nag && \
  sudo /usr/local/sbin/disable-subscription-nag"
```

> [!NOTE]
> `proxmox-config-backup.{sh,service,timer}` (same directory) needs both Astra **and** Pulsar
> set up — a receiving account, a dedicated SSH key pair, the script and its systemd timer.
> See `docs/backup/proxmox-config-copy.md`, *Reinstalling this mechanism from scratch*.

## Remote access

### kubectl from your workstation

```bash
scp <user>@192.168.1.201:/etc/rancher/k3s/k3s.yaml ~/.kube/config
# Replace 127.0.0.1 with the server IP:
sed -i 's/127.0.0.1/192.168.1.201/' ~/.kube/config
# Rename context for clarity:
kubectl config rename-context default pulsar
```

### Recommended tools

- **k9s** — powerful terminal UI for Kubernetes (`k9s -c pod`)
- **lazydocker** — terminal UI for Docker containers and images
