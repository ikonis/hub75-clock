#!/bin/bash
# ============================================================================
# HUB75 Smart Clock - Update Script
# ============================================================================
# Pulls latest code from GitHub and restarts the clock service.
# Run from anywhere: ~/update-clock.sh
# ============================================================================

set -e

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
CLOCK_DIR="/opt/hub75-clock"
CONFIG_DIR="/etc/hub75-clock"
SERVICE_NAME="hub75-clock"

# Find repo — script lives in home dir, repo may be elsewhere
if [ ! -f "$REPO_DIR/clock/hub75_clock.py" ]; then
    if [ -f "$CONFIG_DIR/config.yaml" ]; then
        REPO_DIR=$(grep "repo_path" "$CONFIG_DIR/config.yaml" | awk '{print $2}' | tr -d '"')
    fi
fi

echo "[update] pulling latest..."
git -C "$REPO_DIR" pull origin $(git -C "$REPO_DIR" rev-parse --abbrev-ref HEAD)
echo "[update] updated to $(git -C "$REPO_DIR" rev-parse --short HEAD)"

echo "[update] copying files..."
sudo cp "$REPO_DIR/clock/hub75_clock.py" "$CLOCK_DIR/"
sudo cp "$REPO_DIR/clock/theme_loader.py" "$CLOCK_DIR/"
sudo mkdir -p "$CONFIG_DIR/themes" "$CONFIG_DIR/animations"
sudo cp "$REPO_DIR/themes/"*.json "$CONFIG_DIR/themes/"
sudo cp "$REPO_DIR/animations/"*.py "$CONFIG_DIR/animations/"
sudo chmod 644 "$CONFIG_DIR/animations/"*.py

echo "[update] restarting..."
sudo systemctl restart "$SERVICE_NAME"

echo "[update] done."
sudo journalctl -u "$SERVICE_NAME" -n 10 --no-pager
