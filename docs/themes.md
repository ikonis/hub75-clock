# Themes

Themes control the background, text colors, and animation behavior of the clock face. Each theme is a JSON file. The clock loads all `.json` files from its themes directory at startup and watches for changes. Drop a new file in and the clock picks it up within seconds, no restart required.

---

## Where themes live

Built-in themes are installed to `/etc/hub75-clock/themes/` by `install.sh`. That is also where the clock reads them from at runtime. Add your own `.json` files to the same directory.

```
/etc/hub75-clock/themes/
├── day.json
├── sunrise.json
├── sunset.json
├── late_evening.json
├── night.json
├── away.json
└── your_custom_theme.json   ← drop it here
```

The repo ships the built-in themes under `themes/` and the installer copies them on first install. On subsequent `make update` runs the directory is left alone so your edits survive.

---

## Activating a theme

**From Home Assistant:** The clock registers a `select` entity (`Theme`) on the device page. Pick any loaded theme from the dropdown. The selection takes effect immediately.

**Via MQTT:** Publish the theme name as a plain string or as a JSON object to the theme command topic:

```bash
# Plain string
mosquitto_pub -h <broker> -u <user> -P <pass> \
  -t hub75_clock/theme/set \
  -m 'Night'

# JSON object
mosquitto_pub -h <broker> -u <user> -P <pass> \
  -t hub75_clock/theme/set \
  -m '{"theme": "Night"}'
```

The clock publishes the active theme name to `hub75_clock/theme/state` (retained) so the HA select entity stays in sync.

**Available themes list:** `hub75_clock/themes/available` (retained JSON array) is updated automatically whenever files are added or removed from the themes directory.

---

## JSON schema

Every field except `name` is optional. Omitting a field uses the default.

### Identity

| Field | Type | Default | Description |
|---|---|---|---|
| `name` | string | **required** | Display name shown in Home Assistant and used as the theme identifier. Must be unique across all files in the themes folder. |
| `description` | string | `""` | Free-text note for your own reference. Not displayed anywhere by the clock. |

### Background

| Field | Type | Default | Description |
|---|---|---|---|
| `background_type` | string | `"solid"` | `"solid"` fills the animation zone with a single color. `"gradient"` blends between two colors with a split point. |
| `background_color` | hex string | `"#000820"` | Fill color when `background_type` is `"solid"`. |
| `background_top` | hex string | `"#0F0019"` | Top color when `background_type` is `"gradient"`. |
| `background_bottom` | hex string | `"#3C1400"` | Bottom color when `background_type` is `"gradient"`. |
| `background_split` | float 0.0–1.0 | `0.5` | Fraction of the animation zone height where the gradient transitions. `0.5` = halfway. `0.25` = upper quarter. |
| `background_gradient_direction` | string | `"sunset"` | `"sunrise"` or `"sunset"`. Controls which end is solid and which fades. See [Gradient direction](#gradient-direction) below. |

### Text colors

All values are hex color strings (`"#RRGGBB"`). When a key is present in the theme, it overrides the day/night color from `config.yaml` for that element.

| Field | Type | Default | Description |
|---|---|---|---|
| `colors.time` | hex string | from config | Large clock digits. |
| `colors.low_temp` | hex string | from config | Low temperature value in the banner. |
| `colors.high_temp` | hex string | from config | High temperature value in the banner. |
| `colors.condition` | hex string | from config | Weather condition word in the banner (e.g. `RAIN`, `CLEAR`). |

### Stars

| Field | Type | Default | Description |
|---|---|---|---|
| `stars_enabled` | bool | `false` | Show twinkling stars in the animation zone. Use for night themes where the condition is CLEAR, SUNNY, or PARTLYCLOUDY. |

### Cameos

One-shot animated events that fire at a configurable rate. Only one cameo runs at a time; if one is already playing, rolls for new ones are skipped until it finishes.

| Field | Type | Default | Description |
|---|---|---|---|
| `cameos` | array | `[]` | List of cameo objects. Each has `name` (string) and `chance_per_minute` (float). |

**Cameo object fields:**

| Field | Type | Description |
|---|---|---|
| `name` | string | Which animation to spawn. Must match the `name` attribute of an animation file in `/etc/hub75-clock/animations/`. |
| `chance_per_minute` | float | Expected spawns per minute on average. The roll is evaluated every frame at runtime FPS. |

Example:

```json
"cameos": [
  {"name": "shooting_star", "chance_per_minute": 8},
  {"name": "ufo", "chance_per_minute": 2}
]
```

**Built-in animations** (installed to `/etc/hub75-clock/animations/` by `install.sh`):

| Name | Layer | Conditions | Themes | Description |
|---|---|---|---|---|
| `clouds` | foreground | _(any)_ | Day, Sunrise, Sunset, Late Evening | **Persistent** — add without `chance_per_minute`. Handles clouds AND all precipitation (rain, tstorm with lightning, snow, sleet). Driven by `cloud_density`, `cloud_speed`, `precipitation`, and `colors.cloud_day`. |
| `shooting_star` | celestial | CLEAR, PARTLYCLOUDY | Night, Late Evening | Fast diagonal streak with fading tail |
| `ufo` | foreground | CLEAR, PARTLYCLOUDY | Night, Late Evening | Saucer silhouette, cycling belly lights, occasional tractor beam abduction |
| `satellite` | celestial | CLEAR | Night | ISS-silhouette cross, diagonal slow pass |
| `meteor` | celestial | CLEAR | Night, Late Evening | Fast bidirectional diagonal with orange/red history trail |
| `comet` | celestial | CLEAR | Night | Slow diagonal with blue-white gradient tail |
| `airplane` | foreground | _(any)_ | Day, Sunrise, Sunset | Fuselage + wings + windows, mirrors to face direction of travel |
| `bird_flock` | foreground | _(any)_ | Day | V-formation of 5–7 birds with alternating flap frames |
| `butterfly` | foreground | CLEAR | Day | Open/closed wing frames, sine wave vertical drift, orange |
| `hot_air_balloon` | foreground | CLEAR, PARTLYCLOUDY | Day, Sunrise | 7×10px balloon with ROYGBIV stripes, drifts upward |
| `tumbleweed` | foreground | _(any)_ | Day | Rolling circle with rotation transform, slight bounce |
| `rainbow` | foreground | CLEAR, PARTLYCLOUDY | Day | ROYGBIV arc, 2px thick bands, fade in/hold/fade out |
| `firefly` | foreground | CLEAR | Night, Late Evening | 6–8 dots, independent sine-phase blink, slow drift, 2px tall |
| `snowman` | foreground | SNOW | _(any)_ | Pixel-art snowman, lower-right corner, fade in/out |
| `santa` | foreground | _(any)_ | Night, Late Evening | Sleigh + reindeer silhouette, right-to-left, sine altitude |
| `fireworks` | foreground | _(any)_ | _(any)_ | 1–3 physics-based rockets, 16–20 sparks each with velocity tails |
| `jack_o_lantern` | foreground | _(any)_ | Night, Late Evening | 9×7px pumpkin with triangle eyes and zigzag mouth, fade in/out |
| `easter_egg` | foreground | _(any)_ | Day | 6×8px striped oval, bounces left-to-right |
| `rocket` | foreground | _(any)_ | _(any)_ | 3×7px rocket, accelerates upward from random X, flame trail |
| `submarine` | foreground | _(any)_ | Day | Long hull + conning tower + periscope, slow left-to-right |
| `ghost` | foreground | _(any)_ | Night, Late Evening | Pac-Man ghost (Blinky/Pinky/Inky/Clyde colors), directional pupils, sine float |

The `layer` column shows when the animation is drawn relative to weather particles. `celestial` renders behind rain and snow; `foreground` renders in front. See `docs/animations.md` for details.

See `docs/animations.md` for the drop-in animation interface and how to write your own.

### Clouds and precipitation

All clouds and precipitation are handled by the persistent `clouds` cameo animation. To enable clouds (with or without precipitation), add `{"name": "clouds"}` to the `cameos` array. Cloud count, size, speed, and particle type are controlled by the fields below.

| Field | Type | Default | Description |
|---|---|---|---|
| `cloud_density` | string | `"medium"` | Number of clouds. `"sparse"` = 2, `"medium"` = 4, `"dense"` = 7. |
| `cloud_speed` | string | `"medium"` | How fast clouds drift left. `"slow"` = 0.2 px/frame, `"medium"` = 0.4, `"fast"` = 0.7. |
| `precipitation` | string | `"none"` | Precipitation particles to emit below clouds. See table below. |
| `colors.cloud_day` | hex string | `"#646464"` | Cloud body color. Override per-theme for mood. |

**Precipitation modes:**

| Value | Effect |
|---|---|
| `"none"` | Clouds only, no particles. |
| `"rain"` | 2–4 blue rain streaks per cloud, 1.5 px/frame. |
| `"heavy_rain"` | 4–6 darker streaks per cloud, 2.5 px/frame. |
| `"tstorm"` | Heavy rain plus lightning bolts (8–15 s intervals) with a brief background flash. |
| `"snow"` | 2–3 white dots per cloud, 0.3–0.5 px/frame with gentle lateral wobble. |
| `"sleet"` | Mixed: half fast cyan-gray streaks, half slow wobbling dots. |

All particles are owned by the cloud that spawned them. They fall downward and wrap back to the cloud bottom when they exit the animation zone. When the cloud wraps around to the right edge, its particles are reset.

### Sun and Moon

| Field | Type | Default | Description |
|---|---|---|---|
| `sun_enabled` | bool | `true` | Draw the sun quarter-circle glow in the top-right corner when the condition is SUNNY and night mode is off. Set to `false` for themes where the background already represents the sun (e.g. sunrise gradient, sunset gradient), so the glow doesn't stack on top of the coloured sky. |
| `moon_enabled` | bool | `false` | Draw a small moon disk (radius 3, ~7×7px) in the upper-left corner of the animation zone with a mottled gray surface and a dim glow border. Intended for night and late-evening themes. |

### Condition overrides

| Field | Type | Default | Description |
|---|---|---|---|
| `condition_overrides` | object | `{}` | Per-condition background overrides. Keys are condition strings (see below). Values are objects containing any subset of the background fields (`background_type`, `background_color`, `background_top`, `background_bottom`, `background_split`, `background_gradient_direction`). Text colors, `stars_enabled`, `cameos`, and `sun_enabled` cannot be overridden per-condition. |

Example:

```json
"condition_overrides": {
  "TSTORM": {
    "background_type": "solid",
    "background_color": "#010005"
  },
  "RAIN": {
    "background_type": "gradient",
    "background_top": "#030010",
    "background_bottom": "#010008",
    "background_gradient_direction": "sunset"
  }
}
```

---

## Valid condition strings for overrides

```
CLEAR           SUNNY           PARTLYCLOUDY    CLOUDY
RAIN            SNOW            SLEET           TSTORM
ICE             FLOOD           BLIZZARD        HURRICANE
TROPICAL_STORM  FREEZING_RAIN   FREEZING_DRIZZLE
DUST            SMOKE
```

Aliased conditions (BLIZZARD→SNOW, HURRICANE→TSTORM, FLOOD→RAIN, etc.) are normalized before the override lookup, so use the canonical name, not the alias, as the key.

---

## Gradient direction

`background_gradient_direction` controls which portion of the animation zone is a solid fill and which fades.

```
sunrise:                    sunset:
┌──────────────┐            ┌──────────────┐
│  background  │            │  background  │  ← solid top
│     _top_    │  ← fades   │     _top_    │
│              │    down     │              │
├──────────────┤            ├──────────────┤  ← split point
│              │            │              │
│  background  │  ← solid   │  background  │  ← fades down
│   _bottom_   │   bottom   │   _bottom_   │
└──────────────┘            └──────────────┘
```

**Sunrise:** The top portion fades from `background_top` (at the very top) down to `background_bottom` (at the split). The bottom portion below the split is a solid fill of `background_bottom`. Good for dawn: dark purple sky above a warm horizon, flat dark ground below.

**Sunset:** The top portion above the split is a solid fill of `background_top`. The bottom portion fades from `background_top` (at the split) down to `background_bottom` (at the very bottom). Good for dusk. The sky holds its color and bleeds into a warm horizon at the bottom.

`background_split: 0.5` puts the transition at the vertical midpoint of the animation zone. Lower values (e.g. `0.25`) push it toward the top; higher values (e.g. `0.75`) push it toward the bottom.

---

## Installing a theme

1. Write your JSON file (see [example](#complete-example) below).
2. Copy it to the themes directory:
   ```bash
   sudo cp stormy_night.json /etc/hub75-clock/themes/
   ```
3. The clock detects the new file within a few seconds and adds it to the available themes list.
4. Select it from the HA device page or via MQTT.

No restart required.

---

## Complete example

`stormy_night.json`: a dark, dramatic theme for thunderstorm nights with lightning.

```json
{
  "name": "Stormy Night",
  "description": "Dark stormy sky with lightning",

  "background_type": "solid",
  "background_color": "#010004",

  "colors": {
    "time":      "#383838",
    "low_temp":  "#001C2A",
    "high_temp": "#2A1100",
    "condition": "#141418",
    "cloud_day": "#1C1C24"
  },

  "stars_enabled": false,
  "cameos": [{"name": "clouds"}],

  "cloud_density": "dense",
  "cloud_speed": "fast",
  "precipitation": "tstorm",

  "sun_enabled": false,
  "moon_enabled": false
}
```

**Field-by-field notes:**

- `background_color: "#010004"`: near-black with a faint purple tint. Keeps the panel very dim.
- `colors.time: "#383838"`: dark grey — a bright clock face is intrusive at night.
- `colors.cloud_day: "#1C1C24"`: very dark clouds, barely visible — storm clouds blocking all light.
- `precipitation: "tstorm"`: heavy rain particles plus random lightning bolts with a brief background flash. Lightning interval is 8–15 seconds.
- `cloud_density: "dense"` + `cloud_speed: "fast"`: 7 fast-moving clouds feel stormy and oppressive.
- `stars_enabled: false`: no stars; total overcast.

---

## Tips

- **Keep colors dim for night themes.** Time and temperature colors in the `#303030`–`#606060` range are readable without lighting up a dark room. Use `#F0F0F0` only for daytime themes.

- **Condition overrides are the right place for weather-reactive backgrounds.** A day theme might have a bright blue sky by default but darken to near-black during TSTORM. That way you get one theme that adapts rather than needing separate themes for every combination of time-of-day and weather.

- **Theme names must be unique** across all `.json` files in the themes folder. If two files declare the same `name`, the second one loaded wins (load order is filesystem-alphabetical). Use a clear, descriptive name.

- **You can have as many themes as you want.** The HA select entity updates its options list automatically. There is no limit.

- **Drop a theme file in place to update it.** The watchdog detects the write and reloads. If the active theme was modified, it stays active with the new settings applied immediately.
