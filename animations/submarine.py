import math
import random


class Animation:
    name = "submarine"
    conditions = []
    themes = ["Day"]
    layer = "foreground"

    # --- Appearance settings ---
    # Edit colors directly in _HULL and _SCOPE below.
    # Key areas: hull (olive green ~100,160,100), porthole (cyan 160,220,255),
    #            propeller (dark green ~55,90,55), periscope (dark green ~65,108,65)
    # ---------------------------

    # Sub hull: 18 wide, 5 tall. Conning tower at dx=12..14, periscope at dx=13
    _HULL = [
        # Main hull (oval)
        (2, 2, 80, 130, 80), (3, 2, 100, 160, 100), (4, 2, 110, 170, 110),
        (5, 2, 110, 170, 110), (6, 2, 110, 170, 110), (7, 2, 110, 170, 110),
        (8, 2, 110, 170, 110), (9, 2, 110, 170, 110), (10, 2, 110, 170, 110),
        (11, 2, 110, 170, 110), (12, 2, 110, 170, 110), (13, 2, 110, 170, 110),
        (14, 2, 100, 160, 100), (15, 2, 80, 130, 80),
        # Hull top/bottom rounding
        (1, 2, 60, 100, 60),
        (3, 1, 80, 130, 80), (4, 1, 100, 160, 100), (5, 1, 100, 160, 100),
        (6, 1, 100, 160, 100), (7, 1, 100, 160, 100), (8, 1, 100, 160, 100),
        (9, 1, 100, 160, 100), (10, 1, 100, 160, 100), (11, 1, 100, 160, 100),
        (12, 1, 100, 160, 100), (13, 1, 100, 160, 100), (14, 1, 80, 130, 80),
        (3, 3, 80, 130, 80), (4, 3, 100, 160, 100), (5, 3, 100, 160, 100),
        (6, 3, 100, 160, 100), (7, 3, 100, 160, 100), (8, 3, 100, 160, 100),
        (9, 3, 100, 160, 100), (10, 3, 100, 160, 100), (11, 3, 100, 160, 100),
        (12, 3, 100, 160, 100), (13, 3, 100, 160, 100), (14, 3, 80, 130, 80),
        # Propeller (right side)
        (16, 1, 60, 100, 60), (16, 3, 60, 100, 60), (17, 2, 50, 90, 50),
        # Porthole
        (7, 2, 160, 220, 255),
        # Conning tower
        (10, 0, 80, 130, 80), (11, 0, 90, 140, 90), (12, 0, 80, 130, 80),
        (10, 1, 85, 135, 85), (11, 1, 95, 145, 95), (12, 1, 85, 135, 85),
    ]
    # Periscope (extends above hull, at dx=11, dy=-2..-1)
    _SCOPE = [(11, -2, 60, 100, 60), (11, -1, 70, 115, 70)]

    def __init__(self, width, height, cfg, animator):
        self._w = width
        self._at = animator.anim_top
        self._ab = animator.anim_bottom
        mid = (self._at + self._ab) // 2
        self._base_y = float(mid - 2)
        self.x = float(-20)
        self._vx = 0.25 + random.random() * 0.15
        self._wave = random.random() * math.pi * 2

    def update(self):
        self.x += self._vx
        self._wave += 0.04

    def draw(self, canvas):
        ox = int(round(self.x))
        oy = int(round(self._base_y + math.sin(self._wave) * 1.0))
        for dx, dy, r, g, b in self._HULL:
            px, py = ox + dx, oy + dy
            if 0 <= px < self._w and self._at <= py <= self._ab:
                canvas.SetPixel(px, py, r, g, b)
        for dx, dy, r, g, b in self._SCOPE:
            px, py = ox + dx, oy + dy
            if 0 <= px < self._w and self._at <= py <= self._ab:
                canvas.SetPixel(px, py, r, g, b)

    def is_done(self) -> bool:
        return self.x > self._w + 22
