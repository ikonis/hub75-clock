import math
import random


class Animation:
    name = "comet"
    conditions = ["CLEAR"]
    themes = ["Night"]
    layer = "celestial"

    # --- Appearance settings ---
    COLOR_HEAD      = (220, 240, 255)   # bright blue-white leading pixel
    COLOR_HEAD_GLOW = (120, 160, 220)   # 1px glow halo around head
    TAIL_R = 180   # tail root red channel (fades to 0 at tip)
    TAIL_G = 200   # tail root green channel
    TAIL_B = 255   # tail root blue channel (fades least — stays blue)
    # ---------------------------

    def __init__(self, width, height, cfg, animator):
        self._w = width
        self._at = animator.anim_top
        self._ab = animator.anim_bottom
        self._tail_len = random.randint(10, 14)
        # Random diagonal: down-left or down-right
        speed = 0.35 + random.random() * 0.25
        steep = 0.20 + random.random() * 0.15
        if random.choice([True, False]):
            self._vx = speed
            self.x = float(-self._tail_len - 2)
        else:
            self._vx = -speed
            self.x = float(width + self._tail_len + 2)
        self.y = float(self._at + random.randint(1, 6))
        self._vy = steep   # always drifts downward
        self._frame = 0

    def update(self):
        self._frame += 1
        self.x += self._vx
        self.y += self._vy

    def draw(self, canvas):
        hx = int(round(self.x))
        hy = int(round(self.y))

        # Tail direction: opposite to velocity
        vlen = math.sqrt(self._vx ** 2 + self._vy ** 2)
        tdx = -self._vx / vlen
        tdy = -self._vy / vlen

        for i in range(1, self._tail_len + 1):
            tx = hx + int(round(tdx * i))
            ty = hy + int(round(tdy * i))
            if not (0 <= tx < self._w and self._at <= ty <= self._ab):
                continue
            t = i / self._tail_len
            r = int(self.TAIL_R * (1 - t))
            g = int(self.TAIL_G * (1 - t * 0.6))
            b = int(self.TAIL_B * (1 - t * 0.3))
            canvas.SetPixel(tx, ty, r, g, b)
            if i < self._tail_len // 2:
                dim = int((1 - t) * 80)
                for off in (-1, 1):
                    ny = ty + off
                    if self._at <= ny <= self._ab:
                        canvas.SetPixel(tx, ny, dim // 2, dim // 2, dim)

        # Bright blue-white head
        if 0 <= hx < self._w and self._at <= hy <= self._ab:
            canvas.SetPixel(hx, hy, *self.COLOR_HEAD)
            for ddx, ddy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                gx, gy = hx + ddx, hy + ddy
                if 0 <= gx < self._w and self._at <= gy <= self._ab:
                    canvas.SetPixel(gx, gy, *self.COLOR_HEAD_GLOW)

    def is_done(self) -> bool:
        return (self.x < -self._tail_len - 4 or
                self.x > self._w + self._tail_len + 4 or
                self.y > self._ab + 2)
