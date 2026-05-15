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
    # Try to find it from config
    if [ -f "$CONFIG_DIR/config.yaml" ]; then
        REPO_DIR=$(grep "repo_path" "$CONFIG_DIR/config.yaml" | awk '{print $2}' | tr -d '"')
    fi
fi

echo "[update] fetching latest tags..."
git -C "$REPO_DIR" fetch origin --tags --force
LATEST=$(git -C "$REPO_DIR" describe --tags --abbrev=0 2>/dev/null)
if [ -z "$LATEST" ]; then
    echo "[update] no tags found, falling back to git pull"
    git -C "$REPO_DIR" pull
else
    git -C "$REPO_DIR" checkout "$LATEST"
    echo "[update] checked out $LATEST"
fi

echo "[update] copying files to $CLOCK_DIR..."
sudo cp "$REPO_DIR/clock/hub75_clock.py" "$CLOCK_DIR/"
sudo cp "$REPO_DIR/clock/theme_loader.py" "$CLOCK_DIR/"

echo "[update] restarting service..."
sudo systemctl restart $SERVICE_NAME

echo "[update] done."
sudo journalctl -u $SERVICE_NAME -n 10 --no-pager
