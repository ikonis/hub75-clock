import math
import random


class Animation:
    name = "fireworks"
    conditions = []
    themes = []
    layer = "foreground"

    # --- Appearance settings ---
    _COLORS = [
        (255, 255, 255),  # white
        (255, 200,  20),  # gold
        (255,  40,  40),  # red
        ( 60, 120, 255),  # blue
        ( 40, 255,  80),  # green
        (200,  60, 255),  # purple
    ]
    # ---------------------------

    _GRAVITY = 0.06

    def __init__(self, width, height, cfg, animator):
        self._w = width
        self._at = animator.anim_top
        self._ab = animator.anim_bottom

        # 1–3 rockets, each with a staggered launch delay
        n = random.randint(1, 3)
        self._rockets = []
        delay = 0
        for _ in range(n):
            self._rockets.append(self._make_rocket(delay))
            delay += random.randint(5, 12)   # ~0.3–0.8 s at 15 fps

    def _make_rocket(self, delay):
        zone = self._ab - self._at
        target_y = self._at + random.randint(1, zone // 3)
        dist = float(self._ab - target_y)
        vy0 = -math.sqrt(2.0 * self._GRAVITY * max(dist, 1.0))
        return {
            "phase": "wait",
            "delay": delay,
            "x":     float(random.randint(8, self._w - 8)),
            "y":     float(self._ab),
            "vy":    vy0,
            "sparks": [],
        }

    def _explode(self, rk):
        rk["phase"] = "explode"
        n = random.randint(16, 20)
        for i in range(n):
            angle = (2.0 * math.pi * i / n) + random.uniform(-0.3, 0.3)
            speed = 0.8 + random.random() * 1.6
            color = random.choice(self._COLORS)   # each spark picks its own color
            life = 30 + random.randint(0, 12)
            rk["sparks"].append({
                "x": rk["x"], "y": rk["y"],
                "vx": math.cos(angle) * speed,
                "vy": math.sin(angle) * speed,
                "life": life, "max": life,
                "r": color[0], "g": color[1], "b": color[2],
            })

    def update(self):
        for rk in self._rockets:
            if rk["phase"] == "wait":
                rk["delay"] -= 1
                if rk["delay"] <= 0:
                    rk["phase"] = "launch"

            elif rk["phase"] == "launch":
                rk["vy"] += self._GRAVITY
                rk["y"]  += rk["vy"]
                if rk["vy"] >= 0 or rk["y"] <= self._at:
                    rk["y"] = max(rk["y"], float(self._at + 1))
                    self._explode(rk)

            elif rk["phase"] == "explode":
                alive = False
                for sp in rk["sparks"]:
                    sp["vy"] += self._GRAVITY
                    sp["x"]  += sp["vx"]
                    sp["y"]  += sp["vy"]
                    sp["life"] -= 1
                    if sp["life"] > 0:
                        alive = True
                if not alive:
                    rk["phase"] = "done"

    def _px(self, canvas, x, y, r, g, b):
        px, py = int(round(x)), int(round(y))
        if 0 <= px < self._w and self._at <= py <= self._ab:
            canvas.SetPixel(px, py,
                            max(0, min(255, r)),
                            max(0, min(255, g)),
                            max(0, min(255, b)))

    def draw(self, canvas):
        for rk in self._rockets:
            if rk["phase"] == "launch":
                rx, ry = rk["x"], rk["y"]
                self._px(canvas, rx, ry,     255, 230, 120)
                self._px(canvas, rx, ry + 1, 255, 120,   0)
                self._px(canvas, rx, ry + 2, 160,  50,   0)

            elif rk["phase"] == "explode":
                for sp in rk["sparks"]:
                    if sp["life"] <= 0:
                        continue
                    alpha = sp["life"] / float(sp["max"])
                    r = int(sp["r"] * alpha)
                    g = int(sp["g"] * alpha)
                    b = int(sp["b"] * alpha)
                    # Head at full brightness
                    self._px(canvas, sp["x"], sp["y"], r, g, b)
                    # Tail: 2 pixels behind in the opposite direction of travel
                    spd = math.sqrt(sp["vx"] ** 2 + sp["vy"] ** 2)
                    if spd > 0.01:
                        uvx = sp["vx"] / spd
                        uvy = sp["vy"] / spd
                        self._px(canvas,
                                 sp["x"] - uvx, sp["y"] - uvy,
                                 int(r * 0.6), int(g * 0.6), int(b * 0.6))
                        self._px(canvas,
                                 sp["x"] - 2 * uvx, sp["y"] - 2 * uvy,
                                 int(r * 0.3), int(g * 0.3), int(b * 0.3))

    def is_done(self) -> bool:
        return all(rk["phase"] == "done" for rk in self._rockets)
