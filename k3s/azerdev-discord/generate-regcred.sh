#!/bin/bash
# This script generates a Kubernetes secret to access the GitHub Container Registry.
# It is used to deploy private images from the registry to the cluster.

# --- CONFIGURATION ---
NAMESPACE="redirects"
SECRET_NAME="regcred-azerdev-discord"
OUTPUT_FILE="regcred.yaml"
# ---------------------

# --- PERMISSION CHECK ---
if command -v kubectl >/dev/null 2>&1 && kubectl config view >/dev/null 2>&1; then
    KUBECTL_CMD="kubectl"
elif command -v sudo >/dev/null 2>&1; then
    echo "Notice: Current user cannot access k8s config. Switching to 'sudo kubectl'."
    if sudo -v; then
        KUBECTL_CMD="sudo kubectl"
    else
        echo "ERROR: Sudo authentication failed."
        exit 1
    fi
else
    echo "ERROR: Unable to use 'kubectl' (config access denied) and 'sudo' is not available."
    exit 1
fi
# ------------------------

echo "--------------------------------------------------"
echo " Generating Kubernetes Secret: $SECRET_NAME"
echo " Target Namespace: $NAMESPACE"
echo " Output File: $OUTPUT_FILE"
echo "--------------------------------------------------"

# Safety Check
if [ -f "$OUTPUT_FILE" ]; then
    echo "WARNING: $OUTPUT_FILE already exists."
    read -p "Do you want to overwrite it? (y/N) " confirm
    if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
        echo "Operation cancelled."
        exit 0
    fi
fi

# Credential Collection
echo ""
echo "Please enter your GitHub Container Registry credentials:"
read -p "GitHub Username: " GH_USER
read -s -p "GitHub PAT (Token): " GH_TOKEN
echo ""
read -p "GitHub Email: " GH_EMAIL
echo ""

# YAML Generation
if ! YAML_CONTENT=$($KUBECTL_CMD create secret docker-registry "$SECRET_NAME" \
  --docker-server=ghcr.io \
  --docker-username="$GH_USER" \
  --docker-password="$GH_TOKEN" \
  --docker-email="$GH_EMAIL" \
  -n "$NAMESPACE" \
  --dry-run=client -o yaml); then
    echo ""
    echo "❌ ERROR: Failed to generate YAML. Check your credentials or permissions."
    exit 1
fi

# Save to file
echo "$YAML_CONTENT" > "$OUTPUT_FILE"

echo "--------------------------------------------------"
echo "✅ Success! File '$OUTPUT_FILE' created."
echo "--------------------------------------------------"
