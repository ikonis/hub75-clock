import math
import random


class Animation:
    name = "hot_air_balloon"
    conditions = ["CLEAR", "PARTLYCLOUDY"]
    themes = ["Day", "Sunrise"]
    layer = "foreground"

    # --- Appearance settings ---
    # Edit colors directly in _BALLOON, _ROPES, _BASKET below.
    # Balloon uses ROYGBIV stripe pattern: red (255,60,60), orange (255,160,0),
    #   yellow (255,240,0), green (60,180,60), blue (40,120,220)
    # Ropes/basket: warm wood brown ~(110,75,40)
    # ---------------------------

    # Balloon: 7 wide, 7 tall oval with colorful stripes
    # (dx, dy, r, g, b)
    _BALLOON = []
    # Row 0: tip
    _BALLOON += [(3, 0, 255, 60, 60)]
    # Row 1
    _BALLOON += [(2, 1, 255, 60, 60), (3, 1, 255, 160, 0), (4, 1, 255, 60, 60)]
    # Row 2
    _BALLOON += [(1, 2, 255, 160, 0), (2, 2, 255, 240, 0), (3, 2, 60, 180, 60),
                 (4, 2, 255, 240, 0), (5, 2, 255, 160, 0)]
    # Row 3 (widest)
    _BALLOON += [(0, 3, 60, 180, 60), (1, 3, 40, 120, 220), (2, 3, 60, 180, 60),
                 (3, 3, 255, 60, 60), (4, 3, 60, 180, 60),
                 (5, 3, 40, 120, 220), (6, 3, 60, 180, 60)]
    # Row 4
    _BALLOON += [(1, 4, 255, 160, 0), (2, 4, 60, 180, 60), (3, 4, 40, 120, 220),
                 (4, 4, 60, 180, 60), (5, 4, 255, 160, 0)]
    # Row 5
    _BALLOON += [(2, 5, 255, 60, 60), (3, 5, 255, 160, 0), (4, 5, 255, 60, 60)]
    # Row 6: bottom
    _BALLOON += [(3, 6, 255, 60, 60)]
    # Ropes
    _ROPES = [(2, 7, 100, 70, 40), (4, 7, 100, 70, 40)]
    # Basket
    _BASKET = [(2, 8, 120, 80, 40), (3, 8, 140, 100, 50), (4, 8, 120, 80, 40),
               (2, 9, 110, 70, 35), (3, 9, 130, 90, 45), (4, 9, 110, 70, 35)]

    def __init__(self, width, height, cfg, animator):
        self._w = width
        self._at = animator.anim_top
        self._ab = animator.anim_bottom
        self.x = float(random.randint(5, width - 12))
        self.y = float(self._ab - 9)     # start near bottom
        self._vx = (random.random() - 0.5) * 0.15
        self._vy = -0.08                 # drifts upward
        self._sway = random.random() * math.pi * 2

    def update(self):
        self._sway += 0.04
        self.x += self._vx + math.sin(self._sway) * 0.04
        self.y += self._vy

    def draw(self, canvas):
        ox = int(round(self.x))
        oy = int(round(self.y))
        for dx, dy, r, g, b in self._BALLOON + self._ROPES + self._BASKET:
            px, py = ox + dx, oy + dy
            if 0 <= px < self._w and self._at <= py <= self._ab:
                canvas.SetPixel(px, py, r, g, b)

    def is_done(self) -> bool:
        return self.y < self._at - 12 or self.x < -10 or self.x > self._w + 2
