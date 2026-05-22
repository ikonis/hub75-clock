#include "Animation.h"
#include "WeatherAnimator.h"
#include <nlohmann/json.hpp>
#include <cmath>
#include <random>

class SubmarineAnimation : public Animation {
public:
    SubmarineAnimation(int width, int height, const nlohmann::json& cfg,
                       WeatherAnimator* animator)
        : _w(width), _h(height), _cfg(cfg), _animator(animator)
    {
        static std::mt19937 rng{std::random_device{}()};
        std::uniform_real_distribution<float> rnd01(0.0f, 1.0f);

        _at    = animator->animTop;
        _ab    = animator->animBottom;
        int mid = (_at + _ab) / 2;
        _baseY = float(mid - 2);
        _x     = -20.0f;
        _vx    = 0.25f + rnd01(rng) * 0.15f;
        _wave  = rnd01(rng) * float(M_PI) * 2.0f;
    }

    void update() override {
        _x    += _vx;
        _wave += 0.04f;
    }

    void draw(rgb_matrix::FrameCanvas* canvas) override {
        static const struct Pixel { int dx, dy, r, g, b; } HULL[] = {
            {2,2,80,130,80},{3,2,100,160,100},{4,2,110,170,110},{5,2,110,170,110},
            {6,2,110,170,110},{7,2,110,170,110},{8,2,110,170,110},{9,2,110,170,110},
            {10,2,110,170,110},{11,2,110,170,110},{12,2,110,170,110},{13,2,110,170,110},
            {14,2,100,160,100},{15,2,80,130,80},
            {1,2,60,100,60},
            {3,1,80,130,80},{4,1,100,160,100},{5,1,100,160,100},{6,1,100,160,100},
            {7,1,100,160,100},{8,1,100,160,100},{9,1,100,160,100},{10,1,100,160,100},
            {11,1,100,160,100},{12,1,100,160,100},{13,1,100,160,100},{14,1,80,130,80},
            {3,3,80,130,80},{4,3,100,160,100},{5,3,100,160,100},{6,3,100,160,100},
            {7,3,100,160,100},{8,3,100,160,100},{9,3,100,160,100},{10,3,100,160,100},
            {11,3,100,160,100},{12,3,100,160,100},{13,3,100,160,100},{14,3,80,130,80},
            // Propeller
            {16,1,60,100,60},{16,3,60,100,60},{17,2,50,90,50},
            // Porthole (overwrite)
            {7,2,160,220,255},
            // Conning tower
            {10,0,80,130,80},{11,0,90,140,90},{12,0,80,130,80},
            {10,1,85,135,85},{11,1,95,145,95},{12,1,85,135,85},
        };
        static const struct Pixel SCOPE[] = {
            {11,-2,60,100,60},{11,-1,70,115,70}
        };

        int ox = int(std::round(_x));
        int oy = int(std::round(_baseY + std::sin(_wave) * 1.0f));

        for (const auto& p : HULL) {
            int px = ox + p.dx, py = oy + p.dy;
            if (px >= 0 && px < _w && py >= _at && py <= _ab)
                canvas->SetPixel(px, py, p.r, p.g, p.b);
        }
        for (const auto& p : SCOPE) {
            int px = ox + p.dx, py = oy + p.dy;
            if (px >= 0 && px < _w && py >= _at && py <= _ab)
                canvas->SetPixel(px, py, p.r, p.g, p.b);
        }
    }

    bool isDone() const override { return _x > float(_w + 22); }

    const std::string& name()       const override { static std::string n = "submarine";  return n; }
    const std::string& layer()      const override { static std::string l = "foreground"; return l; }
    bool               persistent() const override { return false; }

private:
    int              _w, _h, _at, _ab;
    nlohmann::json   _cfg;
    WeatherAnimator* _animator;
    float _x = 0.0f, _baseY = 0.0f, _vx = 0.0f, _wave = 0.0f;
};

extern "C" std::unique_ptr<Animation> create_submarine(
    int w, int h, const nlohmann::json& cfg, WeatherAnimator* a)
{
    return std::make_unique<SubmarineAnimation>(w, h, cfg, a);
}
