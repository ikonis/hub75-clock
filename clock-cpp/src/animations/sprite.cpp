#include "Animation.h"
#include "WeatherAnimator.h"

#include <algorithm>
#include <cmath>
#include <filesystem>
#include <fstream>
#include <map>
#include <memory>
#include <nlohmann/json.hpp>
#include <random>
#include <stdexcept>
#include <string>
#include <vector>

namespace {
struct SpritePixel { int x, y, r, g, b, a; };
struct LoadedSprite {
    int width = 1;
    int height = 1;
    std::vector<std::vector<SpritePixel>> frames;
};
struct SpriteItem {
    std::string sprite;
    int x = 0;
    int y = 0;
    int frame = -1;
};
struct MotionFrame {
    int durationMs = 100;
    std::vector<SpriteItem> sprites;
};

static int clampByte(int v) {
    return std::max(0, std::min(255, v));
}

static std::filesystem::path jsonPath(const nlohmann::json& cfg,
                                      const std::string& dirKey,
                                      const std::string& defaultDir,
                                      std::string requested) {
    std::string dir = defaultDir;
    if (cfg.contains("animations") && cfg["animations"].is_object())
        dir = cfg["animations"].value(dirKey, dir);
    if (requested.size() < 5 || requested.substr(requested.size() - 5) != ".json") requested += ".json";
    return std::filesystem::path(dir) / requested;
}

static std::string spritesDir(const nlohmann::json& cfg) {
    std::string dir = "/etc/hub75-clock/sprites";
    if (cfg.contains("animations") && cfg["animations"].is_object())
        dir = cfg["animations"].value("sprites_dir", dir);
    return dir;
}

static std::filesystem::path randomSpritePath(const nlohmann::json& cfg) {
    static std::mt19937 rng{std::random_device{}()};
    std::vector<std::filesystem::path> choices;
    std::filesystem::path dir = spritesDir(cfg);
    if (std::filesystem::exists(dir)) {
        for (const auto& entry : std::filesystem::directory_iterator(dir)) {
            if (entry.is_regular_file() && entry.path().extension() == ".json")
                choices.push_back(entry.path());
        }
    }
    if (choices.empty()) throw std::runtime_error("no sprite JSON files found in " + dir.string());
    std::uniform_int_distribution<size_t> pick(0, choices.size() - 1);
    return choices[pick(rng)];
}

static nlohmann::json loadJson(const std::filesystem::path& path, const std::string& label) {
    std::ifstream in(path);
    if (!in) throw std::runtime_error(label + " file not found: " + path.string());
    nlohmann::json data;
    in >> data;
    if (!data.is_object()) throw std::runtime_error(label + " file is not an object: " + path.string());
    return data;
}

static bool parseColor(const nlohmann::json& value, int& r, int& g, int& b, int& a) {
    if (value.is_null()) return false;
    if (value.is_string()) {
        std::string h = value.get<std::string>();
        if (!h.empty() && h[0] == '#') h.erase(h.begin());
        if (h.size() != 6 && h.size() != 8) return false;
        try {
            r = std::stoi(h.substr(0, 2), nullptr, 16);
            g = std::stoi(h.substr(2, 2), nullptr, 16);
            b = std::stoi(h.substr(4, 2), nullptr, 16);
            a = h.size() == 8 ? std::stoi(h.substr(6, 2), nullptr, 16) : 255;
            return true;
        } catch (...) {
            return false;
        }
    }
    if (value.is_array() && (value.size() == 3 || value.size() == 4)) {
        r = clampByte(value[0].get<int>());
        g = clampByte(value[1].get<int>());
        b = clampByte(value[2].get<int>());
        a = value.size() == 4 ? clampByte(value[3].get<int>()) : 255;
        return true;
    }
    return false;
}

static std::vector<SpritePixel> parseRows(const nlohmann::json& rows) {
    std::vector<SpritePixel> pixels;
    if (!rows.is_array()) return pixels;
    for (int y = 0; y < int(rows.size()); ++y) {
        if (!rows[y].is_array()) continue;
        for (int x = 0; x < int(rows[y].size()); ++x) {
            int r = 0, g = 0, b = 0, a = 0;
            if (parseColor(rows[y][x], r, g, b, a))
                pixels.push_back({x, y, r, g, b, a});
        }
    }
    return pixels;
}

static LoadedSprite parseSprite(const nlohmann::json& sprite) {
    LoadedSprite out;
    out.width = sprite.value("width", 1);
    out.height = sprite.value("height", 1);
    if (sprite.contains("frames") && sprite["frames"].is_array() && !sprite["frames"].empty()) {
        for (const auto& frame : sprite["frames"]) {
            out.frames.push_back(parseRows(frame.value("pixels", nlohmann::json::array())));
        }
    }
    if (out.frames.empty()) {
        out.frames.push_back(parseRows(sprite.value("pixels", nlohmann::json::array())));
    }
    return out;
}

static std::string requestedSpriteName(const nlohmann::json& cfg) {
    if (cfg.contains("_cameo") && cfg["_cameo"].is_object()) {
        const auto& cameo = cfg["_cameo"];
        if (cameo.contains("sprite") && cameo["sprite"].is_string()) return cameo["sprite"].get<std::string>();
        if (cameo.contains("sprite_name") && cameo["sprite_name"].is_string()) return cameo["sprite_name"].get<std::string>();
    }
    return "";
}

static std::string requestedAnimationName(const nlohmann::json& cfg) {
    if (cfg.contains("_cameo") && cfg["_cameo"].is_object()) {
        const auto& cameo = cfg["_cameo"];
        if (cameo.contains("animation") && cameo["animation"].is_string()) return cameo["animation"].get<std::string>();
        if (cameo.contains("sprite_animation") && cameo["sprite_animation"].is_string()) return cameo["sprite_animation"].get<std::string>();
    }
    return "";
}
}

class SpriteAnimation : public Animation {
public:
    SpriteAnimation(int width, int height, const nlohmann::json& cfg,
                    WeatherAnimator* animator)
        : _w(width), _h(height), _cfg(cfg), _animator(animator) {
        static std::mt19937 rng{std::random_device{}()};
        _at = animator->animTop;
        _ab = animator->animBottom;
        if (cfg.contains("animation") && cfg["animation"].is_object())
            _fps = std::max(1, cfg["animation"].value("fps", 15));

        float speedMult = 1.0f;
        if (cfg.contains("animation_settings") && cfg["animation_settings"].contains("sprite"))
            speedMult = cfg["animation_settings"]["sprite"].value("speed", 1.0f);

        std::string requestedAnimation = requestedAnimationName(cfg);
        if (!requestedAnimation.empty()) {
            _useTimeline = true;
            _timeline = loadJson(jsonPath(cfg, "sprite_animations_dir", "/etc/hub75-clock/sprite-animations",
                                          requestedAnimation), "sprite animation");
            _speed = _timeline.value("speed", 1.0f) * speedMult;
            _loop = _timeline.value("loop", false);
            if (cfg.contains("_cameo") && cfg["_cameo"].is_object())
                _loop = cfg["_cameo"].value("loop", _loop);
            parseTimeline();
            return;
        }

        std::string requested = requestedSpriteName(cfg);
        nlohmann::json spriteJson = loadJson(requested.empty()
            ? randomSpritePath(cfg)
            : jsonPath(cfg, "sprites_dir", "/etc/hub75-clock/sprites", requested), "sprite");
        _single = parseSprite(spriteJson);
        _sw = _single.width;
        _sh = _single.height;
        _motion = spriteJson.value("motion", std::string("left"));
        _speed = spriteJson.value("speed", 1.0f) * speedMult;

        std::uniform_int_distribution<int> rndX(2, std::max(2, _w - _sw - 2));
        std::uniform_int_distribution<int> rndY(2, std::max(2, _ab - _at - _sh));
        if (_motion == "right") {
            _x = float(-_sw - 1);
            _y = float(_at + rndY(rng));
            _vx = std::max(0.1f, _speed);
        } else if (_motion == "up") {
            _x = float(rndX(rng));
            _y = float(_ab + 1);
            _vy = -std::max(0.1f, _speed);
        } else {
            _x = float(_w + 1);
            _y = float(_at + rndY(rng));
            _vx = -std::max(0.1f, _speed);
        }
    }

    void update() override {
        if (_useTimeline) {
            if (_done || _frames.empty()) return;
            int ticks = std::max(1, int(std::round(_frames[_frameIndex].durationMs /
                (1000.0f / float(_fps)) / std::max(0.05f, _speed))));
            if (++_frameTick >= ticks) {
                _frameTick = 0;
                ++_frameIndex;
                if (_frameIndex >= int(_frames.size())) {
                    if (_loop) _frameIndex = 0;
                    else _done = true;
                }
            }
            return;
        }
        _x += _vx;
        _y += _vy;
    }

    void draw(rgb_matrix::FrameCanvas* canvas) override {
        if (_useTimeline) {
            if (_done || _frames.empty()) return;
            for (const auto& item : _frames[_frameIndex].sprites) {
                const LoadedSprite& sprite = loadSprite(item.sprite);
                int frame = item.frame >= 0 ? item.frame : _frameIndex;
                const auto& pixels = sprite.frames[frame % sprite.frames.size()];
                drawPixels(canvas, item.x, _at + item.y, pixels);
            }
            return;
        }
        drawPixels(canvas, int(std::round(_x)), int(std::round(_y)), _single.frames[0]);
    }

    bool isDone() const override {
        if (_useTimeline) return _done;
        return _x > float(_w + _sw + 2) || _x < float(-_sw - 2) ||
               _y < float(_at - _sh - 2) || _y > float(_ab + _sh + 2);
    }

    const std::string& name() const override { static std::string n = "sprite"; return n; }
    const std::string& layer() const override { static std::string l = "foreground"; return l; }
    bool persistent() const override { return false; }

private:
    int _w, _h, _at, _ab, _sw = 1, _sh = 1, _fps = 15;
    nlohmann::json _cfg;
    nlohmann::json _timeline;
    WeatherAnimator* _animator;
    LoadedSprite _single;
    std::map<std::string, LoadedSprite> _spriteCache;
    std::vector<MotionFrame> _frames;
    std::string _motion;
    float _x = 0.0f, _y = 0.0f, _vx = 0.0f, _vy = 0.0f, _speed = 1.0f;
    bool _useTimeline = false, _loop = false, _done = false;
    int _frameIndex = 0, _frameTick = 0;

    const LoadedSprite& loadSprite(const std::string& name) {
        auto key = name;
        if (key.size() >= 5 && key.substr(key.size() - 5) == ".json") key = key.substr(0, key.size() - 5);
        auto it = _spriteCache.find(key);
        if (it == _spriteCache.end()) {
            auto data = loadJson(jsonPath(_cfg, "sprites_dir", "/etc/hub75-clock/sprites", key), "sprite");
            it = _spriteCache.emplace(key, parseSprite(data)).first;
        }
        return it->second;
    }

    void parseTimeline() {
        if (!_timeline.contains("frames") || !_timeline["frames"].is_array()) return;
        for (const auto& frameJson : _timeline["frames"]) {
            MotionFrame frame;
            frame.durationMs = frameJson.value("duration_ms", 100);
            if (frameJson.contains("sprites") && frameJson["sprites"].is_array()) {
                for (const auto& itemJson : frameJson["sprites"]) {
                    SpriteItem item;
                    item.sprite = itemJson.value("sprite", std::string(""));
                    item.x = itemJson.value("x", 0);
                    item.y = itemJson.value("y", 0);
                    item.frame = itemJson.value("frame", -1);
                    if (!item.sprite.empty()) frame.sprites.push_back(std::move(item));
                }
            }
            _frames.push_back(std::move(frame));
        }
    }

    void drawPixels(rgb_matrix::FrameCanvas* canvas, int ox, int oy,
                    const std::vector<SpritePixel>& pixels) const {
        for (const auto& p : pixels) {
            int px = ox + p.x;
            int py = oy + p.y;
            if (px < 0 || px >= _w || py < _at || py > _ab) continue;
            if (p.a >= 255)
                render::SetPixel(canvas, px, py, p.r, p.g, p.b);
            else if (p.a > 0)
                render::BlendPixel(canvas, px, py, p.r, p.g, p.b, float(p.a) / 255.0f);
        }
    }
};

extern "C" std::unique_ptr<Animation> create_sprite(
    int w, int h, const nlohmann::json& cfg, WeatherAnimator* a) {
    return std::make_unique<SpriteAnimation>(w, h, cfg, a);
}
