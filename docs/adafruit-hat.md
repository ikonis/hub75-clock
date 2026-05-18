# HUB75 Smart Clock: Adafruit RGB Matrix HAT

> **Note:** HAT support is untested and community-supported. The primary supported build uses direct GPIO wiring without a HAT. These notes are provided for users who already have an Adafruit HAT and want to try it, but issues specific to the HAT configuration are not actively supported.

Using an Adafruit RGB Matrix HAT simplifies wiring significantly. Just plug the HAT onto the Pi's 40-pin header and connect the HUB75 panel to the HAT's output connector.

---

## Compatible HATs

| HAT | Notes |
|-----|-------|
| [Adafruit RGB Matrix HAT + RTC](https://www.adafruit.com/product/2345) | Basic HAT, no PWM mod |
| [Adafruit RGB Matrix Bonnet](https://www.adafruit.com/product/3211) | Smaller form factor, same pinout |

Both include built-in level shifters, so no separate level shifting is needed.

---

## Wiring

Simply:
1. Seat the HAT onto the Pi 40-pin GPIO header
2. Connect the HUB75 panel's data cable to the HAT's HUB75 output connector
3. Connect panel power (5V) to the HAT's power input terminals or directly to the panel

That's it. No individual wire connections needed.

---

## Config Changes

In `/etc/hub75-clock/config.yaml`, change `hardware_mapping`:

**Standard HAT (no PWM mod):**
```yaml
panel:
  hardware_mapping: adafruit-hat
  gpio_slowdown: 4  # Pi 4
```

**HAT with PWM modification (better image quality, less flicker):**
```yaml
panel:
  hardware_mapping: adafruit-hat-pwm
  gpio_slowdown: 4  # Pi 4
```

---

## PWM Modification (Optional but Recommended)

The Adafruit HAT has a solder jumper that enables hardware PWM for smoother display output. See Adafruit's guide:
https://learn.adafruit.com/adafruit-rgb-matrix-plus-real-time-clock-hat-for-raspberry-pi/driving-matrices

If you do the PWM mod, use `adafruit-hat-pwm` as the hardware_mapping.

---

## Sensor Wiring with HAT

The HAT occupies most of the GPIO header but leaves some pins exposed. Check your specific HAT's documentation for which pins are available.

For the LD2410C UART, the HAT typically leaves the UART pins (GPIO14/15, physical pins 8/10) accessible. Connect LD2410C to those.

For the PIR sensor, use a GPIO pin that is not used by the HAT. GPIO26 (physical pin 37) is typically free on Adafruit HATs.

---

## configure.sh

When running `./scripts/configure.sh`, select **Adafruit HAT** or **Adafruit HAT (PWM mod)** when prompted for hardware mapping. The script will set the correct value automatically.
