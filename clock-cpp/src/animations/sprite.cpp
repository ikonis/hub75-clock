#include "Animation.h"
#include "WeatherAnimator.h"

#include <algorithm>
#include <cmath>
#include <filesystem>
#include <fstream>
#include <memory>
#include <nlohmann/json.hpp>
#include <random>
#include <stdexcept>
#include <string>
#include <vector>

namespace {
struct SpritePixel {
    int x, y, r, g, b, a;
};

static int clampByte(int v) {
    return std::max(0, std::min(255, v));
}

static std::string spritePath(const nlohmann::json& cfg, const std::string& requested) {
    std::string dir = "/etc/hub75-clock/sprites";
    if (cfg.contains("animations") && cfg["animations"].is_object())
        dir = cfg["animations"].value("sprites_dir", dir);
    std::string file = requested;
    if (file.size() < 5 || file.substr(file.size() - 5) != ".json") file += ".json";
    return (std::filesystem::path(dir) / file).string();
}

static std::string spritesDir(const nlohmann::json& cfg) {
    std::string dir = "/etc/hub75-clock/sprites";
    if (cfg.contains("animations") && cfg["animations"].is_object())
        dir = cfg["animations"].value("sprites_dir", dir);
    return dir;
}

static std::string randomSpritePath(const nlohmann::json& cfg) {
    static std::mt19937 rng{std::random_device{}()};
    std::vector<std::filesystem::path> choices;
    std::filesystem::path dir = spritesDir(cfg);
    if (std::filesystem::exists(dir)) {
        for (const auto& entry : std::filesystem::directory_iterator(dir)) {
            if (entry.is_regular_file() && entry.path().extension() == ".json")
                choices.push_back(entry.path());
        }
    }
    if (choices.empty())
        throw std::runtime_error("no sprite JSON files found in " + dir.string());
    std::uniform_int_distribution<size_t> pick(0, choices.size() - 1);
    return choices[pick(rng)].string();
}

static nlohmann::json loadSpriteJson(const std::string& path) {
    std::ifstream in(path);
    if (!in) throw std::runtime_error("sprite file not found: " + path);
    nlohmann::json data;
    in >> data;
    if (!data.is_object()) throw std::runtime_error("sprite file is not an object: " + path);
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

static std::vector<SpritePixel> parsePixels(const nlohmann::json& sprite) {
    std::vector<SpritePixel> pixels;
    const nlohmann::json* rows = nullptr;
    if (sprite.contains("frames") && sprite["frames"].is_array() && !sprite["frames"].empty() &&
        sprite["frames"][0].contains("pixels")) {
        rows = &sprite["frames"][0]["pixels"];
    } else if (sprite.contains("pixels")) {
        rows = &sprite["pixels"];
    }
    if (!rows || !rows->is_array()) return pixels;

    for (int y = 0; y < int(rows->size()); ++y) {
        if (!(*rows)[y].is_array()) continue;
        const auto& row = (*rows)[y];
        for (int x = 0; x < int(row.size()); ++x) {
            int r = 0, g = 0, b = 0, a = 0;
            if (parseColor(row[x], r, g, b, a))
                pixels.push_back({x, y, r, g, b, a});
        }
    }
    return pixels;
}

static std::string requestedSpriteName(const nlohmann::json& cfg) {
    if (cfg.contains("_cameo") && cfg["_cameo"].is_object()) {
        const auto& cameo = cfg["_cameo"];
        if (cameo.contains("sprite") && cameo["sprite"].is_string()) return cameo["sprite"].get<std::string>();
        if (cameo.contains("sprite_name") && cameo["sprite_name"].is_string()) return cameo["sprite_name"].get<std::string>();
    }
    return "";
}
}

class SpriteAnimation : public Animation {
public:
    SpriteAnimation(int width, int height, const nlohmann::json& cfg,
                    WeatherAnimator* animator)
        : _w(width), _h(height), _cfg(cfg), _animator(animator)
    {
        static std::mt19937 rng{std::random_device{}()};
        _at = animator->animTop;
        _ab = animator->animBottom;

        std::string requested = requestedSpriteName(cfg);
        _sprite = loadSpriteJson(requested.empty() ? randomSpritePath(cfg) : spritePath(cfg, requested));
        _pixels = parsePixels(_sprite);
        _sw = _sprite.value("width", 1);
        _sh = _sprite.value("height", 1);
        _motion = _sprite.value("motion", std::string("left"));
        _speed = _sprite.value("speed", 1.0f);

        float speedMult = 1.0f;
        if (cfg.contains("animation_settings") && cfg["animation_settings"].contains("sprite"))
            speedMult = cfg["animation_settings"]["sprite"].value("speed", 1.0f);
        _speed *= speedMult;

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
        _x += _vx;
        _y += _vy;
    }

    void draw(rgb_matrix::FrameCanvas* canvas) override {
        int ox = int(std::round(_x));
        int oy = int(std::round(_y));
        for (const auto& p : _pixels) {
            int px = ox + p.x;
            int py = oy + p.y;
            if (px < 0 || px >= _w || py < _at || py > _ab) continue;
            if (p.a >= 255)
                render::SetPixel(canvas, px, py, p.r, p.g, p.b);
            else if (p.a > 0)
                render::BlendPixel(canvas, px, py, p.r, p.g, p.b, float(p.a) / 255.0f);
        }
    }

    bool isDone() const override {
        return _x > float(_w + _sw + 2) || _x < float(-_sw - 2) ||
               _y < float(_at - _sh - 2) || _y > float(_ab + _sh + 2);
    }

    const std::string& name() const override { static std::string n = "sprite"; return n; }
    const std::string& layer() const override { static std::string l = "foreground"; return l; }
    bool persistent() const override { return false; }

protected:
    int _w, _h, _at, _ab, _sw = 1, _sh = 1;
    nlohmann::json _cfg;
    nlohmann::json _sprite;
    WeatherAnimator* _animator;
    std::vector<SpritePixel> _pixels;
    std::string _motion;
    float _x = 0.0f, _y = 0.0f, _vx = 0.0f, _vy = 0.0f, _speed = 1.0f;
};

extern "C" std::unique_ptr<Animation> create_sprite(
    int w, int h, const nlohmann::json& cfg, WeatherAnimator* a)
{
    return std::make_unique<SpriteAnimation>(w, h, cfg, a);
}
