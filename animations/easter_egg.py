import math
import random


class Animation:
    name = "easter_egg"
    conditions = []
    themes = ["Day"]
    layer = "foreground"
    speed = 1.0

    # Oval egg: 6 wide, 8 tall with stripe pattern
    _STRIPES = [
        # (dx, dy) → color index 0-3
        (1, 0, 0), (2, 0, 0), (3, 0, 0), (4, 0, 0),
        (0, 1, 1), (1, 1, 0), (2, 1, 1), (3, 1, 0), (4, 1, 1), (5, 1, 1),
        (0, 2, 2), (1, 2, 1), (2, 2, 2), (3, 2, 1), (4, 2, 2), (5, 2, 2),
        (0, 3, 3), (1, 3, 2), (2, 3, 3), (3, 3, 2), (4, 3, 3), (5, 3, 3),
        (0, 4, 0), (1, 4, 3), (2, 4, 0), (3, 4, 3), (4, 4, 0), (5, 4, 0),
        (0, 5, 1), (1, 5, 0), (2, 5, 1), (3, 5, 0), (4, 5, 1), (5, 5, 1),
        (1, 6, 2), (2, 6, 1), (3, 6, 2), (4, 6, 1),
        (2, 7, 3), (3, 7, 2),
    ]
    # --- Appearance settings ---
    _PALETTE = [
        (255,  80, 120),  # pink
        (255, 200,   0),  # yellow
        (100, 200, 255),  # sky blue
        (160, 255, 120),  # mint green
    ]
    # ---------------------------

    def __init__(self, width, height, cfg, animator):
        self._w = width
        self._at = animator.anim_top
        self._ab = animator.anim_bottom
        self.x = float(-8)
        self._base_y = float(self._ab - 8)
        self._vx = (0.3 + random.random() * 0.15) * self.speed
        self._bounce = 0.0

    def update(self):
        self.x += self._vx
        self._bounce += self._vx * 0.5

    def draw(self, canvas):
        ox = int(round(self.x))
        oy = int(self._base_y - abs(math.sin(self._bounce)) * 2)
        for dx, dy, ci in self._STRIPES:
            r, g, b = self._PALETTE[ci]
            px, py = ox + dx, oy + dy
            if 0 <= px < self._w and self._at <= py <= self._ab:
                canvas.SetPixel(px, py, r, g, b)

    def is_done(self) -> bool:
        return self.x > self._w + 8
