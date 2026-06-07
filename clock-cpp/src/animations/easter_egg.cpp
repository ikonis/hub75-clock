#include "Animation.h"
#include "WeatherAnimator.h"
#include <nlohmann/json.hpp>
#include <cmath>
#include <random>

class EasterEggAnimation : public Animation {
public:
    EasterEggAnimation(int width, int height, const nlohmann::json& cfg,
                       WeatherAnimator* animator)
        : _w(width), _h(height), _cfg(cfg), _animator(animator)
    {
        static std::mt19937 rng{std::random_device{}()};
        std::uniform_real_distribution<float> rnd01(0.0f, 1.0f);

        _at     = animator->animTop;
        _ab     = animator->animBottom;

        float _speedMult = 1.0f;
        if (cfg.contains("animation_settings") && cfg["animation_settings"].contains("easter_egg"))
            _speedMult = cfg["animation_settings"]["easter_egg"].value("speed", 1.0f);

        _x      = -8.0f;
        _baseY  = float(_ab - 8);
        _vx     = (0.3f + rnd01(rng) * 0.15f) * _speedMult;
        _bounce = 0.0f;
    }

    void update() override {
        _x      += _vx;
        _bounce += _vx * 0.5f;
    }

    void draw(rgb_matrix::FrameCanvas* canvas) override {
        // Stripe pattern: (dx, dy, color_index)
        static const struct SPixel { int dx, dy, ci; } STRIPES[] = {
            {1,0,0},{2,0,0},{3,0,0},{4,0,0},
            {0,1,1},{1,1,0},{2,1,1},{3,1,0},{4,1,1},{5,1,1},
            {0,2,2},{1,2,1},{2,2,2},{3,2,1},{4,2,2},{5,2,2},
            {0,3,3},{1,3,2},{2,3,3},{3,3,2},{4,3,3},{5,3,3},
            {0,4,0},{1,4,3},{2,4,0},{3,4,3},{4,4,0},{5,4,0},
            {0,5,1},{1,5,0},{2,5,1},{3,5,0},{4,5,1},{5,5,1},
            {1,6,2},{2,6,1},{3,6,2},{4,6,1},
            {2,7,3},{3,7,2},
        };
        static const int PAL[4][3] = {
            {255,  80, 120},  // pink
            {255, 200,   0},  // yellow
            {100, 200, 255},  // sky blue
            {160, 255, 120},  // mint green
        };

        int ox = int(std::round(_x));
        int oy = int(_baseY - std::abs(std::sin(_bounce)) * 2.0f);

        for (const auto& p : STRIPES) {
            int px = ox + p.dx, py = oy + p.dy;
            if (px >= 0 && px < _w && py >= _at && py <= _ab)
                render::SetPixel(canvas, px, py, PAL[p.ci][0], PAL[p.ci][1], PAL[p.ci][2]);
        }
    }

    bool isDone() const override { return _x > float(_w + 8); }

    const std::string& name()       const override { static std::string n = "easter_egg"; return n; }
    const std::string& layer()      const override { static std::string l = "foreground"; return l; }
    bool               persistent() const override { return false; }

private:
    int              _w, _h, _at, _ab;
    nlohmann::json   _cfg;
    WeatherAnimator* _animator;
    float _x = 0.0f, _baseY = 0.0f, _vx = 0.0f, _bounce = 0.0f;
};

extern "C" std::unique_ptr<Animation> create_easter_egg(
    int w, int h, const nlohmann::json& cfg, WeatherAnimator* a)
{
    return std::make_unique<EasterEggAnimation>(w, h, cfg, a);
}
