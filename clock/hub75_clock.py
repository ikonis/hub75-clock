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
import threading
import random
import re
import importlib.util
import subprocess
import queue
from datetime import datetime, timezone
from typing import List, Optional, Tuple

import yaml
from rgbmatrix import RGBMatrix, RGBMatrixOptions, graphics
import paho.mqtt.client as mqtt
from theme_loader import ThemeLoader, Theme


DEFAULT_ANIMATION_SETTINGS = {
    "rocket": {"speed": 0.25},
    "meteor": {"speed": 0.30},
    "hot_air_balloon": {"speed": 0.5},
    "santa": {"speed": 0.5},
    "tumbleweed": {"speed": 0.5},
    "fireworks": {"speed": 1.0},
    "flutterflies": {"speed": 1.0},
    "snake": {"speed": 1.0},
    "clouds": {
        "speed": 1.0,
        "particle_speed": 1.0,
        "rain_speed": 1.0,
        "heavy_rain_speed": 1.0,
        "snow_speed": 1.0,
        "sleet_fast_speed": 1.0,
        "sleet_slow_speed": 1.0,
    },
}


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
            "theme":            "hub75_clock/theme/set",
            "theme_state":      "hub75_clock/theme/state",
            "themes_available": "hub75_clock/themes/available",
            "ld2410_params":    "hub75_clock/ld2410/params",
            "ld2410_read":      "hub75_clock/ld2410/read",
        },
    },
    "ha_discovery": {
        "enabled":            True,
        "prefix":             "homeassistant",
        "ha_discovery_name":  "HUB75 Clock",
        "ha_discovery_area":  "",
    },
    "theme_builder": {
        "mode": "off",
        "service_name": "hub75-theme-builder",
        "host": "0.0.0.0",
        "port": 8765,
        "url": "",
    },
    "ld2410_tuner": {
        "mode": "off",
        "service_name": "hub75-ld2410-tuner",
        "host": "0.0.0.0",
        "port": 8766,
        "url": "",
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
        "time_day":        "#F0F0F0",
        "low_temp_day":    "#00CCFF",
        "high_temp_day":   "#FF8C00",
        "condition_day":   "#909090",
        "alert_text":      "#FFFFFF",
        "alert_bg":        "#CC0000",
        "cloud_day":       [70, 70, 70],
        "sun_day":         [220, 160, 30],
        "ice_day":         [80, 140, 160],
        "outline":         [0, 0, 0],
        "sky_day":         "#000820",
    },
    "animation": {
        "fps":                        90,
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
    "themes": {
        "themes_dir":    "/etc/hub75-clock/themes",
        "default_theme": "Day",
    },
    "animations": {
        "animations_dir": "/etc/hub75-clock/animations",
        "sprites_dir": "/etc/hub75-clock/sprites",
        "settings_path": "/etc/hub75-clock/animations.yaml",
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
    try:
        cfg["animation"]["fps"] = max(1, int(cfg["animation"].get("fps", 90)))
    except Exception:
        cfg["animation"]["fps"] = 90
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
        save.pop("animation_settings", None)
        with open(config_path, 'w') as f:
            yaml.dump(save, f, default_flow_style=False, allow_unicode=True)
        print(f"[config] saved to {config_path}")
    except Exception as e:
        print(f"[config] save failed: {e}")


def load_animation_settings(path: str) -> dict:
    try:
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        if not isinstance(data, dict):
            print(f"[config] animation settings ignored: {path} is not a mapping")
            return {}
        added_names = []
        for name, defaults_for_animation in DEFAULT_ANIMATION_SETTINGS.items():
            if name in data:
                continue
            data[name] = defaults_for_animation
            added_names.append(name)
        if added_names:
            parent = os.path.dirname(path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            with open(path, "a", encoding="utf-8") as f:
                f.write("\n# Added automatically for new animation defaults.\n")
                for name in added_names:
                    defaults_for_animation = DEFAULT_ANIMATION_SETTINGS[name]
                    f.write(f"\n{name}:\n")
                    for key, value in defaults_for_animation.items():
                        f.write(f"  {key}: {value}\n")
            print(f"[config] added missing animation defaults to {path}")
        print(f"[config] loaded {path}")
        return data
    except FileNotFoundError:
        try:
            parent = os.path.dirname(path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write("# Per-animation speed multipliers.\n")
                f.write("# Added automatically; edit these values to tune runtime speed.\n")
                for name, defaults_for_animation in DEFAULT_ANIMATION_SETTINGS.items():
                    f.write(f"\n{name}:\n")
                    for key, value in defaults_for_animation.items():
                        f.write(f"  {key}: {value}\n")
            print(f"[config] created {path}")
            return dict(DEFAULT_ANIMATION_SETTINGS)
        except Exception as e:
            print(f"[config] animation settings create failed: {e}")
            return {}
    except Exception as e:
        print(f"[config] animation settings ignored: {e}")
        return {}


def get_available_fonts(fonts_dir: str) -> List[str]:
    """Return sorted list of .bdf filenames in the fonts directory."""
    try:
        return sorted([f for f in os.listdir(fonts_dir) if f.endswith('.bdf')])
    except Exception:
        return []


try:
    from watchdog.observers import Observer as _WatchdogObserver
    from watchdog.events import FileSystemEventHandler as _WatchdogHandler
    _WATCHDOG_OK = True
except ImportError:
    _WATCHDOG_OK = False


class AnimationLoader:
    """Drop-in animation loader. Watches a directory for .py files, imports each,
    and registers the Animation class found inside by its `name` attribute."""

    def __init__(self, animations_dir: str, settings: dict = None):
        self._dir = animations_dir
        self._settings = settings or {}
        self._registry: dict = {}
        self._observer = None
        os.makedirs(animations_dir, exist_ok=True)
        self._scan()
        self._start_watcher()

    def _scan(self):
        try:
            entries = list(os.scandir(self._dir))
        except OSError:
            return
        for entry in entries:
            if not entry.name.endswith(".py") or not entry.is_file():
                continue
            self._load_file(entry.path)

    def _load_file(self, path: str):
        try:
            mod_name = "hub75_anim_" + os.path.basename(path)[:-3]
            spec = importlib.util.spec_from_file_location(mod_name, path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            cls = getattr(mod, "Animation", None)
            if cls is None:
                print(f"[animations] warning: {path} has no Animation class — skipping")
                return
            anim_name = getattr(cls, "name", None)
            if not anim_name:
                print(f"[animations] warning: Animation in {path} has no name — skipping")
                return
            self._apply_settings(anim_name, cls)
            self._registry[anim_name] = cls
            print(f"[animations] loaded: {anim_name}")
        except Exception as e:
            print(f"[animations] warning: failed to load {path}: {e}")

    def _apply_settings(self, anim_name: str, cls):
        settings = self._settings.get(anim_name, {})
        if not isinstance(settings, dict):
            return
        applied = []
        for key, value in settings.items():
            if key.startswith("_") or not isinstance(value, (int, float)):
                continue
            if hasattr(cls, key):
                setattr(cls, key, float(value))
                applied.append(f"{key}={value}")
        if applied:
            print(f"[animations] settings {anim_name}: {', '.join(applied)}")

    def _reload(self):
        self._registry = {}
        self._scan()

    def _start_watcher(self):
        if not _WATCHDOG_OK:
            return
        loader = self

        class _H(_WatchdogHandler):
            def on_any_event(self, event):
                if event.is_directory:
                    return
                src = getattr(event, "src_path", "")
                dst = getattr(event, "dest_path", "")
                if src.endswith(".py") or dst.endswith(".py"):
                    loader._reload()

        self._observer = _WatchdogObserver()
        self._observer.schedule(_H(), self._dir, recursive=False)
        self._observer.daemon = True
        self._observer.start()

    def get(self, name: str):
        return self._registry.get(name)

    def available(self) -> list:
        return sorted(self._registry.keys())

    def stop(self):
        if self._observer:
            self._observer.stop()
            self._observer.join()
            self._observer = None


class CameoManager:
    def __init__(self, loader: AnimationLoader, cfg: dict):
        self._loader = loader
        self._cfg = cfg
        self._active = None
        self._persistent_cloud = None
        self._persistent_others: list = []

    def reset(self):
        self._active = None

    def _cfg_for_cameo(self, cameo_cfg: dict):
        cfg = dict(self._cfg)
        cfg["_cameo"] = dict(cameo_cfg or {})
        return cfg

    def setup_persistent(self, cameos: list, animator):
        self._persistent_cloud = None
        self._persistent_others = []
        for cameo_cfg in cameos:
            cls = self._loader.get(cameo_cfg.get("name", ""))
            if cls is None or not getattr(cls, "persistent", False):
                continue
            try:
                inst = cls(animator.width, animator.height, self._cfg_for_cameo(cameo_cfg), animator)
                if getattr(cls, "name", "") == "clouds":
                    self._persistent_cloud = inst
                else:
                    self._persistent_others.append(inst)
            except Exception as e:
                print(f"[animations] warning: failed to spawn persistent {cls}: {e}")

    def update(self, cameos: list, fps: float, animator):
        if self._persistent_cloud is not None:
            try:
                self._persistent_cloud.update()
            except Exception as e:
                print(f"[animations] warning: persistent cloud update error: {e}")

        for p in self._persistent_others:
            try:
                p.update()
            except Exception as e:
                print(f"[animations] warning: persistent update error: {e}")

        if self._active is not None:
            try:
                self._active.update()
                if self._active.is_done():
                    self._active = None
            except Exception as e:
                print(f"[animations] warning: active update error: {e}")
                self._active = None

        if self._active is None:
            winners = []
            for cameo_cfg in cameos:
                cls = self._loader.get(cameo_cfg.get("name", ""))
                if cls is None or getattr(cls, "persistent", False):
                    continue
                prob = cameo_cfg.get("chance_per_minute", 0) / 60.0 / fps
                if random.random() < prob:
                    winners.append((cls, cameo_cfg))
            if winners:
                cls, cameo_cfg = random.choice(winners)
                try:
                    self._active = cls(animator.width, animator.height, self._cfg_for_cameo(cameo_cfg), animator)
                except Exception as e:
                    print(f"[animations] warning: failed to spawn {cls}: {e}")

    def _draw_persistent_layer(self, canvas, layer: str):
        failed = []
        for p in self._persistent_others:
            if getattr(p, "layer", "foreground") != layer:
                continue
            try:
                p.draw(canvas)
            except Exception as e:
                print(f"[animations] warning: persistent draw error: {e}")
                failed.append(p)
        if failed:
            self._persistent_others = [
                p for p in self._persistent_others if p not in failed
            ]

    def draw_celestial(self, canvas):
        self._draw_persistent_layer(canvas, "celestial")
        if (self._active is not None and
                getattr(self._active, "layer", "foreground") == "celestial"):
            try:
                self._active.draw(canvas)
            except Exception as e:
                print(f"[animations] warning: draw error: {e}")
                self._active = None

    def draw_clouds(self, canvas):
        if self._persistent_cloud is not None:
            try:
                self._persistent_cloud.draw(canvas)
            except Exception as e:
                print(f"[animations] warning: cloud draw error: {e}")
                self._persistent_cloud = None

    def draw_foreground(self, canvas):
        self._draw_persistent_layer(canvas, "foreground")
        if (self._active is not None and
                getattr(self._active, "layer", "foreground") == "foreground"):
            try:
                self._active.draw(canvas)
            except Exception as e:
                print(f"[animations] warning: draw error: {e}")
                self._active = None


class _TrackedCanvas:
    """Small SetPixel proxy that lets animations blend against pixels already drawn."""

    def __init__(self, canvas, width: int, height: int):
        self._canvas = canvas
        self._w = width
        self._h = height
        self._pix = [(0, 0, 0)] * (width * height)

    def _idx(self, x: int, y: int):
        if 0 <= x < self._w and 0 <= y < self._h:
            return y * self._w + x
        return None

    def SetPixel(self, x: int, y: int, r: int, g: int, b: int):
        idx = self._idx(x, y)
        if idx is None:
            return
        color = (
            max(0, min(255, int(r))),
            max(0, min(255, int(g))),
            max(0, min(255, int(b))),
        )
        self._pix[idx] = color
        self._canvas.SetPixel(x, y, color[0], color[1], color[2])

    def GetPixel(self, x: int, y: int):
        idx = self._idx(x, y)
        if idx is None:
            return (0, 0, 0)
        return self._pix[idx]

    def BlendPixel(self, x: int, y: int, r: int, g: int, b: int, alpha: float):
        idx = self._idx(x, y)
        if idx is None:
            return
        a = max(0.0, min(1.0, float(alpha)))
        if a <= 0.0:
            return
        if a >= 1.0:
            self.SetPixel(x, y, r, g, b)
            return
        br, bg, bb = self._pix[idx]
        self.SetPixel(
            x, y,
            int(br * (1.0 - a) + r * a),
            int(bg * (1.0 - a) + g * a),
            int(bb * (1.0 - a) + b * a),
        )

    def AddPixel(self, x: int, y: int, r: int, g: int, b: int, alpha: float = 1.0):
        idx = self._idx(x, y)
        if idx is None:
            return
        a = max(0.0, min(1.0, float(alpha)))
        if a <= 0.0:
            return
        br, bg, bb = self._pix[idx]
        self.SetPixel(
            x, y,
            min(255, int(br + r * a)),
            min(255, int(bg + g * a)),
            min(255, int(bb + b * a)),
        )


class WeatherAnimator:
    def __init__(self, cfg: dict, layout: dict, animation_loader: "AnimationLoader" = None):
        self.cfg = cfg
        self.layout = layout
        self.width   = cfg["panel"]["width"]
        self.height  = cfg["panel"]["height"]
        self.banner_bottom = layout["banner"]["bottom"]
        self.anim_top    = self.banner_bottom + 1
        self.anim_bottom = self.height - 1
        self.condition = "CLEAR"
        self.current_theme: Optional[Theme] = None
        self.frame = 0
        self._fps = cfg.get("animation", {}).get("fps", 15)
        _loader = animation_loader or AnimationLoader(
            cfg.get("animations", {}).get("animations_dir", "/etc/hub75-clock/animations")
        )
        self._cameo_manager = CameoManager(_loader, cfg)
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
        self._cameo_manager.setup_persistent(theme.cameos, self)

    def _color(self, key: str) -> Tuple:
        return parse_color(self.cfg["colors"][key])

    def _count(self, range_key: str) -> int:
        lo, hi = self.cfg["animation"][range_key]
        return max(1, random.randint(lo, hi))

    def _init_for_condition(self):
        self.condition = self._CONDITION_ALIASES.get(self.condition, self.condition)
        print(f"[animator] condition={self.condition}")
        self._cameo_manager.reset()

    def update(self):
        self.frame += 1

        if self.current_theme and self.current_theme.cameos:
            fps = self.cfg["animation"]["fps"]
            self._cameo_manager.update(self.current_theme.cameos, fps, self)

    def _draw_hazard_stripes(self, canvas):
        for y in range(self.anim_top, self.anim_bottom + 1):
            for x in range(self.width):
                if (x + y) % 10 < 5:
                    canvas.SetPixel(x, y, 40, 20, 0)

    def _draw_background(self, canvas):
        if self.current_theme is None:
            col = parse_color(self.cfg["colors"].get("sky_day", "#000820"))
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

    def _background_color_at(self, y: int) -> tuple:
        if self.current_theme is None:
            return parse_color(self.cfg["colors"].get("sky_day", "#000820"))

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

        if bg_type == "solid":
            return parse_color(bg_color)

        if bg_type != "gradient":
            return (0, 0, 0)

        top_col = parse_color(bg_top)
        bot_col = parse_color(bg_bottom)
        zone_h = self.anim_bottom - self.anim_top
        split_y = self.anim_top + int(zone_h * bg_split)

        if bg_dir == "sunrise":
            if y <= split_y:
                span = split_y - self.anim_top
                t = (y - self.anim_top) / span if span > 0 else 1.0
                return tuple(int(top_col[i] + (bot_col[i] - top_col[i]) * t) for i in range(3))
            return bot_col

        if y < split_y:
            return top_col
        span = self.anim_bottom - split_y
        t = (y - split_y) / span if span > 0 else 1.0
        return tuple(int(top_col[i] + (bot_col[i] - top_col[i]) * t) for i in range(3))

    def _draw_sun(self, canvas):
        color = self._color("sun_day")
        ox = self.width - 1
        oy = self.anim_top
        radius = 12
        glow_radius = 20
        for y in range(oy, oy + glow_radius + 1):
            sky = self._background_color_at(y)
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
        canvas = _TrackedCanvas(canvas, self.width, self.height)
        if alert_active:
            self._draw_hazard_stripes(canvas)
            return

        self._draw_background(canvas)

        # Celestial cameos: stars, shooting stars, meteor, comet
        self._cameo_manager.draw_celestial(canvas)

        # Sun and moon — theme JSON is sole authority
        if self.current_theme and self.current_theme.sun_enabled:
            self._draw_sun(canvas)
        if self.current_theme and self.current_theme.moon_enabled:
            self._draw_moon(canvas)

        # Layered cameo draws — strict back to front
        self._cameo_manager.draw_clouds(canvas)
        self._cameo_manager.draw_foreground(canvas)

    def _draw_moon(self, canvas):
        cx, cy = 3, self.anim_top + 3
        radius = 3
        glow_r = 5
        # Glow
        for dy in range(-glow_r, glow_r + 1):
            for dx in range(-glow_r, glow_r + 1):
                dist = math.sqrt(dx * dx + dy * dy)
                if radius < dist <= glow_r:
                    fade = 1.0 - (dist - radius) / (glow_r - radius)
                    sky = self._background_color_at(cy + dy)
                    gc = (
                        int(200 * fade * 0.4 + sky[0] * (1.0 - fade * 0.4)),
                        int(200 * fade * 0.4 + sky[1] * (1.0 - fade * 0.4)),
                        int(160 * fade * 0.3 + sky[2] * (1.0 - fade * 0.3)),
                    )
                    self._px(canvas, cx + dx, cy + dy, gc)
        # Filled disk with mottled surface
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                if dx * dx + dy * dy <= radius * radius:
                    shade = 180 + ((dx * 13 + dy * 7) % 40) - 20
                    # Two crater patches
                    if (dx == -1 and dy == -1) or (dx == 1 and dy == 1):
                        shade = 120
                    shade = max(80, min(220, shade))
                    self._px(canvas, cx + dx, cy + dy,
                              (shade, shade, int(shade * 0.85)))

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
        self._stopping = False
        self._thread = None
        self._io_lock = threading.Lock()
        self._cmd_responses = queue.Queue(maxsize=8)
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
            self._stopping = False
            time.sleep(0.1)
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()

    def stop(self):
        self._stopping = True
        self.running = False
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        if self.serial:
            try:
                with self._io_lock:
                    self.serial.close()
            except: pass

    def _send_cmd(self, cmd_word: bytes, data: bytes = b""):
        if self._stopping or not self.serial: return
        payload = cmd_word + data
        length = len(payload).to_bytes(2, "little")
        frame = self.CMD_HEAD + length + payload + self.CMD_TAIL
        try:
            with self._io_lock:
                if self._stopping or not self.serial or not self.serial.is_open:
                    return
                self.serial.write(frame)
            time.sleep(0.05)
        except Exception as e:
            if not self._stopping:
                print(f"[ld2410] cmd error: {e}")

    def _drain_cmd_responses(self):
        while True:
            try:
                self._cmd_responses.get_nowait()
            except queue.Empty:
                return

    def _send_cmd_wait(self, cmd_word: bytes, data: bytes = b"", timeout: float = 1.0):
        self._drain_cmd_responses()
        self._send_cmd(cmd_word, data)
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                payload = self._cmd_responses.get(timeout=max(0.05, deadline - time.time()))
            except queue.Empty:
                break
            if len(payload) >= 2 and payload[:2] == bytes([cmd_word[0], cmd_word[1] + 1]):
                return payload
        return None

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
        if self._stopping or not self.serial: return
        try:
            self._send_cmd(b"\xFF\x00")
            time.sleep(0.1)
            if self._stopping:
                return
            data = (gate.to_bytes(4, "little") +
                    move_thresh.to_bytes(4, "little") +
                    still_thresh.to_bytes(4, "little"))
            self._send_cmd(b"\x64\x00", data)
            time.sleep(0.1)
            self._send_cmd(b"\xFE\x00")
            print(f"[ld2410] gate {gate} move={move_thresh} still={still_thresh}")
        except Exception as e:
            if not self._stopping:
                print(f"[ld2410] gate config error: {e}")

    def read_parameters(self):
        if self._stopping or not self.serial:
            return None
        try:
            self._send_cmd(b"\xFF\x00")
            time.sleep(0.1)
            response = self._send_cmd_wait(b"\x61\x00", timeout=1.0)
            time.sleep(0.1)
            self._send_cmd(b"\xFE\x00")
            if not response or len(response) < 28:
                return None
            if response[2] != 0x00 or response[3] != 0x00 or response[4] != 0xAA:
                return None
            max_gate = int(response[5])
            max_move_gate = int(response[6])
            max_still_gate = int(response[7])
            gate_count = min(9, max_gate + 1)
            move = [int(v) for v in response[8:8 + gate_count]]
            still_start = 8 + gate_count
            still = [int(v) for v in response[still_start:still_start + gate_count]]
            while len(move) < 9:
                move.append(0)
            while len(still) < 9:
                still.append(0)
            timeout_idx = still_start + gate_count
            timeout = 0
            if len(response) >= timeout_idx + 2:
                timeout = response[timeout_idx] | (response[timeout_idx + 1] << 8)
            for gate in range(9):
                self._gate_thresholds[gate] = {"move": move[gate], "still": still[gate]}
            return {
                "max_gate": max_gate,
                "max_move_gate": max_move_gate,
                "max_still_gate": max_still_gate,
                "move_thresholds": move,
                "still_thresholds": still,
                "timeout_seconds": timeout,
            }
        except Exception as e:
            if not self._stopping:
                print(f"[ld2410] read parameters error: {e}")
            return None

    def _run(self):
        buf = bytearray()
        while self.running:
            try:
                with self._io_lock:
                    if self._stopping or not self.serial or not self.serial.is_open:
                        return
                    waiting = self.serial.in_waiting
                    chunk = self.serial.read(waiting) if waiting else b""
                if chunk:
                    buf.extend(chunk)
                    self._process(buf)
                else:
                    time.sleep(0.02)
            except Exception as e:
                if not self._stopping:
                    print(f"[ld2410] read error: {e}")
                time.sleep(1)

    def _process(self, buf: bytearray):
        while True:
            cmd_i = buf.find(self.CMD_HEAD)
            data_i = buf.find(self.HEAD)
            if cmd_i >= 0 and (data_i < 0 or cmd_i < data_i):
                if cmd_i > 0:
                    del buf[:cmd_i]
                if len(buf) < 10:
                    return
                dl = buf[4] | (buf[5] << 8)
                if dl > 512:
                    del buf[:]
                    return
                total = 4 + 2 + dl + 4
                if len(buf) < total:
                    return
                if bytes(buf[total-4:total]) != self.CMD_TAIL:
                    del buf[:1]
                    continue
                payload = bytes(buf[6:6+dl])
                try:
                    self._cmd_responses.put_nowait(payload)
                except queue.Full:
                    pass
                del buf[:total]
                continue

            i = data_i
            if i < 0:
                if len(buf) > 1024: del buf[:-4]
                return
            if i > 0: del buf[:i]
            if len(buf) < 10: return
            dl = buf[4] | (buf[5] << 8)
            if dl > 512:
                print(f"[ld2410] dropping oversized frame length: {dl}")
                del buf[:]
                continue
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
        opts.led_rgb_sequence  = cfg["panel"]["led_rgb_sequence"]
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

        self.animation_loader = AnimationLoader(
            cfg.get("animations", {}).get("animations_dir", "/etc/hub75-clock/animations"),
            cfg.get("animation_settings", {}),
        )
        self.animator = WeatherAnimator(cfg, layout, self.animation_loader)
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
        self._alert_cycle_timer = 0
        self._alert_show_message = False
        self._engineering_lock = threading.Lock()
        self._engineering_running = False
        self._ensure_theme_builder_startup_state()
        self._ensure_ld2410_tuner_startup_state()

    # ------------------------------------------------------------------
    # MQTT
    # ------------------------------------------------------------------
    def _request_engineering_mode(self, enable: bool):
        with self._engineering_lock:
            if self._engineering_running:
                print("[ld2410] engineering mode change already in progress")
                return
            self._engineering_running = True

        def _target():
            try:
                self._set_engineering_mode(enable)
            finally:
                with self._engineering_lock:
                    self._engineering_running = False

        threading.Thread(target=_target, daemon=True).start()

    def _set_engineering_mode(self, enable: bool):
        if self.ld2410 is None:
            return
        if enable:
            self.ld2410._enable_engineering_mode()
        else:
            self.ld2410._disable_engineering_mode()
        client_id = self.cfg["mqtt"]["client_id"]
        em_state_topic = (self.cfg["mqtt"]["topics"]
                          .get("engineering_mode", f"{client_id}/engineering_mode") + "/state")
        self.mqtt_client.publish(em_state_topic, "on" if enable else "off", retain=True)

    def _write_gate_config_async(self, gate: int, move_thresh: int, still_thresh: int):
        if self.ld2410 is None:
            return
        threading.Thread(
            target=self.ld2410.write_gate_config,
            args=(gate, move_thresh, still_thresh),
            daemon=True,
        ).start()

    def _read_ld2410_params_async(self):
        if self.ld2410 is None:
            return

        def _target():
            params = self.ld2410.read_parameters()
            if params:
                client_id = self.cfg["mqtt"]["client_id"]
                topic = self.cfg["mqtt"]["topics"].get("ld2410_params", f"{client_id}/ld2410/params")
                self.mqtt_client.publish(topic, json.dumps(params), retain=True)

        threading.Thread(target=_target, daemon=True).start()

    def _theme_builder_cfg(self):
        return self.cfg.get("theme_builder", {})

    def _theme_builder_state_topic(self):
        client_id = self.cfg["mqtt"]["client_id"]
        return f"{client_id}/theme_builder/state"

    def _theme_builder_url_topic(self):
        client_id = self.cfg["mqtt"]["client_id"]
        return f"{client_id}/theme_builder/url"

    def _theme_builder_url(self):
        tb = self._theme_builder_cfg()
        if tb.get("url"):
            return tb["url"]
        return f"http://{self.cfg['mqtt']['client_id']}.local:{int(tb.get('port', 8765))}/"

    def _theme_builder_is_active(self) -> bool:
        service = self._theme_builder_cfg().get("service_name", "hub75-theme-builder")
        try:
            return subprocess.run(
                ["systemctl", "is-active", "--quiet", service],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            ).returncode == 0
        except Exception:
            return False

    def _publish_theme_builder_state(self):
        if self._theme_builder_cfg().get("mode", "off") == "off":
            return
        active = self._theme_builder_is_active()
        self.mqtt_client.publish(self._theme_builder_state_topic(), "on" if active else "off", retain=True)
        self.mqtt_client.publish(self._theme_builder_url_topic(), self._theme_builder_url(), retain=True)

    def _set_theme_builder(self, enable: bool):
        tb = self._theme_builder_cfg()
        if tb.get("mode", "off") == "off":
            return
        service = tb.get("service_name", "hub75-theme-builder")
        action = "start" if enable else "stop"
        try:
            subprocess.run(["systemctl", action, service], check=False)
        except Exception as e:
            print(f"[theme_builder] {action} failed: {e}")
        self._publish_theme_builder_state()

    def _set_theme_builder_async(self, enable: bool):
        threading.Thread(target=self._set_theme_builder, args=(enable,), daemon=True).start()

    def _ensure_theme_builder_startup_state(self):
        tb = self._theme_builder_cfg()
        if tb.get("mode", "off") != "ha":
            return
        service = tb.get("service_name", "hub75-theme-builder")
        try:
            subprocess.run(
                ["systemctl", "stop", service],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as e:
            print(f"[theme_builder] startup stop failed: {e}")

    def _ld2410_tuner_cfg(self):
        return self.cfg.get("ld2410_tuner", {})

    def _ld2410_tuner_state_topic(self):
        client_id = self.cfg["mqtt"]["client_id"]
        return f"{client_id}/ld2410_tuner/state"

    def _ld2410_tuner_url_topic(self):
        client_id = self.cfg["mqtt"]["client_id"]
        return f"{client_id}/ld2410_tuner/url"

    def _ld2410_tuner_url(self):
        lt = self._ld2410_tuner_cfg()
        if lt.get("url"):
            return lt["url"]
        return f"http://{self.cfg['mqtt']['client_id']}.local:{int(lt.get('port', 8766))}/"

    def _ld2410_tuner_is_active(self) -> bool:
        service = self._ld2410_tuner_cfg().get("service_name", "hub75-ld2410-tuner")
        try:
            return subprocess.run(
                ["systemctl", "is-active", "--quiet", service],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            ).returncode == 0
        except Exception:
            return False

    def _publish_ld2410_tuner_state(self):
        if self._ld2410_tuner_cfg().get("mode", "off") == "off":
            return
        active = self._ld2410_tuner_is_active()
        self.mqtt_client.publish(self._ld2410_tuner_state_topic(), "on" if active else "off", retain=True)
        self.mqtt_client.publish(self._ld2410_tuner_url_topic(), self._ld2410_tuner_url(), retain=True)

    def _set_ld2410_tuner(self, enable: bool):
        lt = self._ld2410_tuner_cfg()
        if lt.get("mode", "off") == "off":
            return
        service = lt.get("service_name", "hub75-ld2410-tuner")
        action = "start" if enable else "stop"
        try:
            subprocess.run(["systemctl", action, service], check=False)
        except Exception as e:
            print(f"[ld2410_tuner] {action} failed: {e}")
        self._publish_ld2410_tuner_state()

    def _set_ld2410_tuner_async(self, enable: bool):
        threading.Thread(target=self._set_ld2410_tuner, args=(enable,), daemon=True).start()

    def _ensure_ld2410_tuner_startup_state(self):
        lt = self._ld2410_tuner_cfg()
        if lt.get("mode", "off") != "ha":
            return
        service = lt.get("service_name", "hub75-ld2410-tuner")
        try:
            subprocess.run(
                ["systemctl", "stop", service],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as e:
            print(f"[ld2410_tuner] startup stop failed: {e}")

    def _on_connect(self, client, userdata, flags, rc):
        if rc != 0:
            print(f"[mqtt] connect failed rc={rc}"); return
        print("[mqtt] connected")
        self.mqtt_connected = True
        client.publish(self.topic_avail, "online", retain=True)
        client_id = self.cfg["mqtt"]["client_id"]
        topics = self.cfg["mqtt"]["topics"]
        for t in (topics["weather"], topics["config"], topics["alert"],
                  topics.get("gates", f"{client_id}/gates"),
                  topics.get("engineering_mode", f"{client_id}/engineering_mode"),
                  topics.get("bucket", f"{client_id}/bucket"),
                  topics.get("ld2410_read", f"{client_id}/ld2410/read"),
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
        self._publish_theme_builder_state()
        self._publish_ld2410_tuner_state()
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
                    self._write_gate_config_async(gate, gt["move"], gt["still"])
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
                self._request_engineering_mode(em)

            if "theme_builder" in payload:
                if getattr(msg, "retain", False):
                    print("[theme_builder] ignored retained command")
                    self._publish_theme_builder_state()
                else:
                    self._set_theme_builder_async(bool(payload["theme_builder"]))

            if "ld2410_tuner" in payload:
                if getattr(msg, "retain", False):
                    print("[ld2410_tuner] ignored retained command")
                    self._publish_ld2410_tuner_state()
                else:
                    self._set_ld2410_tuner_async(bool(payload["ld2410_tuner"]))

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

            if "theme" in payload:
                theme_name = payload["theme"]
                theme = self.theme_loader.get_theme(theme_name)
                if theme:
                    self.animator.set_theme(theme)
                    self.mqtt_client.publish(topics["theme_state"], theme.name, retain=True)
                    print(f"[theme] set to {theme.name}")
                else:
                    print(f"[theme] unknown theme: {theme_name}")

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
                        self._write_gate_config_async(
                            int(g["gate"]),
                            int(g.get("move", 50)),
                            int(g.get("still", 30)),
                        )
                elif "gate" in payload:
                    self._write_gate_config_async(
                        int(payload["gate"]),
                        int(payload.get("move", 50)),
                        int(payload.get("still", 30)),
                    )
            if "engineering_mode" in payload:
                em = bool(payload["engineering_mode"])
                self._request_engineering_mode(em)

        elif msg.topic == topics.get("engineering_mode", f"{client_id}/engineering_mode"):
            if "engineering_mode" in payload:
                em = bool(payload["engineering_mode"])
                self._request_engineering_mode(em)

        elif msg.topic == topics.get("bucket", f"{client_id}/bucket"):
            if "bucket" in payload:
                self._apply_bucket(payload["bucket"])

        elif msg.topic == topics.get("ld2410_read", f"{client_id}/ld2410/read"):
            if not getattr(msg, "retain", False):
                self._read_ld2410_params_async()

        elif msg.topic == topics.get("theme"):
            theme_name = payload if isinstance(payload, str) else payload.get("theme", "")
            theme = self.theme_loader.get_theme(theme_name)
            if theme:
                self.animator.set_theme(theme)
                self.mqtt_client.publish(topics["theme_state"], theme.name, retain=True)
                print(f"[theme] set to {theme.name}")
            else:
                print(f"[theme] unknown theme: {theme_name}")

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
                "has_entity_name": True,
            }), retain=True)

    def _apply_bucket(self, bucket: str):
        self.bucket = bucket
        print(f"[config] bucket={bucket}")

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
                json.dumps({**s, "device": device, "availability": avail, "has_entity_name": True}), retain=True)

        # Remove old per-gate energy diagnostic entities; the tuner owns that detail now.
        for gate in range(9):
            for energy_type in ("move", "still"):
                self.mqtt_client.publish(
                    f"{prefix}/sensor/{client_id}_g{gate}_{energy_type}_energy/config",
                    "",
                    retain=True,
                )

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
                json.dumps({**s, "device": device, "availability": avail, "has_entity_name": True}), retain=True)

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
                "has_entity_name":  True,
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
                            "has_entity_name": True,
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
                    "has_entity_name": True,
                }), retain=True)

        # --- Switch + URL sensor: theme builder webserver ---
        if self._theme_builder_cfg().get("mode", "off") == "ha":
            self.mqtt_client.publish(
                f"{prefix}/switch/{client_id}_theme_builder/config",
                json.dumps({
                    "name":          "Theme Builder",
                    "unique_id":     f"{client_id}_theme_builder",
                    "device":        device,
                    "availability":  avail,
                    "command_topic": topics["config"],
                    "payload_on":    '{"theme_builder": true}',
                    "payload_off":   '{"theme_builder": false}',
                    "state_topic":   self._theme_builder_state_topic(),
                    "state_on":      "on",
                    "state_off":     "off",
                    "entity_category": "config",
                    "icon":          "mdi:palette-outline",
                    "has_entity_name": True,
                }), retain=True)
            self.mqtt_client.publish(
                f"{prefix}/sensor/{client_id}_theme_builder_url/config",
                json.dumps({
                    "name":          "Theme Builder URL",
                    "unique_id":     f"{client_id}_theme_builder_url",
                    "device":        device,
                    "availability":  avail,
                    "state_topic":   self._theme_builder_url_topic(),
                    "entity_category": "diagnostic",
                    "icon":          "mdi:web",
                    "has_entity_name": True,
                }), retain=True)

        # --- Switch + URL sensor: LD2410 tuner webserver ---
        if self.ld2410 is not None and self._ld2410_tuner_cfg().get("mode", "off") == "ha":
            self.mqtt_client.publish(
                f"{prefix}/switch/{client_id}_ld2410_tuner/config",
                json.dumps({
                    "name":          "LD2410 Tuner",
                    "unique_id":     f"{client_id}_ld2410_tuner",
                    "device":        device,
                    "availability":  avail,
                    "command_topic": topics["config"],
                    "payload_on":    '{"ld2410_tuner": true}',
                    "payload_off":   '{"ld2410_tuner": false}',
                    "state_topic":   self._ld2410_tuner_state_topic(),
                    "state_on":      "on",
                    "state_off":     "off",
                    "entity_category": "config",
                    "icon":          "mdi:radar",
                    "has_entity_name": True,
                }), retain=True)
            self.mqtt_client.publish(
                f"{prefix}/sensor/{client_id}_ld2410_tuner_url/config",
                json.dumps({
                    "name":          "LD2410 Tuner URL",
                    "unique_id":     f"{client_id}_ld2410_tuner_url",
                    "device":        device,
                    "availability":  avail,
                    "state_topic":   self._ld2410_tuner_url_topic(),
                    "entity_category": "diagnostic",
                    "icon":          "mdi:web",
                    "has_entity_name": True,
                }), retain=True)

        # Remove old update entities if they were previously discovered.
        for component, uid in (
            ("binary_sensor", f"{client_id}_update_available"),
            ("sensor", f"{client_id}_update_info"),
            ("button", f"{client_id}_update_check"),
            ("button", f"{client_id}_update_install"),
        ):
            self.mqtt_client.publish(
                f"{prefix}/{component}/{uid}/config",
                "",
                retain=True,
            )

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
                "has_entity_name": True,
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
        if self.veml   is not None: self.veml.stop()
        if self.pir    is not None: self.pir.stop()
        if self.ld2410 is not None: self.ld2410.stop()
        try:
            self.mqtt_client.publish(self.topic_avail, "offline", retain=True)
            self.mqtt_client.loop_stop(); self.mqtt_client.disconnect()
        except: pass
        if getattr(self, "theme_loader", None) is not None:
            self.theme_loader.stop()
        if getattr(self, "animation_loader", None) is not None:
            self.animation_loader.stop()
        if self.pir is not None:
            try: GPIO.cleanup()
            except: pass

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------
    def _render_loop(self):
        try:
            while self.running:
                fps = self.cfg["animation"]["fps"]
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
                high_x = panel_w - len(high_text) * font_w
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
            high_x = panel_w - len(high_text) * font_w
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

        if tl.get("outline", True):
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
    settings_path = cfg.get("animations", {}).get("settings_path", "/etc/hub75-clock/animations.yaml")
    cfg["animation_settings"] = load_animation_settings(settings_path)
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
