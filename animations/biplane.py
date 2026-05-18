import math
import random


class Animation:
    name = "biplane"
    conditions = ["CLEAR"]
    themes = ["Day"]

    # Facing right: body 8px, double wings, prop dot at front
    _SPRITE = [
        # Upper wing
        (1, 0, 180, 160, 120), (2, 0, 190, 170, 130), (3, 0, 190, 170, 130),
        (4, 0, 180, 160, 120), (5, 0, 160, 140, 100),
        # Wing struts
        (2, 1, 140, 120, 80), (5, 1, 140, 120, 80),
        # Fuselage
        (0, 2, 200, 180, 140), (1, 2, 210, 190, 150), (2, 2, 210, 190, 150),
        (3, 2, 200, 180, 140), (4, 2, 190, 170, 130),
        (5, 2, 180, 160, 120), (6, 2, 160, 140, 100), (7, 2, 140, 120, 80),
        # Lower wing
        (1, 3, 180, 160, 120), (2, 3, 190, 170, 130), (3, 3, 190, 170, 130),
        (4, 3, 180, 160, 120), (5, 3, 160, 140, 100),
        # Tail
        (6, 1, 160, 140, 100), (7, 1, 150, 130, 90),
        (6, 3, 160, 140, 100),
        # Cockpit
        (3, 2, 100, 160, 200),
    ]

    def __init__(self, width, height, cfg, animator):
        self._w = width
        self._at = animator.anim_top
        self._ab = animator.anim_bottom
        self._right = random.choice([True, False])
        self.y = float(self._at + random.randint(3, 10))
        if self._right:
            self.x = float(-10)
            self._vx = 0.4 + random.random() * 0.2
        else:
            self.x = float(width + 2)
            self._vx = -(0.4 + random.random() * 0.2)
        self._frame = 0

    def update(self):
        self.x += self._vx
        self._frame += 1

    def draw(self, canvas):
        ox = int(round(self.x))
        oy = int(round(self.y))
        for dx, dy, r, g, b in self._SPRITE:
            if not self._right:
                dx = 8 - dx
            px, py = ox + dx, oy + dy
            if 0 <= px < self._w and self._at - 2 <= py <= self._ab:
                canvas.SetPixel(px, py, r, g, b)
        # Propeller dot — alternates y position
        prop_dx = -1 if self._right else 9
        prop_dy = 2 + ((self._frame // 3) % 2)
        ppx = ox + prop_dx
        ppy = oy + prop_dy
        if 0 <= ppx < self._w and self._at <= ppy <= self._ab:
            canvas.SetPixel(ppx, ppy, 220, 200, 160)

    def is_done(self) -> bool:
        return self.x > self._w + 12 or self.x < -12
