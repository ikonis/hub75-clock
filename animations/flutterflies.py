import math
import random


class Animation:
    name = "flutterflies"
    conditions = ["CLEAR"]
    themes = ["Day"]
    layer = "foreground"
    persistent = True
    speed = 1.0

    _PASTEL_COLORS = [
        (100, 160, 255),  # soft blue
        (255, 240, 100),  # soft yellow
        (255, 130, 180),  # soft pink
        (130, 230, 140),  # soft green
        (255, 170,  80),  # soft orange
    ]

    # Wings open: 3px horizontal. Wings closed: 2px vertical.
    _OPEN   = [(-1, 0, 0.80), (0, 0, 1.00), (1, 0, 0.80)]
    _CLOSED = [(0, 0, 1.00), (0, 1, 0.70)]

    def __init__(self, width, height, cfg, animator):
        self._w     = width
        self._at    = animator.anim_top
        self._ab    = animator.anim_bottom
        self._frame = 0

        colors = random.sample(self._PASTEL_COLORS, min(5, len(self._PASTEL_COLORS)))
        count  = random.randint(4, 6)
        self._flutterflies = []
        for i in range(count):
            color = colors[i % len(colors)]
            self._flutterflies.append({
                'x':           float(random.randint(2, width - 2)),
                'y':           float(random.randint(self._at + 2, self._ab - 2)),
                'angle':       random.random() * math.pi * 2,
                'speed':       (0.18 + random.random() * 0.12) * self.speed,
                'turn':        (0.08 + random.random() * 0.06) * self.speed,
                'wave':        random.random() * math.pi * 2,
                'flap_offset': random.randint(0, 11),
                'color':       color,
            })
        self._wave_speed = 0.10 * self.speed

    def update(self):
        self._frame += 1
        for f in self._flutterflies:
            f['wave']  += self._wave_speed
            f['angle'] += f['turn'] * math.sin(f['wave'])
            f['x']     += f['speed'] * math.cos(f['angle'])
            f['y']     += f['speed'] * math.sin(f['angle']) * 0.5

            # Wrap around all edges
            if f['x'] < -2:
                f['x'] = self._w + 1
            elif f['x'] > self._w + 1:
                f['x'] = -1.0

            if f['y'] < self._at:
                f['y'] = float(self._ab)
            elif f['y'] > self._ab:
                f['y'] = float(self._at)

    def draw(self, canvas):
        for f in self._flutterflies:
            flap   = (self._frame + f['flap_offset']) // 5
            sprite = self._OPEN if flap % 2 == 0 else self._CLOSED
            ox     = int(round(f['x']))
            oy     = int(round(f['y']))
            cr, cg, cb = f['color']
            for dx, dy, brt in sprite:
                px, py = ox + dx, oy + dy
                if 0 <= px < self._w and self._at <= py <= self._ab:
                    canvas.SetPixel(px, py,
                                    int(cr * brt), int(cg * brt), int(cb * brt))

    def is_done(self) -> bool:
        return False
