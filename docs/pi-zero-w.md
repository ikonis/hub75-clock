# HUB75 Smart Clock — Raspberry Pi Zero W Build Notes

> **Note:** The Raspberry Pi 4 is the primary supported platform. This document covers the additional steps required to build and run the clock on a Pi Zero W. These steps are community-supported and require more technical comfort.

---

## Why Pi Zero W Needs Extra Steps

The Pi Zero W uses an ARMv6 processor. The `rpi-rgb-led-matrix` library includes code for the Raspberry Pi 5's RP1 chip which fails to compile on ARMv6. You need to stub out the RP1 backend before building.

---

## Hardware Differences

| | Pi Zero W | Pi 4 |
|--|--|--|
| Architecture | ARMv6 32-bit | ARMv8 64-bit |
| gpio_slowdown | 2 | 4 |
| UART port | /dev/serial0 | /dev/ttyAMA0 |
| Performance | Slower, some lag on config changes | Fast, very responsive |
| Build process | Requires RP1 stub hack | Standard build |

---

## OS

Use **Raspberry Pi OS Lite (32-bit, Bookworm)**. Do NOT use 64-bit on Pi Zero W — it is not supported on ARMv6.

---

## Building rpi-rgb-led-matrix on Pi Zero W

The standard build will fail. Follow these steps exactly:

### 1. Clone the repo

```bash
cd ~
git clone https://github.com/hzeller/rpi-rgb-led-matrix
cd rpi-rgb-led-matrix
```

### 2. Edit the Makefile to remove RP1 objects

```bash
nano lib/Makefile
```

Find the `OBJECTS` line and remove these entries:
```
rp1/rp1_rio_backend.o
```

Save and exit.

### 3. Comment out RP1 includes in source files

```bash
nano lib/led-matrix.cc
```

Find and comment out:
```cpp
// #include "rp1/rp1_rio_backend.h"
```

Do the same in `lib/framebuffer.cc`.

### 4. Create RP1 stub header

```bash
mkdir -p lib/rp1
nano lib/rp1/rp1_rio_backend.h
```

Paste this content:

```cpp
#pragma once
namespace rgb_matrix {
namespace internal {
class Rp1RioBackend {
public:
    static bool IsAvailable() { return false; }
};
class Rp1PioBackend {
public:
    static bool IsAvailable() { return false; }
};
}
}
```

Save and exit.

### 5. Build with custom setup.py

```bash
mkdir /tmp/rgbmatrix_build
cat > /tmp/rgbmatrix_build/setup.py << 'EOF'
from setuptools import setup, Extension
import os

lib_dir = os.path.expanduser('~/rpi-rgb-led-matrix/lib')
inc_dir = os.path.expanduser('~/rpi-rgb-led-matrix/include')

module = Extension(
    'rgbmatrix._rgbmatrix',
    sources=[
        os.path.expanduser('~/rpi-rgb-led-matrix/bindings/python/rgbmatrix/led-matrix-swig.cc'),
    ],
    include_dirs=[inc_dir, lib_dir],
    library_dirs=[lib_dir],
    libraries=['rgbmatrix'],
    extra_compile_args=['-std=c++11'],
)

setup(
    name='rgbmatrix',
    packages=['rgbmatrix'],
    package_dir={'rgbmatrix': os.path.expanduser('~/rpi-rgb-led-matrix/bindings/python/rgbmatrix')},
    ext_modules=[module],
)
EOF
```

First build the C++ library:

```bash
cd ~/rpi-rgb-led-matrix
make -C lib
```

Then build the Python bindings:

```bash
cd /tmp/rgbmatrix_build
sudo python3 setup.py install
```

### 6. Verify

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

The Pi Zero W is a single-core ARMv6 at 1GHz. The clock runs well at 15fps for normal conditions but may feel sluggish when:

- Receiving lots of MQTT messages (gate data, engineering mode)
- Changing conditions or buckets rapidly

For best performance on Zero W:
- Keep `engineering_mode` off unless actively tuning
- Set `animation.fps: 12` instead of 15
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
