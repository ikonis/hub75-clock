import math
import random


class Animation:
    name = "satellite"
    conditions = ["CLEAR"]
    themes = ["Night"]
    layer = "celestial"
    speed = 0.8

    # --- Appearance settings ---
    # Edit colors directly in _SPRITE below.
    # Key areas: solar panels (blue 40-60, 80-120, 120-180),
    #            body (silver ~200,200,220), truss (gray 100,100,120)
    # ---------------------------

    # ISS-like profile: central body + solar panel wings
    # Offsets from top-left of bounding box (11 wide, 3 tall)
    _SPRITE = [
        # Left solar panel
        (0, 1, 40, 80, 120), (1, 1, 60, 120, 180),
        # Body
        (3, 0, 180, 180, 200), (4, 0, 200, 200, 220),
        (3, 1, 200, 200, 220), (4, 1, 220, 220, 240), (5, 1, 200, 200, 220),
        (3, 2, 180, 180, 200), (4, 2, 200, 200, 220),
        # Right solar panel
        (7, 1, 60, 120, 180), (8, 1, 40, 80, 120),
        # Truss connector
        (2, 1, 100, 100, 120), (6, 1, 100, 100, 120),
    ]

    def __init__(self, width, height, cfg, animator):
        self._w = width
        self._at = animator.anim_top
        self._ab = animator.anim_bottom
        zone_h = self._ab - self._at
        direction = random.choice(["right_to_left", "left_to_right", "top_to_bottom", "bottom_to_top"])
        drift = (0.12 + random.random() * 0.06) * self.speed
        speed = (0.4 + random.random() * 0.2) * self.speed
        if direction == "right_to_left":
            self.x  = float(width - 2)
            self.y  = float(self._at + random.randint(0, zone_h - 4))
            self._vx = -speed
            self._vy =  drift
        elif direction == "left_to_right":
            self.x  = float(-10)
            self.y  = float(self._at + random.randint(0, zone_h - 4))
            self._vx =  speed
            self._vy =  drift
        elif direction == "top_to_bottom":
            self.x  = float(random.randint(2, width - 12))
            self.y  = float(self._at)
            self._vx = (random.random() - 0.5) * drift
            self._vy =  speed
        else:  # bottom_to_top
            self.x  = float(random.randint(2, width - 12))
            self.y  = float(self._ab)
            self._vx = (random.random() - 0.5) * drift
            self._vy = -speed

    def update(self):
        self.x += self._vx
        self.y += self._vy

    def draw(self, canvas):
        ox = int(round(self.x))
        oy = int(round(self.y))
        for dx, dy, r, g, b in self._SPRITE:
            px = ox + dx
            py = oy + dy
            if 0 <= px < self._w and self._at <= py <= self._ab:
                canvas.SetPixel(px, py, r, g, b)

    def is_done(self) -> bool:
        return (self.x < -12 or self.x > self._w + 12 or
                self.y < self._at - 4 or self.y > self._ab + 4)
