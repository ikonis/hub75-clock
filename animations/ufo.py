import math
import random


class Animation:
    name = "ufo"
    conditions = ["CLEAR", "PARTLYCLOUDY"]
    themes = ["Night", "Late Evening"]

    # Saucer sprite (9 wide, 5 tall), row by row, (dx, dy, r, g, b)
    _BODY = [
        # dome (top, 3 wide centered)
        (3, 0, 120, 220, 140), (4, 0, 140, 255, 160), (5, 0, 120, 220, 140),
        # upper hull
        (1, 1, 60, 160, 70), (2, 1, 90, 200, 100), (3, 1, 110, 230, 120),
        (4, 1, 120, 240, 130), (5, 1, 110, 230, 120), (6, 1, 90, 200, 100),
        (7, 1, 60, 160, 70),
        # mid hull (widest)
        (0, 2, 40, 100, 50), (1, 2, 70, 170, 80), (2, 2, 100, 210, 110),
        (3, 2, 110, 220, 120), (4, 2, 120, 230, 130), (5, 2, 110, 220, 120),
        (6, 2, 100, 210, 110), (7, 2, 70, 170, 80), (8, 2, 40, 100, 50),
        # lower hull
        (1, 3, 50, 140, 60), (2, 3, 70, 170, 80), (3, 3, 80, 180, 90),
        (4, 3, 90, 190, 100), (5, 3, 80, 180, 90), (6, 3, 70, 170, 80),
        (7, 3, 50, 140, 60),
    ]
    # Underbelly lights (cycle through positions)
    _LIGHTS = [(2, 4), (4, 4), (6, 4)]

    def __init__(self, width, height, cfg, animator):
        self._w = width
        self._at = animator.anim_top
        self._ab = animator.anim_bottom
        self.x = float(width)          # start off right edge
        self.y = float(self._at + random.randint(2, 8))
        self._vx = -(0.25 + random.random() * 0.2)
        self._frame = 0
        self._wobble_offset = random.random() * math.pi * 2
        self._light_phase = 0

    def update(self):
        self._frame += 1
        self.x += self._vx
        self._wobble_offset += 0.08
        self._light_phase = (self._light_phase + 1) % (len(self._LIGHTS) * 6)

    def draw(self, canvas):
        ox = int(round(self.x))
        oy = int(round(self.y + math.sin(self._wobble_offset) * 1.2))
        # Body
        for dx, dy, r, g, b in self._BODY:
            canvas.SetPixel(ox + dx, oy + dy, r, g, b)
        # Cycling light under belly
        li = self._light_phase // 6
        for idx, (ldx, ldy) in enumerate(self._LIGHTS):
            if idx == li:
                canvas.SetPixel(ox + ldx, oy + ldy, 0, 255, 180)
            else:
                canvas.SetPixel(ox + ldx, oy + ldy, 0, 60, 40)
        # Glow trail
        for i in range(1, 5):
            gx = ox + 9 + i
            gb = max(0, 20 - i * 5)
            if 0 <= gx < self._w:
                canvas.SetPixel(gx, oy + 2, 0, gb, gb // 2)

    def is_done(self) -> bool:
        return self.x < -10
