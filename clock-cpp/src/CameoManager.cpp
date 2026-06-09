#include "CameoManager.h"
#include "WeatherAnimator.h"
#include <algorithm>
#include <cstdlib>
#include <iostream>
#include <memory>
#include <nlohmann/json.hpp>

// Forward-declare every statically-linked animation factory.
extern "C" std::unique_ptr<Animation> create_airplane(int, int, const nlohmann::json&, WeatherAnimator*);
extern "C" std::unique_ptr<Animation> create_bird_flock(int, int, const nlohmann::json&, WeatherAnimator*);
extern "C" std::unique_ptr<Animation> create_butterfly(int, int, const nlohmann::json&, WeatherAnimator*);
extern "C" std::unique_ptr<Animation> create_clouds(int, int, const nlohmann::json&, WeatherAnimator*);
extern "C" std::unique_ptr<Animation> create_comet(int, int, const nlohmann::json&, WeatherAnimator*);
extern "C" std::unique_ptr<Animation> create_easter_egg(int, int, const nlohmann::json&, WeatherAnimator*);
extern "C" std::unique_ptr<Animation> create_firefly(int, int, const nlohmann::json&, WeatherAnimator*);
extern "C" std::unique_ptr<Animation> create_fireworks(int, int, const nlohmann::json&, WeatherAnimator*);
extern "C" std::unique_ptr<Animation> create_flutterflies(int, int, const nlohmann::json&, WeatherAnimator*);
extern "C" std::unique_ptr<Animation> create_ghost(int, int, const nlohmann::json&, WeatherAnimator*);
extern "C" std::unique_ptr<Animation> create_hot_air_balloon(int, int, const nlohmann::json&, WeatherAnimator*);
extern "C" std::unique_ptr<Animation> create_jack_o_lantern(int, int, const nlohmann::json&, WeatherAnimator*);
extern "C" std::unique_ptr<Animation> create_meteor(int, int, const nlohmann::json&, WeatherAnimator*);
extern "C" std::unique_ptr<Animation> create_rainbow(int, int, const nlohmann::json&, WeatherAnimator*);
extern "C" std::unique_ptr<Animation> create_rocket(int, int, const nlohmann::json&, WeatherAnimator*);
extern "C" std::unique_ptr<Animation> create_santa(int, int, const nlohmann::json&, WeatherAnimator*);
extern "C" std::unique_ptr<Animation> create_satellite(int, int, const nlohmann::json&, WeatherAnimator*);
extern "C" std::unique_ptr<Animation> create_shooting_star(int, int, const nlohmann::json&, WeatherAnimator*);
extern "C" std::unique_ptr<Animation> create_snowman(int, int, const nlohmann::json&, WeatherAnimator*);
extern "C" std::unique_ptr<Animation> create_snake(int, int, const nlohmann::json&, WeatherAnimator*);
extern "C" std::unique_ptr<Animation> create_sprite(int, int, const nlohmann::json&, WeatherAnimator*);
extern "C" std::unique_ptr<Animation> create_stars(int, int, const nlohmann::json&, WeatherAnimator*);
extern "C" std::unique_ptr<Animation> create_submarine(int, int, const nlohmann::json&, WeatherAnimator*);
extern "C" std::unique_ptr<Animation> create_test_plane(int, int, const nlohmann::json&, WeatherAnimator*);
extern "C" std::unique_ptr<Animation> create_tumbleweed(int, int, const nlohmann::json&, WeatherAnimator*);
extern "C" std::unique_ptr<Animation> create_ufo(int, int, const nlohmann::json&, WeatherAnimator*);

namespace {
nlohmann::json cfgForCameo(const nlohmann::json& cfg, const CameoEntry& cameo) {
    nlohmann::json out = cfg;
    out["_cameo"] = cameo.raw.is_object() ? cameo.raw : nlohmann::json::object({{"name", cameo.name}});
    return out;
}
}

CameoManager::CameoManager(WeatherAnimator* animator)
    : _animator(animator) {}

void CameoManager::registerFactory(const std::string& name, Factory factory) {
    _registry[name] = std::move(factory);
}

void CameoManager::_registerAnimation(const std::string& name, const std::string& layer,
                                      bool persistent, Factory factory) {
    _registry[name] = factory;
    _info[name] = AnimationInfo{std::move(factory), layer, persistent};
}

void CameoManager::loadPlugins() {
    // Register all statically-linked animation factories by name.
    // Each entry maps the animation name string (matching theme JSON cameo names)
    // to the corresponding extern "C" factory function.
    struct Entry { const char* name; const char* layer; bool persistent; Factory fn; };
    Entry entries[] = {
        { "airplane",        "foreground", false, create_airplane        },
        { "bird_flock",      "foreground", false, create_bird_flock      },
        { "butterfly",       "foreground", false, create_butterfly       },
        { "clouds",          "foreground", true,  create_clouds          },
        { "comet",           "celestial",  false, create_comet           },
        { "easter_egg",      "foreground", false, create_easter_egg      },
        { "firefly",         "foreground", true,  create_firefly         },
        { "fireworks",       "foreground", false, create_fireworks       },
        { "flutterflies",    "foreground", true,  create_flutterflies    },
        { "ghost",           "foreground", false, create_ghost           },
        { "hot_air_balloon", "foreground", false, create_hot_air_balloon },
        { "jack_o_lantern",  "foreground", false, create_jack_o_lantern  },
        { "meteor",          "celestial",  false, create_meteor          },
        { "rainbow",         "foreground", false, create_rainbow         },
        { "rocket",          "foreground", false, create_rocket          },
        { "santa",           "foreground", false, create_santa           },
        { "satellite",       "celestial",  false, create_satellite       },
        { "shooting_star",   "celestial",  false, create_shooting_star   },
        { "snowman",         "foreground", false, create_snowman         },
        { "snake",           "foreground", true,  create_snake           },
        { "sprite",          "foreground", false, create_sprite          },
        { "stars",           "celestial",  true,  create_stars           },
        { "submarine",       "foreground", false, create_submarine       },
        { "testPlane",       "foreground", false, create_test_plane      },
        { "tumbleweed",      "foreground", false, create_tumbleweed      },
        { "ufo",             "foreground", false, create_ufo             },
    };
    for (auto& e : entries)
        _registerAnimation(e.name, e.layer, e.persistent, e.fn);
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
        auto it = _info.find(entry.name);
        if (it == _info.end()) {
            std::cerr << "[cameo] Unknown animation: " << entry.name << "\n";
            continue;
        }
        if (!it->second.persistent) continue;
        nlohmann::json cameoCfg = cfgForCameo(_animator->cfg, entry);
        _persistent.push_back(it->second.factory(
            _animator->width, _animator->height,
            cameoCfg, _animator));
    }
}

void CameoManager::update() {
    for (auto it = _persistent.begin(); it != _persistent.end();) {
        try {
            (*it)->update();
            ++it;
        } catch (const std::exception& e) {
            std::cerr << "[cameo] Persistent update failed for "
                      << ((*it) ? (*it)->name() : std::string("<null>"))
                      << ": " << e.what() << "\n";
            it = _persistent.erase(it);
        } catch (...) {
            std::cerr << "[cameo] Persistent update failed with unknown exception\n";
            it = _persistent.erase(it);
        }
    }

    ++_framesSinceLastCheck;

    if (_activeCelestial) {
        try {
            _activeCelestial->update();
            if (_activeCelestial->isDone()) _activeCelestial.reset();
        } catch (const std::exception& e) {
            std::cerr << "[cameo] Active celestial failed: " << e.what() << "\n";
            _activeCelestial.reset();
        } catch (...) {
            std::cerr << "[cameo] Active celestial failed with unknown exception\n";
            _activeCelestial.reset();
        }
    } else {
        _trySpawnCelestial();
    }

    if (_activeForeground) {
        try {
            _activeForeground->update();
            if (_activeForeground->isDone()) _activeForeground.reset();
        } catch (const std::exception& e) {
            std::cerr << "[cameo] Active foreground failed: " << e.what() << "\n";
            _activeForeground.reset();
        } catch (...) {
            std::cerr << "[cameo] Active foreground failed with unknown exception\n";
            _activeForeground.reset();
        }
    } else {
        _trySpawnForeground();
    }
}

void CameoManager::_trySpawnCelestial() {
    if (!_animator->currentTheme) return;
    int fps = std::max(1, _animator->cfg["animation"].value("fps", 15));

    for (const auto& entry : _animator->currentTheme->cameos) {
        if (entry.chancePerMinute <= 0) continue;
        auto it = _info.find(entry.name);
        if (it == _info.end() || it->second.layer != "celestial" || it->second.persistent) continue;

        // chancePerMinute / (60 * fps) = probability per frame.
        float prob = static_cast<float>(entry.chancePerMinute) / (60.0f * fps);
        if (static_cast<float>(rand()) / RAND_MAX < prob) {
            nlohmann::json cameoCfg = cfgForCameo(_animator->cfg, entry);
            _activeCelestial = it->second.factory(_animator->width, _animator->height,
                                                  cameoCfg, _animator);
            return;
        }
    }
}

void CameoManager::_trySpawnForeground() {
    if (!_animator->currentTheme) return;
    int fps = std::max(1, _animator->cfg["animation"].value("fps", 15));

    for (const auto& entry : _animator->currentTheme->cameos) {
        if (entry.chancePerMinute <= 0) continue;
        auto it = _info.find(entry.name);
        if (it == _info.end() || it->second.layer != "foreground" || it->second.persistent) continue;

        float prob = static_cast<float>(entry.chancePerMinute) / (60.0f * fps);
        if (static_cast<float>(rand()) / RAND_MAX < prob) {
            nlohmann::json cameoCfg = cfgForCameo(_animator->cfg, entry);
            _activeForeground = it->second.factory(_animator->width, _animator->height,
                                                   cameoCfg, _animator);
            return;
        }
    }
}

void CameoManager::drawBackground(rgb_matrix::FrameCanvas* canvas) {
    _drawLayer(canvas, "background");
}

void CameoManager::drawCelestial(rgb_matrix::FrameCanvas* canvas) {
    _drawLayer(canvas, "celestial");
    if (_activeCelestial && _activeCelestial->layer() == "celestial") {
        try {
            _activeCelestial->draw(canvas);
        } catch (const std::exception& e) {
            std::cerr << "[cameo] Active celestial draw failed: " << e.what() << "\n";
            _activeCelestial.reset();
        } catch (...) {
            std::cerr << "[cameo] Active celestial draw failed with unknown exception\n";
            _activeCelestial.reset();
        }
    }
}

void CameoManager::drawClouds(rgb_matrix::FrameCanvas* canvas) {
    _drawLayer(canvas, "foreground");
}

void CameoManager::drawForeground(rgb_matrix::FrameCanvas* canvas) {
    if (_activeForeground && _activeForeground->layer() == "foreground") {
        try {
            _activeForeground->draw(canvas);
        } catch (const std::exception& e) {
            std::cerr << "[cameo] Active foreground draw failed: " << e.what() << "\n";
            _activeForeground.reset();
        } catch (...) {
            std::cerr << "[cameo] Active foreground draw failed with unknown exception\n";
            _activeForeground.reset();
        }
    }
}

void CameoManager::_drawLayer(rgb_matrix::FrameCanvas* canvas, const std::string& layer) {
    for (auto it = _persistent.begin(); it != _persistent.end();) {
        if ((*it)->layer() != layer) {
            ++it;
            continue;
        }
        try {
            (*it)->draw(canvas);
            ++it;
        } catch (const std::exception& e) {
            std::cerr << "[cameo] Persistent draw failed for "
                      << ((*it) ? (*it)->name() : std::string("<null>"))
                      << ": " << e.what() << "\n";
            it = _persistent.erase(it);
        } catch (...) {
            std::cerr << "[cameo] Persistent draw failed with unknown exception\n";
            it = _persistent.erase(it);
        }
    }
}
