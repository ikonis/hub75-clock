#include "Animation.h"
#include "WeatherAnimator.h"

#include <algorithm>
#include <cmath>
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

static std::string airplaneSpritePath(const nlohmann::json& cfg) {
    std::string dir = "/etc/hub75-clock/sprites";
    if (cfg.contains("animations") && cfg["animations"].is_object())
        dir = cfg["animations"].value("sprites_dir", dir);
    return dir + "/airplane.json";
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

static nlohmann::json loadSprite(const nlohmann::json& cfg) {
    const std::string path = airplaneSpritePath(cfg);
    std::ifstream in(path);
    if (!in) throw std::runtime_error("sprite file not found: " + path);
    nlohmann::json data;
    in >> data;
    if (!data.is_object()) throw std::runtime_error("sprite file is not an object: " + path);
    return data;
}

static std::vector<SpritePixel> parsePixels(const nlohmann::json& sprite) {
    std::vector<SpritePixel> pixels;
    if (!sprite.contains("pixels") || !sprite["pixels"].is_array()) return pixels;
    const auto& rows = sprite["pixels"];
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
}

class TestPlaneAnimation : public Animation {
public:
    TestPlaneAnimation(int width, int height, const nlohmann::json& cfg,
                       WeatherAnimator* animator)
        : _w(width), _h(height), _cfg(cfg), _animator(animator)
    {
        static std::mt19937 rng{std::random_device{}()};
        std::uniform_real_distribution<float> rnd01(0.0f, 1.0f);
        std::uniform_int_distribution<int> rndY(5, 11);

        _at = animator->animTop;
        _ab = animator->animBottom;
        _sprite = loadSprite(cfg);
        _pixels = parsePixels(_sprite);
        _sw = _sprite.value("width", 9);
        _sh = _sprite.value("height", 4);

        float speedMult = 0.8f;
        if (cfg.contains("animation_settings") && cfg["animation_settings"].contains("testPlane"))
            speedMult = cfg["animation_settings"]["testPlane"].value("speed", 0.8f);

        _right = (rnd01(rng) < 0.5f);
        _y = float(_at + rndY(rng));
        if (_right) {
            _x = float(-_sw - 1);
            _vx = (0.45f + rnd01(rng) * 0.2f) * speedMult;
        } else {
            _x = float(width + 1);
            _vx = -(0.45f + rnd01(rng) * 0.2f) * speedMult;
        }
    }

    void update() override {
        _x += _vx;
    }

    void draw(rgb_matrix::FrameCanvas* canvas) override {
        int ox = int(std::round(_x));
        int oy = int(std::round(_y)) - 1;
        for (const auto& p : _pixels) {
            int dx = _right ? (_sw - 1 - p.x) : p.x;
            int px = ox + dx;
            int py = oy + p.y;
            if (px < 0 || px >= _w || py < _at - 2 || py > _ab) continue;
            if (p.a >= 255)
                render::SetPixel(canvas, px, py, p.r, p.g, p.b);
            else if (p.a > 0)
                render::BlendPixel(canvas, px, py, p.r, p.g, p.b, float(p.a) / 255.0f);
        }
    }

    bool isDone() const override {
        return _x > float(_w + _sw + 3) || _x < float(-_sw - 3);
    }

    const std::string& name() const override { static std::string n = "testPlane"; return n; }
    const std::string& layer() const override { static std::string l = "foreground"; return l; }
    bool persistent() const override { return false; }

private:
    int _w, _h, _at, _ab, _sw = 9, _sh = 4;
    nlohmann::json _cfg;
    nlohmann::json _sprite;
    WeatherAnimator* _animator;
    std::vector<SpritePixel> _pixels;
    float _x = 0.0f, _y = 0.0f, _vx = 0.0f;
    bool _right = false;
};

extern "C" std::unique_ptr<Animation> create_test_plane(
    int w, int h, const nlohmann::json& cfg, WeatherAnimator* a)
{
    return std::make_unique<TestPlaneAnimation>(w, h, cfg, a);
}
