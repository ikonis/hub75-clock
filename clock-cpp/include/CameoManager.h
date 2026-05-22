#pragma once

#include "Animation.h"
#include <led-matrix.h>
#include <memory>
#include <string>
#include <unordered_map>
#include <vector>

class WeatherAnimator;

// CameoManager owns and schedules all animation plugin instances.
//
// Persistent cameos (clouds) run every frame on a dedicated track.
// Chance-based cameos share a single active slot per layer: one celestial
// cameo (shooting_star, comet, …) and one foreground cameo (firefly,
// butterfly, …) may run concurrently.

class CameoManager {
public:
    // Factory signature: animation plugins register a factory here.
    using Factory = std::function<std::unique_ptr<Animation>(
        int width, int height, const nlohmann::json& cfg,
        WeatherAnimator* animator)>;

    explicit CameoManager(WeatherAnimator* animator);
    ~CameoManager() = default;

    // Register a plugin factory by animation name.
    void registerFactory(const std::string& name, Factory factory);

    // Load all factories from the animations/ plugin directory (called once).
    void loadPlugins();

    // Called when condition or theme changes to rebuild the cameo roster.
    void reset();
    void setupPersistent();

    // Per-frame calls.
    void update();
    void drawBackground(rgb_matrix::FrameCanvas* canvas);
    void drawCelestial(rgb_matrix::FrameCanvas* canvas);
    void drawClouds(rgb_matrix::FrameCanvas* canvas);
    void drawForeground(rgb_matrix::FrameCanvas* canvas);

private:
    WeatherAnimator* _animator;

    std::unordered_map<std::string, Factory> _registry;

    // Persistent (clouds): always running while condition matches.
    std::vector<std::unique_ptr<Animation>> _persistent;

    // Chance-based: one active slot per layer.
    std::unique_ptr<Animation> _activeCelestial;
    std::unique_ptr<Animation> _activeForeground;

    int _framesSinceLastCheck = 0;

    void _trySpawnCelestial();
    void _trySpawnForeground();
    void _drawLayer(rgb_matrix::FrameCanvas* canvas, const std::string& layer);
};
