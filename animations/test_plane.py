import json
import os
import random


class Animation:
    name = "testPlane"
    conditions = []
    themes = ["Day", "Sunrise", "Sunset"]
    layer = "foreground"
    persistent = False
    speed = 0.8

    def __init__(self, width, height, cfg, animator):
        self._w = width
        self._at = animator.anim_top
        self._ab = animator.anim_bottom
        self._cfg = cfg
        self._sprite = self._load_sprite("airplane")
        self._pixels = self._parse_pixels(self._sprite)
        self._sw = int(self._sprite.get("width", 9))
        self._sh = int(self._sprite.get("height", 4))
        self._right = random.choice([True, False])
        self._trail = []
        self._trail_max = 18
        self.y = float(self._at + random.randint(5, 11))

        if self._right:
            self.x = float(-self._sw - 1)
            self._vx = (0.45 + random.random() * 0.2) * self.speed
        else:
            self.x = float(width + 1)
            self._vx = -(0.45 + random.random() * 0.2) * self.speed

    def _load_sprite(self, name):
        sprites_dir = self._cfg.get("animations", {}).get("sprites_dir", "/etc/hub75-clock/sprites")
        path = os.path.join(sprites_dir, name if name.endswith(".json") else name + ".json")
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise RuntimeError(f"sprite file is not an object: {path}")
        return data

    def _parse_pixels(self, sprite):
        pixels = []
        for y, row in enumerate(sprite.get("pixels", [])):
            for x, value in enumerate(row):
                color = self._parse_color(value)
                if color is not None:
                    pixels.append((x, y, color))
        return pixels

    def _parse_color(self, value):
        if value is None:
            return None
        if isinstance(value, str):
            h = value.lstrip("#")
            if len(h) not in (6, 8):
                return None
            try:
                return (
                    int(h[0:2], 16),
                    int(h[2:4], 16),
                    int(h[4:6], 16),
                    int(h[6:8], 16) if len(h) == 8 else 255,
                )
            except ValueError:
                return None
        if isinstance(value, list) and len(value) in (3, 4):
            rgba = [max(0, min(255, int(v))) for v in value]
            if len(rgba) == 3:
                rgba.append(255)
            return tuple(rgba)
        return None

    def draw(self, canvas):
        for i, (tx, ty) in enumerate(self._trail):
            fade = (i + 1) / len(self._trail)
            alpha = 0.42 * fade
            if alpha <= 0.02:
                continue
            px, py = int(round(tx)), int(round(ty))
            if 0 <= px < self._w and self._at <= py <= self._ab:
                canvas.BlendPixel(px, py, 175, 175, 180, alpha)
                if i % 3 == 0 and self._at <= py + 1 <= self._ab:
                    canvas.BlendPixel(px, py + 1, 150, 150, 155, alpha * 0.45)

        ox = int(round(self.x))
        oy = int(round(self.y)) - 1
        for dx, dy, (r, g, b, a) in self._pixels:
            if self._right:
                dx = self._sw - 1 - dx
            px, py = ox + dx, oy + dy
            if 0 <= px < self._w and self._at - 2 <= py <= self._ab:
                if a >= 255:
                    canvas.SetPixel(px, py, r, g, b)
                elif a > 0 and hasattr(canvas, "BlendPixel"):
                    canvas.BlendPixel(px, py, r, g, b, a / 255.0)
                elif a > 0:
                    canvas.SetPixel(px, py, r, g, b)

    def update(self):
        trail_x = self.x - 2 if self._right else self.x + self._sw + 1
        trail_y = self.y + 1
        self._trail.append((trail_x, trail_y))
        if len(self._trail) > self._trail_max:
            self._trail.pop(0)
        self.x += self._vx

    def is_done(self) -> bool:
        return self.x > self._w + self._sw + 3 or self.x < -self._sw - 3
