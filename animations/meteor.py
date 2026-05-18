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
        # Fast diagonal, head is bright white, tail is orange/red fade
        speed = 3.5 + random.random() * 1.5
        angle = math.radians(random.uniform(200, 250))  # steep downward-left
        self._vx = math.cos(angle) * speed
        self._vy = math.sin(angle) * speed
        # Start from upper region
        self.x = float(random.randint(20, width - 5))
        self.y = float(self._at + random.randint(0, 4))
        self._life = 0
        self._max_life = int((width / abs(self._vx)) * 0.6)
        self._history: list = []  # [(x, y)] trail positions

    def update(self):
        self._life += 1
        self._history.append((self.x, self.y))
        if len(self._history) > 6:
            self._history.pop(0)
        self.x += self._vx
        self.y += self._vy

    def draw(self, canvas):
        # Tail: orange/red fade
        tail_colors = [
            (200, 100, 20), (180, 60, 10), (140, 30, 5), (100, 15, 2), (60, 5, 0), (30, 2, 0)
        ]
        for i, (hx, hy) in enumerate(reversed(self._history)):
            c = tail_colors[min(i, len(tail_colors) - 1)]
            px, py = int(round(hx)), int(round(hy))
            if 0 <= px < self._w and self._at <= py <= self._ab:
                canvas.SetPixel(px, py, *c)
        # Bright white head
        hx, hy = int(round(self.x)), int(round(self.y))
        if 0 <= hx < self._w and self._at <= hy <= self._ab:
            canvas.SetPixel(hx, hy, 255, 255, 255)
            # Glow
            for ddx, ddy in ((-1,0),(1,0),(0,-1),(0,1)):
                gx, gy = hx + ddx, hy + ddy
                if 0 <= gx < self._w and self._at <= gy <= self._ab:
                    canvas.SetPixel(gx, gy, 230, 180, 80)

    def is_done(self) -> bool:
        return (self.x < -2 or self.x >= self._w or
                self.y < self._at or self.y > self._ab)
