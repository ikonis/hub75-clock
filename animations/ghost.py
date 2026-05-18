import math
import random


class Animation:
    name = "ghost"
    conditions = []
    themes = ["Night", "Late Evening"]

    # Ghost: dome top + wavy bottom skirt, ~7 wide x 9 tall
    # (dx, dy, r, g, b)
    _DOME = [
        # Top dome
        (2, 0, 160, 160, 180), (3, 0, 180, 180, 200), (4, 0, 160, 160, 180),
        (1, 1, 150, 150, 170), (2, 1, 190, 190, 210), (3, 1, 200, 200, 220),
        (4, 1, 190, 190, 210), (5, 1, 150, 150, 170),
        (0, 2, 140, 140, 160), (1, 2, 180, 180, 200), (2, 2, 200, 200, 220),
        (3, 2, 210, 210, 230), (4, 2, 200, 200, 220), (5, 2, 180, 180, 200),
        (6, 2, 140, 140, 160),
        # Body
        (0, 3, 140, 140, 160), (1, 3, 180, 180, 200), (2, 3, 200, 200, 220),
        (3, 3, 210, 210, 230), (4, 3, 200, 200, 220), (5, 3, 180, 180, 200),
        (6, 3, 140, 140, 160),
        (0, 4, 140, 140, 160), (1, 4, 170, 170, 190), (2, 4, 190, 190, 210),
        (3, 4, 200, 200, 220), (4, 4, 190, 190, 210), (5, 4, 170, 170, 190),
        (6, 4, 140, 140, 160),
        # Eyes
        (2, 2, 40, 40, 80), (3, 2, 40, 40, 80), (4, 2, 40, 40, 80),
        (2, 3, 40, 40, 80), (4, 3, 40, 40, 80),
    ]
    # Wavy skirt bottom — redrawn each frame based on wave phase
    _SKIRT_BASE = [0, 1, 2, 1, 0, 1, 2, 1]  # y offsets for each x column 0-6

    def __init__(self, width, height, cfg, animator):
        self._w = width
        self._at = animator.anim_top
        self._ab = animator.anim_bottom
        self.x = float(width + 2)
        mid = (self._at + self._ab) // 2
        self._base_y = float(mid - 5 + random.randint(0, 3))
        self._vx = -(0.3 + random.random() * 0.15)
        self._wave = random.random() * math.pi * 2
        self._bob = random.random() * math.pi * 2

    def update(self):
        self.x += self._vx
        self._wave += 0.08
        self._bob += 0.05

    def draw(self, canvas):
        ox = int(round(self.x))
        oy = int(round(self._base_y + math.sin(self._bob) * 2.0))
        # Draw dome body
        for dx, dy, r, g, b in self._DOME:
            px, py = ox + dx, oy + dy
            if 0 <= px < self._w and self._at <= py <= self._ab:
                canvas.SetPixel(px, py, r, g, b)
        # Draw wavy skirt at bottom of body (dy=5..7)
        for col in range(7):
            skirt_dy = 5 + int(1.0 + math.sin(self._wave + col * 0.8))
            px = ox + col
            py = oy + skirt_dy
            if 0 <= px < self._w and self._at <= py <= self._ab:
                canvas.SetPixel(px, py, 130, 130, 150)
            # Second skirt row
            py2 = py + 1
            if 0 <= px < self._w and self._at <= py2 <= self._ab:
                canvas.SetPixel(px, py2, 110, 110, 130)

    def is_done(self) -> bool:
        return self.x < -10
