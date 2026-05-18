import math
import random


class Animation:
    name = "fish"
    conditions = ["RAIN", "SNOW"]
    themes = []

    # Fish facing right: body oval + tail + eye, 9 wide x 5 tall
    # Mirror for left-facing direction
    _BODY_R = [
        # Tail (leftmost)
        (0, 1, 50, 100, 160), (0, 3, 50, 100, 160),
        (1, 0, 60, 120, 180), (1, 2, 80, 140, 200), (1, 4, 60, 120, 180),
        # Body
        (2, 1, 80, 150, 210), (2, 2, 100, 170, 230), (2, 3, 80, 150, 210),
        (3, 0, 70, 140, 200), (3, 1, 100, 170, 230), (3, 2, 120, 190, 240),
        (3, 3, 100, 170, 230), (3, 4, 70, 140, 200),
        (4, 0, 70, 140, 200), (4, 1, 100, 170, 230), (4, 2, 120, 190, 240),
        (4, 3, 100, 170, 230), (4, 4, 70, 140, 200),
        (5, 1, 90, 160, 220), (5, 2, 110, 180, 235), (5, 3, 90, 160, 220),
        (6, 1, 80, 150, 210), (6, 2, 100, 170, 230), (6, 3, 80, 150, 210),
        (7, 2, 70, 130, 190),
        # Eye (near head)
        (6, 1, 20, 20, 40),
        # Fin on top
        (4, 0, 60, 120, 175),
    ]
    # Left-facing mirrors dx: (8 - dx)
    _BODY_L = [(8 - dx, dy, r, g, b) for dx, dy, r, g, b in _BODY_R]

    def __init__(self, width, height, cfg, animator):
        self._w = width
        self._at = animator.anim_top
        self._ab = animator.anim_bottom
        self._go_right = random.random() < 0.5
        if self._go_right:
            self.x = float(-12)
            self._vx = 0.4 + random.random() * 0.2
            self._body = self._BODY_R
        else:
            self.x = float(width + 12)
            self._vx = -(0.4 + random.random() * 0.2)
            self._body = self._BODY_L
        mid = (self._at + self._ab) // 2
        self._base_y = float(mid - 2 + random.randint(-3, 3))
        self._wave = random.random() * math.pi * 2

    def update(self):
        self.x += self._vx
        self._wave += 0.12

    def draw(self, canvas):
        ox = int(round(self.x))
        oy = int(round(self._base_y + math.sin(self._wave) * 2.5))
        for dx, dy, r, g, b in self._body:
            px, py = ox + dx, oy + dy
            if 0 <= px < self._w and self._at <= py <= self._ab:
                canvas.SetPixel(px, py, r, g, b)

    def is_done(self) -> bool:
        if self._go_right:
            return self.x > self._w + 12
        return self.x < -12
