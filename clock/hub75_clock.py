#!/usr/bin/env python3
"""
HUB75 Smart Clock
================================
Changes from v1:
  - Per-element colors (time, low temp, high temp, condition, alert)
  - Colors changeable live via MQTT, saved to config.yaml
  - Font switching via MQTT (triggers auto-restart)
  - On startup, publishes available font list to hub75_clock/fonts_available
  - Hex color support in config (#RRGGBB)
"""

import os
import sys
import time
import math
import json
import signal
import subprocess
import threading
import random
import re
from datetime import datetime, timezone
from typing import List, Optional, Tuple

import yaml
from rgbmatrix import RGBMatrix, RGBMatrixOptions, graphics
import paho.mqtt.client as mqtt
from theme_loader import ThemeLoader, Theme

VERSION = "1.0.0"

try:
    import board
    import adafruit_veml7700
    HAS_VEML7700 = True
except (ImportError, NotImplementedError) as e:
    HAS_VEML7700 = False
    print(f"[init] VEML7700 unavailable: {e}")

try:
    import serial
    HAS_LD2410 = True
except ImportError:
    HAS_LD2410 = False
    print("[init] pyserial not found - LD2410C disabled")

try:
    import RPi.GPIO as GPIO
    HAS_PIR = True
except (ImportError, RuntimeError) as e:
    HAS_PIR = False
    print(f"[init] RPi.GPIO unavailable: {e}")


# ============================================================================
# COLOR HELPERS
# ============================================================================

def hex_to_rgb(hex_str: str) -> Tuple[int, int, int]:
    """Convert #RRGGBB to (r, g, b). Falls back to white on error."""
    try:
        h = hex_str.lstrip('#')
        return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
    except Exception:
        return (240, 240, 240)

def rgb_to_hex(r: int, g: int, b: int) -> str:
    return f"#{r:02X}{g:02X}{b:02X}"

def parse_color(val) -> Tuple[int, int, int]:
    """Accept either '#RRGGBB' string or [r, g, b] list."""
    if isinstance(val, str):
        return hex_to_rgb(val)
    elif isinstance(val, (list, tuple)) and len(val) == 3:
        return tuple(int(x) for x in val)
    return (240, 240, 240)


# ============================================================================
# CONFIG + LAYOUT LOADER
# ============================================================================

DEFAULTS = {
    "mqtt": {
        "broker": "",
        "port": 1883,
        "username": "",
        "password": "",
        "client_id": "hub75_clock",
        "topics": {
            "weather":          "clock/weather",
            "config":           "clock/config",
            "alert":            "clock/alert",
            "lux":              "hub75_clock/lux",
            "presence":         "hub75_clock/presence",
            "motion":           "hub75_clock/motion",
            "pir":              "hub75_clock/pir",
            "availability":     "hub75_clock/status",
            "fonts_available":  "hub75_clock/fonts_available",
            "gates":            "hub75_clock/gates",
            "engineering_mode": "hub75_clock/engineering_mode",
            "bucket":           "hub75_clock/bucket",
            "version_state":    "hub75_clock/version",
            "update":           "hub75_clock/update/install",
            "update_latest":    "hub75_clock/update/latest",
            "theme":            "hub75_clock/theme/set",
            "theme_state":      "hub75_clock/theme/state",
            "themes_available": "hub75_clock/themes/available",
        },
    },
    "ha_discovery": {
        "enabled":            True,
        "prefix":             "homeassistant",
        "ha_discovery_name":  "HUB75 Clock",
        "ha_discovery_area":  "",
    },
    "panel": {
        "hardware_mapping":    "regular",
        "gpio_slowdown":       2,
        "led_rgb_sequence":    "RBG",
        "pwm_bits":            11,
        "pwm_lsb_nanoseconds": 130,
        "brightness":          60,
    },
    "fonts": {
        # Use filenames only - resolved against fonts_dir at runtime
        "fonts_dir":   "/home/pi/rpi-rgb-led-matrix/fonts",
        "banner_name": "4x6.bdf",
        "banner_w":    4,
        "banner_h":    6,
        "time_name":   "spleen-12x24.bdf",
        "time_w":      12,
        "time_h":      24,
        "alert_name":  "4x6.bdf",
        "alert_w":     4,
        "alert_h":     6,
    },
    "colors": {
        # All colors accept either "#RRGGBB" or [r, g, b]
        "time_day":        "#F0F0F0",
        "time_night":      "#505050",
        "low_temp_day":    "#00CCFF",
        "low_temp_night":  "#004455",
        "high_temp_day":   "#FF8C00",
        "high_temp_night": "#553300",
        "condition_day":   "#909090",
        "condition_night": "#404040",
        "alert_text":      "#FFFFFF",
        "alert_bg":        "#CC0000",
        # Animation colors
        "rain_day":        [22, 42, 115],
        "rain_night":      [10, 18, 50],
        "snow_day":        [180, 180, 200],
        "snow_night":      [50, 50, 70],
        "sleet_day":       [120, 160, 180],
        "sleet_night":     [40, 55, 70],
        "lightning":       [200, 200, 40],
        "cloud_day":       [70, 70, 70],
        "cloud_night":     [25, 25, 25],
        "sun_day":         [220, 160, 30],
        "sun_night":       [70, 50, 10],
        "ice_day":         [80, 140, 160],
        "ice_night":       [25, 45, 55],
        "outline":         [0, 0, 0],
        "sky_day":         "#000820",
        "separator":       "#1A1A1A",
        "evening_top":     "#0F0019",
        "evening_bottom":  "#3C1400",
        "night_bg":        "#020005",
        "late_evening_bg": "#05000F",
    },
    "animation": {
        "fps":                        15,
        "fps_night":                   8,
        "rain_count":                [5, 8],
        "snow_count":                [6, 10],
        "sleet_count":               [6, 10],
        "tstorm_rain_count":         [5, 8],
        "tstorm_lightning_chance":   0.015,
        "tstorm_lightning_duration": 2,
    },
    "alert": {
        "scroll_speed": 1,
        "scroll_gap":   8,
        "flash":        False,
        "flash_period": 10,
        "fill_region":  True,
    },
    "sensors": {
        "lux_interval":       10.0,
        "pir_poll_interval":   0.1,
        "veml7700_enabled":   True,
        "ld2410_enabled":     True,
        "ld2410_port":        "/dev/serial0",
        "ld2410_baud":        256000,
        "pir_enabled":        True,
        "pir_gpio":           6,
        "pir_invert":         False,
    },
    "time_format": {
        "use_24h":     False,
        "blink_colon": False,
    },
    "update": {
        "enabled":     True,
        "repo_path":   "/home/pi/hub75-clock",
        "github_repo": "YOUR_GITHUB/hub75-clock",  # replace with your GitHub username/repo
    },
    "themes": {
        "themes_dir":    "/etc/hub75-clock/themes",
        "default_theme": "Day",
    },
}

DEFAULT_LAYOUT = {
    "banner": {"top": 1, "bottom": 7},
    "time":   {"top": 8, "bottom": 31, "outline": True,
               "zone_left": 0, "zone_right": 63},
    "weather": {
        "show_outdoor_temp": False,
        "show_condition_word": True,
        "zone_left": 0, "zone_right": 63,
        "high_row": 8, "low_row": 16,
        "condition_row": 23, "outdoor_row": 30,
    },
    "animation": {"zone_top": 8, "zone_bottom": 31, "particle_scale": 1.0},
}


def deep_merge(base: dict, overlay: dict) -> dict:
    out = dict(base)
    for k, v in (overlay or {}).items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config(config_path: str) -> dict:
    try:
        with open(config_path) as f:
            user = yaml.safe_load(f) or {}
        cfg = deep_merge(DEFAULTS, user)
        print(f"[config] loaded {config_path}")
    except FileNotFoundError:
        print(f"[config] {config_path} not found - using defaults")
        cfg = dict(DEFAULTS)
    except Exception as e:
        print(f"[config] error: {e} - using defaults")
        cfg = dict(DEFAULTS)

    if not cfg["mqtt"].get("broker"):
        raise ValueError("[config] mqtt.broker is not set — please add your MQTT broker IP to config.yaml")

    cfg["panel"].setdefault("width", 64)
    cfg["panel"].setdefault("height", 32)

    # Resolve full font paths from names
    fonts_dir = cfg["fonts"]["fonts_dir"]
    for key in ("banner", "time", "alert"):
        name_key = f"{key}_name"
        path_key = f"{key}_path"
        if name_key in cfg["fonts"]:
            cfg["fonts"][path_key] = os.path.join(fonts_dir, cfg["fonts"][name_key])

    return cfg


def save_config(config_path: str, cfg: dict):
    """Save config back to yaml, preserving structure."""
    try:
        # Build a saveable version (remove computed path keys, keep name keys)
        save = dict(cfg)
        fonts_save = dict(cfg["fonts"])
        for key in ("banner_path", "time_path", "alert_path"):
            fonts_save.pop(key, None)
        save["fonts"] = fonts_save
        with open(config_path, 'w') as f:
            yaml.dump(save, f, default_flow_style=False, allow_unicode=True)
        print(f"[config] saved to {config_path}")
    except Exception as e:
        print(f"[config] save failed: {e}")



def get_available_fonts(fonts_dir: str) -> List[str]:
    """Return sorted list of .bdf filenames in the fonts directory."""
    try:
        return sorted([f for f in os.listdir(fonts_dir) if f.endswith('.bdf')])
    except Exception:
        return []


# ============================================================================
# WEATHER ANIMATOR
# ============================================================================

class Particle:
    __slots__ = ("x", "y", "vx", "vy", "color", "length")
    def __init__(self, x, y, vx, vy, color, length=1):
        self.x = x; self.y = y; self.vx = vx; self.vy = vy
        self.color = color; self.length = length



# ============================================================================
# WEATHER ANIMATOR (v2: full background, drifting clouds, sun rays, stars)
# ============================================================================


# ============================================================================
# WEATHER ANIMATOR
# ============================================================================

class Cloud:
    """A drifting cartoon cloud."""
    __slots__ = ("x", "y", "vx", "size", "color")
    def __init__(self, x, y, vx, size, color):
        self.x = x; self.y = y; self.vx = vx
        self.size = size; self.color = color


class Star:
    """A twinkling star."""
    __slots__ = ("x", "y", "phase", "speed", "max_brightness")
    def __init__(self, x, y, phase, speed, max_brightness):
        self.x = x; self.y = y; self.phase = phase
        self.speed = speed; self.max_brightness = max_brightness


class LightningBolt:
    """A zigzag lightning bolt."""
    __slots__ = ("points", "life", "max_life")
    def __init__(self, points, life):
        self.points = points
        self.life = life
        self.max_life = life


class ShootingStar:
    """A fast-moving streak across the night sky."""
    __slots__ = ("x", "y", "vx", "vy", "life", "max_life")
    def __init__(self, x, y, vx, vy, life):
        self.x = x; self.y = y; self.vx = vx; self.vy = vy
        self.life = life; self.max_life = life


class WeatherAnimator:
    def __init__(self, cfg: dict, layout: dict):
        self.cfg = cfg
        self.layout = layout
        self.width   = cfg["panel"]["width"]
        self.height  = cfg["panel"]["height"]
        self.banner_bottom = layout["banner"]["bottom"]
        self.anim_top    = self.banner_bottom + 1
        self.anim_bottom = self.height - 1
        self.particles: List[Particle] = []
        self.clouds: List[Cloud] = []
        self.stars: List[Star] = []
        self.shooting_stars: List[ShootingStar] = []
        self.bolts: List[LightningBolt] = []
        self._ice_cracks = []
        self.condition = "CLEAR"
        self.current_theme: Optional[Theme] = None
        self.night_mode = False
        self.frame = 0
        self._init_for_condition()

    _CONDITION_ALIASES = {
        "BLIZZARD":        "SNOW",
        "HURRICANE":       "TSTORM",
        "TROPICAL_STORM":  "TSTORM",
        "FLOOD":           "RAIN",
        "FREEZING_RAIN":   "ICE",
        "FREEZING_DRIZZLE": "SLEET",
        "DUST":            "CLOUDY",
        "SMOKE":           "CLOUDY",
        "FOG":             "CLOUDY",
        "WINDY":           "CLOUDY",
        "EXCEPTIONAL":     "CLOUDY",
    }

    def set_condition(self, condition: str):
        c = (condition or "CLEAR").upper().strip()
        c = self._CONDITION_ALIASES.get(c, c)
        if c == self.condition:
            return
        self.condition = c
        self._init_for_condition()

    def set_theme(self, theme: Theme):
        self.current_theme = theme
        self._init_for_condition()

    def set_night_mode(self, night: bool):
        if night == self.night_mode:
            return
        self.night_mode = night
        self._init_for_condition()

    def _color(self, day_key: str, night_key: str) -> Tuple:
        c = self.cfg["colors"]
        raw = c[night_key] if self.night_mode else c[day_key]
        return parse_color(raw)

    def _count(self, range_key: str) -> int:
        lo, hi = self.cfg["animation"][range_key]
        if self.night_mode:
            lo, hi = max(2, lo // 2), max(3, hi // 2)
        return max(1, random.randint(lo, hi))

    def _theme_cloud_count(self) -> int:
        if self.current_theme is None:
            return random.randint(2, 3)
        density = self.current_theme.cloud_density
        if density == "sparse":
            return 2
        elif density == "dense":
            return random.randint(5, 6)
        return random.randint(3, 4)

    def _theme_cloud_speed(self) -> float:
        if self.current_theme is None:
            return random.uniform(0.08, 0.18)
        speed = self.current_theme.cloud_speed
        if speed == "slow":
            return random.uniform(0.04, 0.10)
        elif speed == "fast":
            return random.uniform(0.14, 0.28)
        return random.uniform(0.08, 0.18)

    def _init_for_condition(self):
        self.condition = self._CONDITION_ALIASES.get(self.condition, self.condition)
        print(f"[animator] condition={self.condition}")
        self.particles = []
        self.clouds = []
        self.stars = []
        self.shooting_stars = []
        self.bolts = []

        stars_ok = (self.current_theme.stars_enabled if self.current_theme else self.night_mode)
        clouds_ok = (self.current_theme.clouds_enabled if self.current_theme else True)

        if self.condition == "CLEAR":
            if stars_ok:
                self._init_stars()
        elif self.condition == "SUNNY":
            if clouds_ok:
                self._init_clear_day()
            if stars_ok:
                self._init_stars()
        elif self.condition == "CLOUDY":
            if stars_ok:
                self._init_stars()
            if clouds_ok:
                self._init_clouds()
        elif self.condition in ("PARTLYCLOUDY", "FOG"):
            if stars_ok:
                self._init_stars()
            if clouds_ok:
                self._init_partly_cloudy()
        elif self.condition == "ICE":
            self._init_ice()
        elif self.condition == "RAIN":
            self._init_rain(fast=False)
        elif self.condition == "SNOW":
            self._init_snow()
        elif self.condition == "SLEET":
            self._init_sleet()
        elif self.condition == "TSTORM":
            self._init_rain(fast=True)
        else:
            if stars_ok:
                self._init_stars()
            if clouds_ok:
                self._init_partly_cloudy()

    def _init_stars(self):
        anim_h = self.anim_bottom - self.anim_top + 1
        count = max(8, (self.width * anim_h) // 30)
        for _ in range(count):
            self.stars.append(Star(
                x=random.randint(0, self.width - 1),
                y=random.randint(self.anim_top, self.anim_bottom),
                phase=random.random() * 6.28,
                speed=random.uniform(0.05, 0.15),
                max_brightness=random.choice([60, 80, 100, 140, 200]),
            ))

    def _init_clear_day(self):
        color = self._color("cloud_day", "cloud_night")
        count = self._theme_cloud_count()
        for _ in range(count):
            direction = random.choice([-1, 1])
            speed = self._theme_cloud_speed() * direction
            self.clouds.append(Cloud(
                x=random.uniform(0, self.width),
                y=random.randint(self.anim_top + 1, self.anim_bottom - 5),
                vx=speed,
                size=random.choice(["small", "medium"]),
                color=color,
            ))

    def _init_clouds(self):
        color = self._color("cloud_day", "cloud_night")
        count = self._theme_cloud_count()
        for _ in range(count):
            direction = random.choice([-1, 1])
            speed = self._theme_cloud_speed() * direction
            size = random.choice(["medium", "large"])
            self.clouds.append(Cloud(
                x=random.uniform(0, self.width),
                y=random.randint(self.anim_top + 1, self.anim_bottom - 5),
                vx=speed,
                size=size,
                color=color,
            ))

    def _init_partly_cloudy(self):
        color = self._color("cloud_day", "cloud_night")
        count = self._theme_cloud_count()
        for _ in range(count):
            direction = random.choice([-1, 1])
            speed = self._theme_cloud_speed() * direction
            size = random.choice(["small", "medium"])
            self.clouds.append(Cloud(
                x=random.uniform(0, self.width),
                y=random.randint(self.anim_top + 1, self.anim_bottom - 5),
                vx=speed,
                size=size,
                color=color,
            ))

    def _init_rain(self, fast=False):
        color = self._color("rain_day", "rain_night")
        count = self._count("rain_count")
        if fast:
            count = int(count * 1.5)
        for _ in range(count):
            vy = random.uniform(0.9, 1.4) if fast else random.uniform(0.5, 0.8)
            self.particles.append(Particle(
                x=random.uniform(0, self.width),
                y=random.uniform(self.anim_top, self.anim_bottom),
                vx=0, vy=vy,
                color=color,
                length=random.randint(2, 3),
            ))

    def _init_snow(self):
        color = self._color("snow_day", "snow_night")
        for _ in range(self._count("snow_count")):
            self.particles.append(Particle(
                x=random.uniform(0, self.width),
                y=random.uniform(self.anim_top, self.anim_bottom),
                vx=random.uniform(-0.1, 0.1),
                vy=random.uniform(0.15, 0.3),
                color=color, length=1,
            ))

    def _init_sleet(self):
        color = self._color("sleet_day", "sleet_night")
        for _ in range(self._count("sleet_count")):
            self.particles.append(Particle(
                x=random.uniform(0, self.width),
                y=random.uniform(self.anim_top, self.anim_bottom),
                vx=random.uniform(-0.05, 0.05),
                vy=random.uniform(0.4, 0.6),
                color=color,
                length=random.choice([1, 2]),
            ))
    def _init_ice(self):
        """ICE: light blue background with static crack lines."""
        self._ice_cracks = self._generate_ice_cracks()

    def _generate_ice_cracks(self):
        cracks = []
        color = self._color("ice_day", "ice_night")
        count = random.randint(3, 5)
        for _ in range(count):
            x = random.randint(4, self.width - 4)
            y = self.anim_top
            points = [(x, y)]
            while y < self.anim_bottom:
                x += random.randint(-4, 4)
                x = max(1, min(self.width - 2, x))
                y += random.randint(3, 6)
                y = min(self.anim_bottom, y)
                points.append((x, y))
            cracks.append((points, color))
        return cracks



    def _make_bolt(self):
        """Generate a random zigzag lightning bolt in the animation zone."""
        color = parse_color(self.cfg["colors"]["lightning"])
        x = random.randint(8, self.width - 8)
        y = self.anim_top
        points = [(x, y)]
        while y < self.anim_bottom - 2:
            x += random.randint(-3, 3)
            x = max(1, min(self.width - 2, x))
            y += random.randint(2, 4)
            y = min(self.anim_bottom, y)
            points.append((x, y))
        life = self.cfg["animation"]["tstorm_lightning_duration"] * 2
        return LightningBolt(points=points, life=life)

    def update(self):
        self.frame += 1

        for p in self.particles:
            p.x += p.vx; p.y += p.vy
            if p.y > self.anim_bottom:
                p.y = self.anim_top
                p.x = random.uniform(0, self.width)
            if p.x < 0: p.x = self.width - 1
            elif p.x >= self.width: p.x = 0

        for c in self.clouds:
            c.x += c.vx
            if c.vx > 0 and c.x > self.width + 12:
                c.x = -12
            elif c.vx < 0 and c.x < -12:
                c.x = self.width + 12

        # Lightning bolts (TSTORM)
        if self.condition == "TSTORM":
            self.bolts = [b for b in self.bolts if b.life > 0]
            for b in self.bolts:
                b.life -= 1
            if (not self.bolts and
                    random.random() < self.cfg["animation"]["tstorm_lightning_chance"]):
                self.bolts.append(self._make_bolt())

        # Shooting stars
        shooting_ok = (self.current_theme.shooting_stars_enabled
                       if self.current_theme else False)
        if shooting_ok and self.condition in ("CLEAR", "PARTLYCLOUDY"):
            for ss in self.shooting_stars:
                ss.life -= 1
                ss.x += ss.vx
                ss.y += ss.vy
            self.shooting_stars = [ss for ss in self.shooting_stars if ss.life > 0]
            if random.random() < 0.004:
                anim_third = self.anim_top + (self.anim_bottom - self.anim_top + 1) // 3
                speed = random.uniform(1.0, 2.5)
                if random.random() < 0.5:
                    speed = -speed
                self.shooting_stars.append(ShootingStar(
                    x=random.uniform(0, self.width),
                    y=random.uniform(self.anim_top, anim_third),
                    vx=speed,
                    vy=random.uniform(0.8, 1.4),
                    life=random.randint(10, 16),
                ))

    def _draw_hazard_stripes(self, canvas):
        for y in range(self.anim_top, self.anim_bottom + 1):
            for x in range(self.width):
                if (x + y) % 10 < 5:
                    canvas.SetPixel(x, y, 40, 20, 0)

    def _draw_background(self, canvas):
        if self.current_theme is None:
            col = parse_color(self.cfg["colors"].get("night_bg", "#020005"))
            for y in range(self.anim_top, self.anim_bottom + 1):
                for x in range(self.width):
                    canvas.SetPixel(x, y, col[0], col[1], col[2])
            return

        theme = self.current_theme
        bg_type    = theme.background_type
        bg_color   = theme.background_color
        bg_top     = theme.background_top
        bg_bottom  = theme.background_bottom
        bg_split   = theme.background_split
        bg_dir     = theme.background_gradient_direction

        override = theme.condition_overrides.get(self.condition, {})
        if override:
            bg_type   = override.get("background_type",               bg_type)
            bg_color  = override.get("background_color",              bg_color)
            bg_top    = override.get("background_top",                bg_top)
            bg_bottom = override.get("background_bottom",             bg_bottom)
            bg_split  = override.get("background_split",              bg_split)
            bg_dir    = override.get("background_gradient_direction", bg_dir)

        zone_h = self.anim_bottom - self.anim_top

        if bg_type == "solid":
            col = parse_color(bg_color)
            for y in range(self.anim_top, self.anim_bottom + 1):
                for x in range(self.width):
                    canvas.SetPixel(x, y, col[0], col[1], col[2])

        elif bg_type == "gradient":
            top_col = parse_color(bg_top)
            bot_col = parse_color(bg_bottom)
            split_y = self.anim_top + int(zone_h * bg_split)

            if bg_dir == "sunrise":
                # Top portion: gradient from background_top (at anim_top) to background_bottom (at split_y)
                for y in range(self.anim_top, split_y + 1):
                    span = split_y - self.anim_top
                    t = (y - self.anim_top) / span if span > 0 else 1.0
                    r = int(top_col[0] + (bot_col[0] - top_col[0]) * t)
                    g = int(top_col[1] + (bot_col[1] - top_col[1]) * t)
                    b = int(top_col[2] + (bot_col[2] - top_col[2]) * t)
                    for x in range(self.width):
                        canvas.SetPixel(x, y, r, g, b)
                # Bottom portion: solid background_bottom
                for y in range(split_y + 1, self.anim_bottom + 1):
                    for x in range(self.width):
                        canvas.SetPixel(x, y, bot_col[0], bot_col[1], bot_col[2])

            else:  # sunset (default)
                # Top portion: solid background_top
                for y in range(self.anim_top, split_y):
                    for x in range(self.width):
                        canvas.SetPixel(x, y, top_col[0], top_col[1], top_col[2])
                # Bottom portion: gradient from background_top (at split_y) to background_bottom (at anim_bottom)
                for y in range(split_y, self.anim_bottom + 1):
                    span = self.anim_bottom - split_y
                    t = (y - split_y) / span if span > 0 else 1.0
                    r = int(top_col[0] + (bot_col[0] - top_col[0]) * t)
                    g = int(top_col[1] + (bot_col[1] - top_col[1]) * t)
                    b = int(top_col[2] + (bot_col[2] - top_col[2]) * t)
                    for x in range(self.width):
                        canvas.SetPixel(x, y, r, g, b)

        else:
            for y in range(self.anim_top, self.anim_bottom + 1):
                for x in range(self.width):
                    canvas.SetPixel(x, y, 0, 0, 0)

    def _draw_sun(self, canvas):
        color = self._color("sun_day", "sun_night")
        ox = self.width - 1
        oy = self.anim_top
        radius = 12
        glow_radius = 20
        # Use theme background color for glow blend, fall back to sky_day
        if self.current_theme and self.current_theme.background_type == "solid":
            sky = parse_color(self.current_theme.background_color)
        else:
            sky = parse_color(self.cfg["colors"].get("sky_day", "#000820"))
        for y in range(oy, oy + glow_radius + 1):
            for x in range(ox - glow_radius, ox + 1):
                dist = math.sqrt((ox - x) ** 2 + (y - oy) ** 2)
                if dist <= radius:
                    self._px(canvas, x, y, color)
                elif dist <= glow_radius:
                    fade = 1.0 - (dist - radius) / (glow_radius - radius)
                    gc = (
                        int(color[0] * fade + sky[0] * (1.0 - fade)),
                        int(color[1] * fade + sky[1] * (1.0 - fade)),
                        int(color[2] * fade + sky[2] * (1.0 - fade)),
                    )
                    self._px(canvas, x, y, gc)

    def draw(self, canvas, alert_active: bool = False):
        """Draw background animation. Banner area never touched."""
        if alert_active:
            self._draw_hazard_stripes(canvas)
            return

        self._draw_background(canvas)

        # Stars: populated by _init_for_condition only when theme allows them
        for s in self.stars:
            phase = s.phase + (self.frame * s.speed)
            level = (math.sin(phase) + 1.0) * 0.5
            b = int(s.max_brightness * level)
            if b > 5:
                self._px(canvas, s.x, s.y, (b, b, b))

        # Shooting stars
        for ss in self.shooting_stars:
            brightness = int(220 * (ss.life / ss.max_life))
            self._px(canvas, int(ss.x), int(ss.y), (brightness, brightness, brightness))
            for i in range(1, 6):
                trail_b = int(brightness * (1.0 - i / 5.0))
                if trail_b > 5:
                    self._px(canvas, int(ss.x - ss.vx * i), int(ss.y - ss.vy * i),
                             (trail_b, trail_b, trail_b))

        # Sun: drawn before clouds so clouds pass in front of it
        if self.condition == "SUNNY" and not self.night_mode:
            self._draw_sun(canvas)

        # Clouds
        for c in self.clouds:
            self._draw_cloud(canvas, c)

        # ICE: light blue bg + static crack lines
        if self.condition == "ICE":
            ice_bg = parse_color(self.cfg["colors"].get("ice_bg", "#001830"))
            for y in range(self.anim_top, self.anim_bottom + 1):
                for x in range(self.width):
                    canvas.SetPixel(x, y, ice_bg[0], ice_bg[1], ice_bg[2])
            for points, color in self._ice_cracks:
                for i in range(len(points) - 1):
                    x1, y1 = points[i]
                    x2, y2 = points[i + 1]
                    self._line(canvas, x1, y1, x2, y2, color)

        # Particles (rain/snow/sleet/tstorm)
        for p in self.particles:
            xi, yi = int(p.x), int(p.y)
            if p.length == 1:
                self._px(canvas, xi, yi, p.color)
            else:
                for i in range(p.length):
                    self._px(canvas, xi, yi + i, p.color)

        # Lightning bolts (TSTORM)
        for bolt in self.bolts:
            color = parse_color(self.cfg["colors"]["lightning"])
            max_life = bolt.max_life
            fade = bolt.life / max_life
            c = tuple(int(v * fade) for v in color)
            for i in range(len(bolt.points) - 1):
                x1, y1 = bolt.points[i]
                x2, y2 = bolt.points[i + 1]
                self._line(canvas, x1, y1, x2, y2, c)

    def _draw_cloud(self, canvas, cloud: Cloud):
        x = int(cloud.x)
        y = int(cloud.y)
        c = cloud.color
        if cloud.size == "small":
            shape = [
                "  XXX  ",
                " XXXXX ",
                "XXXXXXX",
            ]
        elif cloud.size == "medium":
            shape = [
                "   XXXX   ",
                " XXXXXXXX ",
                "XXXXXXXXXX",
                " XXXXXXXX ",
            ]
        else:  # large
            shape = [
                "   XXXXX   ",
                " XXXXXXXXX ",
                "XXXXXXXXXXX",
                "XXXXXXXXXXX",
                " XXXXXXXXX ",
            ]
        for row, line in enumerate(shape):
            for col, ch in enumerate(line):
                if ch == "X":
                    self._px(canvas, x + col, y + row, c)

    def _line(self, canvas, x1, y1, x2, y2, color):
        dx, dy = abs(x2 - x1), abs(y2 - y1)
        sx = 1 if x1 < x2 else -1
        sy = 1 if y1 < y2 else -1
        err = dx - dy
        while True:
            self._px(canvas, x1, y1, color)
            if x1 == x2 and y1 == y2: break
            e2 = 2 * err
            if e2 > -dy: err -= dy; x1 += sx
            if e2 < dx:  err += dx; y1 += sy

    def _px(self, canvas, x, y, color):
        if 0 <= x < self.width and self.anim_top <= y <= self.anim_bottom:
            canvas.SetPixel(x, y, color[0], color[1], color[2])


# ============================================================================
# ALERT OVERLAY
# ============================================================================

class AlertOverlay:
    def __init__(self, cfg: dict, font: graphics.Font, font_w: int, font_h: int):
        self.cfg = cfg
        self.font = font
        self.font_w = font_w
        self.font_h = font_h
        self.message: Optional[str] = None
        self.expires_at: Optional[float] = None
        self.scroll_offset = 0
        self.flash_counter = 0
        self.flash_visible = True

    def set_alert(self, message: Optional[str], expires_iso: Optional[str]):
        if not message:
            self.clear(); return
        self.message = message
        self.scroll_offset = 0
        self.flash_counter = 0
        self.flash_visible = True
        if expires_iso:
            try:
                dt = datetime.fromisoformat(expires_iso)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                self.expires_at = dt.timestamp()
            except Exception as e:
                print(f"[alert] bad expiry: {e}")
                self.expires_at = None
        else:
            self.expires_at = None
        print(f"[alert] active: {message!r}")

    def clear(self):
        if self.message: print("[alert] cleared")
        self.message = None; self.expires_at = None; self.scroll_offset = 0

    def is_active(self) -> bool:
        if self.message is None: return False
        if self.expires_at and time.time() >= self.expires_at:
            self.clear(); return False
        return True

    def update(self):
        if not self.is_active(): return
        text_w = len(self.message) * self.font_w
        gap = self.cfg["alert"]["scroll_gap"]
        self.scroll_offset += self.cfg["alert"]["scroll_speed"]
        if self.scroll_offset >= text_w + gap:
            self.scroll_offset = 0
        if self.cfg["alert"]["flash"]:
            self.flash_counter += 1
            if self.flash_counter >= self.cfg["alert"]["flash_period"]:
                self.flash_counter = 0
                self.flash_visible = not self.flash_visible

    def draw(self, canvas, banner_top: int, banner_bottom: int, panel_width: int, panel_height: int = 32):
        if not self.is_active(): return
        border = parse_color(self.cfg["colors"]["alert_bg"])
        # 1px red border around entire panel
        for x in range(panel_width):
            canvas.SetPixel(x, 0, border[0], border[1], border[2])
            canvas.SetPixel(x, panel_height - 1, border[0], border[1], border[2])
        for y in range(panel_height):
            canvas.SetPixel(0, y, border[0], border[1], border[2])
            canvas.SetPixel(panel_width - 1, y, border[0], border[1], border[2])

    def draw_banner_scroll(self, canvas, banner_top: int, banner_bottom: int,
                           scroll_left: int, scroll_right: int,
                           font, font_w: int, font_h: int):
        if not self.is_active(): return
        if self.cfg["alert"]["flash"] and not self.flash_visible: return

        fg = parse_color(self.cfg["colors"]["alert_text"])
        region_h = banner_bottom - banner_top + 1
        text_y = banner_top + (region_h - font_h) // 2 + font_h - 1
        col = graphics.Color(fg[0], fg[1], fg[2])
        text_w = len(self.message) * font_w
        gap = self.cfg["alert"]["scroll_gap"]
        scroll_w = scroll_right - scroll_left
        x1 = scroll_left + scroll_w - self.scroll_offset
        x2 = x1 + text_w + gap
        if x1 < scroll_right and x1 + text_w > scroll_left:
            graphics.DrawText(canvas, font, x1, text_y, col, self.message)
        if x2 < scroll_right and x2 + text_w > scroll_left:
            graphics.DrawText(canvas, font, x2, text_y, col, self.message)


# ============================================================================

class VEML7700Sensor:
    def __init__(self, mqtt_client, topic: str, interval: float):
        self.mqtt = mqtt_client; self.topic = topic; self.interval = interval
        self.running = False; self.sensor = None; self.last_lux = 0.0
        if HAS_VEML7700:
            try:
                self.sensor = adafruit_veml7700.VEML7700(board.I2C())
                print("[veml7700] initialized")
            except Exception as e:
                print(f"[veml7700] init failed: {e}")

    def start(self):
        if self.sensor:
            self.running = True
            threading.Thread(target=self._run, daemon=True).start()

    def stop(self): self.running = False

    def _run(self):
        while self.running:
            try:
                lux = self.sensor.lux; self.last_lux = lux
                self.mqtt.publish(self.topic, json.dumps({"lux": round(lux, 2)}), retain=True)
            except Exception as e:
                print(f"[veml7700] read error: {e}")
            time.sleep(self.interval)


class PIRSensor:
    def __init__(self, mqtt_client, topic: str, gpio_pin: int, poll: float, invert: bool = False):
        self.mqtt = mqtt_client; self.topic = topic; self.gpio = gpio_pin
        self.poll = poll; self.running = False; self.last_state = None
        self._raw_state = None; self._raw_changed_at = 0.0
        self.invert = invert
        if HAS_PIR:
            try:
                GPIO.setwarnings(False); GPIO.setmode(GPIO.BCM)
                GPIO.setup(self.gpio, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
                print(f"[pir] initialized on GPIO{self.gpio}")
            except Exception as e:
                print(f"[pir] init failed: {e}")

    def start(self):
        if HAS_PIR:
            self.running = True
            threading.Thread(target=self._run, daemon=True).start()

    def stop(self): self.running = False

    def _run(self):
        while self.running:
            try:
                raw = bool(GPIO.input(self.gpio))
                if self.invert:
                    raw = not raw
                if raw != self._raw_state:
                    self._raw_state = raw
                    self._raw_changed_at = time.time()
                if (self._raw_state != self.last_state and
                        time.time() - self._raw_changed_at >= 0.5):
                    self.last_state = self._raw_state
                    self.mqtt.publish(self.topic, json.dumps({"motion": self.last_state}), retain=True)
            except Exception as e:
                print(f"[pir] read error: {e}")
            time.sleep(self.poll)


class LD2410Sensor:
    HEAD     = b"\xF4\xF3\xF2\xF1"
    TAIL     = b"\xF8\xF7\xF6\xF5"
    CMD_HEAD = b"\xFD\xFC\xFB\xFA"
    CMD_TAIL = b"\x04\x03\x02\x01"

    def __init__(self, mqtt_client, presence_topic: str, motion_topic: str, port: str, baud: int):
        self.mqtt = mqtt_client
        self.presence_topic = presence_topic
        self.motion_topic = motion_topic
        self.serial = None
        self.running = False
        self._last_pub = 0.0
        self.engineering_mode = False
        self._gate_thresholds = {i: {"move": 50, "still": 30} for i in range(9)}
        if HAS_LD2410:
            try:
                self.serial = serial.Serial(port, baud, timeout=0.5)
                print(f"[ld2410] opened {port}")
            except Exception as e:
                print(f"[ld2410] init failed: {e}")

    def start(self):
        if self.serial:
            self.running = True
            time.sleep(0.1)
            self._enable_engineering_mode()
            threading.Thread(target=self._run, daemon=True).start()

    def stop(self):
        self.running = False
        if self.serial:
            try: self.serial.close()
            except: pass

    def _send_cmd(self, cmd_word: bytes, data: bytes = b""):
        if not self.serial: return
        payload = cmd_word + data
        length = len(payload).to_bytes(2, "little")
        frame = self.CMD_HEAD + length + payload + self.CMD_TAIL
        try:
            self.serial.write(frame)
            time.sleep(0.05)
        except Exception as e:
            print(f"[ld2410] cmd error: {e}")

    def _enable_engineering_mode(self):
        self._send_cmd(b"\xFF\x00")
        time.sleep(0.1)
        self._send_cmd(b"\x62\x00")
        time.sleep(0.1)
        self._send_cmd(b"\xFE\x00")
        self.engineering_mode = True
        print("[ld2410] engineering mode enabled")

    def _disable_engineering_mode(self):
        self._send_cmd(b"\xFF\x00")
        time.sleep(0.1)
        self._send_cmd(b"\x63\x00")
        time.sleep(0.1)
        self._send_cmd(b"\xFE\x00")
        self.engineering_mode = False
        print("[ld2410] engineering mode disabled")

    def _toggle_engineering(self, enable: bool):
        target = self._enable_engineering_mode if enable else self._disable_engineering_mode
        threading.Thread(target=target, daemon=True).start()

    def write_gate_config(self, gate: int, move_thresh: int, still_thresh: int):
        if not self.serial: return
        try:
            self._send_cmd(b"\xFF\x00")
            time.sleep(0.1)
            data = (gate.to_bytes(4, "little") +
                    move_thresh.to_bytes(4, "little") +
                    still_thresh.to_bytes(4, "little"))
            self._send_cmd(b"\x64\x00", data)
            time.sleep(0.1)
            self._send_cmd(b"\xFE\x00")
            print(f"[ld2410] gate {gate} move={move_thresh} still={still_thresh}")
        except Exception as e:
            print(f"[ld2410] gate config error: {e}")

    def _run(self):
        buf = bytearray()
        while self.running:
            try:
                if self.serial.in_waiting:
                    buf.extend(self.serial.read(self.serial.in_waiting))
                    self._process(buf)
                else:
                    time.sleep(0.02)
            except Exception as e:
                print(f"[ld2410] read error: {e}")
                time.sleep(1)

    def _process(self, buf: bytearray):
        while True:
            i = buf.find(self.HEAD)
            if i < 0:
                if len(buf) > 1024: del buf[:-4]
                return
            if i > 0: del buf[:i]
            if len(buf) < 10: return
            dl = buf[4] | (buf[5] << 8)
            total = 4 + 2 + dl + 4
            if len(buf) < total: return
            if bytes(buf[total-4:total]) != self.TAIL:
                del buf[:1]; continue
            data = buf[6:6+dl]
            if data and data[0] == 0x01:
                self._parse_engineering(data)
            elif data and data[0] == 0x02:
                self._parse_basic(data)
            del buf[:total]

    def _parse_basic(self, data: bytes):
        if len(data) < 13 or data[1] != 0xAA: return
        target     = data[2]
        move_dist  = data[3] | (data[4] << 8)
        move_e     = data[5]
        still_dist = data[6] | (data[7] << 8)
        still_e    = data[8]
        now = time.time()
        if now - self._last_pub < 0.5: return
        self._last_pub = now
        self.mqtt.publish(self.presence_topic, json.dumps({
            "presence":       target != 0x00,
            "target_state":   target,
            "move_distance":  move_dist,
            "still_distance": still_dist,
        }), retain=True)
        self.mqtt.publish(self.motion_topic, json.dumps({
            "move_energy":  move_e,
            "still_energy": still_e,
        }))

    def _parse_engineering(self, data: bytes):
        if len(data) < 27 or data[1] != 0xAA: return
        target     = data[2]
        move_dist  = data[3] | (data[4] << 8)
        move_e     = data[5]
        still_dist = data[6] | (data[7] << 8)
        still_e    = data[8]
        move_gates  = list(data[9:18])
        still_gates = list(data[18:27])
        now = time.time()
        if now - self._last_pub < 0.5: return
        self._last_pub = now
        self.mqtt.publish(self.presence_topic, json.dumps({
            "presence":       target != 0x00,
            "target_state":   target,
            "move_distance":  move_dist,
            "still_distance": still_dist,
        }), retain=True)
        payload = {"move_energy": move_e, "still_energy": still_e}
        if self.engineering_mode:
            payload["move_gates"]  = move_gates
            payload["still_gates"] = still_gates
        self.mqtt.publish(self.motion_topic, json.dumps({
            **payload,
        }))


# ============================================================================
# MAIN CLOCK
# ============================================================================

class HUB75Clock:
    def __init__(self, cfg: dict, layout: dict, config_path: str):
        self.cfg = cfg
        self.layout = layout
        self.config_path = config_path
        self.running = False
        self.bucket = "Day"
        self.night_mode = False

        opts = RGBMatrixOptions()
        opts.rows              = 32
        opts.cols              = 64
        opts.chain_length      = 1
        opts.parallel          = 1
        opts.hardware_mapping  = cfg["panel"]["hardware_mapping"]
        opts.gpio_slowdown     = cfg["panel"]["gpio_slowdown"]
        opts.pwm_bits          = cfg["panel"]["pwm_bits"]
        opts.pwm_lsb_nanoseconds = cfg["panel"]["pwm_lsb_nanoseconds"]
        opts.brightness        = cfg["panel"]["brightness"]
        opts.led_rgb_sequence  = "RBG"
        opts.drop_privileges   = False
        self.matrix = RGBMatrix(options=opts)
        self.canvas = self.matrix.CreateFrameCanvas()

        fonts_dir = cfg["fonts"]["fonts_dir"]
        self.font_banner = graphics.Font()
        self.font_banner.LoadFont(cfg["fonts"]["banner_path"])
        self.font_time = graphics.Font()
        self.font_time.LoadFont(cfg["fonts"]["time_path"])
        self.font_alert = graphics.Font()
        self.font_alert.LoadFont(cfg["fonts"]["alert_path"])

        # Publish available fonts
        available = get_available_fonts(fonts_dir)
        self._fonts_available = available

        self.weather_low       = "--"
        self.weather_high      = "--"
        self.weather_condition = "CLEAR"
        self.weather_outdoor   = None

        self.animator = WeatherAnimator(cfg, layout)
        self.alert    = AlertOverlay(cfg, self.font_alert,
                                     cfg["fonts"]["alert_w"],
                                     cfg["fonts"]["alert_h"])

        self.theme_loader = ThemeLoader(cfg["themes"]["themes_dir"])
        self.theme_loader.on_themes_changed = self._on_themes_changed
        default_theme = self.theme_loader.get_theme(cfg["themes"]["default_theme"])
        if default_theme:
            self.animator.set_theme(default_theme)

        topics = cfg["mqtt"]["topics"]
        self.topic_avail = topics["availability"]
        self.mqtt_connected = False
        self.mqtt_client = mqtt.Client(client_id=cfg["mqtt"]["client_id"])
        self.mqtt_client.on_connect    = self._on_connect
        self.mqtt_client.on_message    = self._on_message
        self.mqtt_client.on_disconnect = self._on_disconnect
        if cfg["mqtt"]["username"]:
            self.mqtt_client.username_pw_set(cfg["mqtt"]["username"], cfg["mqtt"]["password"])
        self.mqtt_client.will_set(self.topic_avail, "offline", retain=True)

        sc = cfg["sensors"]
        self.veml = (VEML7700Sensor(self.mqtt_client, topics["lux"], sc["lux_interval"])
                     if sc.get("veml7700_enabled", True) else None)
        self.pir = (PIRSensor(self.mqtt_client, topics["pir"], sc["pir_gpio"], sc["pir_poll_interval"], sc.get("pir_invert", False))
                    if sc.get("pir_enabled", True) else None)
        self.ld2410 = (LD2410Sensor(self.mqtt_client, topics["presence"], topics["motion"],
                                     sc["ld2410_port"], sc["ld2410_baud"])
                       if sc.get("ld2410_enabled", True) else None)
        self._latest_version = None
        self._alert_cycle_timer = 0
        self._alert_show_message = False

    # ------------------------------------------------------------------
    # MQTT
    # ------------------------------------------------------------------
    def _set_engineering_mode(self, enable: bool):
        if enable:
            self.ld2410._enable_engineering_mode()
        else:
            self.ld2410._disable_engineering_mode()
        client_id = self.cfg["mqtt"]["client_id"]
        em_state_topic = (self.cfg["mqtt"]["topics"]
                          .get("engineering_mode", f"{client_id}/engineering_mode") + "/state")
        self.mqtt_client.publish(em_state_topic, "on" if enable else "off", retain=True)

    def _on_connect(self, client, userdata, flags, rc):
        if rc != 0:
            print(f"[mqtt] connect failed rc={rc}"); return
        print("[mqtt] connected")
        self.mqtt_connected = True
        client.publish(self.topic_avail, "online", retain=True)
        client_id = self.cfg["mqtt"]["client_id"]
        topics = self.cfg["mqtt"]["topics"]
        client.publish(topics["version_state"], VERSION, retain=True)
        client.subscribe(topics["update"])
        if self.cfg["update"]["enabled"]:
            threading.Thread(target=self._check_latest_version, daemon=True).start()
        for t in (topics["weather"], topics["config"], topics["alert"],
                  topics.get("gates", f"{client_id}/gates"),
                  topics.get("engineering_mode", f"{client_id}/engineering_mode"),
                  topics.get("bucket", f"{client_id}/bucket"),
                  topics["theme"]):
            client.subscribe(t)
        client.publish(topics["themes_available"],
                       json.dumps(self.theme_loader.available_themes()), retain=True)
        current_theme = self.animator.current_theme
        if current_theme:
            client.publish(topics["theme_state"], current_theme.name, retain=True)
        client.subscribe(f"{client_id}/gate/+/move_thresh")
        client.subscribe(f"{client_id}/gate/+/still_thresh")
        # Publish available fonts
        client.publish(topics["fonts_available"],
                       json.dumps(self._fonts_available), retain=True)
        # Publish initial states
        client.publish(f"{client_id}/brightness/state",
                       str(self.cfg["panel"]["brightness"]), retain=True)
        em_state_topic = topics.get("engineering_mode", f"{client_id}/engineering_mode") + "/state"
        if self.ld2410 is not None:
            client.publish(em_state_topic, "on" if self.ld2410.engineering_mode else "off", retain=True)
        if self.cfg["ha_discovery"]["enabled"]:
            self._publish_discovery()

    def _on_disconnect(self, client, userdata, rc):
        print(f"[mqtt] disconnected rc={rc}")

    def _on_message(self, client, userdata, msg):
        client_id = self.cfg["mqtt"]["client_id"]
        topics = self.cfg["mqtt"]["topics"]

        # Gate threshold topics carry plain numeric payloads, not JSON
        tp = msg.topic.split('/')
        if (len(tp) == 4 and tp[0] == client_id and tp[1] == "gate"
                and tp[3] in ("move_thresh", "still_thresh")):
            if self.ld2410 is not None:
                try:
                    gate = int(tp[2])
                    value = int(float(msg.payload.decode()))
                    gt = self.ld2410._gate_thresholds[gate]
                    if tp[3] == "move_thresh":
                        gt["move"] = value
                    else:
                        gt["still"] = value
                    self.ld2410.write_gate_config(gate, gt["move"], gt["still"])
                    self.mqtt_client.publish(msg.topic, str(value), retain=True)
                except Exception as e:
                    print(f"[gates] threshold error: {e}")
            return

        try:
            payload = json.loads(msg.payload.decode()) if msg.payload else {}
        except Exception:
            payload = msg.payload.decode(errors="replace").strip()
        if not isinstance(payload, (dict, str)):
            return

        if msg.topic == topics["weather"]:
            if "low_temp"  in payload:
                try: self.weather_low  = str(int(payload["low_temp"]))
                except: pass
            if "high_temp" in payload:
                try: self.weather_high = str(int(payload["high_temp"]))
                except: pass
            if "condition" in payload:
                c = (payload["condition"] or "CLEAR").upper().strip()
                self.animator.set_condition(c); self.weather_condition = c
            if "outdoor_temp" in payload and payload["outdoor_temp"] is not None:
                self.weather_outdoor = str(int(payload["outdoor_temp"]))
            print(f"[weather] {self.weather_low}/{self.weather_high} {self.weather_condition}")

        elif msg.topic == topics["config"]:
            needs_save = False
            restart_needed = False

            if "brightness" in payload:
                b = max(1, min(100, int(payload["brightness"])))
                self.matrix.brightness = b
                self.cfg["panel"]["brightness"] = b
                needs_save = True
                self.mqtt_client.publish(f"{client_id}/brightness/state", str(b), retain=True)
                print(f"[config] brightness={b}")

            if "engineering_mode" in payload:
                em = bool(payload["engineering_mode"])
                threading.Thread(target=self._set_engineering_mode, args=(em,), daemon=True).start()

            if "night_mode" in payload:
                self.night_mode = bool(payload["night_mode"])
                self.animator.set_night_mode(self.night_mode)
                print(f"[config] night_mode={self.night_mode}")

            if "bucket" in payload:
                self._apply_bucket(payload["bucket"])

            if "colors" in payload:
                # Update individual color keys
                # When a _day key is set, auto-derive the _night version at 33% brightness
                for key, val in payload["colors"].items():
                    if key in self.cfg["colors"]:
                        if isinstance(val, (list, tuple)):
                            r, g, b = int(val[0]), int(val[1]), int(val[2])
                            self.cfg["colors"][key] = rgb_to_hex(r, g, b)
                        else:
                            self.cfg["colors"][key] = val
                        # Auto-derive night variant
                        if key.endswith("_day"):
                            night_key = key.replace("_day", "_night")
                            r, g, b = parse_color(self.cfg["colors"][key])
                            self.cfg["colors"][night_key] = rgb_to_hex(
                                max(0, r // 3), max(0, g // 3), max(0, b // 3))
                needs_save = True
                print(f"[config] colors updated")

            if "font_time" in payload:
                fname = payload["font_time"]
                fonts_dir = self.cfg["fonts"]["fonts_dir"]
                fpath = os.path.join(fonts_dir, fname)
                if os.path.exists(fpath):
                    self.cfg["fonts"]["time_name"] = fname
                    needs_save = True
                    restart_needed = True
                    print(f"[config] font_time={fname} - will restart")

            if "font_banner" in payload:
                fname = payload["font_banner"]
                fonts_dir = self.cfg["fonts"]["fonts_dir"]
                fpath = os.path.join(fonts_dir, fname)
                if os.path.exists(fpath):
                    self.cfg["fonts"]["banner_name"] = fname
                    needs_save = True
                    restart_needed = True
                    print(f"[config] font_banner={fname} - will restart")

            if needs_save:
                save_config(self.config_path, self.cfg)

            if restart_needed:
                print("[config] restarting for font change...")
                time.sleep(0.5)
                os.execv(sys.executable, [sys.executable] + sys.argv)

        elif msg.topic == topics["alert"]:
            if not payload or payload.get("clear"):
                self.alert.clear()
            else:
                self.alert.set_alert(payload.get("message", ""), payload.get("expires"))

        elif msg.topic == topics.get("gates", f"{client_id}/gates"):
            if self.ld2410 is not None:
                if "gates" in payload:
                    for g in payload["gates"]:
                        self.ld2410.write_gate_config(
                            int(g["gate"]),
                            int(g.get("move", 50)),
                            int(g.get("still", 30)),
                        )
                elif "gate" in payload:
                    self.ld2410.write_gate_config(
                        int(payload["gate"]),
                        int(payload.get("move", 50)),
                        int(payload.get("still", 30)),
                    )
            if "engineering_mode" in payload:
                em = bool(payload["engineering_mode"])
                threading.Thread(target=self._set_engineering_mode, args=(em,), daemon=True).start()

        elif msg.topic == topics.get("engineering_mode", f"{client_id}/engineering_mode"):
            if "engineering_mode" in payload:
                em = bool(payload["engineering_mode"])
                threading.Thread(target=self._set_engineering_mode, args=(em,), daemon=True).start()

        elif msg.topic == topics.get("bucket", f"{client_id}/bucket"):
            if "bucket" in payload:
                self._apply_bucket(payload["bucket"])

        elif msg.topic == topics.get("theme"):
            theme_name = payload if isinstance(payload, str) else payload.get("theme", "")
            theme = self.theme_loader.get_theme(theme_name)
            if theme:
                self.animator.set_theme(theme)
                self.mqtt_client.publish(topics["theme_state"], theme.name, retain=True)
                print(f"[theme] set to {theme.name}")
            else:
                print(f"[theme] unknown theme: {theme_name}")

        elif msg.topic == topics.get("update"):
            raw = msg.payload.decode().strip() if msg.payload else ""
            action = raw if isinstance(payload, str) else payload.get("action", "")
            if raw == "install" or action == "install":
                threading.Thread(target=self._do_update, daemon=True).start()

    def _on_themes_changed(self, themes: dict):
        names = sorted(themes.keys())
        self.mqtt_client.publish(
            self.cfg["mqtt"]["topics"]["themes_available"],
            json.dumps(names), retain=True)
        print(f"[theme] themes reloaded: {names}")
        self._publish_theme_discovery()

    def _publish_theme_discovery(self):
        prefix    = self.cfg["ha_discovery"]["prefix"]
        topics    = self.cfg["mqtt"]["topics"]
        client_id = self.cfg["mqtt"]["client_id"]
        dev_name  = self.cfg["ha_discovery"]["ha_discovery_name"]
        device    = {"identifiers": [client_id], "name": dev_name,
                     "model": "HUB75 Smart Clock", "manufacturer": "DIY"}
        if self.cfg["ha_discovery"].get("ha_discovery_area"):
            device["suggested_area"] = self.cfg["ha_discovery"]["ha_discovery_area"]
        avail = [{"topic": self.topic_avail}]
        self.mqtt_client.publish(
            f"{prefix}/select/{client_id}_theme/config",
            json.dumps({
                "name":          "Theme",
                "unique_id":     f"{client_id}_theme",
                "device":        device,
                "availability":  avail,
                "state_topic":   topics["theme_state"],
                "command_topic": topics["theme"],
                "options":       self.theme_loader.available_themes(),
                "entity_category": "config",
                "icon":          "mdi:palette",
            }), retain=True)

    def _apply_bucket(self, bucket: str):
        self.bucket = bucket
        self.night_mode = bucket in ("Late Evening", "Night")
        self.animator.set_night_mode(self.night_mode)
        print(f"[config] bucket={bucket} night_mode={self.night_mode}")

    def _check_latest_version(self):
        try:
            import urllib.request, json as _json
            repo = self.cfg["update"]["github_repo"]
            url = f"https://api.github.com/repos/{repo}/releases/latest"
            with urllib.request.urlopen(url, timeout=10) as r:
                data = _json.loads(r.read())
            self._latest_version = data["tag_name"].lstrip("v")
            topics = self.cfg["mqtt"]["topics"]
            self.mqtt_client.publish(
                topics["update_latest"],
                self._latest_version, retain=True)
            print(f"[update] latest version: {self._latest_version}")
        except Exception as e:
            print(f"[update] version check failed: {e}")

    def _do_update(self):
        try:
            repo_path = self.cfg["update"]["repo_path"]
            print("[update] fetching latest tags...")
            subprocess.run(["git", "-C", repo_path, "fetch", "--tags"],
                          capture_output=True, text=True, timeout=60)
            result = subprocess.run(
                ["git", "-C", repo_path, "describe", "--tags", "--abbrev=0"],
                capture_output=True, text=True, timeout=10)
            latest_tag = result.stdout.strip()
            if not latest_tag:
                print("[update] no tags found, falling back to git pull")
                subprocess.run(["git", "-C", repo_path, "pull"],
                              capture_output=True, text=True, timeout=60)
            else:
                subprocess.run(["git", "-C", repo_path, "checkout", latest_tag],
                              capture_output=True, text=True, timeout=30)
                print(f"[update] checked out {latest_tag}")
            time.sleep(1)
            os.execv(sys.executable, [sys.executable] + sys.argv)
        except Exception as e:
            print(f"[update] failed: {e}")

    def _publish_discovery(self):
        prefix    = self.cfg["ha_discovery"]["prefix"]
        topics    = self.cfg["mqtt"]["topics"]
        client_id = self.cfg["mqtt"]["client_id"]
        dev_name  = self.cfg["ha_discovery"]["ha_discovery_name"]

        device = {
            "identifiers": [client_id],
            "name":         dev_name,
            "model":        "HUB75 Smart Clock",
            "manufacturer": "DIY",
        }
        if self.cfg["ha_discovery"].get("ha_discovery_area"):
            device["suggested_area"] = self.cfg["ha_discovery"]["ha_discovery_area"]

        avail      = [{"topic": self.topic_avail}]
        em_state_t = topics.get("engineering_mode", f"{client_id}/engineering_mode") + "/state"

        # --- Sensors ---
        sensor_configs = []
        if self.veml is not None:
            sensor_configs.append(
                {"name": "Illuminance", "unique_id": f"{client_id}_lux",
                 "state_topic": topics["lux"], "value_template": "{{ value_json.lux }}",
                 "unit_of_measurement": "lx", "device_class": "illuminance", "state_class": "measurement"})
        if self.ld2410 is not None:
            sensor_configs += [
                {"name": "Move Energy", "unique_id": f"{client_id}_move_energy",
                 "state_topic": topics["motion"], "value_template": "{{ value_json.move_energy }}",
                 "state_class": "measurement"},
                {"name": "Still Energy", "unique_id": f"{client_id}_still_energy",
                 "state_topic": topics["motion"], "value_template": "{{ value_json.still_energy }}",
                 "state_class": "measurement"},
                {"name": "Move Distance", "unique_id": f"{client_id}_move_distance",
                 "state_topic": topics["presence"], "value_template": "{{ value_json.move_distance }}",
                 "unit_of_measurement": "cm", "device_class": "distance", "state_class": "measurement"},
                {"name": "Still Distance", "unique_id": f"{client_id}_still_distance",
                 "state_topic": topics["presence"], "value_template": "{{ value_json.still_distance }}",
                 "unit_of_measurement": "cm", "device_class": "distance", "state_class": "measurement"},
            ]
        for s in sensor_configs:
            self.mqtt_client.publish(
                f"{prefix}/sensor/{s['unique_id']}/config",
                json.dumps({**s, "device": device, "availability": avail}), retain=True)

        # --- Gate energy diagnostic sensors (only available when engineering mode is on) ---
        if self.ld2410 is not None:
            gate_avail = [
                {"topic": self.topic_avail},
                {"topic": em_state_t, "payload_available": "on", "payload_not_available": "off"},
            ]
            for gate in range(9):
                for energy_type, label in (("move", "Move"), ("still", "Still")):
                    uid = f"{client_id}_g{gate}_{energy_type}_energy"
                    self.mqtt_client.publish(
                        f"{prefix}/sensor/{uid}/config",
                        json.dumps({
                            "name":           f"Gate {gate} {label} Energy",
                            "unique_id":      uid,
                            "device":         device,
                            "availability":   gate_avail,
                            "availability_mode": "all",
                            "state_topic":    topics["motion"],
                            "value_template": f"{{{{ value_json.{energy_type}_gates[{gate}] }}}}",
                            "state_class":    "measurement",
                            "entity_category": "diagnostic",
                        }), retain=True)

        # --- Binary sensors ---
        binary_configs = []
        if self.pir is not None:
            binary_configs.append(
                {"name": "Motion", "unique_id": f"{client_id}_pir",
                 "state_topic": topics["pir"], "value_template": "{{ value_json.motion }}",
                 "payload_on": "True", "payload_off": "False", "device_class": "motion"})
        if self.ld2410 is not None:
            binary_configs.append(
                {"name": "Presence", "unique_id": f"{client_id}_presence",
                 "state_topic": topics["presence"], "value_template": "{{ value_json.presence }}",
                 "payload_on": "True", "payload_off": "False", "device_class": "occupancy"})
        for s in binary_configs:
            self.mqtt_client.publish(
                f"{prefix}/binary_sensor/{s['unique_id']}/config",
                json.dumps({**s, "device": device, "availability": avail}), retain=True)

        # --- Number: brightness ---
        self.mqtt_client.publish(
            f"{prefix}/number/{client_id}_brightness/config",
            json.dumps({
                "name":             "Brightness",
                "unique_id":        f"{client_id}_brightness",
                "device":           device,
                "availability":     avail,
                "command_topic":    topics["config"],
                "command_template": '{"brightness": {{ value }}}',
                "state_topic":      f"{client_id}/brightness/state",
                "min": 1, "max": 100, "step": 1,
                "entity_category":  "config",
            }), retain=True)

        # --- Number: gate thresholds (18 entities) ---
        if self.ld2410 is not None:
            for gate in range(9):
                for thresh_type, label in (("move", "Move"), ("still", "Still")):
                    uid       = f"{client_id}_g{gate}_{thresh_type}_thresh"
                    cmd_topic = f"{client_id}/gate/{gate}/{thresh_type}_thresh"
                    self.mqtt_client.publish(
                        f"{prefix}/number/{uid}/config",
                        json.dumps({
                            "name":            f"Gate {gate} {label} Threshold",
                            "unique_id":       uid,
                            "device":          device,
                            "availability":    avail,
                            "command_topic":   cmd_topic,
                            "state_topic":     cmd_topic,
                            "min": 0, "max": 100, "step": 5,
                            "entity_category": "config",
                        }), retain=True)

        # --- Switch: engineering mode ---
        if self.ld2410 is not None:
            self.mqtt_client.publish(
                f"{prefix}/switch/{client_id}_engineering_mode/config",
                json.dumps({
                    "name":          "Engineering Mode",
                    "unique_id":     f"{client_id}_engineering_mode",
                    "device":        device,
                    "availability":  avail,
                    "command_topic": topics["config"],
                    "payload_on":    '{"engineering_mode": true}',
                    "payload_off":   '{"engineering_mode": false}',
                    "state_topic":   em_state_t,
                    "state_on":      "on",
                    "state_off":     "off",
                    "entity_category": "config",
                }), retain=True)

        # --- Update entity ---
        self.mqtt_client.publish(
            f"{prefix}/update/{client_id}_firmware/config",
            json.dumps({
                "name":                  "Firmware",
                "unique_id":             f"{client_id}_firmware",
                "device":                device,
                "availability":          avail,
                "state_topic":           topics["version_state"],
                "latest_version_topic":  topics["update_latest"],
                "command_topic":         topics["update"],
                "payload_install":       "install",
                "entity_category":       "config",
                "device_class":          "firmware",
            }), retain=True)

        # --- Select: theme ---
        self.mqtt_client.publish(
            f"{prefix}/select/{client_id}_theme/config",
            json.dumps({
                "name":          "Theme",
                "unique_id":     f"{client_id}_theme",
                "device":        device,
                "availability":  avail,
                "state_topic":   topics["theme_state"],
                "command_topic": topics["theme"],
                "options":       self.theme_loader.available_themes(),
                "entity_category": "config",
                "icon":          "mdi:palette",
            }), retain=True)

        print("[mqtt] HA discovery published")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def start(self):
        print(f"[clock] starting - {self.cfg['panel']['width']}x{self.cfg['panel']['height']}")
        try:
            self.mqtt_client.reconnect_delay_set(min_delay=5, max_delay=30)
            self.mqtt_client.connect_async(self.cfg["mqtt"]["broker"], self.cfg["mqtt"]["port"], 60)
            self.mqtt_client.loop_start()
        except Exception as e:
            print(f"[mqtt] connect error: {e} (will retry)")
        if self.veml   is not None: self.veml.start()
        if self.pir    is not None: self.pir.start()
        if self.ld2410 is not None: self.ld2410.start()
        self.running = True
        self._render_loop()

    def stop(self):
        print("[clock] stopping")
        self.running = False
        try:
            self.mqtt_client.publish(self.topic_avail, "offline", retain=True)
            self.mqtt_client.loop_stop(); self.mqtt_client.disconnect()
        except: pass
        if self.veml   is not None: self.veml.stop()
        if self.pir    is not None: self.pir.stop()
        if self.ld2410 is not None: self.ld2410.stop()
        if self.pir is not None:
            try: GPIO.cleanup()
            except: pass

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------
    def _render_loop(self):
        try:
            while self.running:
                fps = (self.cfg["animation"]["fps_night"]
                       if self.night_mode else self.cfg["animation"]["fps"])
                t0 = time.time()
                self.canvas.Clear()
                banner_top    = self.layout["banner"]["top"]
                banner_bottom = self.layout["banner"]["bottom"]
                self.animator.update()
                alert_active = self.alert.is_active()
                if alert_active:
                    frames_per_cycle = fps * 20
                    self._alert_cycle_timer += 1
                    if self._alert_cycle_timer >= frames_per_cycle:
                        self._alert_show_message = not self._alert_show_message
                        self._alert_cycle_timer = 0
                else:
                    self._alert_cycle_timer = 0
                    self._alert_show_message = False
                self.animator.draw(self.canvas, alert_active=False)
                if alert_active:
                    self.animator._draw_hazard_stripes(self.canvas)
                self.alert.update()
                self._draw_banner()
                self._draw_time()
                if alert_active:
                    self.alert.draw(
                        self.canvas, banner_top, banner_bottom,
                        self.cfg["panel"]["width"], self.cfg["panel"]["height"])
                self.canvas = self.matrix.SwapOnVSync(self.canvas)
                dt = time.time() - t0
                sleep = (1.0 / fps) - dt
                if sleep > 0: time.sleep(sleep)
        except KeyboardInterrupt:
            pass

    def _col(self, key: str) -> graphics.Color:
        """Get a graphics.Color by key. Theme colors override config colors."""
        theme = self.animator.current_theme
        if theme is not None and key in theme.colors:
            r, g, b = hex_to_rgb(theme.colors[key])
            return graphics.Color(r, g, b)
        colors = self.cfg["colors"]
        if self.night_mode:
            night_key = key + "_night"
            if night_key in colors:
                r, g, b = parse_color(colors[night_key])
                return graphics.Color(r, g, b)
        day_key = key + "_day"
        if day_key in colors:
            r, g, b = parse_color(colors[day_key])
            return graphics.Color(r, g, b)
        if key in colors:
            r, g, b = parse_color(colors[key])
            return graphics.Color(r, g, b)
        return graphics.Color(200, 200, 200)

    def _display_condition(self) -> str:
        return {
            "SUNNY":           "SUNNY",
            "CLEAR":           "CLEAR",
            "PARTLYCLOUDY":    "CLOUDY",
            "CLOUDY":          "CLOUDY",
            "FOG":             "CLOUDY",
            "RAIN":            "RAIN",
            "SNOW":            "SNOW",
            "SLEET":           "SLEET",
            "TSTORM":          "TSTORM",
            "ICE":             "ICE",
            "BLIZZARD":        "BLIZZARD",
            "HURRICANE":       "HURRCN",
            "TROPICAL_STORM":  "T-STORM",
            "FLOOD":           "FLOOD",
            "FREEZING_RAIN":   "FRZRAIN",
            "FREEZING_DRIZZLE": "FRZDRIZ",
            "DUST":            "DUSTY",
            "SMOKE":           "SMOKY",
            "WINDY":           "WINDY",
        }.get(self.weather_condition, self.weather_condition)

    def _draw_banner(self):
        if not self.mqtt_connected:
            tl = self.layout
            font_w = self.cfg["fonts"]["banner_w"]
            font_h = self.cfg["fonts"]["banner_h"]
            panel_w = self.cfg["panel"]["width"]
            banner_top = tl["banner"]["top"]
            banner_bottom = tl["banner"]["bottom"]
            region_h = banner_bottom - banner_top + 1
            baseline = banner_top + (region_h - font_h) // 2 + font_h - 1
            msg = "Connecting..."
            x = max(0, (panel_w - len(msg) * font_w) // 2)
            col = graphics.Color(80, 80, 80)
            graphics.DrawText(self.canvas, self.font_banner, x, baseline, col, msg)
            return
        tl       = self.layout
        font_w   = self.cfg["fonts"]["banner_w"]
        font_h   = self.cfg["fonts"]["banner_h"]
        panel_w  = self.cfg["panel"]["width"]
        banner_top    = tl["banner"]["top"]
        banner_bottom = tl["banner"]["bottom"]
        region_h = banner_bottom - banner_top + 1
        baseline = banner_top + (region_h - font_h) // 2 + font_h - 1

        low_text  = f"{self.weather_low}\u00B0"
        high_text = f"{self.weather_high}\u00B0"

        if self.alert.is_active():
            if self._alert_show_message:
                # Full-width scrolling alert message \u2014 temps hidden
                self.alert.draw_banner_scroll(self.canvas, banner_top, banner_bottom,
                                              0, panel_w,
                                              self.font_banner, font_w, font_h)
            else:
                # Temps visible, condition word replaced with "ALERT"
                graphics.DrawText(self.canvas, self.font_banner, 1, baseline,
                                 self._col("low_temp"), low_text)
                high_x = panel_w - len(high_text) * font_w - 1
                graphics.DrawText(self.canvas, self.font_banner, high_x, baseline,
                                 self._col("high_temp"), high_text)
                alert_label = "ALERT"
                alert_x = max(0, (panel_w - len(alert_label) * font_w) // 2)
                alert_rgb = parse_color(self.cfg["colors"]["alert_bg"])
                graphics.DrawText(self.canvas, self.font_banner, alert_x, baseline,
                                 graphics.Color(*alert_rgb), alert_label)
        else:
            graphics.DrawText(self.canvas, self.font_banner, 1, baseline,
                             self._col("low_temp"), low_text)
            high_x = panel_w - len(high_text) * font_w - 1
            graphics.DrawText(self.canvas, self.font_banner, high_x, baseline,
                             self._col("high_temp"), high_text)
            cond_text = self._display_condition()
            cond_x = max(0, (panel_w - len(cond_text) * font_w) // 2)
            graphics.DrawText(self.canvas, self.font_banner, cond_x, baseline,
                             self._col("condition"), cond_text)

    def _draw_time(self):
        tl      = self.layout["time"]
        font_w  = self.cfg["fonts"]["time_w"]
        font_h  = self.cfg["fonts"]["time_h"]
        panel_w = self.cfg["panel"]["width"]

        now = datetime.now()
        if self.cfg["time_format"]["use_24h"]:
            time_str = now.strftime("%H:%M")
        else:
            time_str = now.strftime("%I:%M").lstrip("0") or "12:00"

        if self.cfg["time_format"]["blink_colon"] and now.second % 2:
            time_str = time_str.replace(":", " ")

        col = self._col("time")

        zone_left  = tl.get("zone_left",  0)
        zone_right = tl.get("zone_right", panel_w - 1)
        zone_w     = zone_right - zone_left + 1
        text_w     = len(time_str) * font_w
        x          = zone_left + max(0, (zone_w - text_w) // 2)

        region_h  = tl["bottom"] - tl["top"] + 1
        baseline  = tl["top"] + (region_h + font_h) // 2 - 4

        if tl.get("outline", True) and not self.night_mode:
            ol = parse_color(self.cfg["colors"].get("outline", [0, 0, 0]))
            ol_col = graphics.Color(ol[0], ol[1], ol[2])
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    if dx == 0 and dy == 0: continue
                    graphics.DrawText(self.canvas, self.font_time,
                                      x + dx, baseline + dy, ol_col, time_str)

        graphics.DrawText(self.canvas, self.font_time, x, baseline, col, time_str)


# ============================================================================
# ENTRY POINT
# ============================================================================

def main():
    config_path = os.environ.get("CLOCK_CONFIG", "/etc/hub75-clock/config.yaml")

    cfg   = load_config(config_path)
    clock = HUB75Clock(cfg, DEFAULT_LAYOUT, config_path)

    def handle_sig(signum, frame):
        clock.running = False

    signal.signal(signal.SIGTERM, handle_sig)
    signal.signal(signal.SIGINT,  handle_sig)

    try:
        clock.start()
    finally:
        clock.stop()


if __name__ == "__main__":
    main()