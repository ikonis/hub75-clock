#include "CameoManager.h"
#include "WeatherAnimator.h"
#include <iostream>

CameoManager::CameoManager(WeatherAnimator* animator)
    : _animator(animator) {}

void CameoManager::registerFactory(const std::string& name, Factory factory) {
    _registry[name] = std::move(factory);
}

void CameoManager::loadPlugins() {
    // TODO: dynamically load animation shared-libraries from an animations/
    // directory, calling dlopen() + dlsym("createAnimation") for each .so.
    // For now, factories must be registered manually or statically linked.
}

void CameoManager::reset() {
    _persistent.clear();
    _activeCelestial.reset();
    _activeForeground.reset();
    _framesSinceLastCheck = 0;
}

void CameoManager::setupPersistent() {
    if (!_animator->currentTheme) return;

    for (const auto& entry : _animator->currentTheme->cameos) {
        if (entry.chancePerMinute == 0) {
            // chancePerMinute == 0 → treat as persistent (always-on).
            auto it = _registry.find(entry.name);
            if (it == _registry.end()) {
                std::cerr << "[cameo] Unknown animation: " << entry.name << "\n";
                continue;
            }
            _persistent.push_back(it->second(
                _animator->width, _animator->height,
                _animator->cfg, _animator));
        }
    }
}

void CameoManager::update() {
    for (auto& anim : _persistent) anim->update();

    ++_framesSinceLastCheck;

    if (_activeCelestial) {
        _activeCelestial->update();
        if (_activeCelestial->isDone()) _activeCelestial.reset();
    } else {
        _trySpawnCelestial();
    }

    if (_activeForeground) {
        _activeForeground->update();
        if (_activeForeground->isDone()) _activeForeground.reset();
    } else {
        _trySpawnForeground();
    }
}

void CameoManager::_trySpawnCelestial() {
    if (!_animator->currentTheme) return;
    int fps = _animator->cfg["animation"].value("fps", 15);

    for (const auto& entry : _animator->currentTheme->cameos) {
        if (entry.chancePerMinute <= 0) continue;
        auto it = _registry.find(entry.name);
        if (it == _registry.end()) continue;

        // Stub: build the animation to check its layer.
        // In the real impl, register layer info separately to avoid constructing.
        auto anim = it->second(_animator->width, _animator->height,
                                _animator->cfg, _animator);
        if (anim->layer() != "celestial") continue;

        // chancePerMinute / (60 * fps) = probability per frame.
        float prob = static_cast<float>(entry.chancePerMinute) / (60.0f * fps);
        if (static_cast<float>(rand()) / RAND_MAX < prob) {
            _activeCelestial = std::move(anim);
            return;
        }
    }
}

void CameoManager::_trySpawnForeground() {
    if (!_animator->currentTheme) return;
    int fps = _animator->cfg["animation"].value("fps", 15);

    for (const auto& entry : _animator->currentTheme->cameos) {
        if (entry.chancePerMinute <= 0) continue;
        auto it = _registry.find(entry.name);
        if (it == _registry.end()) continue;

        auto anim = it->second(_animator->width, _animator->height,
                                _animator->cfg, _animator);
        if (anim->layer() != "foreground") continue;

        float prob = static_cast<float>(entry.chancePerMinute) / (60.0f * fps);
        if (static_cast<float>(rand()) / RAND_MAX < prob) {
            _activeForeground = std::move(anim);
            return;
        }
    }
}

void CameoManager::drawBackground(rgb_matrix::FrameCanvas* canvas) {
    _drawLayer(canvas, "background");
}

void CameoManager::drawCelestial(rgb_matrix::FrameCanvas* canvas) {
    _drawLayer(canvas, "celestial");
    if (_activeCelestial && _activeCelestial->layer() == "celestial")
        _activeCelestial->draw(canvas);
}

void CameoManager::drawClouds(rgb_matrix::FrameCanvas* canvas) {
    for (auto& anim : _persistent) {
        if (anim->layer() == "foreground") anim->draw(canvas);
    }
}

void CameoManager::drawForeground(rgb_matrix::FrameCanvas* canvas) {
    if (_activeForeground && _activeForeground->layer() == "foreground")
        _activeForeground->draw(canvas);
}

void CameoManager::_drawLayer(rgb_matrix::FrameCanvas* canvas, const std::string& layer) {
    for (auto& anim : _persistent) {
        if (anim->layer() == layer) anim->draw(canvas);
    }
}
