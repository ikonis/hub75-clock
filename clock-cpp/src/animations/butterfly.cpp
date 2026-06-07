#include "Animation.h"
#include "WeatherAnimator.h"
#include <nlohmann/json.hpp>
#include <cmath>
#include <random>
#include <vector>
#include <algorithm>

struct ButterflySingle {
    float x, y, vx, wave;
    int   flapOffset;
    int   cr, cg, cb;
};

class ButterflyAnimation : public Animation {
public:
    ButterflyAnimation(int width, int height, const nlohmann::json& cfg,
                       WeatherAnimator* animator)
        : _w(width), _h(height), _cfg(cfg), _animator(animator)
    {
        static std::mt19937 rng{std::random_device{}()};
        std::uniform_int_distribution<int>    rndY(3, 12);
        std::uniform_real_distribution<float> rnd01(0.0f, 1.0f);

        _at = animator->animTop;
        _ab = animator->animBottom;

        float speedMult = 1.0f;
        if (cfg.contains("animation_settings") && cfg["animation_settings"].contains("butterfly"))
            speedMult = cfg["animation_settings"]["butterfly"].value("speed", 1.0f);

        static const int PASTELS[5][3] = {
            {100, 160, 255},
            {255, 240, 100},
            {255, 130, 180},
            {130, 230, 140},
            {255, 170,  80},
        };
        int order[5] = {0, 1, 2, 3, 4};
        std::shuffle(std::begin(order), std::end(order), rng);

        for (int i = 0; i < 3; ++i) {
            ButterflySingle b;
            bool right  = (rnd01(rng) < 0.5f);
            b.x         = right ? float(-8 - i * 18) : float(width + 8 + i * 18);
            b.y         = float(_at + rndY(rng));
            b.vx        = (0.25f + rnd01(rng) * 0.2f) * speedMult * (right ? 1.0f : -1.0f);
            b.wave      = rnd01(rng) * float(M_PI) * 2.0f;
            b.flapOffset = i * 5;
            b.cr        = PASTELS[order[i]][0];
            b.cg        = PASTELS[order[i]][1];
            b.cb        = PASTELS[order[i]][2];
            _butterflies.push_back(b);
        }
        _frame = 0;
    }

    void update() override {
        ++_frame;
        for (auto& b : _butterflies) {
            b.wave += 0.12f;
            b.x    += b.vx;
            b.y    += std::sin(b.wave) * 0.4f;
        }
    }

    void draw(rgb_matrix::FrameCanvas* canvas) override {
        static const struct WingPx { int dx, dy; float brt; } OPEN[] = {
            {0,0,1.00f},{1,0,1.00f},{2,0,1.00f},
            {0,1,1.00f},{1,1,1.00f},{2,1,1.00f},
            {4,0,1.00f},{5,0,1.00f},{6,0,1.00f},
            {4,1,1.00f},{5,1,1.00f},{6,1,1.00f},
            {0,3,0.86f},{1,3,0.94f},
            {0,4,0.78f},{1,4,0.86f},
            {5,3,0.86f},{6,3,0.94f},
            {5,4,0.78f},{6,4,0.86f},
        };
        static const struct WingPx CLOSED[] = {
            {1,0,1.00f},{2,0,1.00f},
            {1,1,1.00f},{2,1,1.00f},
            {4,0,1.00f},{5,0,1.00f},
            {4,1,1.00f},{5,1,1.00f},
        };
        static const struct { int dx, dy; } BODY[] = {{3,1},{3,2},{3,3}};

        for (const auto& b : _butterflies) {
            int ox = int(std::round(b.x));
            int oy = int(std::round(b.y));
            bool use_open = ((_frame + b.flapOffset) / 5) % 2 == 0;

            const WingPx* wing = use_open ? OPEN : CLOSED;
            int            nw  = use_open ? 20 : 8;
            for (int i = 0; i < nw; ++i) {
                int px = ox + wing[i].dx, py = oy + wing[i].dy;
                if (px >= 0 && px < _w && py >= _at && py <= _ab)
                    render::BlendPixel(canvas, px, py, b.cr, b.cg, b.cb, wing[i].brt);
            }
            for (const auto& bp : BODY) {
                int px = ox + bp.dx, py = oy + bp.dy;
                if (px >= 0 && px < _w && py >= _at && py <= _ab)
                    render::SetPixel(canvas, px, py, 45, 22, 11);
            }
        }
    }

    bool isDone() const override {
        for (const auto& b : _butterflies) {
            if (b.x >= -20.0f && b.x <= float(_w + 20)) return false;
        }
        return true;
    }

    const std::string& name()       const override { static std::string n = "butterfly";  return n; }
    const std::string& layer()      const override { static std::string l = "foreground"; return l; }
    bool               persistent() const override { return false; }

private:
    int              _w, _h, _at, _ab;
    nlohmann::json   _cfg;
    WeatherAnimator* _animator;
    std::vector<ButterflySingle> _butterflies;
    int _frame = 0;
};

extern "C" std::unique_ptr<Animation> create_butterfly(
    int w, int h, const nlohmann::json& cfg, WeatherAnimator* a)
{
    return std::make_unique<ButterflyAnimation>(w, h, cfg, a);
}
