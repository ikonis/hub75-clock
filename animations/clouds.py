import random


# --- Appearance settings ---
DEFAULT_COLOR = "#646464"   # fallback cloud color if theme has no cloud_day color
# ---------------------------


def _parse_hex(h):
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


class Animation:
    name = "clouds"
    conditions = []
    themes = []
    layer = "foreground"
    persistent = True

    _SHAPES = {
        "small": [
            "    XXXXXX    ",
            "  XXXXXXXXXX  ",
            " XXXXXXXXXXXX ",
            "XXXXXXXXXXXXXX",
            " XXXXXXXXXXXX ",
            "  XXXXXXXXXX  ",
        ],
        "medium": [
            "      XXXXXXXX      ",
            "   XXXXXXXXXXXXXX   ",
            "  XXXXXXXXXXXXXXXX  ",
            " XXXXXXXXXXXXXXXXXXXX",
            "XXXXXXXXXXXXXXXXXXXX",
            " XXXXXXXXXXXXXXXXXXXX",
            "  XXXXXXXXXXXXXXXX  ",
            "   XXXXXXXXXXXXXX   ",
        ],
        "large": [
            "       XXXXXXXXXX       ",
            "    XXXXXXXXXXXXXXXX    ",
            "  XXXXXXXXXXXXXXXXXXXXXX",
            " XXXXXXXXXXXXXXXXXXXXXXX",
            "XXXXXXXXXXXXXXXXXXXXXXXXX",
            "XXXXXXXXXXXXXXXXXXXXXXXXX",
            " XXXXXXXXXXXXXXXXXXXXXXX",
            "  XXXXXXXXXXXXXXXXXXXXXX",
            "    XXXXXXXXXXXXXXXX    ",
            "       XXXXXXXXXX       ",
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

        # Read cloud color from theme colors, fall back to DEFAULT_COLOR
        theme_color_hex = None
        if theme is not None:
            theme_color_hex = getattr(theme, "colors", {}).get("cloud_day")
        color = _parse_hex(theme_color_hex) if theme_color_hex else _parse_hex(DEFAULT_COLOR)

        self._clouds = []
        for _ in range(count):
            direction = random.choice([-1, 1])
            speed = (base_speed + random.uniform(-0.03, 0.03)) * direction
            size = (random.choice(["small", "medium"]) if density != "dense"
                    else random.choice(["medium", "large"]))
            self._clouds.append({
                "x": random.uniform(0, width),
                "y": float(random.randint(self._at + 1, max(self._at + 1, self._ab - 10))),
                "vx": speed,
                "size": size,
                "color": color,
            })

    def update(self):
        for c in self._clouds:
            c["x"] += c["vx"]
            if c["vx"] > 0 and c["x"] > self._w + 25:
                c["x"] = -25.0
            elif c["vx"] < 0 and c["x"] < -25:
                c["x"] = float(self._w + 25)

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
