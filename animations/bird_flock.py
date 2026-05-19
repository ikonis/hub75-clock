import math
import random


class Animation:
    name = "bird_flock"
    conditions = []
    themes = ["Day"]
    layer = "foreground"

    def __init__(self, width, height, cfg, animator):
        self._w = width
        self._at = animator.anim_top
        self._ab = animator.anim_bottom
        count = random.randint(5, 7)
        # V formation: leader at (0,0), followers spread behind and to sides
        self._birds = []
        row_y = self._at + random.randint(2, 6)
        for i in range(count):
            if i == 0:
                bx, by = 0.0, 0.0
            else:
                side = 1 if i % 2 == 1 else -1
                rank = (i + 1) // 2
                bx = -rank * 3.5
                by = rank * 1.5 * side
            self._birds.append([bx, by])
        self._vx = 0.35 + random.random() * 0.15
        self._ox = float(-8)
        self._oy = float(row_y)
        self._flap = 0

    def update(self):
        self._ox += self._vx
        self._flap += 1

    def draw(self, canvas):
        # Each bird is a tiny V: center dot + left-wing dot + right-wing dot
        wing_up = (self._flap // 6) % 2 == 0
        for bx, by in self._birds:
            cx = int(round(self._ox + bx))
            cy = int(round(self._oy + by))
            if 0 <= cx < self._w and self._at <= cy <= self._ab:
                canvas.SetPixel(cx, cy, 30, 30, 30)
                wy = cy - (1 if wing_up else 0)
                if 0 <= cx - 1 < self._w and self._at <= wy <= self._ab:
                    canvas.SetPixel(cx - 1, wy, 40, 40, 40)
                if 0 <= cx + 1 < self._w and self._at <= wy <= self._ab:
                    canvas.SetPixel(cx + 1, wy, 40, 40, 40)

    def is_done(self) -> bool:
        return self._ox > self._w + 10
