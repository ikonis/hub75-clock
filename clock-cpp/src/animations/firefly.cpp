#include "Animation.h"
#include "WeatherAnimator.h"
#include <nlohmann/json.hpp>
#include <algorithm>
#include <cmath>
#include <random>
#include <vector>

// Persistent firefly swarm animation.
// Port target: animations/firefly.py

struct Firefly {
    float x, y;
    float phase;
    int   period;
    float bx, by;  // drift velocities
};

class FireflyAnimation : public Animation {
public:
    FireflyAnimation(int width, int height, const nlohmann::json& cfg,
                     WeatherAnimator* animator)
        : _w(width), _h(height), _cfg(cfg), _animator(animator)
    {
        static std::mt19937 rng{std::random_device{}()};
        std::uniform_int_distribution<int>    rndCount(6, 8);
        std::uniform_real_distribution<float> rnd01(0.0f, 1.0f);
        std::uniform_int_distribution<int>    rndPeriod(20, 50);
        std::uniform_int_distribution<int>    rndExtra(0, 60);

        _at = animator->animTop;
        _ab = animator->animBottom;
        if (cfg.contains("animation") && cfg["animation"].is_object())
            _fps = std::max(1, cfg["animation"].value("fps", 15));

        if (cfg.contains("animation_settings") && cfg["animation_settings"].contains("firefly"))
            _speedMult = cfg["animation_settings"]["firefly"].value("speed", 1.0f);
        float drift = 0.24f * (15.0f / float(_fps)) * _speedMult;

        int count = rndCount(rng);
        for (int i = 0; i < count; ++i) {
            Firefly f;
            f.x      = 4.0f + rnd01(rng) * float(width - 8);
            f.y      = float(_at + 2) + rnd01(rng) * float(_ab - _at - 4);
            f.phase  = rnd01(rng) * float(M_PI) * 2.0f;
            f.period = rndPeriod(rng);
            f.bx     = (rnd01(rng) - 0.5f) * drift;
            f.by     = (rnd01(rng) - 0.5f) * drift;
            _flies.push_back(f);
        }
        _frame = 0;
        _total = 120 + rndExtra(rng);
    }

    void update() override {
        static std::mt19937 rng{std::random_device{}()};
        std::uniform_real_distribution<float> rnd01(0.0f, 1.0f);

        ++_frame;
        for (auto& f : _flies) {
            f.x += f.bx;
            f.y += f.by;
            f.x = std::max(1.0f, std::min(float(_w - 2), f.x));
            f.y = std::max(float(_at + 1), std::min(float(_ab - 1), f.y));
            if (rnd01(rng) < 0.04f * (15.0f / float(_fps))) {
                float drift = 0.24f * (15.0f / float(_fps)) * _speedMult;
                f.bx = (rnd01(rng) - 0.5f) * drift;
                f.by = (rnd01(rng) - 0.5f) * drift;
            }
        }
    }

    void draw(rgb_matrix::FrameCanvas* canvas) override {
        for (const auto& f : _flies) {
            float t          = float(_frame % f.period) / float(f.period);
            float brightness = (std::sin(t * float(M_PI) * 2.0f + f.phase) + 1.0f) / 2.0f;
            int   b          = int(brightness * 200.0f);
            if (b > 20) {
                int px = int(std::round(f.x));
                int py = int(std::round(f.y));
                if (px >= 0 && px < _w && py >= _at && py <= _ab) {
                    float alpha = std::min(1.0f, float(b) / 200.0f);
                    render::BlendPixel(canvas, px, py, 220, 220, int(220 * 0.6f), alpha);
                    if (py + 1 <= _ab)
                        render::BlendPixel(canvas, px, py + 1, 180, 180, int(180 * 0.6f), alpha * 0.35f);
                }
            }
        }
    }

    bool isDone() const override { return _frame >= _total; }

    const std::string& name()       const override { static std::string n = "firefly";    return n; }
    const std::string& layer()      const override { static std::string l = "foreground"; return l; }
    bool               persistent() const override { return true; }

private:
    int              _w, _h, _at, _ab;
    nlohmann::json   _cfg;
    WeatherAnimator* _animator;
    std::vector<Firefly> _flies;
    int _frame = 0, _total = 120, _fps = 15;
    float _speedMult = 1.0f;
};

extern "C" std::unique_ptr<Animation> create_firefly(
    int w, int h, const nlohmann::json& cfg, WeatherAnimator* a)
{
    return std::make_unique<FireflyAnimation>(w, h, cfg, a);
}
