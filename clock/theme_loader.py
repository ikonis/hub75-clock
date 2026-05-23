from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass, field
from typing import Optional

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    _WATCHDOG_AVAILABLE = True
except ImportError:
    _WATCHDOG_AVAILABLE = False


@dataclass
class Theme:
    name: str
    description: str = ""
    background_type: str = "solid"
    background_color: str = "#000820"
    background_top: str = "#0F0019"
    background_bottom: str = "#3C1400"
    background_split: float = 0.5
    background_gradient_direction: str = "sunset"
    colors: dict = field(default_factory=dict)
    stars_enabled: bool = False
    shooting_stars_enabled: bool = False
    cameos: list = field(default_factory=list)
    cloud_density: str = "medium"
    cloud_speed: str = "medium"
    sun_enabled: bool = True
    moon_enabled: bool = False
    precipitation: str = "none"
    condition_overrides: dict = field(default_factory=dict)


def _theme_from_dict(data: dict) -> Theme:
    known = {f.name for f in Theme.__dataclass_fields__.values()}  # type: ignore[attr-defined]
    filtered = {k: v for k, v in data.items() if k in known}
    theme = Theme(**filtered)
    # Backward compatibility: shooting_stars_enabled → cameo entry
    if data.get("shooting_stars_enabled") and not any(
        c.get("name") == "shooting_star" for c in theme.cameos
    ):
        theme.cameos = theme.cameos + [{"name": "shooting_star", "chance_per_minute": 8}]
    return theme


class ThemeLoader:
    def __init__(self, themes_dir: str):
        self.themes_dir = themes_dir
        self.on_themes_changed = None
        self._themes: dict[str, Theme] = {}
        self._observer = None
        self._handler = None

        os.makedirs(themes_dir, exist_ok=True)
        self._themes = self.load_all()
        self._start_watcher()

    def load_all(self) -> dict[str, Theme]:
        themes = {}
        for entry in os.scandir(self.themes_dir):
            if not entry.name.endswith(".json") or not entry.is_file():
                continue
            try:
                with open(entry.path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if "name" not in data:
                    data["name"] = entry.name[:-5]
                theme = _theme_from_dict(data)
                themes[theme.name] = theme
            except Exception as e:
                print(f"[theme_loader] Warning: skipping {entry.name}: {e}")
        return themes

    def get_theme(self, name: str) -> Optional[Theme]:
        return self._themes.get(name)

    def available_themes(self) -> list[str]:
        return sorted(self._themes.keys())

    def _reload(self):
        self._themes = self.load_all()
        if callable(self.on_themes_changed):
            self.on_themes_changed(dict(self._themes))

    def _start_watcher(self):
        if not _WATCHDOG_AVAILABLE:
            print("[theme_loader] Warning: watchdog not installed — file watching disabled")
            return

        loader = self

        class _Handler(FileSystemEventHandler):
            def __init__(self):
                super().__init__()
                self._timer = None
                self._lock = threading.Lock()

            def on_any_event(self, event):
                if event.is_directory:
                    return
                if not (getattr(event, "src_path", "").endswith(".json") or
                        getattr(event, "dest_path", "").endswith(".json")):
                    return
                with self._lock:
                    if self._timer is not None:
                        self._timer.cancel()
                    self._timer = threading.Timer(0.5, loader._reload)
                    self._timer.daemon = True
                    self._timer.start()

        self._handler = _Handler()
        self._observer = Observer()
        self._observer.schedule(self._handler, self.themes_dir, recursive=False)
        self._observer.daemon = True
        self._observer.start()

    def stop(self):
        if self._handler is not None:
            with self._handler._lock:
                if self._handler._timer is not None:
                    self._handler._timer.cancel()
                    self._handler._timer = None
        if self._observer is not None:
            self._observer.stop()
            self._observer.join()
            self._observer = None
        self._handler = None
