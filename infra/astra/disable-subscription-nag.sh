#!/bin/sh
# Silences the "No valid subscription" popup in the Proxmox VE web UI. It comes from
# Proxmox.Utils.checked_command() in proxmoxlib.js, which shows the dialog whenever the
# subscription API call does not return an active key — cosmetic only, no feature is gated.
# Idempotent: sed only matches the original, un-patched line, so re-running this after the
# patch is already applied does nothing.
#
# Every proxmox-widget-toolkit update ships a fresh, unpatched proxmoxlib.js, so the patch
# alone does not survive an `apt upgrade`. 89no-subscription-nag (installed as
# /etc/apt/apt.conf.d/89no-subscription-nag) re-runs this script after every dpkg operation.
#
# Installed as /usr/local/sbin/disable-subscription-nag both on Astra and inside LXC 103
# (PBS) — both share the same proxmox-widget-toolkit package and the same proxmoxlib.js.

set -e

JS_FILE="/usr/share/javascript/proxmox-widget-toolkit/proxmoxlib.js"

[ -f "$JS_FILE" ] || exit 0

sed -i "s/res\.data\.status\.toLowerCase() !== 'active'/false/g" "$JS_FILE"
