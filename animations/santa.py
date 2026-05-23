import math
import random


class Animation:
    name = "santa"
    conditions = []
    themes = ["Night", "Late Evening"]
    layer = "foreground"

    # --- Appearance settings ---
    # Edit colors directly in _SPRITE below.
    # Key areas: reindeer (tan 160,120,80), sleigh body (red ~200,40,40),
    #            Santa hat (red 200,40,40), hat trim (white 220,220,220)
    # ---------------------------

    # Santa + sleigh silhouette (facing left, moves right-to-left)
    # (dx, dy, r, g, b) — 0,0 at left edge of sprite, 16 wide total
    _SPRITE = [
        # 3 reindeer (dots with antlers) at front (left side)
        # Reindeer 1
        (0, 2, 160, 120, 80), (1, 2, 160, 120, 80),
        (0, 1, 140, 100, 60), (1, 1, 140, 100, 60),  # antler
        # Reindeer 2
        (3, 2, 160, 120, 80), (4, 2, 160, 120, 80),
        (3, 1, 140, 100, 60),
        # Reindeer 3
        (6, 2, 160, 120, 80), (7, 2, 160, 120, 80),
        (6, 1, 140, 100, 60), (7, 1, 140, 100, 60),
        # Harness ropes
        (2, 2, 80, 60, 40), (5, 2, 80, 60, 40),
        # Sleigh runners
        (8, 3, 80, 60, 40), (9, 3, 80, 60, 40), (10, 3, 80, 60, 40),
        (11, 3, 80, 60, 40), (12, 3, 80, 60, 40),
        # Sleigh body
        (9, 1, 180, 30, 30), (10, 1, 200, 40, 40), (11, 1, 200, 40, 40),
        (12, 1, 180, 30, 30),
        (9, 2, 180, 30, 30), (10, 2, 200, 40, 40), (11, 2, 200, 40, 40),
        (12, 2, 180, 30, 30),
        # Sleigh back wall
        (13, 0, 160, 25, 25), (13, 1, 160, 25, 25), (13, 2, 160, 25, 25),
        # Santa silhouette
        (12, 0, 200, 40, 40),   # hat
        (11, 0, 220, 220, 220),  # white trim
        (13, 1, 50, 30, 20),    # body
    ]

    def __init__(self, width, height, cfg, animator):
        self._w = width
        self._at = animator.anim_top
        self._ab = animator.anim_bottom
        self.x = float(width + 2)  # start off right edge
        self.y = float(self._at + random.randint(1, 5))
        self._vx = -(0.4 + random.random() * 0.2) * 0.5
        self._wave = random.random() * math.pi * 2

    def update(self):
        self.x += self._vx
        self._wave += 0.06

    def draw(self, canvas):
        ox = int(round(self.x))
        oy = int(round(self.y + math.sin(self._wave) * 1.5))
        for dx, dy, r, g, b in self._SPRITE:
            px, py = ox + dx, oy + dy
            if 0 <= px < self._w and self._at - 2 <= py <= self._ab:
                canvas.SetPixel(px, py, r, g, b)

    def is_done(self) -> bool:
        return self.x < -20
