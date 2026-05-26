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
        cameo = self._cfg.get("_cameo", {})
        requested = cameo.get("sprite") or cameo.get("sprite_name")
        sprites_dir = self._cfg.get("animations", {}).get("sprites_dir", "/etc/hub75-clock/sprites")
        if requested:
            path = os.path.join(sprites_dir, requested if requested.endswith(".json") else requested + ".json")
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

    def _parse_pixels(self, sprite):
        pixels = []
        rows = sprite.get("pixels", [])
        for y, row in enumerate(rows):
            for x, value in enumerate(row):
                if value is None:
                    continue
                if isinstance(value, str):
                    h = value.lstrip("#")
                    if len(h) != 6:
                        continue
                    color = (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
                elif isinstance(value, list) and len(value) == 3:
                    color = tuple(max(0, min(255, int(v))) for v in value)
                else:
                    continue
                pixels.append((x, y, color))
        return pixels

    def update(self):
        self.x += self._vx
        self.y += self._vy

    def draw(self, canvas):
        ox = int(round(self.x))
        oy = int(round(self.y))
        for dx, dy, (r, g, b) in self._pixels:
            px = ox + dx
            py = oy + dy
            if 0 <= px < self._w and self._at <= py <= self._ab:
                canvas.SetPixel(px, py, r, g, b)

    def is_done(self) -> bool:
        return (
            self.x > self._w + self._sw + 2 or
            self.x < -self._sw - 2 or
            self.y < self._at - self._sh - 2 or
            self.y > self._ab + self._sh + 2
        )
