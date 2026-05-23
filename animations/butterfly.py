import math
import random


class Animation:
    name = "butterfly"
    conditions = ["CLEAR"]
    themes = ["Day"]
    layer = "foreground"
    speed = 1.0

    _PASTEL_COLORS = [
        (100, 160, 255),  # soft blue
        (255, 240, 100),  # soft yellow
        (255, 130, 180),  # soft pink
        (130, 230, 140),  # soft green
        (255, 170,  80),  # soft orange
    ]

    # Wing pixels as (dx, dy, brightness 0..1) — body drawn separately in dark brown.
    # Sprite is symmetric; used for both left-to-right and right-to-left flight.
    _OPEN = [
        # Left upper wing
        (0, 0, 0.85), (1, 0, 1.00), (2, 0, 0.85),
        (0, 1, 0.90), (1, 1, 1.00), (2, 1, 0.95),
        # Right upper wing
        (4, 0, 0.85), (5, 0, 1.00), (6, 0, 0.85),
        (4, 1, 0.90), (5, 1, 1.00), (6, 1, 0.95),
        # Left lower wing
        (0, 3, 0.70), (1, 3, 0.80),
        (0, 4, 0.60), (1, 4, 0.70),
        # Right lower wing
        (5, 3, 0.70), (6, 3, 0.80),
        (5, 4, 0.60), (6, 4, 0.70),
    ]
    _CLOSED = [
        # Left wing folded
        (1, 0, 0.90), (2, 0, 0.85),
        (1, 1, 0.85), (2, 1, 0.90),
        # Right wing folded
        (4, 0, 0.90), (5, 0, 0.85),
        (4, 1, 0.85), (5, 1, 0.90),
    ]
    _BODY_PIXELS = [(3, 1), (3, 2), (3, 3)]
    _BODY_COLOR  = (45, 22, 11)

    def __init__(self, width, height, cfg, animator):
        self._w     = width
        self._at    = animator.anim_top
        self._ab    = animator.anim_bottom
        self._frame = 0

        colors = random.sample(self._PASTEL_COLORS, 3)
        self._butterflies = []
        for i, color in enumerate(colors):
            right = random.random() < 0.5
            if right:
                x = float(-8 - i * 18)
            else:
                x = float(width + 8 + i * 18)
            y   = float(self._at + random.randint(3, 12))
            vx  = (0.25 + random.random() * 0.2) * (1 if right else -1) * self.speed
            self._butterflies.append({
                'x':           x,
                'y':           y,
                'vx':          vx,
                'wave':        random.random() * math.pi * 2,
                'flap_offset': random.randint(0, 9),
                'color':       color,
            })
        self._wave_speed = 0.12 * self.speed

    def update(self):
        self._frame += 1
        for b in self._butterflies:
            b['wave'] += self._wave_speed
            b['x']   += b['vx']
            b['y']   += math.sin(b['wave']) * 0.4

    def draw(self, canvas):
        for b in self._butterflies:
            flap   = (self._frame + b['flap_offset']) // 5
            sprite = self._OPEN if flap % 2 == 0 else self._CLOSED
            ox     = int(round(b['x']))
            oy     = int(round(b['y']))
            cr, cg, cb = b['color']
            for dx, dy, brt in sprite:
                px, py = ox + dx, oy + dy
                if 0 <= px < self._w and self._at <= py <= self._ab:
                    canvas.SetPixel(px, py,
                                    int(cr * brt), int(cg * brt), int(cb * brt))
            for dx, dy in self._BODY_PIXELS:
                px, py = ox + dx, oy + dy
                if 0 <= px < self._w and self._at <= py <= self._ab:
                    canvas.SetPixel(px, py, *self._BODY_COLOR)

    def is_done(self) -> bool:
        for b in self._butterflies:
            if -20 < b['x'] < self._w + 20:
                return False
        return True
