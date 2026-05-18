import math
import random


class Animation:
    name = "fireworks"
    conditions = []
    themes = []

    _COLORS = [
        (255, 40,  40),   # red
        (255, 200, 20),   # gold
        (255, 255, 255),  # white
        (40,  255, 80),   # green
        (60,  120, 255),  # blue
    ]

    _GRAVITY = 0.06

    def __init__(self, width, height, cfg, animator):
        self._w = width
        self._at = animator.anim_top
        self._ab = animator.anim_bottom
        self._bursts_left = random.randint(2, 3)
        self._phase = "launch"
        self._sparks: list = []
        self._rocket_x = 0.0
        self._rocket_y = 0.0
        self._rocket_vy = 0.0
        self._burst_color = (255, 255, 255)
        self._wait = 0
        self._launch_new()

    def _launch_new(self):
        self._phase = "launch"
        self._rocket_x = float(random.randint(8, self._w - 8))
        self._rocket_y = float(self._ab)
        # Target height: upper third of animation zone
        zone = self._ab - self._at
        target_y = self._at + random.randint(1, zone // 3)
        # Compute initial velocity so rocket naturally peaks at target_y (v^2 = 2*g*d)
        dist = self._rocket_y - target_y
        self._rocket_vy = -math.sqrt(2.0 * self._GRAVITY * max(dist, 1.0))
        self._burst_color = random.choice(self._COLORS)
        self._sparks = []

    def _explode(self):
        self._phase = "explode"
        n = random.randint(10, 14)
        r, g, b = self._burst_color
        for i in range(n):
            angle = (2.0 * math.pi * i / n) + random.uniform(-0.25, 0.25)
            speed = 0.7 + random.random() * 1.4
            life = 28 + random.randint(0, 14)
            self._sparks.append({
                "x":    self._rocket_x,
                "y":    self._rocket_y,
                "vx":   math.cos(angle) * speed,
                "vy":   math.sin(angle) * speed,
                "life": life,
                "max":  life,
                "r": r, "g": g, "b": b,
            })

    def update(self):
        if self._phase == "launch":
            self._rocket_vy += self._GRAVITY
            self._rocket_y  += self._rocket_vy
            # Rocket has peaked (velocity turned positive) or exited zone top
            if self._rocket_vy >= 0 or self._rocket_y <= self._at:
                self._rocket_y = max(self._rocket_y, float(self._at + 1))
                self._explode()

        elif self._phase == "explode":
            alive = False
            for sp in self._sparks:
                sp["vy"] += self._GRAVITY
                sp["x"]  += sp["vx"]
                sp["y"]  += sp["vy"]
                sp["life"] -= 1
                if sp["life"] > 0:
                    alive = True
            if not alive:
                self._bursts_left -= 1
                if self._bursts_left > 0:
                    self._wait = 10
                    self._phase = "wait"
                else:
                    self._phase = "done"

        elif self._phase == "wait":
            self._wait -= 1
            if self._wait <= 0:
                self._launch_new()

    def draw(self, canvas):
        if self._phase == "launch":
            rx = int(round(self._rocket_x))
            ry = int(round(self._rocket_y))
            for dy, cr, cg, cb in ((0, 255, 230, 120), (1, 255, 120, 0), (2, 160, 50, 0)):
                py = ry + dy
                if 0 <= rx < self._w and self._at <= py <= self._ab:
                    canvas.SetPixel(rx, py, cr, cg, cb)

        elif self._phase == "explode":
            for sp in self._sparks:
                if sp["life"] <= 0:
                    continue
                alpha = sp["life"] / float(sp["max"])
                px = int(round(sp["x"]))
                py = int(round(sp["y"]))
                if 0 <= px < self._w and self._at <= py <= self._ab:
                    canvas.SetPixel(px, py,
                                    int(sp["r"] * alpha),
                                    int(sp["g"] * alpha),
                                    int(sp["b"] * alpha))

    def is_done(self) -> bool:
        return self._phase == "done"
