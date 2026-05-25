import math
import random


# --- Appearance settings - edit to customize ---
COLOR_CLOUD      = "#646464"       # default cloud color (overridden by theme cloud_day color)
COLOR_RAIN       = (22, 42, 115)   # rain drop streaks
COLOR_HEAVY_RAIN = (10, 18, 80)    # heavy rain / tstorm streaks
COLOR_SNOW       = (180, 180, 200) # snowflakes
COLOR_SLEET      = (120, 160, 180) # sleet fast particles (slow ones use COLOR_SNOW)
COLOR_LIGHTNING  = (232, 232, 64)  # lightning bolt color
COLOR_FLASH      = (20, 20, 60)    # brief background flash during tstorm strike
# ------------------------------------------------


def _parse_hex(h):
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


# Cloud shapes: list of (dx, dy, radius) circle offsets from cloud anchor point
_CLOUD_CIRCLES = {
    "small": [
        (0,  0, 3),
        (-4, 1, 2),
        ( 4, 1, 2),
    ],
    "medium": [
        ( 0,  0, 4),
        (-5,  1, 3),
        ( 5,  1, 3),
        ( 0, -2, 2),
    ],
    "large": [
        ( 0,  0, 5),
        (-6,  1, 4),
        ( 6,  1, 4),
        (-2, -2, 3),
        ( 3, -2, 3),
    ],
}

# Bounding box for particle spawn: (left_offset, right_offset, height_from_anchor)
_CLOUD_SPAN = {
    "small":  (-5,  5, 5),
    "medium": (-8,  8, 6),
    "large":  (-10, 10, 8),
}

_SPEEDS = {"slow": 0.2, "medium": 0.4, "fast": 0.7}
_COUNTS = {"sparse": 2, "medium": 4, "dense": 7}


class Animation:
    name = "clouds"
    conditions = []
    themes = []
    layer = "foreground"
    persistent = True
    speed = 1.0
    rain_speed = 1.0
    heavy_rain_speed = 1.0
    snow_speed = 1.0
    sleet_fast_speed = 1.0
    sleet_slow_speed = 1.0

    def __init__(self, width, height, cfg, animator):
        self._w = width
        self._at = animator.anim_top
        self._ab = animator.anim_bottom
        theme = getattr(animator, "current_theme", None)

        density      = getattr(theme, "cloud_density",  "medium") if theme else "medium"
        speed_key    = getattr(theme, "cloud_speed",    "medium") if theme else "medium"
        self._precip = getattr(theme, "precipitation",  "none")   if theme else "none"
        self._fps    = cfg.get("animation", {}).get("fps", 15)

        base_speed = _SPEEDS.get(speed_key, 0.4) * self.speed
        count      = _COUNTS.get(density, 4)

        theme_color_hex = getattr(theme, "colors", {}).get("cloud_day") if theme else None
        cloud_color = _parse_hex(theme_color_hex) if theme_color_hex else _parse_hex(COLOR_CLOUD)

        # Sun blend parameters — populated only when theme has sun_enabled
        self._sun_ox    = None
        if getattr(theme, "sun_enabled", False):
            self._sun_ox    = width - 1
            self._sun_oy    = animator.anim_top
            self._sun_r     = 12
            self._sun_glow  = 20
            raw = getattr(theme, "colors", {}).get("sun_day")
            if raw is None:
                raw = animator.cfg.get("colors", {}).get("sun_day", "#DCA01E")
            self._sun_color = (_parse_hex(raw) if isinstance(raw, str)
                               else (int(raw[0]), int(raw[1]), int(raw[2])))

        # Lightning state
        self._bolt          = None
        self._bolt_branches = []
        self._bolt_life     = 0
        self._flash_life    = 0
        self._next_bolt     = self._rand_bolt_interval()

        self._clouds = []
        for _ in range(count):
            x = random.uniform(0, width)
            y = float(random.randint(self._at + 1, max(self._at + 1, self._ab - 12)))
            vx = -(base_speed + random.uniform(0.0, 0.08)) * (30.0 / self._fps)
            size = self._pick_size(density)
            self._clouds.append({
                "x":    x,
                "y":    y,
                "vx":   vx,
                "size": size,
                "color": cloud_color,
                "particles": self._make_particles(x, y, size),
            })

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _rand_bolt_interval(self):
        return random.randint(int(8 * self._fps), int(15 * self._fps))

    def _pick_size(self, density):
        if density == "sparse":
            return random.choice(["small", "medium"])
        elif density == "dense":
            return random.choice(["medium", "large"])
        return random.choice(["small", "medium", "medium", "large"])

    def _make_particles(self, cx, cy, size):
        """Create precipitation particles owned by a cloud at (cx, cy)."""
        p = self._precip
        if p == "none":
            return []

        span_l, span_r, span_h = _CLOUD_SPAN[size]
        bottom = cy + span_h
        particles = []

        if p == "rain":
            for _ in range(random.randint(2, 4)):
                particles.append(self._new_particle(span_l, span_r, bottom, "rain",
                                                    vy=1.5 * (15.0 / self._fps) * self.rain_speed))
        elif p in ("heavy_rain", "tstorm"):
            for _ in range(random.randint(4, 6)):
                particles.append(self._new_particle(span_l, span_r, bottom, "heavy_rain",
                                                    vy=2.5 * (15.0 / self._fps) * self.heavy_rain_speed))
        elif p == "snow":
            for _ in range(random.randint(2, 3)):
                particles.append(self._new_particle(span_l, span_r, bottom, "snow",
                                                    vy=random.uniform(0.3, 0.5) * (15.0 / self._fps) * self.snow_speed))
        elif p == "sleet":
            for i in range(random.randint(3, 5)):
                if i % 2 == 0:
                    particles.append(self._new_particle(span_l, span_r, bottom,
                                                        "sleet_fast", vy=1.5 * (15.0 / self._fps) * self.sleet_fast_speed))
                else:
                    particles.append(self._new_particle(span_l, span_r, bottom,
                                                        "sleet_slow",
                                                        vy=random.uniform(0.4, 0.6) * (15.0 / self._fps) * self.sleet_slow_speed))
        return particles

    def _new_particle(self, span_l, span_r, cloud_bottom, ptype, vy):
        return {
            "lx":     random.uniform(span_l, span_r),
            "y":      random.uniform(cloud_bottom, self._ab),
            "vy":     vy,
            "wobble": random.uniform(0, math.pi * 2),
            "type":   ptype,
        }

    def _respawn(self, p, cx, cy, size):
        span_l, span_r, span_h = _CLOUD_SPAN[size]
        p["lx"] = random.uniform(span_l, span_r)
        p["y"]  = float(cy + span_h)

    def _make_bolt(self, cx, cy, size):
        span_l, span_r, span_h = _CLOUD_SPAN[size]
        x = int(cx + random.uniform(span_l * 0.5, span_r * 0.5))
        x = max(1, min(self._w - 2, x))
        y = max(self._at, min(self._ab - 4, int(cy + span_h)))
        points = [(x, y)]
        target_y = min(self._ab, y + random.randint(10, 16))
        branches = []
        while y < target_y:
            x = max(1, min(self._w - 2, x + random.randint(-2, 2)))
            y = min(target_y, y + random.randint(2, 3))
            points.append((x, y))
            if random.random() < 0.4 and len(points) > 1:
                bx, by = x, y
                branch = [(bx, by)]
                for _ in range(random.randint(1, 3)):
                    bx = max(0, min(self._w - 1, bx + random.randint(-2, 2)))
                    by += random.randint(1, 2)
                    if by > self._ab:
                        break
                    branch.append((bx, by))
                if len(branch) > 1:
                    branches.append(branch)
        return points, branches

    # ------------------------------------------------------------------
    # Update / Draw
    # ------------------------------------------------------------------

    def update(self):
        for c in self._clouds:
            c["x"] += c["vx"]
            span_l, span_r, span_h = _CLOUD_SPAN[c["size"]]
            # Wrap left-to-right
            if c["x"] + span_r < 0:
                c["x"] = float(self._w + abs(span_l) + 4)
                c["y"] = float(random.randint(self._at + 1, max(self._at + 1, self._ab - 12)))
                c["particles"] = self._make_particles(c["x"], c["y"], c["size"])

            # Update particles
            for p in c["particles"]:
                p["wobble"] += 0.15 * self.speed
                if p["type"] in ("snow", "sleet_slow"):
                    p["lx"] += math.sin(p["wobble"]) * 0.25 * self.speed
                p["y"] += p["vy"]
                if p["y"] > self._ab:
                    self._respawn(p, c["x"], c["y"], c["size"])

        # Lightning countdown (tstorm only)
        if self._precip == "tstorm":
            if self._bolt_life > 0:
                self._bolt_life -= 1
            if self._flash_life > 0:
                self._flash_life -= 1
            self._next_bolt -= 1
            if self._next_bolt <= 0 and self._clouds:
                visible = [
                    c for c in self._clouds
                    if c["x"] + _CLOUD_SPAN[c["size"]][0] < self._w
                    and c["x"] + _CLOUD_SPAN[c["size"]][1] >= 0
                    and c["y"] + _CLOUD_SPAN[c["size"]][2] <= self._ab - 4
                ]
                lc = random.choice(visible or self._clouds)
                self._bolt, self._bolt_branches = self._make_bolt(
                    lc["x"], lc["y"], lc["size"])
                self._bolt_life  = random.randint(2, 3)
                self._flash_life = random.randint(1, 2)
                self._next_bolt  = self._rand_bolt_interval()

    def draw(self, canvas):
        # Background flash during tstorm strike
        if self._flash_life > 0:
            fr, fg, fb = COLOR_FLASH
            for fy in range(self._at, self._ab + 1):
                for fx in range(self._w):
                    canvas.SetPixel(fx, fy, fr, fg, fb)

        for c in self._clouds:
            cy = int(round(c["y"]))
            cr, cg, cb = c["color"]
            circles = _CLOUD_CIRCLES[c["size"]]
            max_r = max(r for _, _, r in circles)

            cx = int(round(c["x"]))
            for dx, dy, r in circles:
                diff = max_r - r
                scale = 1.0 if diff == 0 else (0.85 if diff == 1 else 0.70)
                self._fill_circle(canvas, cx + dx, cy + dy, r,
                                  int(cr * scale), int(cg * scale), int(cb * scale))

            # Precipitation particles
            for p in c["particles"]:
                px = int(round(c["x"] + p["lx"]))
                py = int(round(p["y"]))
                t  = p["type"]
                if t == "rain":
                    col = COLOR_RAIN
                    self._vline(canvas, px, py, 3, col)
                elif t == "heavy_rain":
                    col = COLOR_HEAVY_RAIN
                    self._vline(canvas, px, py, 3, col)
                elif t == "snow":
                    col = COLOR_SNOW
                    self._dot(canvas, px, py, col)
                elif t == "sleet_fast":
                    col = COLOR_SLEET
                    self._vline(canvas, px, py, 2, col)
                elif t == "sleet_slow":
                    col = COLOR_SNOW
                    self._dot(canvas, px, py, col)

        # Lightning bolt
        if self._bolt_life > 0 and self._bolt:
            fade = self._bolt_life / 3.0
            lc = (int(COLOR_LIGHTNING[0] * fade),
                  int(COLOR_LIGHTNING[1] * fade),
                  int(COLOR_LIGHTNING[2] * fade))
            self._draw_bolt(canvas, self._bolt, lc)
            dim = (lc[0] // 2, lc[1] // 2, lc[2] // 2)
            for branch in self._bolt_branches:
                self._draw_bolt(canvas, branch, dim)

    # ------------------------------------------------------------------
    # Drawing primitives
    # ------------------------------------------------------------------

    def _fill_circle(self, canvas, cx, cy, r, cr, cg, cb):
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                if dx * dx + dy * dy <= r * r:
                    px, py = cx + dx, cy + dy
                    if 0 <= px < self._w and self._at <= py <= self._ab:
                        pr, pg, pb = cr, cg, cb
                        # EXPERIMENTAL: sun-cloud blending - remove from here...
                        if self._sun_ox is not None:
                            sdx = px - self._sun_ox
                            sdy = py - self._sun_oy
                            dist = math.sqrt(sdx * sdx + sdy * sdy)
                            if dist < self._sun_glow:
                                t = min(0.35, (1.0 - dist / self._sun_glow) ** 2)
                                sr, sg, sb = self._sun_color
                                pr = int(pr * (1.0 - t) + sr * t)
                                pg = int(pg * (1.0 - t) + sg * t)
                                pb = int(pb * (1.0 - t) + sb * t)
                        # ...to here to disable sun-cloud blending
                        canvas.SetPixel(px, py, pr, pg, pb)

    def _vline(self, canvas, x, y, length, col):
        cr, cg, cb = col
        for i in range(length):
            py = y + i
            if 0 <= x < self._w and self._at <= py <= self._ab:
                canvas.SetPixel(x, py, cr, cg, cb)

    def _dot(self, canvas, x, y, col):
        if 0 <= x < self._w and self._at <= y <= self._ab:
            canvas.SetPixel(x, y, col[0], col[1], col[2])

    def _draw_bolt(self, canvas, points, color):
        cr, cg, cb = color
        for i in range(len(points) - 1):
            x1, y1 = points[i]
            x2, y2 = points[i + 1]
            dx, dy = abs(x2 - x1), abs(y2 - y1)
            sx = 1 if x1 < x2 else -1
            sy = 1 if y1 < y2 else -1
            err = dx - dy
            while True:
                if 0 <= x1 < self._w and self._at <= y1 <= self._ab:
                    canvas.SetPixel(x1, y1, cr, cg, cb)
                if x1 == x2 and y1 == y2:
                    break
                e2 = 2 * err
                if e2 > -dy:
                    err -= dy
                    x1 += sx
                if e2 < dx:
                    err += dx
                    y1 += sy

    def is_done(self) -> bool:
        return False
