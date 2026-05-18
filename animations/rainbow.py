import math


class Animation:
    name = "rainbow"
    conditions = ["CLEAR", "PARTLYCLOUDY"]
    themes = ["Day"]

    _BANDS = [
        (255, 0,   0),    # Red
        (255, 165, 0),    # Orange
        (255, 255, 0),    # Yellow
        (0,   200, 0),    # Green
        (0,   0,   255),  # Blue
        (75,  0,   130),  # Indigo
        (148, 0,   211),  # Violet
    ]

    def __init__(self, width, height, cfg, animator):
        self._w = width
        self._at = animator.anim_top
        self._ab = animator.anim_bottom
        self._frame = 0
        # Arc: 3 rows of color bands, arching from bottom-left to bottom-right
        # fade_in: 0-15, hold: 15-60, fade_out: 60-75
        self._fade_in  = 15
        self._hold     = 45
        self._fade_out = 15
        self._total = self._fade_in + self._hold + self._fade_out

    def _alpha(self) -> float:
        f = self._frame
        if f < self._fade_in:
            return f / self._fade_in
        elif f < self._fade_in + self._hold:
            return 1.0
        else:
            return 1.0 - (f - self._fade_in - self._hold) / self._fade_out

    def update(self):
        self._frame += 1

    def draw(self, canvas):
        alpha = max(0.0, min(1.0, self._alpha()))
        if alpha <= 0:
            return
        # Arc parameters: center at bottom-center, radius grows upward
        cx = self._w / 2
        base_y = self._ab + 1
        for bi, (br, bg2, bb) in enumerate(self._BANDS):
            r2 = 26 - bi * 3    # radius decreases for each band inward
            for px in range(self._w):
                dx = px - cx
                # y of arc at this x
                dist = abs(dx)
                if dist > r2:
                    continue
                arc_h = math.sqrt(max(0, r2 * r2 - dx * dx))
                py = int(round(base_y - arc_h))
                if self._at <= py <= self._ab:
                    canvas.SetPixel(
                        px, py,
                        int(br * alpha), int(bg2 * alpha), int(bb * alpha)
                    )

    def is_done(self) -> bool:
        return self._frame >= self._total
