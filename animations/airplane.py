import math
import random


class Animation:
    name = "airplane"
    conditions = []
    themes = ["Day", "Sunrise", "Sunset"]
    layer = "foreground"
    speed = 1.0

    # --- Appearance settings ---
    # Edit colors directly in _SPRITE_R below.
    # Key areas: fuselage (silver-gray ~210,210,220), windows (blue 160,200,255)
    # ---------------------------

    # Sprite offsets — fuselage 8px long, 2px tall, wing at col 3, tail at col 7
    # (dx, dy, r, g, b)  — facing RIGHT
    _SPRITE_R = [
        # Nose cone
        (0, 1, 220, 220, 230),
        # Fuselage top row
        (1, 0, 200, 200, 210), (2, 0, 210, 210, 220), (3, 0, 210, 210, 220),
        (4, 0, 210, 210, 220), (5, 0, 200, 200, 210), (6, 0, 190, 190, 200),
        (7, 0, 180, 180, 190),
        # Fuselage bottom row
        (1, 1, 200, 200, 210), (2, 1, 210, 210, 220), (3, 1, 210, 210, 220),
        (4, 1, 210, 210, 220), (5, 1, 200, 200, 210), (6, 1, 180, 180, 190),
        (7, 1, 160, 160, 170),
        # Wing (below fuselage)
        (2, 2, 180, 180, 190), (3, 2, 200, 200, 210), (4, 2, 200, 200, 210),
        (5, 2, 180, 180, 190),
        # Tail fin
        (6, -1, 190, 190, 200), (7, -1, 180, 180, 190),
        # Windows (dots)
        (2, 1, 160, 200, 255), (4, 1, 160, 200, 255),
    ]

    def __init__(self, width, height, cfg, animator):
        self._w = width
        self._at = animator.anim_top
        self._ab = animator.anim_bottom
        self._right = random.choice([True, False])
        self._trail = []
        self._trail_max = 18
        self.y = float(self._at + random.randint(5, 11))
        if self._right:
            self.x = float(-10)
            self._vx = (0.45 + random.random() * 0.2) * self.speed
        else:
            self.x = float(width + 1)
            self._vx = -(0.45 + random.random() * 0.2) * self.speed

    def draw(self, canvas):
        for i, (tx, ty) in enumerate(self._trail):
            fade = (i + 1) / len(self._trail)
            b = int(85 * fade)
            if b <= 4:
                continue
            px, py = int(round(tx)), int(round(ty))
            if 0 <= px < self._w and self._at <= py <= self._ab:
                canvas.SetPixel(px, py, b, b, b)
                if i % 3 == 0 and self._at <= py + 1 <= self._ab:
                    dim = b // 2
                    canvas.SetPixel(px, py + 1, dim, dim, dim)

        ox = int(round(self.x))
        oy = int(round(self.y))
        for dx, dy, r, g, b in self._SPRITE_R:
            if self._right:
                dx = 8 - dx   # mirror horizontally
            px, py = ox + dx, oy + dy
            if 0 <= px < self._w and self._at - 2 <= py <= self._ab:
                canvas.SetPixel(px, py, r, g, b)

    def update(self):
        trail_x = self.x - 2 if self._right else self.x + 10
        trail_y = self.y + 1
        self._trail.append((trail_x, trail_y))
        if len(self._trail) > self._trail_max:
            self._trail.pop(0)
        self.x += self._vx

    def is_done(self) -> bool:
        return self.x > self._w + 12 or self.x < -12
