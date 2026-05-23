import math
import random


class Animation:
    name = "snowman"
    conditions = ["SNOW"]
    themes = []
    layer = "foreground"
    speed = 1.0

    # --- Appearance settings ---
    # Edit colors directly in _SPRITE below.
    # Key areas: body/head (icy blue-white ~210,230,250), hat (dark gray ~45,45,45),
    #            carrot nose (orange 255,120,0), arms (brown 120,80,40)
    # ---------------------------

    # Pixel art snowman: lower circle (5 dia), upper circle (3 dia), hat, arms, face
    # All offsets from top-left of bounding box, anchored to bottom-right of screen
    _SPRITE = [
        # Hat brim
        (2, 0, 50, 50, 50), (3, 0, 50, 50, 50), (4, 0, 50, 50, 50),
        (5, 0, 50, 50, 50), (6, 0, 50, 50, 50),
        # Hat top
        (3, -2, 40, 40, 40), (4, -2, 40, 40, 40), (5, -2, 40, 40, 40),
        (3, -1, 40, 40, 40), (4, -1, 40, 40, 40), (5, -1, 40, 40, 40),
        # Head circle (3-wide, centered at col 4)
        (3, 1, 200, 220, 240), (4, 1, 220, 240, 255), (5, 1, 200, 220, 240),
        (3, 2, 220, 240, 255), (4, 2, 240, 255, 255), (5, 2, 220, 240, 255),
        (3, 3, 200, 220, 240), (4, 3, 220, 240, 255), (5, 3, 200, 220, 240),
        # Eyes
        (3, 2, 30, 30, 30), (5, 2, 30, 30, 30),
        # Carrot nose
        (4, 2, 255, 120, 0),
        # Body circle (5-wide, centered at col 4)
        (2, 4, 180, 200, 220), (3, 4, 200, 220, 240), (4, 4, 210, 230, 255),
        (5, 4, 200, 220, 240), (6, 4, 180, 200, 220),
        (1, 5, 190, 210, 230), (2, 5, 210, 230, 250), (3, 5, 220, 240, 255),
        (4, 5, 230, 250, 255), (5, 5, 220, 240, 255), (6, 5, 210, 230, 250),
        (7, 5, 190, 210, 230),
        (2, 6, 200, 220, 240), (3, 6, 210, 230, 255), (4, 6, 220, 240, 255),
        (5, 6, 210, 230, 255), (6, 6, 200, 220, 240),
        (3, 7, 190, 210, 230), (4, 7, 200, 220, 240), (5, 7, 190, 210, 230),
        # Buttons on body
        (4, 5, 30, 30, 30),
        # Arms (stick lines)
        (0, 5, 120, 80, 40), (8, 5, 120, 80, 40),
    ]

    def __init__(self, width, height, cfg, animator):
        self._w = width
        self._at = animator.anim_top
        self._ab = animator.anim_bottom
        # Bottom-right position
        self._ox = width - 10
        self._oy = self._ab - 8
        self._frame = 0
        self._fade_in  = 20
        self._hold     = 90
        self._fade_out = 20
        self._total = self._fade_in + self._hold + self._fade_out

    def _alpha(self) -> float:
        f = self._frame
        if f < self._fade_in:
            return f / self._fade_in
        elif f < self._fade_in + self._hold:
            return 1.0
        else:
            return 1.0 - (f - self._fade_in - self._hold) / self._fade_out

    def update(self):
        self._frame += 1

    def draw(self, canvas):
        alpha = max(0.0, min(1.0, self._alpha()))
        for dx, dy, r, g, b in self._SPRITE:
            px, py = self._ox + dx, self._oy + dy
            if 0 <= px < self._w and self._at <= py <= self._ab:
                canvas.SetPixel(px, py, int(r * alpha), int(g * alpha), int(b * alpha))

    def is_done(self) -> bool:
        return self._frame >= self._total
