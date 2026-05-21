import math
import random


class _Star:
    __slots__ = ("x", "y", "vx", "vy", "life", "max_life")

    def __init__(self, x, y, vx, vy, life):
        self.x = x; self.y = y; self.vx = vx; self.vy = vy
        self.life = life; self.max_life = life


class Animation:
    name       = "shooting_star"
    conditions = ["CLEAR", "PARTLYCLOUDY"]
    themes     = []
    layer      = "celestial"
    persistent = False

    _ALLOWED = frozenset({"CLEAR", "PARTLYCLOUDY"})

    def __init__(self, width, height, cfg, animator):
        self._w  = width
        self._at = animator.anim_top
        self._ab = animator.anim_bottom
        self._star = None

        if getattr(animator, "condition", "CLEAR") not in self._ALLOWED:
            return

        anim_third = self._at + (self._ab - self._at + 1) // 3
        speed = random.uniform(1.0, 2.5)
        if random.random() < 0.5:
            speed = -speed
        self._star = _Star(
            x=random.uniform(0, width),
            y=random.uniform(self._at, anim_third),
            vx=speed,
            vy=random.uniform(0.8, 1.4),
            life=random.randint(10, 16),
        )

    def update(self):
        if self._star is None:
            return
        self._star.life -= 1
        self._star.x   += self._star.vx
        self._star.y   += self._star.vy

    def draw(self, canvas):
        if self._star is None:
            return
        ss = self._star
        brightness = int(220 * (ss.life / ss.max_life))
        self._px(canvas, int(ss.x), int(ss.y), brightness)
        for i in range(1, 6):
            trail_b = int(brightness * (1.0 - i / 5.0))
            if trail_b > 5:
                self._px(canvas,
                         int(ss.x - ss.vx * i),
                         int(ss.y - ss.vy * i),
                         trail_b)

    def _px(self, canvas, x, y, b):
        if 0 <= x < self._w and self._at <= y <= self._ab:
            canvas.SetPixel(x, y, b, b, b)

    def is_done(self) -> bool:
        return self._star is None or self._star.life <= 0
