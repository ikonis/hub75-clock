#!/usr/bin/env python3
"""
HUB75 Clock - Sensor Test Utility
Test each sensor in isolation before running the full clock.
  python3 test_sensors.py
"""

import sys
import time
import yaml

CONFIG_FILE = "/etc/hub75-clock/config.yaml"


def load_pir_gpio():
    try:
        with open(CONFIG_FILE) as f:
            cfg = yaml.safe_load(f)
        return int(cfg["sensors"]["pir_gpio"])
    except Exception:
        return 16


def test_veml7700():
    print("\n=== VEML7700 Lux Sensor ===")
    try:
        import board, adafruit_veml7700
        sensor = adafruit_veml7700.VEML7700(board.I2C())
        print("Initialized. Reading (Ctrl+C to stop)...\n")
        while True:
            lux = sensor.lux
            bar = "\u2588" * min(int(lux / 10), 50)
            print(f"  {lux:8.2f} lx  {bar}")
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopped.")
    except ImportError as e:
        print(f"Missing library: {e}")
        print("  sudo pip3 install --break-system-packages "
              "adafruit-circuitpython-veml7700 adafruit-blinka")
    except Exception as e:
        print(f"Error: {e}")
        print("\nTroubleshoot:")
        print("  sudo i2cdetect -y 1   (expect 0x10)")
        print("  SDA=GPIO2 (pin 3), SCL=GPIO3 (pin 5), VIN=3.3V")


def test_pir(gpio_pin=16):
    print(f"\n=== PIR Sensor (BCM GPIO{gpio_pin}) ===")
    try:
        import RPi.GPIO as GPIO
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(gpio_pin, GPIO.IN)
        print("Allow 30-60s warmup. Ctrl+C to stop.\n")
        last = None
        while True:
            state = bool(GPIO.input(gpio_pin))
            if state != last:
                print(f"  [{time.strftime('%H:%M:%S')}] "
                      f"{'MOTION' if state else 'clear'}")
                last = state
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\nStopped.")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        try:
            import RPi.GPIO as GPIO
            GPIO.cleanup()
        except Exception:
            pass


def test_ld2410():
    print("\n=== HLK-LD2410C mmWave ===")
    try:
        import serial
        ser = serial.Serial("/dev/serial0", 256000, timeout=0.5)
        print("Opened /dev/serial0. Move around. Ctrl+C to stop.\n")
        HEAD = b"\xF4\xF3\xF2\xF1"
        TAIL = b"\xF8\xF7\xF6\xF5"
        buf = bytearray()
        frames = 0
        while True:
            if ser.in_waiting:
                buf.extend(ser.read(ser.in_waiting))
            while True:
                idx = buf.find(HEAD)
                if idx < 0:
                    if len(buf) > 1024: del buf[:-4]
                    break
                if idx > 0: del buf[:idx]
                if len(buf) < 10: break
                dl = buf[4] | (buf[5] << 8)
                total = 4 + 2 + dl + 4
                if len(buf) < total: break
                if bytes(buf[total-4:total]) != TAIL:
                    del buf[:1]; continue
                data = buf[6:6+dl]
                del buf[:total]
                if len(data) >= 13 and data[0] == 0x02 and data[1] == 0xAA:
                    frames += 1
                    t = data[2]
                    md = data[3] | (data[4] << 8)
                    me = data[5]
                    sd = data[6] | (data[7] << 8)
                    se = data[8]
                    state = ["none","move","still","both"][min(t,3)]
                    print(f"  #{frames:04d}  {state:5s}  "
                          f"move={md:3d}cm({me:3d})  still={sd:3d}cm({se:3d})")
            time.sleep(0.02)
    except KeyboardInterrupt:
        print("\nStopped.")
    except Exception as e:
        print(f"Error: {e}")
        print("\nTroubleshoot:")
        print("  ls -l /dev/serial0   (must be ttyAMA0, not ttyS0)")
        print("  Wiring: LD2410 TX->GPIO15(pin10), LD2410 RX->GPIO14(pin8)")
        print("  sudo usermod -a -G dialout $USER  then log out/in")


def test_mqtt():
    print("\n=== MQTT Connection ===")
    try:
        import paho.mqtt.client as mqtt, getpass
        broker = input("Broker IP: ").strip()
        user = input("Username (blank=anon): ").strip()
        pw = getpass.getpass("Password: ") if user else ""
        connected = [False]

        def on_connect(c, u, f, rc):
            if rc == 0:
                connected[0] = True
                print(f"Connected to {broker}")
                c.subscribe("hub75_clock/#")
                c.publish("hub75_clock/test", "hello from test_sensors.py")
            else:
                print(f"Failed rc={rc}")

        def on_message(c, u, msg):
            print(f"  {msg.topic} -> {msg.payload.decode(errors='replace')}")

        client = mqtt.Client()
        client.on_connect = on_connect
        client.on_message = on_message
        if user: client.username_pw_set(user, pw)
        client.connect(broker, 1883, 60)
        client.loop_start()
        for _ in range(10):
            if connected[0]: break
            time.sleep(0.5)
        if not connected[0]:
            print("Timed out.")
            return
        print("Listening on hub75_clock/# (Ctrl+C to stop)...\n")
        while True: time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopped.")
    except Exception as e:
        print(f"Error: {e}")


def main():
    pir_gpio = load_pir_gpio()
    tests = {
        "1": ("VEML7700 lux",     test_veml7700),
        "2": (f"PIR motion       (GPIO{pir_gpio})", lambda: test_pir(pir_gpio)),
        "3": ("LD2410C mmWave",   test_ld2410),
        "4": ("MQTT connection",  test_mqtt),
    }
    while True:
        print("\nHUB75 Clock - Sensor Test")
        print("---------------------------")
        for k, (name, _) in tests.items():
            print(f"  {k}. {name}")
        print("  q. quit")
        choice = input("\nSelect: ").strip().lower()
        if choice == "q": break
        if choice in tests: tests[choice][1]()
        else: print("Invalid.")


if __name__ == "__main__":
    main()
