# HUB75 Smart Clock: Raspberry Pi Zero W Build Notes

> **Note:** The Raspberry Pi 4 is the primary supported platform. This document covers the additional steps required to build and run the clock on a Pi Zero W. These steps are community-supported and require more technical comfort.

---

## Why Pi Zero W Needs Extra Steps

The Pi Zero W uses an ARMv6 processor. Recent versions of the `rpi-rgb-led-matrix` library include code for the Raspberry Pi 5's RP1 chip which fails to compile on ARMv6. `install.sh` works around this by pinning to commit `076c54b`, the last version before RP1 support was added, and building with the library's own `make build-python` target instead of pip.

---

## Hardware Differences

| | Pi Zero W | Pi 4 |
|--|--|--|
| Architecture | ARMv6 32-bit | ARMv8 64-bit |
| gpio_slowdown | 2 | 4 |
| UART port | /dev/serial0 | /dev/ttyAMA0 |
| Performance | Best with the C++ runtime | Very responsive with either runtime |
| Build process | Installer pins an older matrix library commit and can build the C++ runtime | Standard build |

---

## OS

Use **Raspberry Pi OS Lite (32-bit, Bookworm)**. Do NOT use 64-bit on Pi Zero W. It is not supported on ARMv6.

---

## Installer Runtime Choice

`install.sh` asks which runtime to install:

- `python` is the suggested default for multicore Pis.
- `cpp` is the suggested default on Pi Zero W and has the lowest CPU overhead.

The selected runtime controls both the systemd service and which updater gets installed to `~/update-clock.sh`. The C++ updater rebuilds `clock-cpp` during `make update`, then stops the service, swaps in the new binary, and restarts it.

---

## Building rpi-rgb-led-matrix on Pi Zero W

`install.sh` handles this automatically. It detects Pi Zero W at runtime, then:

1. Clones `rpi-rgb-led-matrix` to `~/rpi-rgb-led-matrix`
2. Checks out commit `076c54b` (last version before Pi 5 RP1 support was added; later commits fail to compile on ARMv6)
3. Builds the C++ library and Python bindings with the repo's own build targets:

```bash
make build-python PYTHON="$(which python3)"
sudo make install-python PYTHON="$(which python3)"
```

Just run `bash install.sh` as normal. No manual source edits are needed.

### Verify after install

```bash
python3 -c "from rgbmatrix import RGBMatrix, RGBMatrixOptions, graphics; print('OK')"
```

---

## Config Changes for Pi Zero W

In `/etc/hub75-clock/config.yaml`:

```yaml
panel:
  gpio_slowdown: 2  # Pi Zero W value

sensors:
  ld2410_port: /dev/serial0  # Pi Zero W UART
```

---

## Performance Notes

The Pi Zero W is a single-core ARMv6 at 1GHz. The installer defaults to the C++ runtime on Pi Zero because it has the lowest CPU overhead, but the Python runtime remains available if you want it. Both runtimes now default to 90fps.

Things that can still add load:

- Receiving lots of MQTT messages (gate data, engineering mode)
- Changing conditions or buckets rapidly

For best performance on Zero W:
- Keep `engineering_mode` off unless actively tuning
- Use the C++ runtime if the Python runtime feels sluggish
- Set `sensors.lux_interval: 60` (already default)

---

## UART on Pi Zero W

Enable UART the same way as Pi 4 via `raspi-config`. The port will be `/dev/serial0` which is a symlink to the correct UART device.

If you have Bluetooth issues (Zero W has BT on the main UART), disable it:

```bash
sudo systemctl disable hciuart
```

Add to `/boot/firmware/config.txt`:
```
dtoverlay=disable-bt
enable_uart=1
```
