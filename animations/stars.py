import math
import random


class _Star:
    __slots__ = ("x", "y", "phase", "speed", "max_brightness")

    def __init__(self, x, y, phase, speed, max_brightness):
        self.x = x
        self.y = y
        self.phase = phase
        self.speed = speed
        self.max_brightness = max_brightness


class Animation:
    name = "stars"
    conditions = []
    themes = []
    layer = "celestial"
    persistent = True
    # Star twinkle speed multiplier — edit to taste.
    speed = 1.0

    def __init__(self, width, height, cfg, animator):
        self._frame = 0
        self._fps = cfg.get("animation", {}).get("fps", 15)
        self._stars = []

        anim_h = animator.anim_bottom - animator.anim_top + 1
        count = max(8, (width * anim_h) // 30)
        for _ in range(count):
            self._stars.append(_Star(
                x=random.randint(0, width - 1),
                y=random.randint(animator.anim_top, animator.anim_bottom),
                phase=random.random() * 6.28,
                speed=random.uniform(0.05, 0.15) * (15.0 / self._fps) * self.speed,
                max_brightness=random.choice([60, 80, 100, 140, 200]),
            ))

    def update(self):
        self._frame += 1

    def draw(self, canvas):
        for s in self._stars:
            phase = s.phase + (self._frame * s.speed)
            level = (math.sin(phase) + 1.0) * 0.5
            b = int(s.max_brightness * level)
            if b > 5:
                canvas.SetPixel(s.x, s.y, b, b, b)

    def is_done(self) -> bool:
        return False
