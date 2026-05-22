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
    _drawCondition(canvas);
    _cameos->drawCelestial(canvas);
    _cameos->drawClouds(canvas);
    _cameos->drawForeground(canvas);
}

// ── Private helpers ──────────────────────────────────────────────────────────

void WeatherAnimator::_drawBackground(rgb_matrix::FrameCanvas* canvas) {
    // TODO: implement solid / gradient / split background rendering.
    // Reads currentTheme->backgroundType, backgroundColor, backgroundTop,
    // backgroundBottom, backgroundSplit, backgroundGradientDirection.
    (void)canvas;
}

void WeatherAnimator::_drawCondition(rgb_matrix::FrameCanvas* canvas) {
    // TODO: dispatch per-condition drawing (ICE, rain, snow, etc.).
    (void)canvas;
}

void WeatherAnimator::_drawSun(rgb_matrix::FrameCanvas* canvas) {
    // TODO: draw sun disc + glow at top-right corner.
    // Reads currentTheme->colors["sun_day"] or cfg["colors"]["sun_day"].
    // Blends with sky gradient color near the disc edge.
    (void)canvas;
}

void WeatherAnimator::_drawMoon(rgb_matrix::FrameCanvas* canvas) {
    // TODO: draw moon crescent.
    (void)canvas;
}

void WeatherAnimator::_drawStars(rgb_matrix::FrameCanvas* canvas) {
    // TODO: draw static star field when starsEnabled.
    (void)canvas;
}

std::array<int, 3> WeatherAnimator::_resolveColor(const std::string& dayKey,
                                                   const std::string& nightKey) const {
    const std::string& key = nightMode ? nightKey : dayKey;

    // Check theme color overrides first.
    if (currentTheme) {
        auto it = currentTheme->colors.find(key);
        if (it != currentTheme->colors.end()) {
            return resolveColor(it->second);
        }
    }

    // Fall back to cfg["colors"].
    auto& colors = cfg["colors"];
    if (colors.contains(key)) {
        return resolveColor(parseColorValue(colors[key]));
    }
    return {240, 240, 240};
}
