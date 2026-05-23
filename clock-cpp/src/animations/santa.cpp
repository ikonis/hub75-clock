#include "Animation.h"
#include "WeatherAnimator.h"
#include <nlohmann/json.hpp>
#include <cmath>
#include <random>

class SantaAnimation : public Animation {
public:
    SantaAnimation(int width, int height, const nlohmann::json& cfg,
                   WeatherAnimator* animator)
        : _w(width), _h(height), _cfg(cfg), _animator(animator)
    {
        static std::mt19937 rng{std::random_device{}()};
        std::uniform_int_distribution<int>    rndY(1, 5);
        std::uniform_real_distribution<float> rnd01(0.0f, 1.0f);

        _at   = animator->animTop;
        _ab   = animator->animBottom;

        float _speedMult = 1.0f;
        if (cfg.contains("animation_settings") && cfg["animation_settings"].contains("santa"))
            _speedMult = cfg["animation_settings"]["santa"].value("speed", 1.0f);

        _x    = float(width + 2);
        _y    = float(_at + rndY(rng));
        _vx   = -(0.4f + rnd01(rng) * 0.2f) * _speedMult;
        _wave = rnd01(rng) * float(M_PI) * 2.0f;
    }

    void update() override {
        _x    += _vx;
        _wave += 0.06f;
    }

    void draw(rgb_matrix::FrameCanvas* canvas) override {
        static const struct Pixel { int dx, dy, r, g, b; } SPRITE[] = {
            // Reindeer 1
            {0,2,160,120,80},{1,2,160,120,80},
            {0,1,140,100,60},{1,1,140,100,60},
            // Reindeer 2
            {3,2,160,120,80},{4,2,160,120,80},
            {3,1,140,100,60},
            // Reindeer 3
            {6,2,160,120,80},{7,2,160,120,80},
            {6,1,140,100,60},{7,1,140,100,60},
            // Harness
            {2,2,80,60,40},{5,2,80,60,40},
            // Sleigh runners
            {8,3,80,60,40},{9,3,80,60,40},{10,3,80,60,40},{11,3,80,60,40},{12,3,80,60,40},
            // Sleigh body
            {9,1,180,30,30},{10,1,200,40,40},{11,1,200,40,40},{12,1,180,30,30},
            {9,2,180,30,30},{10,2,200,40,40},{11,2,200,40,40},{12,2,180,30,30},
            // Sleigh back wall
            {13,0,160,25,25},{13,1,160,25,25},{13,2,160,25,25},
            // Santa
            {12,0,200,40,40},
            {11,0,220,220,220},
            {13,1,50,30,20},
        };

        int ox = int(std::round(_x));
        int oy = int(std::round(_y + std::sin(_wave) * 1.5f));

        for (const auto& p : SPRITE) {
            int px = ox + p.dx, py = oy + p.dy;
            if (px >= 0 && px < _w && py >= _at - 2 && py <= _ab)
                canvas->SetPixel(px, py, p.r, p.g, p.b);
        }
    }

    bool isDone() const override { return _x < -20.0f; }

    const std::string& name()       const override { static std::string n = "santa";      return n; }
    const std::string& layer()      const override { static std::string l = "foreground"; return l; }
    bool               persistent() const override { return false; }

private:
    int              _w, _h, _at, _ab;
    nlohmann::json   _cfg;
    WeatherAnimator* _animator;
    float _x = 0.0f, _y = 0.0f, _vx = 0.0f, _wave = 0.0f;
};

extern "C" std::unique_ptr<Animation> create_santa(
    int w, int h, const nlohmann::json& cfg, WeatherAnimator* a)
{
    return std::make_unique<SantaAnimation>(w, h, cfg, a);
}
