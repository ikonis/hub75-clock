#!/usr/bin/env python3
"""
HUB75 Clock - RGB sequence test utility
Displays R, G, B letters in their named colors so you can identify the correct
led_rgb_sequence for your panel.

Usage: sudo python3 scripts/test_display.py
"""

import os
import sys
import re
import termios
import tty
import yaml

CONFIG_FILE = "/etc/hub75-clock/config.yaml"

FONT_PREFERENCE = [
    "spleen-16x32.bdf",
    "spleen-12x24.bdf",
    "10x20.bdf",
    "9x18.bdf",
    "7x13.bdf",
    "5x7.bdf",
]


def check_root():
    if os.geteuid() != 0:
        print("This script must be run as root: sudo python3 scripts/test_display.py")
        sys.exit(1)


def load_config():
    try:
        with open(CONFIG_FILE) as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        print(f"Config not found: {CONFIG_FILE}")
        print("Run install.sh first, or create the config with: make config")
        sys.exit(1)


def find_font(config):
    fonts_dir = config.get("fonts", {}).get("fonts_dir", os.path.expanduser("~/hub75-fonts"))
    font_path = None
    for candidate in FONT_PREFERENCE:
        path = os.path.join(fonts_dir, candidate)
        if os.path.exists(path):
            font_path = path
            break
    if font_path is None:
        print(f"[error] No usable font found in {fonts_dir}")
        sys.exit(1)
    return font_path


def getkey():
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
    return ch.lower()


def ask_color(position_label):
    while True:
        print(f"  What color is the {position_label} letter?  r=Red  g=Green  b=Blue : ", end="", flush=True)
        ch = getkey()
        if ch in ("r", "g", "b"):
            print(ch.upper())
            return ch.upper()
        print(f"\n  (press r, g, or b)")


def update_config_sequence(sequence):
    with open(CONFIG_FILE) as f:
        content = f.read()
    new_content = re.sub(
        r"(led_rgb_sequence\s*:\s*)['\"]?\w+['\"]?",
        f"\\g<1>{sequence}",
        content,
    )
    if new_content == content:
        print("  led_rgb_sequence key not found in config — add it manually under 'panel:'")
        return False
    with open(CONFIG_FILE, "w") as f:
        f.write(new_content)
    return True


def main():
    check_root()

    config = load_config()
    panel = config.get("panel", {})
    gpio_slowdown = panel.get("gpio_slowdown", 4)
    hardware_mapping = panel.get("hardware_mapping", "regular")
    current_sequence = panel.get("led_rgb_sequence", "RGB")

    font_path = find_font(config)

    from rgbmatrix import RGBMatrix, RGBMatrixOptions, graphics

    options = RGBMatrixOptions()
    options.rows = 32
    options.cols = 64
    options.hardware_mapping = hardware_mapping
    options.gpio_slowdown = gpio_slowdown
    options.led_rgb_sequence = "RGB"
    options.disable_hardware_pulsing = False

    matrix = RGBMatrix(options=options)
    canvas = matrix.CreateFrameCanvas()

    font = graphics.Font()
    font.LoadFont(font_path)

    font_w = font.CharacterWidth(ord("R"))
    baseline_y = font.baseline

    # Divide the 64px panel into three equal sections and center each letter
    section_w = 64 // 3  # 21px; rightmost section gets the remainder
    section_widths = [section_w, section_w, 64 - 2 * section_w]

    def letter_x(section):
        start = section * section_w
        return start + max(0, (section_widths[section] - font_w) // 2)

    red   = graphics.Color(255, 0, 0)
    green = graphics.Color(0, 255, 0)
    blue  = graphics.Color(0, 0, 255)

    canvas.Clear()
    graphics.DrawText(canvas, font, letter_x(0), baseline_y, red,   "R")
    graphics.DrawText(canvas, font, letter_x(1), baseline_y, green, "G")
    graphics.DrawText(canvas, font, letter_x(2), baseline_y, blue,  "B")
    matrix.SwapOnVSync(canvas)

    print()
    print("Look at the panel. You should see three colored letters: R  G  B")
    print()

    left   = ask_color("LEFT  ")
    center = ask_color("CENTER")
    right  = ask_color("RIGHT ")

    sequence = left + center + right
    print()
    print(f"Derived sequence: {sequence}")

    if sequence == current_sequence:
        print(f"Config already has led_rgb_sequence: {sequence} — no change needed.")
    else:
        print(f"Current config:   led_rgb_sequence: {current_sequence}")
        print(f"Update config.yaml with led_rgb_sequence: {sequence}? [Y/n] ", end="", flush=True)
        ans = getkey()
        print(ans.upper() if ans in "yn" else "Y")
        if ans != "n":
            if update_config_sequence(sequence):
                print(f"Updated led_rgb_sequence to {sequence}.")

    print()
    print("Done. Run  sudo systemctl restart hub75-clock  to apply.")
    print()

    matrix.Clear()


if __name__ == "__main__":
    main()
