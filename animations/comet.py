import math
import random


class Animation:
    name = "comet"
    conditions = ["CLEAR"]
    themes = ["Night"]

    def __init__(self, width, height, cfg, animator):
        self._w = width
        self._at = animator.anim_top
        self._ab = animator.anim_bottom
        # Slow, left-to-right with slight downward arc
        self.x = float(-2)
        self.y = float(self._at + random.randint(1, 6))
        self._vx = 0.25 + random.random() * 0.15
        self._vy = 0.05 + random.random() * 0.04
        self._frame = 0
        self._tail_len = random.randint(10, 14)

    def update(self):
        self._frame += 1
        self.x += self._vx
        self.y += self._vy

    def draw(self, canvas):
        hx = int(round(self.x))
        hy = int(round(self.y))

        # Draw tail (blue-white gradient behind the head)
        for i in range(1, self._tail_len + 1):
            tx = hx - i
            ty = hy  # tail is horizontal-ish
            if not (0 <= tx < self._w and self._at <= ty <= self._ab):
                continue
            t = i / self._tail_len
            r = int(180 * (1 - t))
            g = int(200 * (1 - t * 0.6))
            b = int(255 * (1 - t * 0.3))
            canvas.SetPixel(tx, ty, r, g, b)
            # Thin tail above/below for depth
            if i < self._tail_len // 2:
                dim = int((1 - t) * 80)
                if self._at <= ty - 1 <= self._ab:
                    canvas.SetPixel(tx, ty - 1, dim // 2, dim // 2, dim)
                if self._at <= ty + 1 <= self._ab:
                    canvas.SetPixel(tx, ty + 1, dim // 2, dim // 2, dim)

        # Bright blue-white head
        if 0 <= hx < self._w and self._at <= hy <= self._ab:
            canvas.SetPixel(hx, hy, 220, 240, 255)
            for ddx, ddy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                gx, gy = hx + ddx, hy + ddy
                if 0 <= gx < self._w and self._at <= gy <= self._ab:
                    canvas.SetPixel(gx, gy, 120, 160, 220)

    def is_done(self) -> bool:
        return self.x > self._w + 2
