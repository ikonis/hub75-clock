import math
import random


class Animation:
    name = "rocket"
    conditions = []
    themes = []
    layer = "foreground"

    # Rocket facing upward: 3 wide, 7 tall
    # (dx, dy, r, g, b)
    _BODY = [
        # Nose
        (1, 0, 220, 220, 240),
        # Upper body
        (0, 1, 200, 200, 220), (1, 1, 220, 220, 240), (2, 1, 200, 200, 220),
        (0, 2, 190, 190, 210), (1, 2, 210, 210, 230), (2, 2, 190, 190, 210),
        # Mid body with window
        (0, 3, 190, 190, 210), (1, 3, 100, 180, 255), (2, 3, 190, 190, 210),
        # Lower body
        (0, 4, 200, 60, 60), (1, 4, 220, 70, 70), (2, 4, 200, 60, 60),
        # Fins
        (-1, 5, 180, 50, 50), (0, 5, 210, 65, 65), (1, 5, 220, 70, 70),
        (2, 5, 210, 65, 65), (3, 5, 180, 50, 50),
    ]

    def __init__(self, width, height, cfg, animator):
        self._w = width
        self._at = animator.anim_top
        self._ab = animator.anim_bottom
        self.x = float(random.randint(4, width - 5))
        self.y = float(self._ab - 2)
        self._vy = -(0.5 + random.random() * 0.3)
        self._frame = 0

    def update(self):
        self._vy -= 0.04   # accelerate upward
        self.y += self._vy
        self._frame += 1

    def draw(self, canvas):
        ox = int(round(self.x))
        oy = int(round(self.y))
        for dx, dy, r, g, b in self._BODY:
            px, py = ox + dx, oy + dy
            if 0 <= px < self._w and self._at <= py <= self._ab:
                canvas.SetPixel(px, py, r, g, b)
        # Flame trail below rocket
        flame_y = oy + 6
        for fi in range(4):
            fy = flame_y + fi
            if self._at <= fy <= self._ab:
                fade = 1.0 - fi / 4.0
                fr = int(255 * fade)
                fg = int(120 * fade * (1 - fi * 0.2))
                canvas.SetPixel(ox + 1, fy, fr, fg, 0)
                if fi < 2:
                    canvas.SetPixel(ox, fy, int(fr * 0.6), int(fg * 0.4), 0)
                    canvas.SetPixel(ox + 2, fy, int(fr * 0.6), int(fg * 0.4), 0)

    def is_done(self) -> bool:
        return self.y < self._at - 10
