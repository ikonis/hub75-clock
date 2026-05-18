import math
import random


class Animation:
    name = "meteor"
    conditions = ["CLEAR"]
    themes = ["Night", "Late Evening"]

    def __init__(self, width, height, cfg, animator):
        self._w = width
        self._at = animator.anim_top
        self._ab = animator.anim_bottom
        speed = 3.5 + random.random() * 1.5
        # Steep diagonal: always falls downward, randomize left/right
        if random.choice([True, False]):
            self._vx = speed
            self.x = float(-2)
        else:
            self._vx = -speed
            self.x = float(width + 2)
        self._vy = speed * (0.35 + random.random() * 0.3)   # downward component
        self.y = float(self._at + random.randint(0, 5))
        self._history: list = []

    def update(self):
        self._history.append((self.x, self.y))
        if len(self._history) > 8:
            self._history.pop(0)
        self.x += self._vx
        self.y += self._vy

    def draw(self, canvas):
        tail_colors = [
            (230, 130, 30), (210, 90, 15), (170, 50, 8),
            (130, 25, 4), (90, 10, 2), (55, 4, 0), (30, 1, 0), (12, 0, 0),
        ]
        for i, (hx, hy) in enumerate(reversed(self._history)):
            c = tail_colors[min(i, len(tail_colors) - 1)]
            px, py = int(round(hx)), int(round(hy))
            if 0 <= px < self._w and self._at <= py <= self._ab:
                canvas.SetPixel(px, py, *c)

        hx, hy = int(round(self.x)), int(round(self.y))
        if 0 <= hx < self._w and self._at <= hy <= self._ab:
            canvas.SetPixel(hx, hy, 255, 255, 255)
            for ddx, ddy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                gx, gy = hx + ddx, hy + ddy
                if 0 <= gx < self._w and self._at <= gy <= self._ab:
                    canvas.SetPixel(gx, gy, 255, 210, 80)

    def is_done(self) -> bool:
        return (self.x < -12 or self.x >= self._w + 12 or self.y > self._ab + 2)
