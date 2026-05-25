#pragma once

#include "Theme.h"
#include <led-matrix.h>
#include <nlohmann/json.hpp>
#include <optional>
#include <string>
#include <vector>

// WeatherAnimator drives all per-condition rendering:
//   • background (sky gradient / solid fill)
//   • condition-specific drawing (sun, moon, stars, ice, etc.)
//   • orchestrates CameoManager for plugin animations
//
// Public fields are deliberately public (matching Python's self.* attributes)
// so animation plugins can read them from the animator reference passed to
// their constructor.

class CameoManager;  // forward-declared; defined in CameoManager.h

class WeatherAnimator {
public:
    WeatherAnimator(int width, int height, const nlohmann::json& cfg,
                    rgb_matrix::RGBMatrix* matrix);
    ~WeatherAnimator();

    // ── Public fields read by animation plugins ───────────────────────────
    int                     width;
    int                     height;
    int                     animTop;     // first pixel row used by animations
    int                     animBottom;  // last  pixel row used by animations
    std::string             condition;   // current weather condition string
    std::optional<Theme>    currentTheme;
    int                     frame     = 0;
    nlohmann::json          cfg;        // full config tree

    // ── Mutators called from MQTT callbacks ───────────────────────────────
    void setCondition(const std::string& cond);
    void setTheme(const std::string& themeName, const ThemeLoader& loader);

    // ── Frame loop ────────────────────────────────────────────────────────
    void update();
    void draw(rgb_matrix::FrameCanvas* canvas);

private:
    rgb_matrix::RGBMatrix* _matrix;
    CameoManager*          _cameos;

    void _drawBackground(rgb_matrix::FrameCanvas* canvas);
    void _drawCondition(rgb_matrix::FrameCanvas* canvas);
    void _drawSun(rgb_matrix::FrameCanvas* canvas);
    void _drawMoon(rgb_matrix::FrameCanvas* canvas);

    std::array<int, 3> _resolveColor(const std::string& key) const;
};
