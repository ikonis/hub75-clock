import math
import random


class Animation:
    name = "butterfly"
    conditions = ["CLEAR"]
    themes = ["Day"]
    layer = "foreground"

    # Two frames: wings open and wings closed
    # Body center at (3, 2), wings span ±4
    # Frame 0: wings open
    _OPEN = [
        # Left wing (upper)
        (0, 0, 255, 120, 30), (1, 0, 255, 160, 50), (2, 0, 255, 200, 80),
        (0, 1, 255, 140, 40), (1, 1, 255, 180, 60), (2, 1, 255, 210, 90),
        # Right wing (upper)
        (4, 0, 255, 120, 30), (5, 0, 255, 160, 50), (6, 0, 255, 200, 80),
        (4, 1, 255, 140, 40), (5, 1, 255, 180, 60), (6, 1, 255, 210, 90),
        # Left wing (lower)
        (0, 3, 220, 80, 20), (1, 3, 240, 120, 40),
        (0, 4, 200, 60, 10), (1, 4, 220, 100, 30),
        # Right wing (lower)
        (5, 3, 220, 80, 20), (6, 3, 240, 120, 40),
        (5, 4, 200, 60, 10), (6, 4, 220, 100, 30),
        # Body
        (3, 1, 40, 20, 10), (3, 2, 50, 25, 12), (3, 3, 40, 20, 10),
    ]
    # Frame 1: wings angled (closed-ish)
    _CLOSED = [
        # Left wing (folded up)
        (1, 0, 255, 140, 40), (2, 0, 255, 190, 70),
        (1, 1, 255, 120, 30), (2, 1, 255, 170, 60),
        # Right wing (folded up)
        (4, 0, 255, 140, 40), (5, 0, 255, 190, 70),
        (4, 1, 255, 120, 30), (5, 1, 255, 170, 60),
        # Body
        (3, 1, 40, 20, 10), (3, 2, 50, 25, 12), (3, 3, 40, 20, 10),
    ]

    def __init__(self, width, height, cfg, animator):
        self._w = width
        self._at = animator.anim_top
        self._ab = animator.anim_bottom
        self.x = float(-8)
        self.y = float(self._at + random.randint(3, 12))
        self._vx = 0.3 + random.random() * 0.2
        self._frame = 0
        self._wave = random.random() * math.pi * 2

    def update(self):
        self._frame += 1
        self._wave += 0.12
        self.x += self._vx
        self.y += math.sin(self._wave) * 0.4

    def draw(self, canvas):
        ox = int(round(self.x))
        oy = int(round(self.y))
        sprite = self._OPEN if (self._frame // 5) % 2 == 0 else self._CLOSED
        for dx, dy, r, g, b in sprite:
            px, py = ox + dx, oy + dy
            if 0 <= px < self._w and self._at <= py <= self._ab:
                canvas.SetPixel(px, py, r, g, b)

    def is_done(self) -> bool:
        return self.x > self._w + 10
