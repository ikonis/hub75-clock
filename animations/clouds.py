import math
import random


class Animation:
    name = "clouds"
    conditions = []
    themes = []
    layer = "foreground"
    persistent = True

    _SHAPES = {
        "small": [
            "  XXX  ",
            " XXXXX ",
            "XXXXXXX",
        ],
        "medium": [
            "   XXXX   ",
            " XXXXXXXX ",
            "XXXXXXXXXX",
            " XXXXXXXX ",
        ],
        "large": [
            "   XXXXX   ",
            " XXXXXXXXX ",
            "XXXXXXXXXXX",
            "XXXXXXXXXXX",
            " XXXXXXXXX ",
        ],
    }

    def __init__(self, width, height, cfg, animator):
        self._w = width
        self._at = animator.anim_top
        self._ab = animator.anim_bottom
        theme = getattr(animator, "current_theme", None)

        density = getattr(theme, "cloud_density", "medium") if theme else "medium"
        speed_setting = getattr(theme, "cloud_speed", "medium") if theme else "medium"

        if density == "sparse":
            count = 2
        elif density == "dense":
            count = random.randint(5, 6)
        else:
            count = random.randint(3, 4)

        if speed_setting == "slow":
            base_speed = 0.07
        elif speed_setting == "fast":
            base_speed = 0.21
        else:
            base_speed = 0.13

        # Cloud color: soft gray-white
        color = (176, 184, 200)

        self._clouds = []
        for _ in range(count):
            direction = random.choice([-1, 1])
            speed = (base_speed + random.uniform(-0.03, 0.03)) * direction
            size = random.choice(["small", "medium"]) if density != "dense" else random.choice(["medium", "large"])
            self._clouds.append({
                "x": random.uniform(0, width),
                "y": float(random.randint(self._at + 1, self._ab - 6)),
                "vx": speed,
                "size": size,
                "color": color,
            })

    def update(self):
        for c in self._clouds:
            c["x"] += c["vx"]
            if c["vx"] > 0 and c["x"] > self._w + 12:
                c["x"] = -12.0
            elif c["vx"] < 0 and c["x"] < -12:
                c["x"] = float(self._w + 12)

    def draw(self, canvas):
        for c in self._clouds:
            x = int(round(c["x"]))
            y = int(round(c["y"]))
            cr, cg, cb = c["color"]
            for row, line in enumerate(self._SHAPES[c["size"]]):
                py = y + row
                if py < self._at or py > self._ab:
                    continue
                for col, ch in enumerate(line):
                    if ch == "X":
                        px = x + col
                        if 0 <= px < self._w:
                            canvas.SetPixel(px, py, cr, cg, cb)

    def is_done(self) -> bool:
        return False
