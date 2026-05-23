import math
import random


class Animation:
    name = "ufo"
    conditions = ["CLEAR", "PARTLYCLOUDY"]
    themes = ["Night", "Late Evening"]
    layer = "foreground"
    speed = 1.0

    # Saucer sprite (9 wide, 5 tall), row by row, (dx, dy, r, g, b)
    _BODY = [
        # dome (top, 3 wide centered)
        (3, 0, 120, 220, 140), (4, 0, 140, 255, 160), (5, 0, 120, 220, 140),
        # upper hull
        (1, 1, 60, 160, 70), (2, 1, 90, 200, 100), (3, 1, 110, 230, 120),
        (4, 1, 120, 240, 130), (5, 1, 110, 230, 120), (6, 1, 90, 200, 100),
        (7, 1, 60, 160, 70),
        # mid hull (widest)
        (0, 2, 40, 100, 50), (1, 2, 70, 170, 80), (2, 2, 100, 210, 110),
        (3, 2, 110, 220, 120), (4, 2, 120, 230, 130), (5, 2, 110, 220, 120),
        (6, 2, 100, 210, 110), (7, 2, 70, 170, 80), (8, 2, 40, 100, 50),
        # lower hull
        (1, 3, 50, 140, 60), (2, 3, 70, 170, 80), (3, 3, 80, 180, 90),
        (4, 3, 90, 190, 100), (5, 3, 80, 180, 90), (6, 3, 70, 170, 80),
        (7, 3, 50, 140, 60),
    ]
    # Underbelly lights
    _LIGHTS = [(2, 4), (4, 4), (6, 4)]

    # --- Appearance settings (hull colors are in _BODY list above) ---
    COLOR_LIGHT_ON   = (0, 255, 180)   # active belly light
    COLOR_LIGHT_OFF  = (0,  60,  40)   # inactive belly light
    COLOR_BEAM_G     = 50              # tractor beam green peak (r=0, g=COLOR_BEAM_G, b=g//2)
    COLOR_FIGURE     = (200, 200, 200) # stick figure abductee
    # -----------------------------------------------------------------

    # Tractor beam: triangular rows below the UFO (row offset from dy=5)
    # Each entry is (half_width, alpha_factor)
    _BEAM_ROWS = [(0, 1.0), (1, 0.9), (1, 0.85), (2, 0.8),
                  (2, 0.75), (3, 0.7), (3, 0.65), (4, 0.6)]

    # Stick figure offsets from center
    _FIGURE = [(0, 0), (0, 1), (-1, 1), (1, 1), (-1, 2), (1, 2)]

    def __init__(self, width, height, cfg, animator):
        self._w = width
        self._at = animator.anim_top
        self._ab = animator.anim_bottom
        self.x = float(width)
        self.y = float(self._at + random.randint(2, 8))
        self._vx = -(0.25 + random.random() * 0.2) * self.speed
        self._wobble = random.random() * math.pi * 2
        self._wobble_speed = 0.08 * self.speed
        self._light_phase = 0
        # Tractor beam state
        self._mode = "fly"   # fly | beam_in | abduct | beam_out
        self._beam_triggered = False
        self._beam_frame = 0
        self._figure_y = 0.0

    def _beam_center_x(self):
        return int(round(self.x)) + 4   # center of UFO hull

    def update(self):
        self._wobble += self._wobble_speed
        self._light_phase = (self._light_phase + 1) % (len(self._LIGHTS) * 6)

        if self._mode == "fly":
            self.x += self._vx
            # Trigger beam randomly once, while UFO is in middle third of screen
            if (not self._beam_triggered and
                    self._w * 0.2 <= self.x <= self._w * 0.65 and
                    random.random() < 0.006):
                self._mode = "beam_in"
                self._beam_triggered = True
                self._beam_frame = 0
                self._figure_y = float(self._ab - 3)
        elif self._mode == "beam_in":
            self._beam_frame += 1
            if self._beam_frame >= 36:
                self._mode = "abduct"
                self._beam_frame = 0
        elif self._mode == "abduct":
            self._figure_y -= 0.225 * self.speed   # float upward
            self._beam_frame += 1
            if self._figure_y < self.y + 6:   # absorbed into UFO
                self._mode = "beam_out"
                self._beam_frame = 0
        elif self._mode == "beam_out":
            self._beam_frame += 1
            if self._beam_frame >= 30:
                self._mode = "fly"   # resume flight

    def _draw_beam(self, canvas, intensity):
        cx = self._beam_center_x()
        base_y = int(round(self.y + math.sin(self._wobble) * 1.2)) + 5
        for row, (hw, af) in enumerate(self._BEAM_ROWS):
            by = base_y + row
            if by > self._ab:
                break
            br = int(intensity * af)
            for bx in range(cx - hw, cx + hw + 1):
                if 0 <= bx < self._w:
                    canvas.SetPixel(bx, by, 0, br, br // 2)

    def draw(self, canvas):
        ox = int(round(self.x))
        oy = int(round(self.y + math.sin(self._wobble) * 1.2))

        # Draw beam behind UFO
        if self._mode == "beam_in":
            intensity = min(50, self._beam_frame * 3)
            self._draw_beam(canvas, intensity)
        elif self._mode == "abduct":
            self._draw_beam(canvas, 50)
            # Stick figure floating up
            fx = self._beam_center_x()
            fy = int(round(self._figure_y))
            for ddx, ddy in self._FIGURE:
                px, py = fx + ddx, fy + ddy
                if 0 <= px < self._w and self._at <= py <= self._ab:
                    canvas.SetPixel(px, py, *self.COLOR_FIGURE)
        elif self._mode == "beam_out":
            intensity = max(0, 50 - self._beam_frame * 4)
            if intensity > 0:
                self._draw_beam(canvas, intensity)

        # UFO body
        for dx, dy, r, g, b in self._BODY:
            canvas.SetPixel(ox + dx, oy + dy, r, g, b)

        # Cycling belly light
        li = self._light_phase // 6
        for idx, (ldx, ldy) in enumerate(self._LIGHTS):
            if idx == li:
                canvas.SetPixel(ox + ldx, oy + ldy, *self.COLOR_LIGHT_ON)
            else:
                canvas.SetPixel(ox + ldx, oy + ldy, *self.COLOR_LIGHT_OFF)

        # Glow trail (only while flying)
        if self._mode == "fly":
            for i in range(1, 5):
                gx = ox + 9 + i
                gb = max(0, 20 - i * 5)
                if 0 <= gx < self._w:
                    canvas.SetPixel(gx, oy + 2, 0, gb, gb // 2)

    def is_done(self) -> bool:
        return self.x < -10
