#!/bin/bash
# ============================================================================
# HUB75 Smart Clock - Interactive Configuration Script
# ============================================================================
# Asks you questions about your setup and writes config.yaml automatically.
# Run this after install.sh or any time you want to reconfigure.
#
# Usage:
#   chmod +x scripts/configure.sh
#   ./scripts/configure.sh
# ============================================================================

CONFIG_DIR="/etc/hub75-clock"
CONFIG_FILE="$CONFIG_DIR/config.yaml"
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
USERNAME=$(whoami)
FONTS_DIR="$HOME/hub75-fonts"

echo ""
echo "============================================"
echo "  HUB75 Smart Clock - Configuration Wizard"
echo "============================================"
echo ""
echo "Answer the questions below to generate your config.yaml."
echo "Press Enter to accept the default value shown in [brackets]."
echo ""

# ── Device name ──────────────────────────────────────────────────────────────
read -p "Device name (shown in Home Assistant) [HUB75 Clock]: " HA_NAME
HA_NAME="${HA_NAME:-HUB75 Clock}"

read -p "MQTT client ID (unique, no spaces) [hub75_clock]: " CLIENT_ID
CLIENT_ID="${CLIENT_ID:-hub75_clock}"

read -p "Home Assistant area (optional, leave blank to skip) []: " HA_AREA

THEME_BUILDER_MODE="${THEME_BUILDER_MODE:-off}"
case "$THEME_BUILDER_MODE" in
    off|ha|always) ;;
    *) THEME_BUILDER_MODE="off" ;;
esac
THEME_BUILDER_PORT="${THEME_BUILDER_PORT:-8765}"
THEME_BUILDER_HOST="${THEME_BUILDER_HOST:-0.0.0.0}"
THEME_BUILDER_URL="${THEME_BUILDER_URL:-http://$(hostname).local:${THEME_BUILDER_PORT}/}"
LD2410_TUNER_MODE="${LD2410_TUNER_MODE:-off}"
case "$LD2410_TUNER_MODE" in
    off|ha|always) ;;
    *) LD2410_TUNER_MODE="off" ;;
esac
LD2410_TUNER_PORT="${LD2410_TUNER_PORT:-8766}"
LD2410_TUNER_HOST="${LD2410_TUNER_HOST:-0.0.0.0}"
LD2410_TUNER_URL="${LD2410_TUNER_URL:-http://$(hostname).local:${LD2410_TUNER_PORT}/}"

# ── MQTT ─────────────────────────────────────────────────────────────────────
echo ""
echo "--- MQTT Broker ---"
while true; do
    read -p "MQTT broker IP address: " MQTT_BROKER
    if [[ -n "$MQTT_BROKER" ]]; then
        break
    fi
    echo "  Broker IP is required."
done

read -p "MQTT broker port [1883]: " MQTT_PORT
MQTT_PORT="${MQTT_PORT:-1883}"

read -p "MQTT username (leave blank if none) []: " MQTT_USER
read -p "MQTT password (leave blank if none) []: " MQTT_PASS

# ── Pi model ─────────────────────────────────────────────────────────────────
PI_MODEL=$(cat /proc/cpuinfo | grep "Model" | cut -d: -f2 | xargs 2>/dev/null || echo "")
if echo "$PI_MODEL" | grep -qi "Zero W"; then
    PI_DEFAULT=2
elif echo "$PI_MODEL" | grep -qi "Pi 4"; then
    PI_DEFAULT=1
elif echo "$PI_MODEL" | grep -qi "Pi 3"; then
    PI_DEFAULT=4
else
    PI_DEFAULT=1
fi

echo ""
echo "--- Hardware ---"
echo "Select your Raspberry Pi model:"
echo "  1) Pi 4 (recommended)"
echo "  2) Pi Zero W"
echo "  3) Pi Zero 2 W"
echo "  4) Pi 3B / 3B+"
echo "  5) Other (I'll set gpio_slowdown manually)"
read -p "Choice [$PI_DEFAULT]: " PI_MODEL
PI_MODEL="${PI_MODEL:-$PI_DEFAULT}"

case $PI_MODEL in
    1) GPIO_SLOWDOWN=4 ;;
    2) GPIO_SLOWDOWN=2; UART_PORT="/dev/serial0" ;;
    3) GPIO_SLOWDOWN=2 ;;
    4) GPIO_SLOWDOWN=3 ;;
    5)
        read -p "Enter gpio_slowdown value: " GPIO_SLOWDOWN
        ;;
esac

UART_PORT="${UART_PORT:-/dev/ttyAMA0}"

# ── Hardware mapping ──────────────────────────────────────────────────────────
echo ""
echo "Select panel connection method:"
echo "  1) Direct GPIO wiring (no HAT)"
echo "  2) Adafruit RGB Matrix HAT"
echo "  3) Adafruit RGB Matrix HAT with PWM mod"
read -p "Choice [1]: " HW_MAP_CHOICE
HW_MAP_CHOICE="${HW_MAP_CHOICE:-1}"

case $HW_MAP_CHOICE in
    1) HW_MAP="regular" ;;
    2) HW_MAP="adafruit-hat" ;;
    3) HW_MAP="adafruit-hat-pwm" ;;
    *) HW_MAP="regular" ;;
esac

# ── Sensors ───────────────────────────────────────────────────────────────────
echo ""
echo "--- Sensors ---"
read -p "Do you have a VEML7700 lux sensor? [y/N]: " HAS_VEML
HAS_VEML="${HAS_VEML:-n}"
[[ "$HAS_VEML" =~ ^[Yy]$ ]] && VEML_ENABLED="true" || VEML_ENABLED="false"

read -p "Do you have an LD2410C mmWave sensor? [y/N]: " HAS_LD2410
HAS_LD2410="${HAS_LD2410:-n}"
[[ "$HAS_LD2410" =~ ^[Yy]$ ]] && LD2410_ENABLED="true" || LD2410_ENABLED="false"

if [[ "$LD2410_ENABLED" == "true" ]]; then
    read -p "LD2410C UART port [$UART_PORT]: " LD2410_PORT
    LD2410_PORT="${LD2410_PORT:-$UART_PORT}"
fi

read -p "Do you have a PIR sensor? [y/N]: " HAS_PIR
HAS_PIR="${HAS_PIR:-n}"
[[ "$HAS_PIR" =~ ^[Yy]$ ]] && PIR_ENABLED="true" || PIR_ENABLED="false"

if [[ "$PIR_ENABLED" == "true" ]]; then
    read -p "PIR GPIO pin (BCM number) [16]: " PIR_GPIO
    PIR_GPIO="${PIR_GPIO:-16}"
fi

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo "============================================"
echo "  Configuration Summary"
echo "============================================"
echo "  Device name:      $HA_NAME"
echo "  Client ID:        $CLIENT_ID"
echo "  HA area:          ${HA_AREA:-not set}"
echo "  MQTT broker:      $MQTT_BROKER:$MQTT_PORT"
echo "  Theme builder:    $THEME_BUILDER_MODE"
echo "  Pi model:         gpio_slowdown=$GPIO_SLOWDOWN"
echo "  Panel mapping:    $HW_MAP"
echo "  VEML7700:         $VEML_ENABLED"
echo "  LD2410C:          $LD2410_ENABLED"
echo "  PIR:              $PIR_ENABLED"
echo ""
read -p "Write config.yaml with these settings? [Y/n]: " CONFIRM
CONFIRM="${CONFIRM:-y}"
if [[ ! "$CONFIRM" =~ ^[Yy]$ ]]; then
    echo "Cancelled."
    exit 0
fi

# ── Write config ──────────────────────────────────────────────────────────────
sudo tee "$CONFIG_FILE" > /dev/null << EOF
# ============================================================================
# HUB75 Smart Clock - Configuration
# Generated by configure.sh on $(date)
# ============================================================================

mqtt:
  broker: "$MQTT_BROKER"
  port: $MQTT_PORT
  username: ${MQTT_USER:-null}
  password: ${MQTT_PASS:-null}
  client_id: "$CLIENT_ID"
  topics:
    weather:          clock/weather
    config:           clock/config
    alert:            clock/alert
    lux:              ${CLIENT_ID}/lux
    presence:         ${CLIENT_ID}/presence
    motion:           ${CLIENT_ID}/motion
    pir:              ${CLIENT_ID}/pir
    availability:     ${CLIENT_ID}/status
    fonts_available:  ${CLIENT_ID}/fonts_available
    gates:            ${CLIENT_ID}/gates
    engineering_mode: ${CLIENT_ID}/engineering_mode
    bucket:           ${CLIENT_ID}/bucket
    update:           ${CLIENT_ID}/update/install
    update_check:     ${CLIENT_ID}/update/check
    update_install:   ${CLIENT_ID}/update/install
    update_state:     ${CLIENT_ID}/update/state
    update_latest:    ${CLIENT_ID}/update/latest

ha_discovery:
  enabled: true
  prefix: homeassistant
  ha_discovery_name: "$HA_NAME"
  ha_discovery_area: "$HA_AREA"

theme_builder:
  mode: "$THEME_BUILDER_MODE"
  service_name: hub75-theme-builder
  host: "$THEME_BUILDER_HOST"
  port: $THEME_BUILDER_PORT
  url: "$THEME_BUILDER_URL"

ld2410_tuner:
  mode: "$LD2410_TUNER_MODE"
  service_name: hub75-ld2410-tuner
  host: "$LD2410_TUNER_HOST"
  port: $LD2410_TUNER_PORT
  url: "$LD2410_TUNER_URL"

panel:
  hardware_mapping: $HW_MAP
  gpio_slowdown: $GPIO_SLOWDOWN
  led_rgb_sequence: RBG
  pwm_bits: 11
  pwm_lsb_nanoseconds: 130
  brightness: 60

fonts:
  fonts_dir: /home/$USER/hub75-fonts
  banner_name: 4x6.bdf
  banner_w: 4
  banner_h: 6
  time_name: spleen-12x24.bdf
  time_w: 12
  time_h: 24
  alert_name: 4x6.bdf
  alert_w: 4
  alert_h: 6

colors:
  time_day: "#F0F0F0"
  low_temp_day: "#00CCFF"
  high_temp_day: "#FF8C00"
  condition_day: "#909090"
  alert_text: "#FFFFFF"
  alert_bg: "#CC0000"
  cloud_day: [70, 70, 70]
  sun_day: [220, 160, 30]
  ice_day: [80, 140, 160]
  outline: [0, 0, 0]
  sky_day: "#000820"

animation:
  fps: 90
  rain_count: [5, 8]
  snow_count: [6, 10]
  sleet_count: [6, 10]
  tstorm_rain_count: [5, 8]
  tstorm_lightning_chance: 0.015
  tstorm_lightning_duration: 2

alert:
  scroll_speed: 1
  scroll_gap: 8
  flash: false
  flash_period: 10
  fill_region: true

sensors:
  veml7700_enabled: $VEML_ENABLED
  ld2410_enabled: $LD2410_ENABLED
  pir_enabled: $PIR_ENABLED
  lux_interval: 60.0
  pir_poll_interval: 0.1
  pir_gpio: ${PIR_GPIO:-16}
  pir_invert: false
  ld2410_port: "${LD2410_PORT:-/dev/ttyAMA0}"
  ld2410_baud: 256000

time_format:
  blink_colon: false
  use_24h: false

update:
  enabled: true
  repo_path: "$REPO_DIR"
  branch: ""
  command: "/home/$USER/update-clock.sh"
  check_on_startup: true
  check_time: "03:30"
EOF
sudo chmod 666 "$CONFIG_FILE"

echo ""
echo "Config written to $CONFIG_FILE"
echo ""
echo "Next step: sudo systemctl start hub75-clock"
echo "Check logs: sudo journalctl -u hub75-clock -f --no-pager"
echo ""
read -p "Would you like to test the display and find the correct color order? [Y/n]: " TEST_DISPLAY
TEST_DISPLAY="${TEST_DISPLAY:-y}"
if [[ "$TEST_DISPLAY" =~ ^[Yy]$ ]]; then
    sudo python3 "$(dirname "$0")/test_display.py"
else
    echo "You can run the display test any time with: make rgb"
fi
