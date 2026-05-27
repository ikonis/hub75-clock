import random


class Animation:
    name = "snake"
    conditions = []
    themes = []
    layer = "foreground"
    persistent = True
    speed = 1.0

    CHERRY_COUNT = 4
    CHERRY_SIZE = 3

    def __init__(self, width, height, cfg, animator):
        self._w = width
        self._at = animator.anim_top
        self._ab = animator.anim_bottom
        self._h = self._ab - self._at + 1
        self._fps = max(1, int(cfg.get("animation", {}).get("fps", 15)))
        settings = cfg.get("animation_settings", {}).get("snake", {})
        self._speed = float(settings.get("speed", self.speed)) * self.speed
        self._step_every = max(1, int(round(self._fps / max(1.0, 8.0 * self._speed))))
        self._frame = 0
        self._crash_frames = 0
        self._reset()

    def _reset(self):
        direction = random.choice([(1, 0), (-1, 0), (0, 1), (0, -1)])
        length = random.randint(8, 12)
        margin = length + 2
        if direction[0]:
            x = random.randint(margin, max(margin, self._w - margin - 1))
            y = self._at + random.randint(3, max(3, self._h - 4))
        else:
            x = random.randint(4, max(4, self._w - 5))
            y = self._at + random.randint(margin, max(margin, self._h - margin - 1))

        self._dir = direction
        self._snake = [(x - direction[0] * i, y - direction[1] * i) for i in range(length)]
        self._grow = 0
        self._cherries = []
        self._spawn_cherries()

    def _wrap(self, x, y):
        return x % self._w, self._at + ((y - self._at) % self._h)

    def _occupied(self, x, y):
        return (x, y) in set(self._snake)

    def _spawn_cherries(self):
        attempts = 0
        while len(self._cherries) < self.CHERRY_COUNT and attempts < 300:
            attempts += 1
            x = random.randint(0, max(0, self._w - self.CHERRY_SIZE))
            y = random.randint(self._at, max(self._at, self._ab - self.CHERRY_SIZE + 1))
            cells = [
                (x + dx, y + dy)
                for dx in range(self.CHERRY_SIZE)
                for dy in range(self.CHERRY_SIZE)
            ]
            if any(c in self._snake for c in cells):
                continue
            if any(abs(x - cx) < 5 and abs(y - cy) < 5 for cx, cy in self._cherries):
                continue
            self._cherries.append((x, y))

    def _torus_distance(self, x, y, tx, ty):
        dx = abs(x - tx)
        dx = min(dx, self._w - dx)
        dy = abs((y - self._at) - (ty - self._at))
        dy = min(dy, self._h - dy)
        return dx + dy

    def _nearest_cherry_center(self, x, y):
        if not self._cherries:
            return None
        half = self.CHERRY_SIZE // 2
        return min(
            ((cx + half, cy + half) for cx, cy in self._cherries),
            key=lambda p: self._torus_distance(x, y, p[0], p[1]),
        )

    def _choose_direction(self):
        head_x, head_y = self._snake[0]
        dx, dy = self._dir
        choices = [(dx, dy), (-dy, dx), (dy, -dx)]
        target = self._nearest_cherry_center(head_x, head_y)
        if target is None:
            random.shuffle(choices)
            return choices[0]

        body = set(self._snake[:-1] if self._grow <= 0 else self._snake)
        scored = []
        for ndx, ndy in choices:
            nx, ny = self._wrap(head_x + ndx, head_y + ndy)
            crash = (nx, ny) in body
            score = self._torus_distance(nx, ny, target[0], target[1]) + (999 if crash else 0)
            scored.append((score, random.random(), (ndx, ndy)))
        scored.sort()

        if random.random() < 0.12:
            safe = [item for item in scored if item[0] < 999]
            if safe:
                return random.choice(safe)[2]
        return scored[0][2]

    def _eat_cherry_at(self, x, y):
        for i, (cx, cy) in enumerate(self._cherries):
            if cx <= x < cx + self.CHERRY_SIZE and cy <= y < cy + self.CHERRY_SIZE:
                del self._cherries[i]
                self._grow += 5
                if not self._cherries:
                    self._spawn_cherries()
                return True
        return False

    def _step(self):
        self._dir = self._choose_direction()
        hx, hy = self._snake[0]
        nx, ny = self._wrap(hx + self._dir[0], hy + self._dir[1])
        body = set(self._snake[:-1] if self._grow <= 0 else self._snake)
        if (nx, ny) in body:
            self._crash_frames = 10
            return

        self._snake.insert(0, (nx, ny))
        self._eat_cherry_at(nx, ny)
        if self._grow > 0:
            self._grow -= 1
        else:
            self._snake.pop()

    def update(self):
        self._frame += 1
        if self._crash_frames > 0:
            self._crash_frames -= 1
            if self._crash_frames == 0:
                self._reset()
            return
        if self._frame % self._step_every == 0:
            self._step()

    def draw(self, canvas):
        for cx, cy in self._cherries:
            for dy in range(self.CHERRY_SIZE):
                for dx in range(self.CHERRY_SIZE):
                    px, py = cx + dx, cy + dy
                    if 0 <= px < self._w and self._at <= py <= self._ab:
                        if dx == 1 and dy == 1:
                            canvas.SetPixel(px, py, 255, 45, 60)
                        else:
                            canvas.SetPixel(px, py, 170, 0, 35)

        crash = self._crash_frames > 0 and (self._frame % 2 == 0)
        for i, (x, y) in enumerate(reversed(self._snake)):
            if not (0 <= x < self._w and self._at <= y <= self._ab):
                continue
            if crash:
                color = (220, 30, 30)
            elif i == len(self._snake) - 1:
                color = (210, 255, 120)
            else:
                shade = 100 + int(85 * (i / max(1, len(self._snake) - 1)))
                color = (35, shade, 55)
            canvas.SetPixel(x, y, *color)

    def is_done(self) -> bool:
        return False
