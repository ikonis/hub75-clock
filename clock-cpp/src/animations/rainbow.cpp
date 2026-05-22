#include "Animation.h"
#include "WeatherAnimator.h"
#include <nlohmann/json.hpp>
#include <cmath>
#include <algorithm>

class RainbowAnimation : public Animation {
public:
    RainbowAnimation(int width, int height, const nlohmann::json& cfg,
                     WeatherAnimator* animator)
        : _w(width), _h(height), _cfg(cfg), _animator(animator)
    {
        _at    = animator->animTop;
        _ab    = animator->animBottom;
        _frame = 0;
        _total = 15 + 45 + 15;  // fade_in + hold + fade_out
    }

    void update() override { ++_frame; }

    void draw(rgb_matrix::FrameCanvas* canvas) override {
        float alpha = _alpha();
        alpha = std::max(0.0f, std::min(1.0f, alpha));
        if (alpha <= 0.0f) return;

        static const struct { int r, g, b; } BANDS[] = {
            {255,   0,   0},
            {255, 165,   0},
            {255, 255,   0},
            {  0, 200,   0},
            {  0,   0, 255},
            { 75,   0, 130},
            {148,   0, 211},
        };

        float cx    = float(_w) / 2.0f;
        float baseY = float(_ab + 1);

        for (int bi = 0; bi < 7; ++bi) {
            float r2 = float(26 - bi * 3);
            for (int px = 0; px < _w; ++px) {
                float dx   = float(px) - cx;
                if (std::abs(dx) > r2) continue;
                float arc_h = std::sqrt(std::max(0.0f, r2*r2 - dx*dx));
                int py = int(std::round(baseY - arc_h));
                if (py >= _at && py <= _ab)
                    canvas->SetPixel(px, py,
                        int(BANDS[bi].r * alpha),
                        int(BANDS[bi].g * alpha),
                        int(BANDS[bi].b * alpha));
                if (py + 1 >= _at && py + 1 <= _ab)
                    canvas->SetPixel(px, py + 1,
                        int(BANDS[bi].r * alpha),
                        int(BANDS[bi].g * alpha),
                        int(BANDS[bi].b * alpha));
            }
        }
    }

    bool isDone() const override { return _frame >= _total; }

    const std::string& name()       const override { static std::string n = "rainbow";    return n; }
    const std::string& layer()      const override { static std::string l = "foreground"; return l; }
    bool               persistent() const override { return false; }

private:
    int              _w, _h, _at, _ab;
    nlohmann::json   _cfg;
    WeatherAnimator* _animator;
    int _frame = 0, _total = 75;

    float _alpha() const {
        int f = _frame;
        if (f < 15)       return float(f) / 15.0f;
        if (f < 15 + 45)  return 1.0f;
        return 1.0f - float(f - 60) / 15.0f;
    }
};

extern "C" std::unique_ptr<Animation> create_rainbow(
    int w, int h, const nlohmann::json& cfg, WeatherAnimator* a)
{
    return std::make_unique<RainbowAnimation>(w, h, cfg, a);
}
