# HUB75 Smart Clock


I built this as a bedside clock and it got out of hand. It's a 64×32 HUB75 LED matrix running on a Raspberry Pi 4, showing the time and animated weather conditions pulled from Home Assistant. The LD2410C mmWave sensor handles presence detection, a VEML7700 reads ambient light, and a PIR catches motion. Everything talks to HA over MQTT and shows up as a native device with auto-discovered entities.
Configuration is all YAML. Fonts, colors, brightness curves, which sensors are connected.

Parts of this codebase were written with AI assistance. I have tested it on my own hardware but please audit the code before running it on yours.

---

## Hardware

| Component | Notes |
|---|---|
| [Raspberry Pi 4 Model B](https://amzn.to/4nli8DE) | Debian Bookworm (Raspberry Pi OS Lite), primary supported hardware |
| [64×32 HUB75 LED panel](https://amzn.to/4tELsqA) | P2.5 used in this build. P2/P3/P4/P5 all work electrically; smaller pitch looks better up close |
| [VEML7700](https://amzn.to/3R5NwKr) | Ambient lux, I²C |
| [HLK-LD2410C](https://amzn.to/3Rz9upi) | mmWave presence + distance, UART |
| [PIR sensor (Inland PIR Motion Sensor Module)](https://www.microcenter.com/product/618776/inland-pir-motion-sensor-module) | Motion, GPIO, no adjustment pots, 3-pin VCC/GND/OUT |
| [5V / 5A power supply](https://amzn.to/4drKXKq) | Barrel jack, powers panel + Pi + sensors |

---

## Case / Enclosure

STL and STEP files are in the `case/` folder, designed for the hardware listed in the BOM above. A Bambu Studio `.3mf` file with the print settings used on a P1S is included.

### Variants

**Front cover**
- With cutouts for all three sensors (VEML7700 lux window, PIR dome, LD2410C lens)
- Without VEML7700 cutout, for builds that omit the lux sensor

**Back cover**
- Barrel jack only
- Pi 4 variant with and full port rear cutouts.

**Bottom cover**
- Pi 4
- Pi Zero W

### Hardware required

| Qty | Part | Notes |
|-----|------|-------|
| 10 | [M3×5×4 Heatset Inserts](https://amzn.to/3RABtF4) | Panel and cover mounting |
| 6 | [M3×6 Countersunk Screws](https://amzn.to/4wqe6Or) | Front cover to frame |
| 6 | [M3×6 Hex Screws](https://amzn.to/3R4CC7Q) | Back cover to frame |
| 4 | [M2.5×3.5×4 Heatset Inserts](https://amzn.to/3RABtF4) | Pi mounting |
| 4 | [M2.5×5 Hex Screws](https://amzn.to/4u9nSTS) | Pi to standoffs |

---

## Wiring

### Power

```
5V/5A Supply (+) -----> Panel 5V
5V/5A Supply (+) -----> Pi VBUS (physical pin 2)
5V/5A Supply (+) -----> LD2410C VCC
5V/5A Supply (+) -----> PIR VCC
5V/5A Supply (-) -----> Shared GND (all devices)
```

Internal to the enclosure: barrel jack in, split to panel and Pi. One cable in, everything powered.

### VEML7700, I2C, 3.3V

```
VEML7700    Pi 4                Physical pin
VIN    -->  3.3V                1
GND    -->  GND                 9
SDA    -->  GPIO2 (SDA1)        3
SCL    -->  GPIO3 (SCL1)        5
```

Verify after boot: `sudo i2cdetect -y 1`. Expect `0x10`.

### HLK-LD2410C, UART, 5V power

```
LD2410C     Pi 4                Physical pin
VCC    -->  5V                  2
GND    -->  GND                 20
TX     -->  GPIO15 (RXD0)       10   ← CROSSED: sensor TX to Pi RX
RX     -->  GPIO14 (TXD0)       8    ← CROSSED: sensor RX to Pi TX
OUT         (leave unconnected)
```

After install + reboot: `ls -l /dev/ttyAMA0` must exist and `/dev/serial0` must point to it, not `ttyS0`. If it shows `ttyS0` the Bluetooth disable didn't take. Check `/boot/firmware/config.txt` for `dtoverlay=disable-bt`.

### PIR, GPIO

| PIR Pin | Pi BCM GPIO | Pi Physical Pin |
|---------|-------------|-----------------|
| VCC | 3.3V or 5V | Pin 1 or Pin 2 |
| GND | GND | Pin 39 |
| OUT | GPIO16 | Pin 36 |

> GPIO16 is free in the regular hardware mapping. OE uses GPIO18, not GPIO16.

> The Inland PIR sensor works on 3.3V, freeing up the 5V pins for panel power. If powering the Pi from a barrel jack via GPIO rather than USB-C, connect PIR VCC to pin 1 (3.3V) instead.

Change GPIO pin in `config.yaml` under `sensors.pir_gpio` (BCM number, not physical pin). Allow 30–60 seconds warmup after power-on.

### HUB75 Panel

Connect directly via GPIO, no HAT required. Panel power comes from the external supply directly, not through the Pi's 5V rail.

| HUB75 Signal | HUB75 IDC Pin | Pi BCM GPIO | Pi Physical Pin |
|--------------|---------------|-------------|-----------------|
| R1 | 1 | GPIO11 | 23 |
| G1 | 2 | GPIO27 | 13 |
| B1 | 3 | GPIO7 | 26 |
| GND | 4 | GND | 6 |
| R2 | 5 | GPIO8 | 24 |
| G2 | 6 | GPIO9 | 21 |
| B2 | 7 | GPIO10 | 19 |
| GND | 8 | GND | 14 |
| A | 9 | GPIO22 | 15 |
| B | 10 | GPIO23 | 16 |
| C | 11 | GPIO24 | 18 |
| D | 12 | GPIO25 | 22 |
| CLK | 13 | GPIO17 | 11 |
| STB/LAT | 14 | GPIO4 | 7 |
| OE | 15 | GPIO18 | 12 |
| GND | 16 | GND | 25 |

> **Note:** This is the `regular` hardware mapping from rpi-rgb-led-matrix. Your HUB75 panel connector pin numbering may differ. Verify against your panel's datasheet. Pin 1 is usually marked on the connector.

> Pin 1 on the IDC connector is usually marked with a triangle or dot on the PCB silkscreen, or a red stripe on the ribbon cable.

**Note on 3.3V logic:** The Pi's GPIO is 3.3V. HUB75 panels expect 5V logic. Most panels tolerate 3.3V and work fine. If you get garbled output that `gpio_slowdown` tuning doesn't fix, a 74HCT245 buffer between Pi and panel will resolve it.

Use `hardware_mapping: regular` for direct GPIO wiring. Only use `adafruit-hat` if you have an actual Adafruit RGB Matrix Bonnet.

---

## Installation

> **Note:** Git may not be installed on a fresh Raspberry Pi OS image. Install it first:
> ```bash
> sudo apt install -y git
> ```

### 1. Clone the repo on the Pi

```bash
cd ~
git clone https://github.com/ikonis/hub75-clock.git
cd hub75-clock
```

### 2. Install

```bash
bash install.sh
```

`install.sh` handles everything in one step, then launches the interactive configuration wizard (`scripts/configure.sh`) and prompts to reboot. See [Scripts](#scripts) for the full list of what it does.

### 3. Reboot

Prompted automatically by `install.sh`. Required for UART, Bluetooth, and group changes to take effect.

```bash
sudo reboot
```

### 4. Test sensors

```bash
make test
```

Runs each enabled sensor in sequence with a timed window and prints a PASS/FAIL/SKIP summary. Takes ~25 seconds total. Wave your hand in front of the PIR during the last 15 seconds.

```bash
sudo i2cdetect -y 1        # VEML7700 at 0x10
ls -l /dev/serial0         # must point to ttyAMA0
```

### 5. Test the clock

Python runtime:

```bash
sudo python3 /opt/hub75-clock/hub75_clock.py
```

C++ runtime:

```bash
sudo /opt/hub75-clock/hub75_clock /etc/hub75-clock/config.yaml
```

Root required for matrix DMA/PWM. Panel should light up with time. Banner shows `--/-- CLEAR` until HA pushes weather.

### 6. Start the service

The service is installed and enabled automatically by `install.sh`.

```bash
make start
make status
```

---

## Scripts

### install.sh

Run once on a fresh Pi. Does everything in sequence:

1. Updates apt package lists
2. Installs system packages for both runtimes (git, build-essential, Python headers/tools, CMake, Mosquitto, yaml-cpp, gpiod, and others)
3. Installs Python packages (paho-mqtt, PyYAML, pyserial, RPi.GPIO, adafruit-circuitpython-veml7700, adafruit-blinka, watchdog)
4. Lets you choose the clock runtime: Python is the suggested default for multicore Pis; C++ is suggested for Pi Zero / lowest CPU overhead
5. Lets you choose the theme builder mode: off, Home Assistant controlled, or always running
6. Builds and installs `rpi-rgb-led-matrix` with Python bindings. Pi 4: installs a pinned commit via pip. Pi Zero W: clones, checks out commit `076c54b`, and builds with `make build-python` / `make install-python`. The C++ runtime also builds the matrix C++ library. See `docs/pi-zero-w.md`.
7. Downloads fonts (rpi-rgb-led-matrix bundled BDF fonts + Spleen 12x24/16x32) to `~/hub75-fonts`
8. Enables I2C and UART hardware; disables serial console; disables Bluetooth; blacklists `snd_bcm2835`
9. Adds user to `dialout`, `gpio`, `i2c` groups
10. Installs the selected runtime to `/opt/hub75-clock/`; copies built-in themes to `/etc/hub75-clock/themes/` on first install only; update scripts preserve locally edited themes before syncing; copies Python animation `.py` files when using the Python runtime; installs the theme builder helper files
11. Installs and enables the `hub75-clock` systemd service for the selected runtime
12. Installs the `hub75-theme-builder` systemd service, enabled only when theme builder mode is `always`
13. Installs the matching update script to `~/update-clock.sh`
14. Launches `scripts/configure.sh` to write your `config.yaml`
15. Prompts to reboot

```bash
bash install.sh
```

### update scripts

Pulls the latest code from GitHub, copies updated files to `/opt/hub75-clock/`, and restarts the service. `install.sh` installs either `scripts/update-clock-python.sh` or `scripts/update-clock-cpp.sh` as `~/update-clock.sh`, matching the runtime you selected.

```bash
make update
# or: ~/update-clock.sh
```

When `update.enabled` is true, the clock can also check the currently checked-out branch at startup, once daily at `update.check_time`, or from the Home Assistant **Check Update** button. It publishes retained update status to MQTT and only runs `update.command` when the Home Assistant **Install Update** button is pressed.

### scripts/configure.sh

Interactive configuration wizard. Prompts for your MQTT broker, device name, sensor hardware, GPIO pin, and `gpio_slowdown`, then writes `/etc/hub75-clock/config.yaml` automatically. Launched by `install.sh` on first install; can be re-run any time.

```bash
make config
# or: bash scripts/configure.sh
```

### clock/test_sensors.py

Tests each connected sensor independently without starting the full clock. Reads enabled flags from `config.yaml`, skips disabled sensors, and prints a PASS/FAIL/SKIP summary. Takes ~25 seconds total.

```bash
make test
```

---

## Daily Workflow

```bash
make update     # git pull + copy files + restart service
make logs       # tail live service logs
make restart    # restart after config edit
make status     # check service status
make stop       # stop the service
make start      # start the service
make test       # run test_sensors.py
make config     # open config wizard (reconfigure)
make rgb        # run test_display.py (panel pixel test)
make theme-builder # edit repo themes in the browser
make sprite-builder # edit sprite JSON files in the browser
make ld2410-tuner # tune LD2410 gate thresholds from a phone-friendly page
```

After editing `/etc/hub75-clock/config.yaml` directly:
```bash
make restart
```

---

## Theme Builder

The offline builder is `tools/theme-builder.html`. To edit theme JSON files directly through the browser, run the tiny local helper server:

```bash
make theme-builder
# open http://127.0.0.1:8765/
```

By default it reads and saves themes in the repo `themes/` directory. To edit the installed themes on a clock:

```bash
sudo python3 tools/theme-server.py --themes-dir /etc/hub75-clock/themes --host 0.0.0.0
```

Then browse to `http://<clock-ip>:8765/`. Only run it on a trusted network.

During install, the theme builder can be disabled, left always running, or controlled from Home Assistant. In HA-controlled mode, the clock publishes a Theme Builder switch and a Theme Builder URL sensor through MQTT discovery. The switch starts/stops the `hub75-theme-builder` service; the URL sensor gives you the browser address.

---

## LD2410 Tuner

The LD2410 tuner is a tiny mobile-friendly web UI for live gate tuning:

```bash
make ld2410-tuner
# open http://<clock-ip>:8766/
```

It uses MQTT instead of opening the UART directly, so the clock can keep running while the tuner turns engineering mode on, graphs live move/still gate energy, and publishes gate threshold changes through the same commands the clock already understands. Set `ld2410_tuner.mode` to `ha` to expose an HA switch and URL sensor, or `always` to keep the tuner service running.

The LD2410 stores normal gate sensitivity after successful configuration commands. The next tuning layer can expose max-distance, timeout, and distance-resolution controls; distance resolution requires a module restart before it truly takes effect.

---

## Sprite Builder

The sprite builder edits small JSON sprites used by the generic `sprite` cameo in both runtimes:

```bash
make sprite-builder
# open http://127.0.0.1:8765/sprite-builder.html
```

Sprites live in `sprites/` in the repo and `/etc/hub75-clock/sprites/` on clocks. The same page also includes early animation scaffolding for frame-based sprite animation JSON in `sprite-animations/` and `/etc/hub75-clock/sprite-animations/`.

Use sprites from a theme cameo like:

```json
{ "name": "sprite", "sprite": "rocket", "chance_per_minute": 4 }
```

Sprite pixels use `null` for transparent cells, `#RRGGBB` for solid color, or `#RRGGBBAA` for alpha-blended pixels. Sprite JSON can also carry early `movement` metadata for future cameo behavior work. Animation JSON editing is scaffolded for design work; runtime playback comes later.

---

## Updating

Pull the latest code from GitHub and restart the service:

```bash
make update
# or: ~/update-clock.sh
```

This pulls from the `main` branch, copies the updated files to `/opt/hub75-clock/`, and restarts the service.

---

## Font Selection

Two fonts configured separately: banner (small text row) and time (large digits).

### Banner font

`4x6.bdf` (default): "TSTORM" plus two temps fits in 64px.

### Time font options

| Font | W×H | "12:34" px wide | Source | Notes |
|---|---|---|---|---|
| `9x15B.bdf` | 9×15 | 45px | rpi-rgb-led-matrix | Smaller bold |
| `9x18B.bdf` | 9×18 | 45px | rpi-rgb-led-matrix | Taller bold |
| `10x20.bdf` | 10×20 | 50px | rpi-rgb-led-matrix | Good default |
| `spleen-12x24.bdf` | 12×24 | 60px | install.sh | Chunky terminal. Recommended upgrade. |
| `spleen-16x32.bdf` | 16×32 | 80px | install.sh | Extreme chonk. Single-digit hours only ("6:15"=48px ✓, "12:34"=80px ✗) |

To change the time font, edit `/etc/hub75-clock/config.yaml`:

```yaml
fonts:
  time_name: spleen-12x24.bdf
  time_w: 12
  time_h: 24
```

**Always update `time_w` and `time_h`. They are not auto-detected.**

Browse available fonts:
```bash
ls ~/rpi-rgb-led-matrix/fonts/
```

Test a font on the real panel:
```bash
cd ~/rpi-rgb-led-matrix/examples-api-use
sudo ./text-example -f ~/rpi-rgb-led-matrix/fonts/spleen-12x24.bdf
```

---

## Home Assistant Setup

### Automations

Copy the files from `automations/` into an HA package directory and add the script separately:

```
config/
├── packages/
│   └── hub75_clock/
│       ├── 01_set_theme.yaml          automation: brightness + calls theme script
│       ├── 01b_select_theme_script.yaml  SCRIPT (see note below)
│       ├── 02_push_weather.yaml       automation: weather push every 15 min
│       ├── 03_alerts.yaml             automation: NWS weather alert banner
│       └── 04_online_offline.yaml     automation: offline notification
└── scripts/
    └── clocks_select_theme.yaml       copy of 01b content under script: key
```

In `configuration.yaml`:
```yaml
homeassistant:
  packages: !include_dir_named packages

script: !include_dir_merge_named scripts
```

**Important — the script file:** `01b_select_theme_script.yaml` defines `script.clocks_select_theme`, which `01_set_theme.yaml` calls. Scripts and automations use different HA keys and cannot live in the same file. Copy the contents of `01b_select_theme_script.yaml` into your `config/scripts/` directory (or inline it under a `script:` key in a package). See the comment header in that file for both import options.

Restart HA fully after adding any new package or script file.

### Required HA helpers

Create these helpers before enabling the automations (Settings → Devices & Services → Helpers):

| Helper | Type | Notes |
|---|---|---|
| `input_select.house_bucket` | Select | Options: Day, Sunrise, Sunset, after_sunset, Late Evening, Night, Away |
| `input_text.clock_condition` | Text | Max length 20. Written by `02_push_weather`, read by the theme script. |

### Required HA entities

| Entity | Source |
|---|---|
| A `weather.*` entity | NWS, OpenWeatherMap, or similar integration |
| `sensor.outdoor_temperature` | Your outdoor sensor |

### Auto-registered entities (MQTT Discovery)

The clock registers its device and all entities automatically via MQTT Discovery on connect. The device name and entity prefix come from `mqtt.client_id` and `ha_discovery.ha_discovery_name` in `config.yaml`.

With defaults (`client_id: hub75_clock`, `ha_discovery_name: "HUB75 Clock"`):

| Entity | Description |
|---|---|
| `sensor.hub75_clock_illuminance` | VEML7700 lux |
| `sensor.hub75_clock_move_energy` | LD2410C move energy |
| `sensor.hub75_clock_still_energy` | LD2410C still energy |
| `sensor.hub75_clock_move_distance` | LD2410C move distance (cm) |
| `sensor.hub75_clock_still_distance` | LD2410C still distance (cm) |
| `binary_sensor.hub75_clock_pir` | PIR motion (shown as "Motion" in HA) |
| `binary_sensor.hub75_clock_presence` | LD2410C occupancy |
| `number.hub75_clock_brightness` | Brightness control (1–100) |

Sensors for disabled hardware (e.g. `veml7700_enabled: false`) are not registered.

### MQTT Topics

**HA → Clock:**

| Topic | Payload |
|---|---|
| `clock/weather` | `{"low_temp": 68, "high_temp": 88, "condition": "TSTORM", "outdoor_temp": 64}` |
| `clock/config` | `{"brightness": 40}` — brightness; additional config keys documented in `config.example.yaml` |
| `{client_id}/theme/set` | Theme name string, e.g. `"Rainy Night"` — per-clock, uses `mqtt.client_id` from config |
| `clock/alert` | `{"message": "Tornado Warning - County - until 4:45 PM", "expires": "2026-04-25T16:45:00-05:00"}` |
| `clock/alert` | `{"clear": true}` to dismiss |

**Clock → HA:**

| Topic | Payload |
|---|---|
| `hub75_clock/lux` | `{"lux": 125.5}` |
| `hub75_clock/pir` | `{"motion": true}` |
| `hub75_clock/presence` | `{"presence": true, "target_state": 3, "move_distance": 85, "still_distance": 120}` |
| `hub75_clock/motion` | `{"move_energy": 45, "still_energy": 30}` |
| `hub75_clock/status` | `online` or `offline` |

### Weather conditions

The clock receives a condition string from the weather automation. The script `clocks_select_theme` maps condition + time-of-day bucket to the best precipitation theme:

| Condition | Day-side theme | Night-side theme |
|---|---|---|
| `CLEAR` / `SUNNY` / `PARTLYCLOUDY` | Day / Sunrise / Sunset | Night / Late Evening |
| `CLOUDY` / `FOG` / `SMOKE` / `DUST` / `WINDY` | Day (overcast sky) | Night (no stars) |
| `RAIN` / `FLOOD` | Rainy Day | Rainy Night |
| `TSTORM` / `HURRICANE` / `TROPICAL_STORM` | Stormy Day | Stormy Night |
| `SNOW` / `BLIZZARD` | Snowy Day | Snowy Night |
| `SLEET` / `ICE` / `FREEZING_DRIZZLE` / `FREEZING_RAIN` | Sleety Day | Rainy Night |

All precipitation (rain drops, snow flakes, sleet, lightning) is rendered by the `clouds.py` animation via the `precipitation` field in the theme JSON. See `docs/themes.md` for the full field reference.

Condition is the **most severe expected in the next 12 hours**, not just the current moment.

The condition and temperature windows are configurable at the top of `automations/02_push_weather.yaml`. Change `condition_hours` (default 12) and `temp_hours` (default 24) to suit your preference.

### Brightness

Brightness is controlled by your HA automation; see `automations/01_set_theme.yaml` for the included example.

---

## Tornado Warning Alert

When a Tornado Warning is issued, the banner strip shows a red scrolling overlay. Time and animations stay below. Auto-clears on expiration.

### NWS Alerts setup (HACS)

1. HACS → Integrations → ⋮ → Custom Repositories
2. Add: `https://github.com/finity69x2/nws_alerts` → Integration
3. Install "NWS Alerts" → Restart HA
4. Settings → Devices & Services → Add Integration → NWS Alerts
5. Configure with your GPS coordinates or county code

Only Tornado Warnings trigger the clock alert by default.

To manually test the alert:
```bash
mosquitto_pub -h <broker> -u <user> -P <pass> \
  -t clock/alert \
  -m '{"message":"TEST - County - until 11:59 PM"}'
```

Clear it:
```bash
mosquitto_pub -h <broker> -u <user> -P <pass> \
  -t clock/alert -r \
  -m '{"clear": true}'
```

---

## Troubleshooting

**Blank panel:** Check 5V supply. Check ribbon cable orientation (input side of panel only).

**Garbled colors:** Adjust `panel.gpio_slowdown` (Pi 4: start at 4, try 3–5). If still wrong, add a 74HCT245 buffer.

**Flickering:** Increase `gpio_slowdown`. Confirm `lsmod | grep snd_bcm2835` returns nothing. Service must run as root.

**Time wrong size/position:** `fonts.time_w` and `fonts.time_h` must match the font file exactly. Not auto-detected.

**`/dev/serial0` is `ttyS0`:** Bluetooth still owns PL011. Check for `dtoverlay=disable-bt` in `/boot/firmware/config.txt`. Add it and reboot.

**VEML7700 not found:** `sudo i2cdetect -y 1` should show `10`. Check wiring. Set `sensors.veml7700_enabled: false` to disable.

**Weather stuck at `--/-- CLEAR`:** Manually trigger the weather push automation in HA Developer Tools → Automations. Check the automation trace.

**Alert not clearing:** Publish `{"clear": true}` to `clock/alert` from HA Developer Tools → MQTT.

**`mqtt.broker is not set` error on startup:** Add your broker IP to `/etc/hub75-clock/config.yaml` under `mqtt.broker`, or run `make config` to reconfigure.

---

## File Layout

```
hub75-clock/
├── .gitignore
├── Makefile                    make update / logs / restart / test / config / rgb
├── README.md
├── config.example.yaml         Reference config; configure.sh writes the real config
├── install.sh                  One-shot installer, run once on a fresh Pi
├── update.sh                   Installed to ~/update-clock.sh; called by make update
├── scripts/
│   ├── configure.sh            Interactive config wizard; run by install.sh
│   └── test_display.py         Panel pixel test (make rgb)
├── clock/
│   ├── hub75_clock.py          Main application
│   ├── theme_loader.py         Theme dataclass, JSON loader, file watcher
│   └── test_sensors.py         Per-sensor test utility (make test)
├── themes/
│   └── *.json                  Built-in themes; locally edited installed themes are preserved by update scripts
├── animations/
│   └── *.py                    Built-in drop-in animations; copied to /etc/hub75-clock/animations/
│                               Drop your own .py files there to add custom animations at runtime
├── sprites/
│   └── *.json                  Sprite cameo art for the generic sprite animation
└── automations/
    ├── 01_set_theme.yaml            Set brightness + call theme script on bucket/condition change
    ├── 01b_select_theme_script.yaml Script: maps bucket + condition → theme, publishes to both clocks
    ├── 02_push_weather.yaml         Push forecast weather to clocks every 15 min
    ├── 03_alerts.yaml               NWS alert banner (shared clock/alert topic, all clocks receive)
    └── 04_online_offline.yaml       Offline notification for both clocks
```

Custom animations can be added at runtime by dropping a `.py` file into `/etc/hub75-clock/animations/`. The clock detects the new file within seconds and makes it available for use in theme `cameos` lists without a restart. See `docs/animations.md` for the full interface.

---

## Other Hardware

The Pi 4 is the primary tested platform. Other hardware may work with adjustments:

**Raspberry Pi Zero W**: requires additional build steps. See `docs/pi-zero-w.md`.

**Raspberry Pi 3B / 3B+**: should work with `gpio_slowdown: 3` in `config.yaml`. Untested.

**Raspberry Pi 5**: not currently supported.

---

## Compatibility

| Hardware | Status |
|---|---|
| Raspberry Pi 4 Model B | ✅ Primary / tested |
| Raspberry Pi Zero W 1.1 | 🔧 Community-supported; see `docs/pi-zero-w.md` |
| Raspberry Pi 3B / 3B+ | 🔧 Community-supported, untested, `gpio_slowdown: 3` |
| Raspberry Pi 5 | ❌ Not supported |

---

## Support

[![Buy Me A Coffee](https://img.buymeacoffee.com/button-api/?text=Buy%20me%20a%20coffee&emoji=&slug=ikonis&button_colour=5F7FFF&font_colour=ffffff&font_family=Bree&outline_colour=000000&coffee_colour=FFDD00)](https://buymeacoffee.com/ikonis)

---

## License

MIT.
