#include "Animation.h"
#include "WeatherAnimator.h"
#include <nlohmann/json.hpp>
#include <cmath>
#include <random>

class TumbleweedAnimation : public Animation {
public:
    TumbleweedAnimation(int width, int height, const nlohmann::json& cfg,
                        WeatherAnimator* animator)
        : _w(width), _h(height), _cfg(cfg), _animator(animator)
    {
        static std::mt19937 rng{std::random_device{}()};
        std::uniform_real_distribution<float> rnd01(0.0f, 1.0f);

        _at    = animator->animTop;
        _ab    = animator->animBottom;

        float _speedMult = 1.0f;
        if (cfg.contains("animation_settings") && cfg["animation_settings"].contains("tumbleweed"))
            _speedMult = cfg["animation_settings"]["tumbleweed"].value("speed", 1.0f);

        _x     = -6.0f;
        _baseY = float(_ab - 4);
        _roll  = 0.0f;
        _vx    = (0.35f + rnd01(rng) * 0.2f) * _speedMult;
    }

    void update() override {
        _x    += _vx;
        _roll += _vx * 0.4f;
    }

    void draw(rgb_matrix::FrameCanvas* canvas) override {
        // 5-pixel diameter circle offsets
        static const struct { int dx, dy; } CIRCLE[] = {
            {1,0},{2,0},{3,0},
            {0,1},{4,1},
            {0,2},{4,2},
            {1,3},{2,3},{3,3},
            // spokes
            {2,1},{1,2},{3,2},{2,3},
        };

        int ox     = int(std::round(_x));
        int bounce = int(std::round(std::abs(std::sin(_roll)) * 1.5f));
        int oy     = int(_baseY) - bounce;

        for (const auto& p : CIRCLE) {
            float cx = float(p.dx) - 2.0f;
            float cy = float(p.dy) - 2.0f;
            float rx = cx * std::cos(_roll) - cy * std::sin(_roll);
            float ry = cx * std::sin(_roll) + cy * std::cos(_roll);
            int px = ox + 2 + int(std::round(rx));
            int py = oy + 2 + int(std::round(ry));
            if (px >= 0 && px < _w && py >= _at && py <= _ab) {
                int shade = 140 + int(30.0f * std::sin(_roll + float(p.dx)));
                canvas->SetPixel(px, py, shade, int(shade * 0.7f), int(shade * 0.3f));
            }
        }
    }

    bool isDone() const override { return _x > float(_w + 6); }

    const std::string& name()       const override { static std::string n = "tumbleweed"; return n; }
    const std::string& layer()      const override { static std::string l = "foreground"; return l; }
    bool               persistent() const override { return false; }

private:
    int              _w, _h, _at, _ab;
    nlohmann::json   _cfg;
    WeatherAnimator* _animator;
    float _x = 0.0f, _baseY = 0.0f, _roll = 0.0f, _vx = 0.0f;
};

extern "C" std::unique_ptr<Animation> create_tumbleweed(
    int w, int h, const nlohmann::json& cfg, WeatherAnimator* a)
{
    return std::make_unique<TumbleweedAnimation>(w, h, cfg, a);
}
