#!/bin/bash
# ============================================================================
# HUB75 Smart Clock - Installation Script
# ============================================================================
# Run this script on a fresh Raspberry Pi OS Lite (Bookworm) installation.
# Make sure you have internet access before running.
#
# Usage:
#   bash install.sh
# ============================================================================

set -e

CLOCK_DIR="/opt/hub75-clock"
CONFIG_DIR="/etc/hub75-clock"
REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
SERVICE_NAME="hub75-clock"
FONTS_DIR="$HOME/rpi-rgb-led-matrix/fonts"
USERNAME=$(whoami)

echo ""
echo "============================================"
echo "  HUB75 Smart Clock - Installer"
echo "============================================"
echo ""

# ── Check not running as root ────────────────────────────────────────────────
if [ "$EUID" -eq 0 ]; then
    echo "[error] Do not run this script as root. Run as your normal user."
    echo "        The script will use sudo where needed."
    exit 1
fi

# ── Check OS ─────────────────────────────────────────────────────────────────
if ! grep -q "bookworm" /etc/os-release 2>/dev/null; then
    echo "[warn] This script is tested on Raspberry Pi OS Bookworm."
    echo "       Other versions may work but are not officially supported."
    echo ""
    read -p "Continue anyway? [y/N] " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo "[1/11] Updating package lists..."
sudo apt update -q

echo "[2/11] Installing system packages..."
sudo apt-get install -y git build-essential python3-dev python3-pip \
    python3-pillow cython3 libgraphicsmagick++-dev libwebp-dev \
    i2c-tools wget python3-yaml

echo "[3/11] Installing Python packages..."
sudo pip3 install paho-mqtt --break-system-packages
sudo pip3 install RPi.GPIO --break-system-packages
sudo pip3 install PyYAML --break-system-packages
sudo pip3 install pyserial --break-system-packages
sudo pip3 install adafruit-circuitpython-veml7700 adafruit-blinka --break-system-packages
sudo pip3 install watchdog --break-system-packages

echo "[4/11] Building rpi-rgb-led-matrix..."
sudo pip3 install --break-system-packages \
    "git+https://github.com/hzeller/rpi-rgb-led-matrix@86df760" \
    || { echo "[error] rpi-rgb-led-matrix install failed"; exit 1; }
python3 -c "from rgbmatrix import RGBMatrix, RGBMatrixOptions, graphics; print('      rgbmatrix OK')" \
    || { echo "[error] rgbmatrix import failed"; exit 1; }
echo "      rpi-rgb-led-matrix installed."

echo "[5/11] Installing Spleen fonts..."
mkdir -p "$HOME/hub75-fonts"
for font in 4x6.bdf 5x7.bdf 5x8.bdf 6x10.bdf 7x13.bdf 9x15.bdf 9x18.bdf 10x20.bdf; do
    if [ ! -f "$HOME/hub75-fonts/$font" ]; then
        wget -q "https://raw.githubusercontent.com/hzeller/rpi-rgb-led-matrix/master/fonts/$font" \
             -O "$HOME/hub75-fonts/$font"
        echo "      + $font"
    fi
done
for font in spleen-12x24.bdf spleen-16x32.bdf; do
    if [ ! -f "$HOME/hub75-fonts/$font" ]; then
        wget -q "https://github.com/fcambus/spleen/raw/master/$font" \
             -O "$HOME/hub75-fonts/$font"
        echo "      + $font"
    else
        echo "      (already have $font)"
    fi
done

echo "[6/11] Configuring hardware interfaces..."

# Enable I2C
sudo raspi-config nonint do_i2c 0
echo "      I2C enabled."

# Enable UART hardware, disable serial console (so LD2410C gets the real UART)
sudo raspi-config nonint do_serial_hw 0
sudo raspi-config nonint do_serial_cons 1
echo "      UART hardware enabled, serial console disabled."

# Disable Bluetooth to free PL011 UART for LD2410C
CONFIG_TXT="/boot/firmware/config.txt"
if ! grep -q "dtoverlay=disable-bt" "$CONFIG_TXT"; then
    echo "dtoverlay=disable-bt" | sudo tee -a "$CONFIG_TXT" > /dev/null
    echo "      Bluetooth disabled (dtoverlay=disable-bt added)."
fi
if ! grep -q "enable_uart=1" "$CONFIG_TXT"; then
    echo "enable_uart=1" | sudo tee -a "$CONFIG_TXT" > /dev/null
    echo "      enable_uart=1 added."
fi

# Blacklist snd_bcm2835 to prevent PWM conflict with the LED matrix library
BLACKLIST_FILE="/etc/modprobe.d/blacklist-rgb-matrix.conf"
if [ ! -f "$BLACKLIST_FILE" ]; then
    echo "blacklist snd_bcm2835" | sudo tee "$BLACKLIST_FILE" > /dev/null
    echo "      snd_bcm2835 blacklisted."
fi

echo "[7/11] Adding $USERNAME to hardware groups..."
sudo usermod -a -G dialout,gpio,i2c "$USERNAME"
echo "      Added to dialout, gpio, i2c."

echo "[8/11] Installing clock files..."
sudo mkdir -p "$CLOCK_DIR" "$CONFIG_DIR" "$CONFIG_DIR/themes"
sudo chmod 755 /home/$USERNAME
sudo chmod 755 "$CONFIG_DIR"
sudo chmod 755 "$CONFIG_DIR/themes"
sudo cp "$REPO_DIR/clock/hub75_clock.py" "$CLOCK_DIR/"
sudo cp "$REPO_DIR/clock/test_sensors.py" "$CLOCK_DIR/"
sudo cp "$REPO_DIR/clock/theme_loader.py" "$CLOCK_DIR/"
sudo cp "$REPO_DIR/scripts/test_display.py"  "$CLOCK_DIR/"
# Copy built-in themes only if the themes dir is empty (preserve user edits)
if [ -z "$(ls -A "$CONFIG_DIR/themes" 2>/dev/null)" ]; then
    sudo cp "$REPO_DIR/themes/"*.json "$CONFIG_DIR/themes/"
    echo "      Built-in themes installed to $CONFIG_DIR/themes/"
else
    echo "      Themes dir already has files — skipping built-in theme copy."
fi
sudo chown -R root:root "$CLOCK_DIR"
echo "      Installed to $CLOCK_DIR"

echo "[9/11] Installing systemd service..."
sudo tee /etc/systemd/system/$SERVICE_NAME.service > /dev/null << EOF
[Unit]
Description=HUB75 Smart Clock
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=$CLOCK_DIR
Environment="CLOCK_CONFIG=$CONFIG_DIR/config.yaml"
ExecStart=/usr/bin/python3 $CLOCK_DIR/hub75_clock.py
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable $SERVICE_NAME
echo "      Service installed and enabled."

echo "[10/11] Installing update script..."
cp "$REPO_DIR/update.sh" "$HOME/update-clock.sh"
chmod +x "$HOME/update-clock.sh"
chmod +x "$REPO_DIR/scripts/configure.sh"

echo "[11/11] Writing initial configuration..."
bash "$REPO_DIR/scripts/configure.sh"
sudo chmod 666 "$CONFIG_DIR/config.yaml"

echo ""
echo "============================================"
echo "  Installation complete!"
echo "============================================"
echo ""
echo "  A reboot is required to apply:"
echo "    - UART / Bluetooth configuration"
echo "    - Group membership (dialout, gpio, i2c)"
echo "    - snd_bcm2835 audio blacklist"
echo ""
read -p "Reboot now? [Y/n] " -n 1 -r
echo ""
if [[ "$REPLY" =~ ^[Nn]$ ]]; then
    echo "Remember to reboot before starting the clock."
    echo "  make test     — test sensors"
    echo "  make start    — start service"
    echo "  make logs     — tail logs"
else
    sudo reboot
fi
