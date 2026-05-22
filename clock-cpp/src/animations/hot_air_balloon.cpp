#include "Animation.h"
#include "WeatherAnimator.h"
#include <nlohmann/json.hpp>
#include <cmath>
#include <random>

class HotAirBalloonAnimation : public Animation {
public:
    HotAirBalloonAnimation(int width, int height, const nlohmann::json& cfg,
                            WeatherAnimator* animator)
        : _w(width), _h(height), _cfg(cfg), _animator(animator)
    {
        static std::mt19937 rng{std::random_device{}()};
        std::uniform_int_distribution<int>    rndX(5, width - 12);
        std::uniform_real_distribution<float> rnd01(0.0f, 1.0f);

        _at   = animator->animTop;
        _ab   = animator->animBottom;
        _x    = float(rndX(rng));
        _y    = float(_ab - 9);
        _vx   = (rnd01(rng) - 0.5f) * 0.15f;
        _vy   = -0.08f;
        _sway = rnd01(rng) * float(M_PI) * 2.0f;
    }

    void update() override {
        _sway += 0.04f;
        _x    += _vx + std::sin(_sway) * 0.04f;
        _y    += _vy;
    }

    void draw(rgb_matrix::FrameCanvas* canvas) override {
        static const struct Pixel { int dx, dy, r, g, b; } SPRITE[] = {
            // Balloon tip
            {3,0,255,60,60},
            // Row 1
            {2,1,255,60,60},{3,1,255,160,0},{4,1,255,60,60},
            // Row 2
            {1,2,255,160,0},{2,2,255,240,0},{3,2,60,180,60},{4,2,255,240,0},{5,2,255,160,0},
            // Row 3 (widest)
            {0,3,60,180,60},{1,3,40,120,220},{2,3,60,180,60},{3,3,255,60,60},
            {4,3,60,180,60},{5,3,40,120,220},{6,3,60,180,60},
            // Row 4
            {1,4,255,160,0},{2,4,60,180,60},{3,4,40,120,220},{4,4,60,180,60},{5,4,255,160,0},
            // Row 5
            {2,5,255,60,60},{3,5,255,160,0},{4,5,255,60,60},
            // Row 6
            {3,6,255,60,60},
            // Ropes
            {2,7,100,70,40},{4,7,100,70,40},
            // Basket
            {2,8,120,80,40},{3,8,140,100,50},{4,8,120,80,40},
            {2,9,110,70,35},{3,9,130,90,45},{4,9,110,70,35},
        };

        int ox = int(std::round(_x));
        int oy = int(std::round(_y));
        for (const auto& p : SPRITE) {
            int px = ox + p.dx, py = oy + p.dy;
            if (px >= 0 && px < _w && py >= _at && py <= _ab)
                canvas->SetPixel(px, py, p.r, p.g, p.b);
        }
    }

    bool isDone() const override {
        return _y < float(_at - 12) || _x < -10.0f || _x > float(_w + 2);
    }

    const std::string& name()       const override { static std::string n = "hot_air_balloon"; return n; }
    const std::string& layer()      const override { static std::string l = "foreground";       return l; }
    bool               persistent() const override { return false; }

private:
    int              _w, _h, _at, _ab;
    nlohmann::json   _cfg;
    WeatherAnimator* _animator;
    float _x = 0.0f, _y = 0.0f, _vx = 0.0f, _vy = 0.0f, _sway = 0.0f;
};

extern "C" std::unique_ptr<Animation> create_hot_air_balloon(
    int w, int h, const nlohmann::json& cfg, WeatherAnimator* a)
{
    return std::make_unique<HotAirBalloonAnimation>(w, h, cfg, a);
}
