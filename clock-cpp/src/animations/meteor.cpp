#include "Animation.h"
#include "WeatherAnimator.h"
#include <nlohmann/json.hpp>
#include <cmath>
#include <random>
#include <vector>
#include <array>
#include <algorithm>

class MeteorAnimation : public Animation {
public:
    MeteorAnimation(int width, int height, const nlohmann::json& cfg,
                    WeatherAnimator* animator)
        : _w(width), _h(height), _cfg(cfg), _animator(animator)
    {
        static std::mt19937 rng{std::random_device{}()};
        std::uniform_real_distribution<float> rnd01(0.0f, 1.0f);
        std::uniform_int_distribution<int>    rndY(0, 5);

        _at = animator->animTop;
        _ab = animator->animBottom;

        float _speedMult = 1.0f;
        if (cfg.contains("animation_settings") && cfg["animation_settings"].contains("meteor"))
            _speedMult = cfg["animation_settings"]["meteor"].value("speed", 1.0f);

        float speed = (3.5f + rnd01(rng) * 1.5f) * _speedMult;
        if (rnd01(rng) < 0.5f) {
            _vx = speed;
            _x  = -2.0f;
        } else {
            _vx = -speed;
            _x  = float(width + 2);
        }
        _vy = speed * (0.35f + rnd01(rng) * 0.3f);
        _y  = float(_at + rndY(rng));
    }

    void update() override {
        _history.push_back({_x, _y});
        if (int(_history.size()) > 8)
            _history.erase(_history.begin());
        _x += _vx;
        _y += _vy;
    }

    void draw(rgb_matrix::FrameCanvas* canvas) override {
        static const int TAIL_R[] = {230,210,170,130, 90, 55, 30, 12};
        static const int TAIL_G[] = {130, 90, 50, 25, 10,  4,  1,  0};
        static const int TAIL_B[] = { 30, 15,  8,  4,  2,  0,  0,  0};

        int n = int(_history.size());
        for (int i = 0; i < n; ++i) {
            int ci = n - 1 - i;   // reversed: 0 = closest to head
            int idx = std::min(ci, 7);
            int px = int(std::round(_history[i][0]));
            int py = int(std::round(_history[i][1]));
            if (px >= 0 && px < _w && py >= _at && py <= _ab)
                canvas->SetPixel(px, py, TAIL_R[idx], TAIL_G[idx], TAIL_B[idx]);
        }

        int hx = int(std::round(_x)), hy = int(std::round(_y));
        if (hx >= 0 && hx < _w && hy >= _at && hy <= _ab) {
            canvas->SetPixel(hx, hy, 255, 255, 255);
            static const int DDX[] = {-1, 1, 0, 0};
            static const int DDY[] = { 0, 0,-1, 1};
            for (int i = 0; i < 4; ++i) {
                int gx = hx + DDX[i], gy = hy + DDY[i];
                if (gx >= 0 && gx < _w && gy >= _at && gy <= _ab)
                    canvas->SetPixel(gx, gy, 255, 210, 80);
            }
        }
    }

    bool isDone() const override {
        return (_x < -12.0f || _x >= float(_w + 12) || _y > float(_ab + 2));
    }

    const std::string& name()       const override { static std::string n = "meteor";    return n; }
    const std::string& layer()      const override { static std::string l = "celestial"; return l; }
    bool               persistent() const override { return false; }

private:
    int              _w, _h, _at, _ab;
    nlohmann::json   _cfg;
    WeatherAnimator* _animator;
    float _x = 0.0f, _y = 0.0f, _vx = 0.0f, _vy = 0.0f;
    std::vector<std::array<float, 2>> _history;
};

extern "C" std::unique_ptr<Animation> create_meteor(
    int w, int h, const nlohmann::json& cfg, WeatherAnimator* a)
{
    return std::make_unique<MeteorAnimation>(w, h, cfg, a);
}
