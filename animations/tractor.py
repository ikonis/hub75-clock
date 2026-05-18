import math
import random


class Animation:
    name = "tractor"
    conditions = []
    themes = ["Day"]

    # Tractor facing right: 14 wide, 9 tall
    # Large rear wheel center at (3, 5), r=4; small front wheel center at (11, 6), r=2
    # Cab: (5..8, 0..3), Hood: (9..12, 2..4), Exhaust at (8, -1..0)

    _SPRITE = [
        # Exhaust pipe + smoke
        (8, 0, 60, 55, 50), (8, 1, 60, 55, 50),
        # Cab roof
        (5, 1, 100, 80, 40), (6, 1, 120, 95, 50), (7, 1, 120, 95, 50),
        (8, 1, 110, 85, 45),
        # Cab walls + window
        (5, 2, 100, 80, 40), (6, 2, 160, 200, 230), (7, 2, 160, 200, 230),
        (8, 2, 100, 80, 40),
        (5, 3, 100, 80, 40), (6, 3, 120, 95, 50), (7, 3, 120, 95, 50),
        (8, 3, 100, 80, 40),
        # Hood / engine block
        (9, 2, 110, 85, 45), (10, 2, 120, 95, 50), (11, 2, 120, 95, 50),
        (12, 2, 100, 80, 40),
        (9, 3, 110, 85, 45), (10, 3, 120, 95, 50), (11, 3, 120, 95, 50),
        (12, 3, 100, 80, 40),
        (9, 4, 110, 85, 45), (10, 4, 120, 95, 50), (11, 4, 100, 80, 40),
        # Frame / chassis
        (4, 4, 80, 65, 35), (5, 4, 90, 70, 38), (6, 4, 90, 70, 38),
        (7, 4, 90, 70, 38), (8, 4, 90, 70, 38),
        # Hitch at rear
        (1, 5, 60, 50, 30), (2, 5, 70, 55, 32),
    ]

    def __init__(self, width, height, cfg, animator):
        self._w = width
        self._at = animator.anim_top
        self._ab = animator.anim_bottom
        self.x = float(-18)
        self._vx = 0.2 + random.random() * 0.1
        self._ground_y = self._ab - 4
        self._roll = 0.0

    def _draw_wheel(self, canvas, cx, cy, radius, col_outer, col_inner):
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                dist = math.sqrt(dx * dx + dy * dy)
                if dist <= radius:
                    px, py = cx + dx, cy + dy
                    if 0 <= px < self._w and self._at <= py <= self._ab:
                        if dist >= radius - 1:
                            canvas.SetPixel(px, py, *col_outer)
                        else:
                            canvas.SetPixel(px, py, *col_inner)
        # Spoke tick marks (rotate with roll)
        for spoke in range(4):
            angle = self._roll + spoke * (math.pi / 2)
            sx = cx + int(round(math.cos(angle) * (radius - 1)))
            sy = cy + int(round(math.sin(angle) * (radius - 1)))
            if 0 <= sx < self._w and self._at <= sy <= self._ab:
                canvas.SetPixel(sx, sy, 60, 50, 30)

    def update(self):
        self.x += self._vx
        self._roll += self._vx * 0.3

    def draw(self, canvas):
        ox = int(round(self.x))
        oy = self._ground_y - 8  # sprite top-left offset so wheels sit on ground
        # Static sprite elements
        for dx, dy, r, g, b in self._SPRITE:
            px, py = ox + dx, oy + dy
            if 0 <= px < self._w and self._at <= py <= self._ab:
                canvas.SetPixel(px, py, r, g, b)
        # Large rear wheel: center at sprite (3, 5) from sprite top-left
        self._draw_wheel(canvas, ox + 3, oy + 5, 4,
                         (50, 42, 25), (70, 58, 35))
        # Small front wheel: center at sprite (11, 6)
        self._draw_wheel(canvas, ox + 11, oy + 6, 2,
                         (50, 42, 25), (68, 56, 34))

    def is_done(self) -> bool:
        return self.x > self._w + 20
