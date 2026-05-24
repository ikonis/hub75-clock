#!/bin/bash
# HUB75 Smart Clock updater - C++ service variant.
# Copy this to the C++ clock as ~/update-clock.sh, then chmod +x it.

set -euo pipefail

BRANCH="${BRANCH:-feature/cpp-port}"
THEME_VARIANT="${THEME_VARIANT:-living-room}"

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

echo "[update] mode=cpp branch=$BRANCH repo=$REPO_DIR"

git -C "$REPO_DIR" fetch origin
git -C "$REPO_DIR" checkout "$BRANCH"
git -C "$REPO_DIR" pull --ff-only origin "$BRANCH"

echo "[update] updated to $(git -C "$REPO_DIR" rev-parse --short HEAD)"

sudo mkdir -p "$CLOCK_DIR" "$CONFIG_DIR/themes"

echo "[update] syncing themes from themes/$THEME_VARIANT..."
sudo rsync -av --delete --exclude='__pycache__' \
    "$REPO_DIR/themes/$THEME_VARIANT/" \
    "$CONFIG_DIR/themes/"

echo "[update] building C++ clock..."
cmake -S "$REPO_DIR/clock-cpp" -B "$REPO_DIR/clock-cpp/build"
cmake --build "$REPO_DIR/clock-cpp/build"

echo "[update] stopping $SERVICE_NAME..."
sudo systemctl stop "$SERVICE_NAME"

echo "[update] installing C++ clock binary..."
sudo install -m 0755 "$REPO_DIR/clock-cpp/build/hub75_clock" "$CLOCK_DIR/hub75_clock.new"
sudo mv "$CLOCK_DIR/hub75_clock.new" "$CLOCK_DIR/hub75_clock"

echo "[update] restarting $SERVICE_NAME..."
sudo systemctl restart "$SERVICE_NAME"

echo "[update] done."
sudo journalctl -u "$SERVICE_NAME" -n 20 --no-pager
