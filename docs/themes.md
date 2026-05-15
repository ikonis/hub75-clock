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
| `shooting_stars_enabled` | bool | `false` | Show occasional shooting stars. Requires `stars_enabled: true`. |

### Clouds

| Field | Type | Default | Description |
|---|---|---|---|
| `clouds_enabled` | bool | `false` | Show drifting clouds. Clouds are drawn when the weather condition is CLOUDY, PARTLYCLOUDY, SUNNY, or similar. |
| `cloud_density` | string | `"medium"` | How many clouds to spawn. `"sparse"` = 2, `"medium"` = 3–4, `"dense"` = 5–6. |
| `cloud_speed` | string | `"medium"` | How fast clouds drift. `"slow"` = 0.04–0.10 px/frame, `"medium"` = 0.08–0.18, `"fast"` = 0.14–0.28. |

### Condition overrides

| Field | Type | Default | Description |
|---|---|---|---|
| `condition_overrides` | object | `{}` | Per-condition background overrides. Keys are condition strings (see below). Values are objects containing any subset of the background fields (`background_type`, `background_color`, `background_top`, `background_bottom`, `background_split`, `background_gradient_direction`). Text colors and animation flags cannot be overridden per-condition. |

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

`stormy_night.json`: a dark, dramatic theme for thunderstorm nights.

```json
{
  "name": "Stormy Night",
  "description": "Deep stormy sky, used automatically by night bucket during TSTORM",

  "background_type": "solid",
  "background_color": "#020008",

  "background_top": "#0A0015",
  "background_bottom": "#04000A",
  "background_split": 0.5,
  "background_gradient_direction": "sunset",

  "colors": {
    "time":      "#404040",
    "low_temp":  "#002233",
    "high_temp": "#331A00",
    "condition": "#1A1A1A"
  },

  "stars_enabled": false,
  "shooting_stars_enabled": false,

  "clouds_enabled": true,
  "cloud_density": "dense",
  "cloud_speed": "fast",

  "condition_overrides": {
    "TSTORM": {
      "background_type":  "solid",
      "background_color": "#010005"
    },
    "RAIN": {
      "background_type":  "solid",
      "background_color": "#030010"
    },
    "SNOW": {
      "background_type":  "solid",
      "background_color": "#040010"
    }
  }
}
```

**Field-by-field notes:**

- `background_color: "#020008"`: nearly black with a faint purple tint. Keeps the panel very dim.
- `background_top/bottom`: unused here since `background_type` is `"solid"`, but provided so the file is a complete reference.
- `colors.time: "#404040"`: dark grey instead of white. At night a bright clock face is intrusive.
- `clouds_enabled: true` + `dense` + `fast`: thick fast clouds feel stormy even before rain starts.
- `condition_overrides.TSTORM`: deepens the background further during active thunderstorms. The rain and lightning particles are drawn on top of this.
- `stars_enabled: false`: no stars; this theme is for overcast/stormy sky.

---

## Tips

- **Keep colors dim for night themes.** Time and temperature colors in the `#303030`–`#606060` range are readable without lighting up a dark room. Use `#F0F0F0` only for daytime themes.

- **Condition overrides are the right place for weather-reactive backgrounds.** A day theme might have a bright blue sky by default but darken to near-black during TSTORM. That way you get one theme that adapts rather than needing separate themes for every combination of time-of-day and weather.

- **Theme names must be unique** across all `.json` files in the themes folder. If two files declare the same `name`, the second one loaded wins (load order is filesystem-alphabetical). Use a clear, descriptive name.

- **You can have as many themes as you want.** The HA select entity updates its options list automatically. There is no limit.

- **Drop a theme file in place to update it.** The watchdog detects the write and reloads. If the active theme was modified, it stays active with the new settings applied immediately.
