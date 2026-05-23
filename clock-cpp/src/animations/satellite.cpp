#include "Animation.h"
#include "WeatherAnimator.h"
#include <nlohmann/json.hpp>
#include <cmath>
#include <random>

class SatelliteAnimation : public Animation {
public:
    SatelliteAnimation(int width, int height, const nlohmann::json& cfg,
                       WeatherAnimator* animator)
        : _w(width), _h(height), _cfg(cfg), _animator(animator)
    {
        static std::mt19937 rng{std::random_device{}()};
        std::uniform_real_distribution<float> rnd01(0.0f, 1.0f);
        std::uniform_int_distribution<int>    rndDir(0, 3);
        std::uniform_int_distribution<int>    rndX(2, width - 10);

        _at = animator->animTop;
        _ab = animator->animBottom;

        float _speedMult = 1.0f;
        if (cfg.contains("animation_settings") && cfg["animation_settings"].contains("satellite"))
            _speedMult = cfg["animation_settings"]["satellite"].value("speed", 1.0f);

        std::uniform_int_distribution<int> rndY(_at, std::max(_at, _ab - 4));

        float speed = (0.4f + rnd01(rng) * 0.2f) * _speedMult;
        float drift = (0.12f + rnd01(rng) * 0.06f) * _speedMult;

        int dir = rndDir(rng);
        if (dir == 0) {       // right_to_left
            _x = float(width - 2);
            _y = float(rndY(rng));
            _vx = -speed;
            _vy = drift;
        } else if (dir == 1) { // left_to_right
            _x = -10.0f;
            _y = float(rndY(rng));
            _vx = speed;
            _vy = drift;
        } else if (dir == 2) { // top_to_bottom
            _x = float(rndX(rng));
            _y = float(_at);
            _vx = (rnd01(rng) - 0.5f) * drift;
            _vy = speed;
        } else {               // bottom_to_top
            _x = float(rndX(rng));
            _y = float(_ab);
            _vx = (rnd01(rng) - 0.5f) * drift;
            _vy = -speed;
        }
    }

    void update() override {
        _x += _vx;
        _y += _vy;
    }

    void draw(rgb_matrix::FrameCanvas* canvas) override {
        static const struct Pixel { int dx, dy, r, g, b; } SPRITE[] = {
            {0,1, 40, 80,120},{1,1, 60,120,180},
            {3,0,180,180,200},{4,0,200,200,220},
            {3,1,200,200,220},{4,1,220,220,240},{5,1,200,200,220},
            {3,2,180,180,200},{4,2,200,200,220},
            {7,1, 60,120,180},{8,1, 40, 80,120},
            {2,1,100,100,120},{6,1,100,100,120},
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
        return _x < -12.0f || _x > float(_w + 12) ||
               _y < float(_at - 4) || _y > float(_ab + 4);
    }

    const std::string& name()       const override { static std::string n = "satellite"; return n; }
    const std::string& layer()      const override { static std::string l = "celestial"; return l; }
    bool               persistent() const override { return false; }

private:
    int              _w, _h, _at, _ab;
    nlohmann::json   _cfg;
    WeatherAnimator* _animator;
    float _x = 0.0f, _y = 0.0f, _vx = 0.0f, _vy = 0.0f;
};

extern "C" std::unique_ptr<Animation> create_satellite(
    int w, int h, const nlohmann::json& cfg, WeatherAnimator* a)
{
    return std::make_unique<SatelliteAnimation>(w, h, cfg, a);
}
