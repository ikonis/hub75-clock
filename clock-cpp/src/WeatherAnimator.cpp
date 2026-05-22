#include "WeatherAnimator.h"
#include "CameoManager.h"
#include <algorithm>
#include <cmath>

// ── Constructor / Destructor ─────────────────────────────────────────────────

WeatherAnimator::WeatherAnimator(int w, int h, const nlohmann::json& config,
                                 rgb_matrix::RGBMatrix* matrix)
    : width(w), height(h), cfg(config), _matrix(matrix)
{
    // Layout: top band = clock text; animations fill the rest.
    // Matches Python: anim_top = banner_h + 1, anim_bottom = height - 1.
    int bannerH = cfg.value("/fonts/banner_h"_json_pointer, 6);
    animTop    = bannerH + 1;
    animBottom = height - 1;

    _cameos = new CameoManager(this);
    _cameos->loadPlugins();
}

WeatherAnimator::~WeatherAnimator() {
    delete _cameos;
}

// ── Mutators ─────────────────────────────────────────────────────────────────

void WeatherAnimator::setCondition(const std::string& cond) {
    condition = cond;
    _cameos->reset();
    _cameos->setupPersistent();
}

void WeatherAnimator::setTheme(const std::string& themeName, const ThemeLoader& loader) {
    currentTheme = loader.getTheme(themeName);
    _cameos->reset();
    _cameos->setupPersistent();
}

void WeatherAnimator::setNightMode(bool night) {
    nightMode = night;
}

// ── Frame loop ───────────────────────────────────────────────────────────────

void WeatherAnimator::update() {
    ++frame;
    _cameos->update();
}

void WeatherAnimator::draw(rgb_matrix::FrameCanvas* canvas) {
    _drawBackground(canvas);
    _cameos->drawBackground(canvas);
    _drawStars(canvas);
    if (currentTheme && currentTheme->sunEnabled)  _drawSun(canvas);
    if (currentTheme && currentTheme->moonEnabled) _drawMoon(canvas);
    _cameos->drawCelestial(canvas);
    _cameos->drawClouds(canvas);
    _cameos->drawForeground(canvas);
}

// ── Background ───────────────────────────────────────────────────────────────

void WeatherAnimator::_drawBackground(rgb_matrix::FrameCanvas* canvas) {
    // Defaults when no theme is loaded.
    if (!currentTheme) {
        auto col = resolveColor(parseColorValue(
            cfg.value("/colors/sky_day"_json_pointer, nlohmann::json("#000820"))));
        for (int y = animTop; y <= animBottom; ++y)
            for (int x = 0; x < width; ++x)
                canvas->SetPixel(x, y, col[0], col[1], col[2]);
        return;
    }

    // Resolve effective background fields, then apply condition_overrides.
    std::string bgType   = currentTheme->backgroundType;
    std::string bgColor  = currentTheme->backgroundColor;
    std::string bgTop    = currentTheme->backgroundTop;
    std::string bgBottom = currentTheme->backgroundBottom;
    float       bgSplit  = currentTheme->backgroundSplit;
    std::string bgDir    = currentTheme->backgroundGradientDirection;

    auto ovIt = currentTheme->conditionOverrides.find(condition);
    if (ovIt != currentTheme->conditionOverrides.end()) {
        const auto& ov = ovIt->second;
        if (ov.contains("background_type"))               bgType   = ov["background_type"].get<std::string>();
        if (ov.contains("background_color"))              bgColor  = ov["background_color"].get<std::string>();
        if (ov.contains("background_top"))                bgTop    = ov["background_top"].get<std::string>();
        if (ov.contains("background_bottom"))             bgBottom = ov["background_bottom"].get<std::string>();
        if (ov.contains("background_split"))              bgSplit  = ov["background_split"].get<float>();
        if (ov.contains("background_gradient_direction")) bgDir    = ov["background_gradient_direction"].get<std::string>();
    }

    int zoneH = animBottom - animTop;

    auto setRow = [&](int y, int r, int g, int b) {
        for (int x = 0; x < width; ++x) canvas->SetPixel(x, y, r, g, b);
    };

    if (bgType == "solid") {
        auto col = resolveColor(parseColorValue(nlohmann::json(bgColor)));
        for (int y = animTop; y <= animBottom; ++y)
            setRow(y, col[0], col[1], col[2]);

    } else if (bgType == "gradient") {
        auto topCol = resolveColor(parseColorValue(nlohmann::json(bgTop)));
        auto botCol = resolveColor(parseColorValue(nlohmann::json(bgBottom)));
        int splitY  = animTop + static_cast<int>(zoneH * bgSplit);

        if (bgDir == "sunrise") {
            // Gradient from top→bottom color over the top portion.
            for (int y = animTop; y <= splitY; ++y) {
                int span = splitY - animTop;
                float t  = (span > 0) ? float(y - animTop) / span : 1.0f;
                setRow(y,
                    int(topCol[0] + (botCol[0] - topCol[0]) * t),
                    int(topCol[1] + (botCol[1] - topCol[1]) * t),
                    int(topCol[2] + (botCol[2] - topCol[2]) * t));
            }
            // Solid bottom color below the split.
            for (int y = splitY + 1; y <= animBottom; ++y)
                setRow(y, botCol[0], botCol[1], botCol[2]);

        } else {
            // sunset (default): solid top color, then gradient from split down.
            for (int y = animTop; y < splitY; ++y)
                setRow(y, topCol[0], topCol[1], topCol[2]);
            for (int y = splitY; y <= animBottom; ++y) {
                int span = animBottom - splitY;
                float t  = (span > 0) ? float(y - splitY) / span : 1.0f;
                setRow(y,
                    int(topCol[0] + (botCol[0] - topCol[0]) * t),
                    int(topCol[1] + (botCol[1] - topCol[1]) * t),
                    int(topCol[2] + (botCol[2] - topCol[2]) * t));
            }
        }

    } else {
        for (int y = animTop; y <= animBottom; ++y)
            setRow(y, 0, 0, 0);
    }
}

// ── Condition dispatch ────────────────────────────────────────────────────────

void WeatherAnimator::_drawCondition(rgb_matrix::FrameCanvas* canvas) {
    // TODO: per-condition overlays (ICE tint, etc.)
    (void)canvas;
}

// ── Sun ───────────────────────────────────────────────────────────────────────

void WeatherAnimator::_drawSun(rgb_matrix::FrameCanvas* canvas) {
    // Sun disc anchored at top-right corner (ox = width-1, oy = animTop).
    // Matches Python _draw_sun(): radius=12, glow_radius=20.
    auto sunColor = _resolveColor("sun_day", "sun_night");
    int ox = width - 1;
    int oy = animTop;
    constexpr int RADIUS      = 12;
    constexpr int GLOW_RADIUS = 20;

    // Sky color for glow blend — prefer theme solid background, else sky_day.
    std::array<int, 3> sky = {0, 0, 8};
    if (currentTheme && currentTheme->backgroundType == "solid") {
        sky = resolveColor(parseColorValue(nlohmann::json(currentTheme->backgroundColor)));
    } else {
        sky = resolveColor(parseColorValue(
            cfg.value("/colors/sky_day"_json_pointer, nlohmann::json("#000820"))));
    }

    for (int y = oy; y <= oy + GLOW_RADIUS; ++y) {
        for (int x = ox - GLOW_RADIUS; x <= ox; ++x) {
            if (x < 0 || x >= width || y < animTop || y > animBottom) continue;
            float dist = std::sqrt(float((ox - x) * (ox - x) + (y - oy) * (y - oy)));
            if (dist <= RADIUS) {
                canvas->SetPixel(x, y, sunColor[0], sunColor[1], sunColor[2]);
            } else if (dist <= GLOW_RADIUS) {
                float fade = 1.0f - (dist - RADIUS) / (GLOW_RADIUS - RADIUS);
                int r = int(sunColor[0] * fade + sky[0] * (1.0f - fade));
                int g = int(sunColor[1] * fade + sky[1] * (1.0f - fade));
                int b = int(sunColor[2] * fade + sky[2] * (1.0f - fade));
                canvas->SetPixel(x, y, r, g, b);
            }
        }
    }
}

// ── Moon ──────────────────────────────────────────────────────────────────────

void WeatherAnimator::_drawMoon(rgb_matrix::FrameCanvas* canvas) {
    // Moon disc at (3, animTop + 3), radius=3, glow=5.
    // Matches Python _draw_moon().
    int cx = 3, cy = animTop + 3;
    constexpr int RADIUS = 3;
    constexpr int GLOW_R = 5;

    std::array<int, 3> sky = {0, 0, 8};
    if (currentTheme && currentTheme->backgroundType == "solid") {
        sky = resolveColor(parseColorValue(nlohmann::json(currentTheme->backgroundColor)));
    }

    // Glow
    for (int dy = -GLOW_R; dy <= GLOW_R; ++dy) {
        for (int dx = -GLOW_R; dx <= GLOW_R; ++dx) {
            float dist = std::sqrt(float(dx * dx + dy * dy));
            if (dist > RADIUS && dist <= GLOW_R) {
                float fade = 1.0f - (dist - RADIUS) / (GLOW_R - RADIUS);
                int r = int(200 * fade * 0.4f + sky[0] * (1.0f - fade * 0.4f));
                int g = int(200 * fade * 0.4f + sky[1] * (1.0f - fade * 0.4f));
                int b = int(160 * fade * 0.3f + sky[2] * (1.0f - fade * 0.3f));
                int px = cx + dx, py = cy + dy;
                if (px >= 0 && px < width && py >= animTop && py <= animBottom)
                    canvas->SetPixel(px, py, r, g, b);
            }
        }
    }
    // Filled disc with mottled surface
    for (int dy = -RADIUS; dy <= RADIUS; ++dy) {
        for (int dx = -RADIUS; dx <= RADIUS; ++dx) {
            if (dx * dx + dy * dy <= RADIUS * RADIUS) {
                int shade = 180 + ((dx * 13 + dy * 7) % 40) - 20;
                if ((dx == -1 && dy == -1) || (dx == 1 && dy == 1)) shade = 120;
                shade = std::max(80, std::min(220, shade));
                int px = cx + dx, py = cy + dy;
                if (px >= 0 && px < width && py >= animTop && py <= animBottom)
                    canvas->SetPixel(px, py, shade, shade, int(shade * 0.85f));
            }
        }
    }
}

// ── Stars ─────────────────────────────────────────────────────────────────────

void WeatherAnimator::_drawStars(rgb_matrix::FrameCanvas* canvas) {
    if (!currentTheme || !currentTheme->starsEnabled) return;
    // TODO: initialize star field once, animate twinkle phase per-frame.
    // See Python WeatherAnimator._init_stars() + draw() star loop.
    (void)canvas;
}

// ── Color resolver ────────────────────────────────────────────────────────────

std::array<int, 3> WeatherAnimator::_resolveColor(const std::string& dayKey,
                                                   const std::string& nightKey) const {
    const std::string& key = nightMode ? nightKey : dayKey;

    if (currentTheme) {
        auto it = currentTheme->colors.find(key);
        if (it != currentTheme->colors.end()) return resolveColor(it->second);
    }

    auto& colors = cfg["colors"];
    if (colors.contains(key)) return resolveColor(parseColorValue(colors[key]));
    return {240, 240, 240};
}
