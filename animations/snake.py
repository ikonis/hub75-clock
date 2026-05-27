import random


class Animation:
    name = "snake"
    conditions = []
    themes = []
    layer = "foreground"
    persistent = True
    speed = 1.0

    CELL_SIZE = 3
    CHERRY_COUNT = 4

    def __init__(self, width, height, cfg, animator):
        self._w = width
        self._at = animator.anim_top
        self._ab = animator.anim_bottom
        self._h = self._ab - self._at + 1
        self._cols = max(1, self._w // self.CELL_SIZE)
        self._rows = max(1, self._h // self.CELL_SIZE)
        self._fps = max(1, int(cfg.get("animation", {}).get("fps", 15)))
        settings = cfg.get("animation_settings", {}).get("snake", {})
        self._speed = float(settings.get("speed", self.speed)) * self.speed
        self._step_every = max(1, int(round(self._fps / max(1.0, 8.0 * self._speed))))
        self._frame = 0
        self._crash_frames = 0
        self._reset()

    def _reset(self):
        direction = random.choice([(1, 0), (-1, 0), (0, 1), (0, -1)])
        length = random.randint(6, 9)
        margin = min(length + 1, max(1, min(self._cols, self._rows) // 2))
        if direction[0]:
            x = random.randint(margin, max(margin, self._cols - margin - 1))
            y = random.randint(1, max(1, self._rows - 2))
        else:
            x = random.randint(1, max(1, self._cols - 2))
            y = random.randint(margin, max(margin, self._rows - margin - 1))

        self._dir = direction
        self._snake = [self._wrap_cell(x - direction[0] * i, y - direction[1] * i) for i in range(length)]
        self._grow = 0
        self._cherries = []
        self._spawn_cherries()

    def _wrap_cell(self, x, y):
        return x % self._cols, y % self._rows

    def _cell_to_pixel(self, x, y):
        return x * self.CELL_SIZE, self._at + y * self.CELL_SIZE

    def _spawn_cherries(self):
        attempts = 0
        while len(self._cherries) < self.CHERRY_COUNT and attempts < 300:
            attempts += 1
            pos = (random.randrange(self._cols), random.randrange(self._rows))
            if pos in self._snake or pos in self._cherries:
                continue
            if any(self._torus_distance(pos[0], pos[1], cx, cy) < 3 for cx, cy in self._cherries):
                continue
            self._cherries.append(pos)

    def _torus_distance(self, x, y, tx, ty):
        dx = abs(x - tx)
        dx = min(dx, self._cols - dx)
        dy = abs(y - ty)
        dy = min(dy, self._rows - dy)
        return dx + dy

    def _nearest_cherry(self, x, y):
        if not self._cherries:
            return None
        return min(self._cherries, key=lambda p: self._torus_distance(x, y, p[0], p[1]))

    def _choose_direction(self):
        head_x, head_y = self._snake[0]
        dx, dy = self._dir
        choices = [(dx, dy), (-dy, dx), (dy, -dx)]
        target = self._nearest_cherry(head_x, head_y)
        if target is None:
            random.shuffle(choices)
            return choices[0]

        body = set(self._snake[:-1] if self._grow <= 0 else self._snake)
        scored = []
        for ndx, ndy in choices:
            nx, ny = self._wrap_cell(head_x + ndx, head_y + ndy)
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
        pos = (x, y)
        if pos not in self._cherries:
            return False
        self._cherries.remove(pos)
        self._grow += 3
        if not self._cherries:
            self._spawn_cherries()
        return True

    def _step(self):
        self._dir = self._choose_direction()
        hx, hy = self._snake[0]
        nx, ny = self._wrap_cell(hx + self._dir[0], hy + self._dir[1])
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

    def _draw_block(self, canvas, cell, color, highlight=None):
        ox, oy = self._cell_to_pixel(*cell)
        for dy in range(self.CELL_SIZE):
            for dx in range(self.CELL_SIZE):
                px, py = ox + dx, oy + dy
                if 0 <= px < self._w and self._at <= py <= self._ab:
                    canvas.SetPixel(px, py, *(highlight if highlight and dx == 1 and dy == 1 else color))

    def draw(self, canvas):
        for cherry in self._cherries:
            self._draw_block(canvas, cherry, (170, 0, 35), (255, 45, 60))

        crash = self._crash_frames > 0 and (self._frame % 2 == 0)
        for i, cell in enumerate(reversed(self._snake)):
            if crash:
                color = (220, 30, 30)
            elif i == len(self._snake) - 1:
                color = (210, 255, 120)
            else:
                shade = 100 + int(85 * (i / max(1, len(self._snake) - 1)))
                color = (35, shade, 55)
            self._draw_block(canvas, cell, color)

    def is_done(self) -> bool:
        return False
