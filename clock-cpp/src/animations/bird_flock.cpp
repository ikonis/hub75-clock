#include "Animation.h"
#include "WeatherAnimator.h"
#include <nlohmann/json.hpp>
#include <cmath>
#include <random>
#include <vector>
#include <array>

class BirdFlockAnimation : public Animation {
public:
    BirdFlockAnimation(int width, int height, const nlohmann::json& cfg,
                       WeatherAnimator* animator)
        : _w(width), _h(height), _cfg(cfg), _animator(animator)
    {
        static std::mt19937 rng{std::random_device{}()};
        std::uniform_int_distribution<int>    rndCount(5, 7);
        std::uniform_int_distribution<int>    rndRowY(5, 13);
        std::uniform_real_distribution<float> rnd01(0.0f, 1.0f);

        _at = animator->animTop;
        _ab = animator->animBottom;

        float _speedMult = 1.0f;
        if (cfg.contains("animation_settings") && cfg["animation_settings"].contains("bird_flock"))
            _speedMult = cfg["animation_settings"]["bird_flock"].value("speed", 1.0f);

        int count = rndCount(rng);
        int rowY  = _at + rndRowY(rng);

        for (int i = 0; i < count; ++i) {
            float bx, by;
            if (i == 0) {
                bx = 0.0f; by = 0.0f;
            } else {
                float side = (i % 2 == 1) ? 1.0f : -1.0f;
                int   rank = (i + 1) / 2;
                bx = -float(rank) * 3.5f;
                by =  float(rank) * 1.5f * side;
            }
            _birds.push_back({bx, by});
        }

        _vx   = (0.35f + rnd01(rng) * 0.15f) * _speedMult;
        _ox   = -8.0f;
        _oy   = float(rowY);
        _flap = 0;
    }

    void update() override {
        _ox += _vx;
        ++_flap;
    }

    void draw(rgb_matrix::FrameCanvas* canvas) override {
        bool wing_up = (_flap / 6) % 2 == 0;
        for (const auto& bird : _birds) {
            int cx = int(std::round(_ox + bird[0]));
            int cy = int(std::round(_oy + bird[1]));
            if (cx >= 0 && cx < _w && cy >= _at && cy <= _ab)
                render::SetPixel(canvas, cx, cy, 30, 30, 30);
            int wy = cy - (wing_up ? 1 : 0);
            if (cx - 1 >= 0 && cx - 1 < _w && wy >= _at && wy <= _ab)
                render::SetPixel(canvas, cx - 1, wy, 40, 40, 40);
            if (cx + 1 >= 0 && cx + 1 < _w && wy >= _at && wy <= _ab)
                render::SetPixel(canvas, cx + 1, wy, 40, 40, 40);
        }
    }

    bool isDone() const override { return _ox > float(_w + 10); }

    const std::string& name()       const override { static std::string n = "bird_flock"; return n; }
    const std::string& layer()      const override { static std::string l = "foreground"; return l; }
    bool               persistent() const override { return false; }

private:
    int              _w, _h, _at, _ab;
    nlohmann::json   _cfg;
    WeatherAnimator* _animator;
    std::vector<std::array<float, 2>> _birds;
    float _vx = 0.0f, _ox = 0.0f, _oy = 0.0f;
    int   _flap = 0;
};

extern "C" std::unique_ptr<Animation> create_bird_flock(
    int w, int h, const nlohmann::json& cfg, WeatherAnimator* a)
{
    return std::make_unique<BirdFlockAnimation>(w, h, cfg, a);
}
