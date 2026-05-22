#include "Animation.h"
#include "WeatherAnimator.h"
#include <nlohmann/json.hpp>
#include <cmath>
#include <random>

class ButterflyAnimation : public Animation {
public:
    ButterflyAnimation(int width, int height, const nlohmann::json& cfg,
                       WeatherAnimator* animator)
        : _w(width), _h(height), _cfg(cfg), _animator(animator)
    {
        static std::mt19937 rng{std::random_device{}()};
        std::uniform_int_distribution<int>    rndY(3, 12);
        std::uniform_real_distribution<float> rnd01(0.0f, 1.0f);

        _at   = animator->animTop;
        _ab   = animator->animBottom;
        _x    = -8.0f;
        _y    = float(_at + rndY(rng));
        _vx   = 0.3f + rnd01(rng) * 0.2f;
        _frame = 0;
        _wave  = rnd01(rng) * float(M_PI) * 2.0f;
    }

    void update() override {
        ++_frame;
        _wave += 0.12f;
        _x    += _vx;
        _y    += std::sin(_wave) * 0.4f;
    }

    void draw(rgb_matrix::FrameCanvas* canvas) override {
        // Frame 0: wings open
        static const struct Pixel { int dx, dy, r, g, b; } OPEN[] = {
            {0, 0, 255, 120, 30}, {1, 0, 255, 160, 50}, {2, 0, 255, 200, 80},
            {0, 1, 255, 140, 40}, {1, 1, 255, 180, 60}, {2, 1, 255, 210, 90},
            {4, 0, 255, 120, 30}, {5, 0, 255, 160, 50}, {6, 0, 255, 200, 80},
            {4, 1, 255, 140, 40}, {5, 1, 255, 180, 60}, {6, 1, 255, 210, 90},
            {0, 3, 220,  80, 20}, {1, 3, 240, 120, 40},
            {0, 4, 200,  60, 10}, {1, 4, 220, 100, 30},
            {5, 3, 220,  80, 20}, {6, 3, 240, 120, 40},
            {5, 4, 200,  60, 10}, {6, 4, 220, 100, 30},
            {3, 1,  40,  20, 10}, {3, 2,  50,  25, 12}, {3, 3,  40,  20, 10},
        };
        // Frame 1: wings closed
        static const struct Pixel CLOSED[] = {
            {1, 0, 255, 140, 40}, {2, 0, 255, 190, 70},
            {1, 1, 255, 120, 30}, {2, 1, 255, 170, 60},
            {4, 0, 255, 140, 40}, {5, 0, 255, 190, 70},
            {4, 1, 255, 120, 30}, {5, 1, 255, 170, 60},
            {3, 1,  40,  20, 10}, {3, 2,  50,  25, 12}, {3, 3,  40,  20, 10},
        };

        int ox = int(std::round(_x));
        int oy = int(std::round(_y));
        bool use_open = (_frame / 5) % 2 == 0;

        if (use_open) {
            for (const auto& p : OPEN) {
                int px = ox + p.dx, py = oy + p.dy;
                if (px >= 0 && px < _w && py >= _at && py <= _ab)
                    canvas->SetPixel(px, py, p.r, p.g, p.b);
            }
        } else {
            for (const auto& p : CLOSED) {
                int px = ox + p.dx, py = oy + p.dy;
                if (px >= 0 && px < _w && py >= _at && py <= _ab)
                    canvas->SetPixel(px, py, p.r, p.g, p.b);
            }
        }
    }

    bool isDone() const override { return _x > float(_w + 10); }

    const std::string& name()       const override { static std::string n = "butterfly";  return n; }
    const std::string& layer()      const override { static std::string l = "foreground"; return l; }
    bool               persistent() const override { return false; }

private:
    int              _w, _h, _at, _ab;
    nlohmann::json   _cfg;
    WeatherAnimator* _animator;
    float _x = 0.0f, _y = 0.0f, _vx = 0.0f, _wave = 0.0f;
    int   _frame = 0;
};

extern "C" std::unique_ptr<Animation> create_butterfly(
    int w, int h, const nlohmann::json& cfg, WeatherAnimator* a)
{
    return std::make_unique<ButterflyAnimation>(w, h, cfg, a);
}
