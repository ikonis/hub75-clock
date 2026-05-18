import math
import random


class Animation:
    name = "ghost"
    conditions = []
    themes = ["Night", "Late Evening"]

    # Pac-Man style ghost: 7 wide x 8 tall
    # Body pixels (excluding eye area), drawn in ghost color
    _BODY = [
        # Dome top
        (1, 0), (2, 0), (3, 0), (4, 0), (5, 0),
        # Full rows
        (0, 1), (1, 1), (2, 1), (3, 1), (4, 1), (5, 1), (6, 1),
        # Eye row sides only (1-2 and 4-5 are white eyes)
        (0, 2), (3, 2), (6, 2),
        (0, 3), (3, 3), (6, 3),
        # Lower body
        (0, 4), (1, 4), (2, 4), (3, 4), (4, 4), (5, 4), (6, 4),
        (0, 5), (1, 5), (2, 5), (3, 5), (4, 5), (5, 5), (6, 5),
        # Scalloped bottom: 4 bumps at columns 0, 2, 4, 6
        (0, 6), (2, 6), (4, 6), (6, 6),
    ]
    # White eye ovals
    _EYES_WHITE = [
        (1, 2), (2, 2), (4, 2), (5, 2),
        (1, 3), (2, 3), (4, 3), (5, 3),
    ]
    # Colored pupils (blue, always)
    _PUPILS = [(2, 3), (5, 3)]

    _COLORS = [
        (220, 20,  20),   # red (Blinky)
        (255, 180, 200),  # pink (Pinky)
        (20,  210, 220),  # cyan (Inky)
        (255, 140, 0),    # orange (Clyde)
    ]

    def __init__(self, width, height, cfg, animator):
        self._w = width
        self._at = animator.anim_top
        self._ab = animator.anim_bottom
        self._color = random.choice(self._COLORS)
        self._right = random.choice([True, False])
        if self._right:
            self.x = float(-8)
            self._vx = 0.28 + random.random() * 0.12
        else:
            self.x = float(width + 2)
            self._vx = -(0.28 + random.random() * 0.12)
        mid = (self._at + self._ab) // 2
        self._base_y = float(mid - 4 + random.randint(0, 4))
        self._bob = random.random() * math.pi * 2

    def update(self):
        self.x += self._vx
        self._bob += 0.06

    def draw(self, canvas):
        ox = int(round(self.x))
        oy = int(round(self._base_y + math.sin(self._bob) * 2.0))
        r, g, b = self._color
        for dx, dy in self._BODY:
            px, py = ox + dx, oy + dy
            if 0 <= px < self._w and self._at <= py <= self._ab:
                canvas.SetPixel(px, py, r, g, b)
        for dx, dy in self._EYES_WHITE:
            px, py = ox + dx, oy + dy
            if 0 <= px < self._w and self._at <= py <= self._ab:
                canvas.SetPixel(px, py, 240, 240, 240)
        for dx, dy in self._PUPILS:
            px, py = ox + dx, oy + dy
            if 0 <= px < self._w and self._at <= py <= self._ab:
                canvas.SetPixel(px, py, 30, 30, 200)

    def is_done(self) -> bool:
        return self.x > self._w + 10 or self.x < -12
