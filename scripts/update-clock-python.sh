#!/bin/bash
# HUB75 Smart Clock updater - Python service variant.
# Copy this to the Python clock as ~/update-clock.sh, then chmod +x it.

set -euo pipefail

CLOCK_DIR="${CLOCK_DIR:-/opt/hub75-clock}"
CONFIG_DIR="${CONFIG_DIR:-/etc/hub75-clock}"
SERVICE_NAME="${SERVICE_NAME:-hub75-clock}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="${REPO_DIR:-$SCRIPT_DIR}"

if [ ! -d "$REPO_DIR/.git" ]; then
    if [ -f "$CONFIG_DIR/config.yaml" ]; then
        REPO_DIR="$(grep "repo_path" "$CONFIG_DIR/config.yaml" | awk '{print $2}' | tr -d '"')"
    fi
fi

if [ ! -d "$REPO_DIR/.git" ]; then
    echo "[update] repo not found: $REPO_DIR" >&2
    exit 1
fi

BRANCH="${BRANCH:-$(git -C "$REPO_DIR" rev-parse --abbrev-ref HEAD 2>/dev/null || echo main)}"

echo "[update] mode=python branch=$BRANCH repo=$REPO_DIR"

git -C "$REPO_DIR" fetch origin
git -C "$REPO_DIR" checkout "$BRANCH"
git -C "$REPO_DIR" pull --ff-only origin "$BRANCH"

echo "[update] updated to $(git -C "$REPO_DIR" rev-parse --short HEAD)"

sudo mkdir -p "$CLOCK_DIR" "$CLOCK_DIR/tools" "$CONFIG_DIR/themes" "$CONFIG_DIR/animations"

echo "[update] installing Python clock files..."
sudo cp "$REPO_DIR/clock/hub75_clock.py" "$CLOCK_DIR/"
sudo cp "$REPO_DIR/clock/theme_loader.py" "$CLOCK_DIR/"
sudo cp "$REPO_DIR/tools/theme-builder.html" "$CLOCK_DIR/tools/"
sudo cp "$REPO_DIR/tools/theme-server.py" "$CLOCK_DIR/tools/"

sudo tee /etc/systemd/system/hub75-theme-builder.service > /dev/null << EOF
[Unit]
Description=HUB75 Theme Builder
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=$CLOCK_DIR
ExecStart=/usr/bin/python3 $CLOCK_DIR/tools/theme-server.py --themes-dir $CONFIG_DIR/themes --host 0.0.0.0 --port 8765
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload

echo "[update] syncing themes..."
sudo rsync -av --delete --exclude='__pycache__' \
    "$REPO_DIR/themes/" \
    "$CONFIG_DIR/themes/"

echo "[update] syncing Python animations..."
sudo rsync -av --delete --exclude='__pycache__' \
    "$REPO_DIR/animations/" \
    "$CONFIG_DIR/animations/"

echo "[update] restarting $SERVICE_NAME..."
sudo systemctl restart "$SERVICE_NAME"

echo "[update] done."
sudo journalctl -u "$SERVICE_NAME" -n 20 --no-pager
