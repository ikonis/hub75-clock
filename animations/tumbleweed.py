import math
import random


class Animation:
    name = "tumbleweed"
    conditions = []
    themes = ["Day"]
    layer = "foreground"

    # 5-pixel diameter circle pixel offsets
    _CIRCLE = [
        (1, 0), (2, 0), (3, 0),
        (0, 1), (4, 1),
        (0, 2), (4, 2),
        (1, 3), (2, 3), (3, 3),
        # spokes (inner detail)
        (2, 1), (1, 2), (3, 2), (2, 3),
    ]

    def __init__(self, width, height, cfg, animator):
        self._w = width
        self._at = animator.anim_top
        self._ab = animator.anim_bottom
        self.x = float(-6)
        self._base_y = float(self._ab - 4)
        self._roll = 0.0
        self._vx = 0.35 + random.random() * 0.2

    def update(self):
        self.x += self._vx
        self._roll += self._vx * 0.4   # rotation for bounce effect

    def draw(self, canvas):
        ox = int(round(self.x))
        bounce = int(round(abs(math.sin(self._roll)) * 1.5))
        oy = int(self._base_y - bounce)

        for dx, dy in self._CIRCLE:
            # Rotate pixels slightly based on roll for tumbling look
            cx = dx - 2
            cy = dy - 2
            angle = self._roll
            rx = cx * math.cos(angle) - cy * math.sin(angle)
            ry = cx * math.sin(angle) + cy * math.cos(angle)
            px = ox + 2 + int(round(rx))
            py = oy + 2 + int(round(ry))
            if 0 <= px < self._w and self._at <= py <= self._ab:
                # Vary brightness slightly for texture
                shade = 140 + int(30 * math.sin(self._roll + dx))
                canvas.SetPixel(px, py, shade, int(shade * 0.7), int(shade * 0.3))

    def is_done(self) -> bool:
        return self.x > self._w + 6
