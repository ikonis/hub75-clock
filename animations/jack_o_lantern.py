import math
import random


class Animation:
    name = "jack_o_lantern"
    conditions = []
    themes = ["Night", "Late Evening"]

    # Orange oval pumpkin (9 wide, 7 tall)
    _BODY = [
        # Top
        (3, 0, 200, 100, 0), (4, 0, 220, 110, 0), (5, 0, 200, 100, 0),
        # Row 1
        (1, 1, 180, 80, 0), (2, 1, 210, 105, 0), (3, 1, 230, 115, 0),
        (4, 1, 240, 120, 0), (5, 1, 230, 115, 0), (6, 1, 210, 105, 0),
        (7, 1, 180, 80, 0),
        # Row 2 (widest)
        (0, 2, 160, 70, 0), (1, 2, 200, 100, 0), (2, 2, 220, 110, 0),
        (3, 2, 235, 118, 0), (4, 2, 240, 120, 0), (5, 2, 235, 118, 0),
        (6, 2, 220, 110, 0), (7, 2, 200, 100, 0), (8, 2, 160, 70, 0),
        # Row 3
        (0, 3, 160, 70, 0), (1, 3, 200, 100, 0), (2, 3, 220, 110, 0),
        (3, 3, 235, 118, 0), (4, 3, 240, 120, 0), (5, 3, 235, 118, 0),
        (6, 3, 220, 110, 0), (7, 3, 200, 100, 0), (8, 3, 160, 70, 0),
        # Row 4
        (1, 4, 180, 80, 0), (2, 4, 210, 105, 0), (3, 4, 225, 112, 0),
        (4, 4, 230, 115, 0), (5, 4, 225, 112, 0), (6, 4, 210, 105, 0),
        (7, 4, 180, 80, 0),
        # Row 5
        (2, 5, 180, 80, 0), (3, 5, 200, 100, 0), (4, 5, 200, 100, 0),
        (5, 5, 200, 100, 0), (6, 5, 180, 80, 0),
        # Bottom
        (3, 6, 160, 70, 0), (4, 6, 160, 70, 0), (5, 6, 160, 70, 0),
        # Stem
        (4, -1, 80, 120, 20),
    ]
    # Triangle eyes: apex at top, base at bottom
    # Left eye: apex (2,1), base (1,2)-(3,2)
    # Right eye: apex (6,1), base (5,2)-(7,2)
    _EYES = [
        (2, 1), (1, 2), (2, 2), (3, 2),   # left triangle
        (6, 1), (5, 2), (6, 2), (7, 2),   # right triangle
    ]
    # Triangle nose: apex at top, base below — centered
    _NOSE = [(4, 3), (3, 4), (4, 4), (5, 4)]
    # Jagged zigzag smile across row 5 with teeth dipping into row 4
    _MOUTH = [(1, 5), (2, 4), (3, 5), (4, 4), (5, 5), (6, 4), (7, 5)]

    def __init__(self, width, height, cfg, animator):
        self._w = width
        self._at = animator.anim_top
        self._ab = animator.anim_bottom
        self._ox = width - 12
        self._oy = self._ab - 8
        self._frame = 0
        self._flicker = 0
        self._total = 30 + 90 + 30   # fade in, hold, fade out

    def _alpha(self) -> float:
        f = self._frame
        if f < 30:
            return f / 30.0
        elif f < 120:
            return 1.0
        else:
            return 1.0 - (f - 120) / 30.0

    def update(self):
        self._frame += 1
        self._flicker = (self._frame // 7) % 3

    def draw(self, canvas):
        alpha = max(0.0, min(1.0, self._alpha()))
        ox, oy = self._ox, self._oy
        for dx, dy, r, g, b in self._BODY:
            px, py = ox + dx, oy + dy
            if 0 <= px < self._w and self._at <= py <= self._ab:
                canvas.SetPixel(px, py, int(r * alpha), int(g * alpha), int(b * alpha))
        # Eyes: bright yellow/orange glow with flicker, drawn as cut-outs
        eye_r = int((200 + self._flicker * 20) * alpha)
        eye_g = int((160 + self._flicker * 15) * alpha)
        for ex, ey in self._EYES:
            px, py = ox + ex, oy + ey
            if 0 <= px < self._w and self._at <= py <= self._ab:
                canvas.SetPixel(px, py, eye_r, eye_g, 0)
        # Nose: yellow glow
        nose_r = int(180 * alpha)
        nose_g = int(140 * alpha)
        for nx, ny in self._NOSE:
            px, py = ox + nx, oy + ny
            if 0 <= px < self._w and self._at <= py <= self._ab:
                canvas.SetPixel(px, py, nose_r, nose_g, 0)
        # Mouth: black cutout
        for mx, my in self._MOUTH:
            px, py = ox + mx, oy + my
            if 0 <= px < self._w and self._at <= py <= self._ab:
                canvas.SetPixel(px, py, 0, 0, 0)

    def is_done(self) -> bool:
        return self._frame >= self._total
