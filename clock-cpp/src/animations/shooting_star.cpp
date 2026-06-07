#include "Animation.h"
#include "WeatherAnimator.h"
#include <nlohmann/json.hpp>
#include <cmath>
#include <random>

class ShootingStarAnimation : public Animation {
public:
    ShootingStarAnimation(int width, int height, const nlohmann::json& cfg,
                           WeatherAnimator* animator)
        : _w(width), _h(height), _cfg(cfg), _animator(animator)
    {
        static std::mt19937 rng{std::random_device{}()};
        std::uniform_real_distribution<float> rnd01(0.0f, 1.0f);
        std::uniform_int_distribution<int>    rndLife(10, 16);

        _at    = animator->animTop;
        _ab    = animator->animBottom;
        _valid = false;

        // Only spawn for allowed conditions
        const std::string& cond = animator->condition;
        if (cond != "CLEAR" && cond != "PARTLYCLOUDY") return;

        _valid = true;

        float _speedMult = 1.0f;
        if (cfg.contains("animation_settings") && cfg["animation_settings"].contains("shooting_star"))
            _speedMult = cfg["animation_settings"]["shooting_star"].value("speed", 1.0f);

        int anim_third = _at + (_ab - _at + 1) / 3;
        float speed = (rnd01(rng) * 1.5f + 1.0f) * _speedMult;
        if (rnd01(rng) < 0.5f) speed = -speed;

        _x  = rnd01(rng) * float(width);
        _y  = float(_at) + rnd01(rng) * float(anim_third - _at);
        _vx = speed;
        _vy = (rnd01(rng) * 0.6f + 0.8f) * _speedMult;
        _life    = rndLife(rng);
        _maxLife = _life;
    }

    void update() override {
        if (!_valid) return;
        --_life;
        _x += _vx;
        _y += _vy;
    }

    void draw(rgb_matrix::FrameCanvas* canvas) override {
        if (!_valid) return;
        int brightness = int(220.0f * float(_life) / float(_maxLife));
        _px(canvas, int(_x), int(_y), brightness);
        for (int i = 1; i < 6; ++i) {
            int trail_b = int(float(brightness) * (1.0f - float(i) / 5.0f));
            if (trail_b > 5)
                _px(canvas,
                    int(_x - _vx * i),
                    int(_y - _vy * i),
                    trail_b);
        }
    }

    bool isDone() const override { return !_valid || _life <= 0; }

    const std::string& name()       const override { static std::string n = "shooting_star"; return n; }
    const std::string& layer()      const override { static std::string l = "celestial";      return l; }
    bool               persistent() const override { return false; }

private:
    int              _w, _h, _at, _ab;
    nlohmann::json   _cfg;
    WeatherAnimator* _animator;
    float _x = 0.0f, _y = 0.0f, _vx = 0.0f, _vy = 0.0f;
    int   _life = 0, _maxLife = 1;
    bool  _valid = false;

    void _px(rgb_matrix::FrameCanvas* canvas, int x, int y, int b) const {
        if (x >= 0 && x < _w && y >= _at && y <= _ab)
            render::BlendPixel(canvas, x, y, 230, 230, 230, float(b) / 230.0f);
    }
};

extern "C" std::unique_ptr<Animation> create_shooting_star(
    int w, int h, const nlohmann::json& cfg, WeatherAnimator* a)
{
    return std::make_unique<ShootingStarAnimation>(w, h, cfg, a);
}
