# Liftrank

Strength-training tracker with ranks, served on `http://liftrank.lan` (LAN and VPN).
The image is private: `ghcr.io/enoal-fauchille-bolle/liftrank`.

## First install, on Pulsar

These steps are done once, before the first sync.

1. Create the data folder, owned by uid 1000 (the image's `node` user). The volume uses
   `hostPathType: Directory`, so the pod waits for this folder instead of getting one
   owned by root that it cannot write to:

   ```bash
   sudo install -d -o 1000 -g 1000 /opt/k3s-data/liftrank
   ```

2. Create the pull secret named in `values.yaml` ([secrets.md](../../docs/secrets.md)):

   ```bash
   ../generate-regcred.sh web regcred-liftrank   # prompts for GitHub username + PAT
   kubectl apply -f regcred.yaml
   rm regcred.yaml
   ```

3. On the first start, the server prints a one-time setup code in its log. Open
   `http://liftrank.lan`, then enter that code to create the account:

   ```bash
   kubectl logs -n web deploy/liftrank
   ```
