import json
import os
import random


class Animation:
    name = "sprite"
    conditions = []
    themes = []
    layer = "foreground"
    persistent = False
    speed = 1.0

    def __init__(self, width, height, cfg, animator):
        self._w = width
        self._at = animator.anim_top
        self._ab = animator.anim_bottom
        self._cfg = cfg
        self._fps = max(1, int(cfg.get("animation", {}).get("fps", 15)))
        self._cameo = self._cfg.get("_cameo", {})
        self._sprite_cache = {}
        self._animation = self._load_sprite_animation()
        self._frame_index = 0
        self._frame_tick = 0
        self._done = False

        if self._animation:
            self._frames = self._animation.get("frames", []) or []
            self._loop = bool(self._cameo.get("loop", self._animation.get("loop", False)))
            self._speed = float(self._animation.get("speed", self.speed)) * self.speed
            return

        self._sprite = self._load_sprite()
        self._pixels = self._parse_pixels(self._sprite)
        self._sw = int(self._sprite.get("width", 1))
        self._sh = int(self._sprite.get("height", 1))
        self._motion = self._sprite.get("motion", "left")
        self._speed = float(self._sprite.get("speed", self.speed)) * self.speed

        if self._motion == "right":
            self.x = float(-self._sw - 1)
            self.y = float(self._at + random.randint(2, max(2, self._ab - self._at - self._sh)))
            self._vx = max(0.1, self._speed)
            self._vy = 0.0
        elif self._motion == "up":
            self.x = float(random.randint(2, max(2, self._w - self._sw - 2)))
            self.y = float(self._ab + 1)
            self._vx = 0.0
            self._vy = -max(0.1, self._speed)
        else:
            self.x = float(self._w + 1)
            self.y = float(self._at + random.randint(2, max(2, self._ab - self._at - self._sh)))
            self._vx = -max(0.1, self._speed)
            self._vy = 0.0

    def _load_sprite(self):
        requested = self._cameo.get("sprite") or self._cameo.get("sprite_name")
        sprites_dir = self._cfg.get("animations", {}).get("sprites_dir", "/etc/hub75-clock/sprites")
        if requested:
            path = self._sprite_path(requested)
        else:
            choices = [
                os.path.join(sprites_dir, name)
                for name in os.listdir(sprites_dir)
                if name.endswith(".json")
            ]
            if not choices:
                raise RuntimeError(f"no sprite JSON files found in {sprites_dir}")
            path = random.choice(choices)
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise RuntimeError(f"sprite file is not an object: {path}")
        return data

    def _sprite_path(self, name):
        sprites_dir = self._cfg.get("animations", {}).get("sprites_dir", "/etc/hub75-clock/sprites")
        return os.path.join(sprites_dir, name if name.endswith(".json") else name + ".json")

    def _load_named_sprite(self, name):
        key = name[:-5] if name.endswith(".json") else name
        if key not in self._sprite_cache:
            with open(self._sprite_path(key), encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                raise RuntimeError(f"sprite file is not an object: {key}")
            self._sprite_cache[key] = data
        return self._sprite_cache[key]

    def _load_sprite_animation(self):
        requested = self._cameo.get("animation") or self._cameo.get("sprite_animation")
        if not requested:
            return None
        anim_dir = self._cfg.get("animations", {}).get("sprite_animations_dir", "/etc/hub75-clock/sprite-animations")
        path = os.path.join(anim_dir, requested if requested.endswith(".json") else requested + ".json")
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise RuntimeError(f"sprite animation file is not an object: {path}")
        return data

    def _parse_pixels(self, sprite, frame_index=0):
        pixels = []
        frames = sprite.get("frames") if isinstance(sprite.get("frames"), list) else []
        if frames:
            rows = frames[frame_index % len(frames)].get("pixels", sprite.get("pixels", []))
        else:
            rows = sprite.get("pixels", [])
        for y, row in enumerate(rows):
            for x, value in enumerate(row):
                if value is None:
                    continue
                if isinstance(value, str):
                    h = value.lstrip("#")
                    if len(h) not in (6, 8):
                        continue
                    try:
                        color = (
                            int(h[0:2], 16),
                            int(h[2:4], 16),
                            int(h[4:6], 16),
                            int(h[6:8], 16) if len(h) == 8 else 255,
                        )
                    except ValueError:
                        continue
                elif isinstance(value, list) and len(value) in (3, 4):
                    rgba = [max(0, min(255, int(v))) for v in value]
                    if len(rgba) == 3:
                        rgba.append(255)
                    color = tuple(rgba)
                else:
                    continue
                pixels.append((x, y, color))
        return pixels

    def update(self):
        if self._animation:
            if self._done or not self._frames:
                return
            duration = int(self._frames[self._frame_index].get("duration_ms", 100))
            ticks = max(1, round(duration / (1000 / self._fps) / max(0.05, self._speed)))
            self._frame_tick += 1
            if self._frame_tick >= ticks:
                self._frame_tick = 0
                self._frame_index += 1
                if self._frame_index >= len(self._frames):
                    if self._loop:
                        self._frame_index = 0
                    else:
                        self._done = True
            return
        self.x += self._vx
        self.y += self._vy

    def draw(self, canvas):
        if self._animation:
            if self._done or not self._frames:
                return
            frame = self._frames[self._frame_index]
            for item in frame.get("sprites", []):
                sprite = self._load_named_sprite(item.get("sprite", ""))
                frame_idx = int(item.get("frame", self._frame_index))
                pixels = self._parse_pixels(sprite, frame_idx)
                ox = int(round(item.get("x", 0)))
                oy = int(round(item.get("y", 0))) + self._at
                for dx, dy, (r, g, b, a) in pixels:
                    px = ox + dx
                    py = oy + dy
                    if 0 <= px < self._w and self._at <= py <= self._ab:
                        if a >= 255:
                            canvas.SetPixel(px, py, r, g, b)
                        elif a > 0 and hasattr(canvas, "BlendPixel"):
                            canvas.BlendPixel(px, py, r, g, b, a / 255.0)
                        elif a > 0:
                            canvas.SetPixel(px, py, r, g, b)
            return

        ox = int(round(self.x))
        oy = int(round(self.y))
        for dx, dy, (r, g, b, a) in self._pixels:
            px = ox + dx
            py = oy + dy
            if 0 <= px < self._w and self._at <= py <= self._ab:
                if a >= 255:
                    canvas.SetPixel(px, py, r, g, b)
                elif a > 0 and hasattr(canvas, "BlendPixel"):
                    canvas.BlendPixel(px, py, r, g, b, a / 255.0)
                elif a > 0:
                    canvas.SetPixel(px, py, r, g, b)

    def is_done(self) -> bool:
        if self._animation:
            return self._done
        return (
            self.x > self._w + self._sw + 2 or
            self.x < -self._sw - 2 or
            self.y < self._at - self._sh - 2 or
            self.y > self._ab + self._sh + 2
        )
