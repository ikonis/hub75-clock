import math
import random


class Animation:
    name = "fireworks"
    conditions = []
    themes = []

    _COLORS = [
        (255, 60,  60),   # red
        (60,  255, 60),   # green
        (60,  60,  255),  # blue
        (255, 255, 60),   # yellow
        (255, 60,  255),  # magenta
        (60,  255, 255),  # cyan
        (255, 160, 60),   # orange
        (255, 255, 255),  # white
    ]

    def __init__(self, width, height, cfg, animator):
        self._w = width
        self._at = animator.anim_top
        self._ab = animator.anim_bottom
        self._bursts_remaining = 3
        self._phase = "launch"
        self._frame = 0
        self._sparks: list = []
        self._rocket_x = 0.0
        self._rocket_y = 0.0
        self._apex_y = 0.0
        self._rocket_vy = 0.0
        self._burst_color = (255, 255, 255)
        self._wait = 0
        self._launch_new()

    def _launch_new(self):
        self._phase = "launch"
        self._frame = 0
        self._rocket_x = float(random.randint(10, self._w - 10))
        self._rocket_y = float(self._ab)
        self._apex_y = float(self._at + random.randint(2, 8))
        self._rocket_vy = -(1.5 + random.random() * 1.0)
        self._burst_color = random.choice(self._COLORS)
        self._sparks = []

    def _explode(self):
        self._phase = "explode"
        n = 12 + random.randint(0, 6)
        for i in range(n):
            angle = (2 * math.pi * i) / n + random.uniform(-0.2, 0.2)
            speed = 0.8 + random.random() * 1.5
            self._sparks.append([
                self._rocket_x, self._rocket_y,
                math.cos(angle) * speed,
                math.sin(angle) * speed,
                35 + random.randint(0, 15),   # life
                35 + random.randint(0, 15),   # max_life (for alpha)
            ])

    def update(self):
        self._frame += 1
        if self._phase == "launch":
            self._rocket_y += self._rocket_vy
            if self._rocket_y <= self._apex_y:
                self._rocket_y = self._apex_y
                self._explode()
        elif self._phase == "explode":
            alive = False
            for sp in self._sparks:
                sp[0] += sp[2]
                sp[1] += sp[3]
                sp[3] += 0.06   # gravity
                sp[4] -= 1
                if sp[4] > 0:
                    alive = True
            if not alive:
                self._bursts_remaining -= 1
                if self._bursts_remaining > 0:
                    self._wait = 12
                    self._phase = "wait"
                else:
                    self._phase = "done"
        elif self._phase == "wait":
            self._wait -= 1
            if self._wait <= 0:
                self._launch_new()

    def draw(self, canvas):
        if self._phase == "launch":
            rx, ry = int(round(self._rocket_x)), int(round(self._rocket_y))
            if 0 <= rx < self._w and self._at <= ry <= self._ab:
                canvas.SetPixel(rx, ry, 255, 230, 120)
                if ry + 1 <= self._ab:
                    canvas.SetPixel(rx, ry + 1, 255, 120, 0)
                if ry + 2 <= self._ab:
                    canvas.SetPixel(rx, ry + 2, 180, 60, 0)
        elif self._phase == "explode":
            r, g, b = self._burst_color
            for sp in self._sparks:
                if sp[4] <= 0:
                    continue
                alpha = sp[4] / float(sp[5])
                px, py = int(round(sp[0])), int(round(sp[1]))
                if 0 <= px < self._w and self._at <= py <= self._ab:
                    canvas.SetPixel(px, py, int(r * alpha), int(g * alpha), int(b * alpha))

    def is_done(self) -> bool:
        return self._phase == "done"
