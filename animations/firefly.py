import math
import random


class Animation:
    name = "firefly"
    conditions = ["CLEAR"]
    themes = ["Night", "Late Evening"]
    layer = "foreground"
    persistent = True
    # Speed multiplier — edit this value to tune animation speed without touching logic
    speed = 1.0

    # --- Appearance settings ---
    MAX_BRIGHTNESS  = 200   # peak glow value (0-255); brightness scales with blink phase
    GREEN_RATIO     = 0.6   # green tint multiplier for 2nd pixel (gives yellow-green color)
    # ---------------------------

    def __init__(self, width, height, cfg, animator):
        self._w = width
        self._at = animator.anim_top
        self._ab = animator.anim_bottom
        self._fps = cfg.get("animation", {}).get("fps", 15)
        _drift = 0.06 * (15.0 / self._fps) * self.speed
        count = random.randint(6, 8)
        self._flies = []
        for _ in range(count):
            fx = random.uniform(4, width - 4)
            fy = random.uniform(self._at + 2, self._ab - 2)
            phase = random.random() * math.pi * 2
            period = random.randint(20, 50)     # blink period in frames
            bx = (random.random() - 0.5) * _drift
            by = (random.random() - 0.5) * _drift
            self._flies.append([fx, fy, phase, period, bx, by])
        self._frame = 0
        self._total = 120 + random.randint(0, 60)

    def update(self):
        self._frame += 1
        for fly in self._flies:
            fly[0] += fly[4]
            fly[1] += fly[5]
            fly[0] = max(1.0, min(float(self._w - 2), fly[0]))
            fly[1] = max(float(self._at + 1), min(float(self._ab - 1), fly[1]))
            # Occasionally change drift direction
            if random.random() < 0.01 * (15.0 / self._fps):
                _drift = 0.06 * (15.0 / self._fps) * self.speed
                fly[4] = (random.random() - 0.5) * _drift
                fly[5] = (random.random() - 0.5) * _drift

    def draw(self, canvas):
        for fx, fy, phase, period, *_ in self._flies:
            t = (self._frame % period) / period
            brightness = (math.sin(t * math.pi * 2 + phase) + 1) / 2
            b = int(brightness * self.MAX_BRIGHTNESS)
            if b > 20:
                px, py = int(round(fx)), int(round(fy))
                if 0 <= px < self._w and self._at <= py <= self._ab:
                    canvas.SetPixel(px, py, b, b, int(b * self.GREEN_RATIO))
                    if self._at <= py + 1 <= self._ab:
                        canvas.SetPixel(px, py + 1, b // 2, b // 2, int(b * self.GREEN_RATIO / 2))

    def is_done(self) -> bool:
        return self._frame >= self._total
