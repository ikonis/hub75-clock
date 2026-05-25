#include "Animation.h"
#include "WeatherAnimator.h"
#include <nlohmann/json.hpp>
#include <cmath>
#include <random>

class GhostAnimation : public Animation {
public:
    GhostAnimation(int width, int height, const nlohmann::json& cfg,
                   WeatherAnimator* animator)
        : _w(width), _h(height), _cfg(cfg), _animator(animator)
    {
        static std::mt19937 rng{std::random_device{}()};
        std::uniform_real_distribution<float> rnd01(0.0f, 1.0f);
        std::uniform_int_distribution<int>    rndColor(0, 3);
        std::uniform_int_distribution<int>    rndY(0, 4);

        _at = animator->animTop;
        _ab = animator->animBottom;

        float _speedMult = 1.0f;
        if (cfg.contains("animation_settings") && cfg["animation_settings"].contains("ghost"))
            _speedMult = cfg["animation_settings"]["ghost"].value("speed", 1.0f);

        static const int COLORS[4][3] = {
            {255,   0,   0},
            {255, 184, 255},
            {  0, 255, 255},
            {255, 184,  82},
        };
        int ci = rndColor(rng);
        _r = COLORS[ci][0]; _g = COLORS[ci][1]; _b = COLORS[ci][2];

        _right = (rnd01(rng) < 0.5f);
        if (_right) {
            _x  = -8.0f;
            _vx = (0.28f + rnd01(rng) * 0.12f) * _speedMult;
        } else {
            _x  = float(width + 2);
            _vx = -(0.28f + rnd01(rng) * 0.12f) * _speedMult;
        }
        int mid = (_at + _ab) / 2;
        _baseY = float(mid - 4 + rndY(rng));
        _bob   = rnd01(rng) * float(M_PI) * 2.0f;
    }

    void update() override {
        _x   += _vx;
        _bob += 0.06f;
    }

    void draw(rgb_matrix::FrameCanvas* canvas) override {
        static const struct { int dx, dy; } BODY[] = {
            {1,0},{2,0},{3,0},{4,0},{5,0},
            {0,1},{1,1},{2,1},{3,1},{4,1},{5,1},{6,1},
            {0,2},{3,2},{6,2},
            {0,3},{3,3},{6,3},
            {0,4},{1,4},{2,4},{3,4},{4,4},{5,4},{6,4},
            {0,5},{1,5},{2,5},{3,5},{4,5},{5,5},{6,5},
            {0,6},{2,6},{4,6},{6,6},
        };
        static const struct { int dx, dy; } EYES_WHITE[] = {
            {1,2},{2,2},{4,2},{5,2},
            {1,3},{2,3},{4,3},{5,3},
        };
        struct Pt { int dx, dy; };
        static const Pt PUPILS_R[] = {{2,2},{5,2}};
        static const Pt PUPILS_L[] = {{1,2},{4,2}};

        int ox = int(std::round(_x));
        int oy = int(std::round(_baseY + std::sin(_bob) * 2.0f));

        for (const auto& p : BODY) {
            int px = ox + p.dx, py = oy + p.dy;
            if (px >= 0 && px < _w && py >= _at && py <= _ab)
                canvas->SetPixel(px, py, _r, _g, _b);
        }
        for (const auto& p : EYES_WHITE) {
            int px = ox + p.dx, py = oy + p.dy;
            if (px >= 0 && px < _w && py >= _at && py <= _ab)
                canvas->SetPixel(px, py, 240, 240, 240);
        }
        const auto* pupils = _right ? PUPILS_R : PUPILS_L;
        for (int i = 0; i < 2; ++i) {
            int px = ox + pupils[i].dx, py = oy + pupils[i].dy;
            if (px >= 0 && px < _w && py >= _at && py <= _ab)
                canvas->SetPixel(px, py, 30, 30, 200);
        }
    }

    bool isDone() const override {
        return _x > float(_w + 10) || _x < -12.0f;
    }

    const std::string& name()       const override { static std::string n = "ghost";      return n; }
    const std::string& layer()      const override { static std::string l = "foreground"; return l; }
    bool               persistent() const override { return false; }

private:
    int              _w, _h, _at, _ab;
    nlohmann::json   _cfg;
    WeatherAnimator* _animator;
    float _x = 0.0f, _vx = 0.0f, _baseY = 0.0f, _bob = 0.0f;
    int   _r = 0, _g = 0, _b = 0;
    bool  _right = true;
};

extern "C" std::unique_ptr<Animation> create_ghost(
    int w, int h, const nlohmann::json& cfg, WeatherAnimator* a)
{
    return std::make_unique<GhostAnimation>(w, h, cfg, a);
}
