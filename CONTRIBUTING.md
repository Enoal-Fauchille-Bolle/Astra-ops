# Contributing

Local checks that run before a commit reaches this repository, and the commit
convention they enforce.

## Pre-commit secret scan

The gitignore patterns only catch files by name; a key pasted into a committed
manifest slips through them. The `pre-commit` hook in `.githooks/` scans the staged
changes with [Betterleaks](https://github.com/betterleaks/betterleaks) and refuses the
commit when it finds a secret. Enable the hooks once per clone, and install Betterleaks
(without it, the hook prints a warning and lets the commit through):

```bash
.githooks/setup-hooks.sh        # Linux/macOS (.githooks\setup-hooks.ps1 on Windows)
brew install betterleaks        # macOS, Linux
sudo dnf install betterleaks    # Fedora
```

On Windows, download `betterleaks_<version>_windows_x64.zip` from the
[releases](https://github.com/betterleaks/betterleaks/releases) and put
`betterleaks.exe` on the `PATH`. If the scan flags something that is not a secret,
end that line with a `betterleaks:allow` comment (`# betterleaks:allow` in YAML).

## Pre-commit checks

Portainer and ArgoCD only reject a broken file after the push. Once the hooks are
enabled (see [Pre-commit secret scan](#pre-commit-secret-scan)), the `pre-commit` hook
checks the staged version of what the commit touches:

- **Docker Compose files** in `docker/` must not use `build:`. Portainer redeploys every
  stack every five minutes and recreates a built service each time, which wipes its
  state: publish the image and reference its tag instead. The file is then validated
  with `docker compose config --no-interpolate`, which ignores the `.env` files.
- **Helm charts** in `k3s/` must pass `helm lint` and render with `helm template`.
- **ArgoCD Applications** in `apps/` must point to a path that exists in the commit,
  which catches a chart renamed or removed while its Application still points to it.

The Compose validation needs `docker compose`, the chart checks need `helm`; without
them, the hook prints a warning and lets the commit through. The `build:` rule needs
neither.

## Commit convention

This project uses the **Gitmoji** convention:

```text
<gitmoji> [<scope>] <Subject>
```

- A gitmoji from the [official list](https://gitmoji.dev)
- Scope from the app or area touched, in letters, digits and hyphens starting with a
  letter (e.g., `[SFTPGo]`, `[Homer]`, `[Roots-SMP-Web]`)
- Imperative mood, capitalised, no trailing period, around 60 characters
- A body only when the subject cannot carry the reason, after a blank line

Examples:

- `✨ [Vaultwarden] Migrate to Helm chart`
- `🐛 [n8n] Fix volume mount path`
- `🔧 [ArgoCD] Update ingress hosts`

The `commit-msg` hook in `.githooks/` enforces these rules once the hooks are enabled
(see [Pre-commit secret scan](#pre-commit-secret-scan)). A subject over 72 characters
only draws a warning, and the messages git writes itself (merges, reverts, `fixup!`)
are left alone.
