# Animations

The clock supports a drop-in animation system. Any `.py` file placed in `/etc/hub75-clock/animations/` is automatically loaded at runtime. The watchdog detects new and changed files within seconds — no restart required.

Animations are triggered as **cameos** inside theme JSON files. See `docs/themes.md` for how to add them to a theme.

---

## Python drop-in system

1. `AnimationLoader` scans `/etc/hub75-clock/animations/` at startup and imports every `.py` file that contains a class named `Animation`.
2. Each `Animation` class is registered under its `name` attribute.
3. A watchdog monitors the directory. When any `.py` file changes or a new one appears, the loader rescans and rebuilds the registry.
4. The built-in `shooting_star` animation is always registered as a fallback even if the directory is empty.
5. `CameoManager` uses the registry when a theme's `cameos` list asks for an animation by name.

---

## Writing a Python custom animation

Create a file in `/etc/hub75-clock/animations/` with exactly this structure:

```python
import math
import random


class Animation:
    name = "my_animation"          # unique string key — must match what you put in themes
    conditions = []                # informational: intended weather conditions (not enforced at runtime)
    themes = []                    # informational: intended theme names (not enforced at runtime)
    layer = "foreground"           # "celestial" draws before sun/moon; "foreground" draws last
    persistent = False             # True = runs every frame without a chance_per_minute roll
    speed = 1.0                    # optional multiplier for motion/twinkle speed

    def __init__(self, width, height, cfg, animator):
        self._w = width
        self._at = animator.anim_top   # first row of the animation zone (row 8 on a 64×32 panel)
        self._ab = animator.anim_bottom  # last row of the animation zone (row 31)
        # Initialize your animation state here

    def update(self):
        # Advance state by one frame. Called every frame before draw().
        pass

    def draw(self, canvas):
        # Draw to canvas using canvas.SetPixel(x, y, r, g, b).
        # x must be in 0 .. width-1.
        # y must be in anim_top .. anim_bottom.
        # Do NOT draw outside the animation zone.
        pass

    def is_done(self) -> bool:
        # Return True when the animation has finished. CameoManager will discard it.
        # For persistent animations, return False always.
        return False
```

Drop the file into `/etc/hub75-clock/animations/`. The clock picks it up within a few seconds. Add its `name` to a theme's `cameos` list:

```json
"cameos": [
  {"name": "my_animation", "chance_per_minute": 3}
]
```

---

## Cameo runtime

`CameoManager` maintains one one-shot animation slot plus persistent animations:

- **One-shot slot (`_active`)**: The normal cameo slot. Spawned via `chance_per_minute` probability rolls. Only one runs at a time; while one is active, new rolls are skipped. Cleared on condition change.
- **Persistent animations**: Started once when the theme is applied. They run every frame without any roll and are cleared only on theme change, surviving condition changes. Used for continuously visible effects such as `stars` and `clouds`.

A persistent animation sets `persistent = True` on its class and should return `False` from `is_done()` always. It does not need a `chance_per_minute` entry in the cameos array:

```json
"cameos": [{"name": "stars"}, {"name": "clouds"}]
```

---

## Draw layer ordering

Animations declare their draw layer via the `layer` class attribute:

| Value | When drawn | Examples |
|---|---|---|
| `"celestial"` | After background fill, before sun/moon and clouds | `stars`, `shooting_star`, `meteor`, `comet`, `satellite` |
| `"foreground"` | After clouds, on top of weather particles | `ghost`, `ufo`, all others |

Draw order each frame: background fill -> celestial cameos (`stars`, `shooting_star`, `meteor`, `comet`) -> sun/moon -> clouds and precipitation -> foreground cameos.

---

## Class attributes

### `name` (required)

A unique string key. This is what you put in the theme JSON. If two files declare the same name the second one loaded wins (load order is alphabetical by filename).

### `conditions` (optional, list of strings)

Informational metadata describing the weather conditions this animation is designed for (e.g. `["CLEAR", "RAIN"]`). **Not enforced at runtime.** The clock does not check this attribute before spawning — if the animation is listed in a theme's `cameos` array, it will fire regardless of the current weather condition.

Use this field as documentation for yourself and for tools like the theme builder. An empty list (`[]`) means "suitable for any condition."

### `themes` (optional, list of strings)

Informational metadata describing the theme names this animation is designed for (e.g. `["Night", "Day"]`). **Not enforced at runtime.** The clock does not check this attribute before spawning.

An empty list (`[]`) means "suitable for any theme."

### `layer` (optional, string)

Controls where in the draw stack this animation is rendered. Default is `"foreground"`.

- `"celestial"` — rendered after the background fill and before sun/moon and weather particles. Use for sky objects such as stars, meteors, shooting stars, satellites, and comets.
- `"foreground"` — rendered after clouds and precipitation. Use for everything else.

### `persistent` (optional, bool)

Default `False`. When `True`, the animation is instantiated once when the theme is applied and runs every frame without a `chance_per_minute` roll. It is replaced only when the theme changes. Persistent animations should always return `False` from `is_done()`.

### `speed` (optional, float)

Default `1.0`. Built-in animations use this as a simple multiplier for movement, twinkle, or drift speed so timing can be tuned without rewriting update logic.

---

## `__init__` parameters

| Parameter | Type | Description |
|---|---|---|
| `width` | int | Panel width in pixels (64 for a 64×32 panel) |
| `height` | int | Panel height in pixels (32 for a 64×32 panel) |
| `cfg` | dict | The full clock config dict. Access MQTT or other settings if needed. Usually not needed. |
| `animator` | WeatherAnimator | The running animator instance. Use `animator.anim_top` and `animator.anim_bottom` for the animation zone boundaries. |

---

## Drawing API

`canvas.SetPixel(x, y, r, g, b)` — set a single pixel.

- `x`: 0–63 (left to right)
- `y`: 0–31 (top to bottom)
- `r`, `g`, `b`: 0–255

The animation zone runs from `anim_top` (row 8) to `anim_bottom` (row 31). Rows 0–7 are the banner strip (time, temps, condition). Always guard your pixel writes:

```python
if 0 <= px < self._w and self._at <= py <= self._ab:
    canvas.SetPixel(px, py, r, g, b)
```

---

## Minimal working example

A single pixel that blinks yellow and drifts across the screen:

```python
import random


class Animation:
    name = "blink_dot"
    conditions = []
    themes = []

    def __init__(self, width, height, cfg, animator):
        self._w = width
        self._at = animator.anim_top
        self._ab = animator.anim_bottom
        self.x = 0.0
        self.y = float(self._at + random.randint(0, self._ab - self._at))
        self._frame = 0

    def update(self):
        self.x += 0.4
        self._frame += 1

    def draw(self, canvas):
        if self._frame % 8 < 4:   # blink: on for 4 frames, off for 4
            px, py = int(self.x), int(self.y)
            if 0 <= px < self._w and self._at <= py <= self._ab:
                canvas.SetPixel(px, py, 255, 220, 0)

    def is_done(self) -> bool:
        return self.x > self._w + 2
```

---

## Built-in animations reference

These are installed as `.py` files in `/etc/hub75-clock/animations/`.

### Space / Night

Celestial animations are drawn before sun/moon and clouds so meteors appear to fall behind weather. Foreground night animations draw after clouds.

| File | Name | Conditions | Themes | Description |
|---|---|---|---|---|
| `stars.py` | `stars` | CLEAR, PARTLYCLOUDY | Night, Late Evening | **Persistent.** Twinkling star field. Add without `chance_per_minute`; rendered in the celestial layer before sun/moon. |
| `shooting_star.py` | `shooting_star` | CLEAR, PARTLYCLOUDY | Night, Late Evening | Fast diagonal streak with fading tail. Built-in fallback; always registered even if the file is missing. |
| `ufo.py` | `ufo` | CLEAR, PARTLYCLOUDY | Night, Late Evening | Saucer silhouette drifting across with cycling teal belly lights, glow trail, and occasional tractor beam abduction sequence. |
| `satellite.py` | `satellite` | CLEAR | Night | ISS-profile cross sprite, slow diagonal pass from top-right to bottom-left. |
| `meteor.py` | `meteor` | CLEAR | Night, Late Evening | Fast bidirectional diagonal (3.5–5 px/frame) with 6-frame orange/red history trail. |
| `comet.py` | `comet` | CLEAR | Night | Slow diagonal with 10–14px blue-white gradient tail, always drifts downward. |

### Day / Sky (layer: foreground)

| File | Name | Conditions | Themes | Description |
|---|---|---|---|---|
| `clouds.py` | `clouds` | _(any)_ | Day, Sunrise, Sunset, Late Evening | **Persistent.** Drifting clouds plus optional precipitation particles. Count, size, and speed driven by `cloud_density`/`cloud_speed`. Precipitation type set by `precipitation` field (`"none"`, `"rain"`, `"heavy_rain"`, `"tstorm"`, `"snow"`, `"sleet"`). Tstorm mode adds random lightning bolts and background flash. All particles are owned by their parent cloud and wrap with it. |
| `airplane.py` | `airplane` | _(any)_ | Day, Sunrise, Sunset | 8px fuselage + wings + windows, random left/right direction, mirrors sprite to face direction of travel. |
| `bird_flock.py` | `bird_flock` | _(any)_ | Day | V-formation of 5–7 birds with alternating flap frames. |
| `butterfly.py` | `butterfly` | CLEAR | Day | Open/closed wing frames every 5 ticks, sine wave vertical drift, orange. |
| `flutterflies.py` | `flutterflies` | CLEAR | Day | **Persistent.** Small pastel butterfly group with gentle wandering motion. Add without `chance_per_minute`. |
| `hot_air_balloon.py` | `hot_air_balloon` | CLEAR, PARTLYCLOUDY | Day, Sunrise | 7×10px balloon with ROYGBIV stripes, drifts upward. |
| `tumbleweed.py` | `tumbleweed` | _(any)_ | Day | 5px circle with rotation transform, slight bounce via `|sin|×1.5`. |

### Weather (layer: foreground)

| File | Name | Conditions | Themes | Description |
|---|---|---|---|---|
| `rainbow.py` | `rainbow` | CLEAR, PARTLYCLOUDY | Day | ROYGBIV arc using radius math per band, 2px thick, fade in 15 / hold 45 / fade out 15 frames. |
| `firefly.py` | `firefly` | CLEAR | Night, Late Evening | 6–8 dots with independent sine-phase blink, slow random drift, yellow-green, 2px tall. |
| `snowman.py` | `snowman` | SNOW | _(any)_ | Pixel-art snowman lower-right corner, fade in 20 / hold 90 / fade out 20 frames, flickering eyes. |

### Holiday (layer: foreground)

| File | Name | Conditions | Themes | Description |
|---|---|---|---|---|
| `santa.py` | `santa` | _(any)_ | Night, Late Evening | 14px-wide sleigh + reindeer silhouette, right-to-left, sine wave altitude. |
| `fireworks.py` | `fireworks` | _(any)_ | _(any)_ | 1–3 rockets with staggered launches. Physics-based: gravity applied each frame, apex triggers explosion. 16–20 sparks per burst with velocity-based tails at 60%/30% brightness. |
| `jack_o_lantern.py` | `jack_o_lantern` | _(any)_ | Night, Late Evening | 9×7px orange pumpkin with triangle eyes, triangle nose, zigzag mouth. Lower-right corner, fade in/out. |
| `easter_egg.py` | `easter_egg` | _(any)_ | Day | 6×8px oval with 4-color stripe pattern, bounces left-to-right with slight vertical bob. |

### Fun (layer: foreground)

| File | Name | Conditions | Themes | Description |
|---|---|---|---|---|
| `rocket.py` | `rocket` | _(any)_ | _(any)_ | 3×7px rocket sprite, accelerates upward from a random X position, flame trail below, exits top. |
| `submarine.py` | `submarine` | _(any)_ | Day | Long hull + conning tower + periscope, slow left-to-right with slight sine wave. |
| `ghost.py` | `ghost` | _(any)_ | Night, Late Evening | Pac-Man ghost (7×8px): Blinky/Pinky/Inky/Clyde colors, directional pupils, scalloped bottom, sine float. |

---

## Chance per minute tuning

`chance_per_minute` controls how often a cameo spawns on average. The roll is evaluated every frame:

```
probability_per_frame = chance_per_minute / 60 / fps
```

At 90 fps with `chance_per_minute: 8`:

```
8 / 60 / 90 = 0.0015  →  ~1 spawn per 675 frames (~7.5 seconds)
```

At lower FPS, the per-frame probability is higher so the per-minute rate stays the same:

```
8 / 60 / 30 = 0.0044  →  still ~8 spawns per minute on average
```

Typical values:

| Rate | Feel |
|---|---|
| 1–2 | Rare, occasional surprise |
| 4–8 | Regular — visible but not constant |
| 15–20 | Frequent |
| 30+ | Near-continuous |

Only one cameo runs at a time. While one is active, rolls for all cameos are skipped. High rates shorten the idle time between cameos; a new one starts almost immediately after the previous finishes.

---

## Tips

- **Keep animations entirely within the animation zone.** The banner rows (0–7) must stay intact. Always guard pixel writes with the `anim_top` / `anim_bottom` check.
- **Do not import heavy libraries.** `math` and `random` are always available. Avoid anything that requires install-time dependencies.
- **Name collisions:** if your file's `Animation.name` matches an existing built-in, your file wins because `_scan()` processes files alphabetically and yours will likely run after the built-in. Prefix custom names to avoid accidental overrides (`"my_ufo"` instead of `"ufo"`).
- **Errors are logged, not crashed.** If your file has a syntax error or the `Animation` class is missing required attributes, the loader prints a warning and skips the file. The rest of the animations continue working.
- **Test interactively:** run the clock manually (`sudo python3 /opt/hub75-clock/hub75_clock.py`) and watch the logs with `make logs` while you drop files in. The watchdog reloads within 2 seconds of a file write.
