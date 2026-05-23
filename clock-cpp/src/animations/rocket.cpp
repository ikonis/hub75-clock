#include "Animation.h"
#include "WeatherAnimator.h"
#include <nlohmann/json.hpp>
#include <cmath>
#include <random>

class RocketAnimation : public Animation {
public:
    RocketAnimation(int width, int height, const nlohmann::json& cfg,
                    WeatherAnimator* animator)
        : _w(width), _h(height), _cfg(cfg), _animator(animator)
    {
        static std::mt19937 rng{std::random_device{}()};
        std::uniform_int_distribution<int>    rndX(4, width - 5);
        std::uniform_real_distribution<float> rnd01(0.0f, 1.0f);

        _at    = animator->animTop;
        _ab    = animator->animBottom;

        float _speedMult = 1.0f;
        if (cfg.contains("animation_settings") && cfg["animation_settings"].contains("rocket"))
            _speedMult = cfg["animation_settings"]["rocket"].value("speed", 1.0f);

        _x       = float(rndX(rng));
        _y       = float(_ab - 2);
        _vy      = -(0.5f + rnd01(rng) * 0.3f) * _speedMult;
        _accel   = 0.04f * _speedMult;
        _frame   = 0;
    }

    void update() override {
        _vy -= _accel;
        _y  += _vy;
        ++_frame;
    }

    void draw(rgb_matrix::FrameCanvas* canvas) override {
        static const struct Pixel { int dx, dy, r, g, b; } BODY[] = {
            {1,0,220,220,240},
            {0,1,200,200,220},{1,1,220,220,240},{2,1,200,200,220},
            {0,2,190,190,210},{1,2,210,210,230},{2,2,190,190,210},
            {0,3,190,190,210},{1,3,100,180,255},{2,3,190,190,210},
            {0,4,200, 60, 60},{1,4,220, 70, 70},{2,4,200, 60, 60},
            {-1,5,180,50,50},{0,5,210,65,65},{1,5,220,70,70},
            {2,5,210,65,65},{3,5,180,50,50},
        };

        int ox = int(std::round(_x));
        int oy = int(std::round(_y));

        for (const auto& p : BODY) {
            int px = ox + p.dx, py = oy + p.dy;
            if (px >= 0 && px < _w && py >= _at && py <= _ab)
                canvas->SetPixel(px, py, p.r, p.g, p.b);
        }

        // Flame trail below rocket
        int flame_y = oy + 6;
        for (int fi = 0; fi < 4; ++fi) {
            int fy = flame_y + fi;
            if (fy < _at || fy > _ab) continue;
            float fade = 1.0f - float(fi) / 4.0f;
            int   fr   = int(255 * fade);
            int   fg   = int(120 * fade * (1.0f - fi * 0.2f));
            canvas->SetPixel(ox + 1, fy, fr, fg, 0);
            if (fi < 2) {
                canvas->SetPixel(ox,     fy, int(fr*0.6f), int(fg*0.4f), 0);
                canvas->SetPixel(ox + 2, fy, int(fr*0.6f), int(fg*0.4f), 0);
            }
        }
    }

    bool isDone() const override { return _y < float(_at - 10); }

    const std::string& name()       const override { static std::string n = "rocket";     return n; }
    const std::string& layer()      const override { static std::string l = "foreground"; return l; }
    bool               persistent() const override { return false; }

private:
    int              _w, _h, _at, _ab;
    nlohmann::json   _cfg;
    WeatherAnimator* _animator;
    float _x = 0.0f, _y = 0.0f, _vy = 0.0f, _accel = 0.04f;
    int   _frame = 0;
};

extern "C" std::unique_ptr<Animation> create_rocket(
    int w, int h, const nlohmann::json& cfg, WeatherAnimator* a)
{
    return std::make_unique<RocketAnimation>(w, h, cfg, a);
}
