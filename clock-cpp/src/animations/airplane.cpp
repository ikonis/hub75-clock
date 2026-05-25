#include "Animation.h"
#include "WeatherAnimator.h"
#include <nlohmann/json.hpp>
#include <cmath>
#include <random>
#include <vector>

struct TrailPoint {
    float x, y;
};

class AirplaneAnimation : public Animation {
public:
    AirplaneAnimation(int width, int height, const nlohmann::json& cfg,
                      WeatherAnimator* animator)
        : _w(width), _h(height), _cfg(cfg), _animator(animator)
    {
        static std::mt19937 rng{std::random_device{}()};
        std::uniform_real_distribution<float> rnd01(0.0f, 1.0f);
        std::uniform_int_distribution<int>    rndY(5, 11);

        _at = animator->animTop;
        _ab = animator->animBottom;

        float _speedMult = 0.8f;
        if (cfg.contains("animation_settings") && cfg["animation_settings"].contains("airplane"))
            _speedMult = cfg["animation_settings"]["airplane"].value("speed", 0.8f);

        _right = (rnd01(rng) < 0.5f);
        _y = float(_at + rndY(rng));
        if (_right) {
            _x  = -10.0f;
            _vx = (0.45f + rnd01(rng) * 0.2f) * _speedMult;
        } else {
            _x  = float(width + 1);
            _vx = -(0.45f + rnd01(rng) * 0.2f) * _speedMult;
        }
    }

    void update() override {
        float trailX = _right ? (_x - 2.0f) : (_x + 10.0f);
        float trailY = _y + 1.0f;
        _trail.push_back({trailX, trailY});
        if (_trail.size() > _trailMax)
            _trail.erase(_trail.begin());
        _x += _vx;
    }

    void draw(rgb_matrix::FrameCanvas* canvas) override {
        static const struct Pixel { int dx, dy, r, g, b; } SPRITE_R[] = {
            // Nose cone
            {0, 1, 220, 220, 230},
            // Fuselage top row
            {1, 0, 200, 200, 210}, {2, 0, 210, 210, 220}, {3, 0, 210, 210, 220},
            {4, 0, 210, 210, 220}, {5, 0, 200, 200, 210}, {6, 0, 190, 190, 200},
            {7, 0, 180, 180, 190},
            // Fuselage bottom row
            {1, 1, 200, 200, 210}, {2, 1, 210, 210, 220}, {3, 1, 210, 210, 220},
            {4, 1, 210, 210, 220}, {5, 1, 200, 200, 210}, {6, 1, 180, 180, 190},
            {7, 1, 160, 160, 170},
            // Wing (below fuselage)
            {2, 2, 180, 180, 190}, {3, 2, 200, 200, 210}, {4, 2, 200, 200, 210},
            {5, 2, 180, 180, 190},
            // Tail fin
            {6, -1, 190, 190, 200}, {7, -1, 180, 180, 190},
            // Windows (overwrite fuselage slots)
            {2, 1, 160, 200, 255}, {4, 1, 160, 200, 255},
        };

        for (size_t i = 0; i < _trail.size(); ++i) {
            float fade = float(i + 1) / float(_trail.size());
            int b = int(85.0f * fade);
            if (b <= 4) continue;
            int px = int(std::round(_trail[i].x));
            int py = int(std::round(_trail[i].y));
            if (px >= 0 && px < _w && py >= _at && py <= _ab) {
                canvas->SetPixel(px, py, b, b, b);
                if (i % 3 == 0 && py + 1 <= _ab) {
                    int dim = b / 2;
                    canvas->SetPixel(px, py + 1, dim, dim, dim);
                }
            }
        }

        int ox = int(std::round(_x));
        int oy = int(std::round(_y));
        for (const auto& p : SPRITE_R) {
            int dx = _right ? (8 - p.dx) : p.dx;
            int px = ox + dx;
            int py = oy + p.dy;
            if (px >= 0 && px < _w && py >= _at - 2 && py <= _ab)
                canvas->SetPixel(px, py, p.r, p.g, p.b);
        }
    }

    bool isDone() const override {
        return _x > float(_w + 12) || _x < -12.0f;
    }

    const std::string& name()       const override { static std::string n = "airplane";   return n; }
    const std::string& layer()      const override { static std::string l = "foreground"; return l; }
    bool               persistent() const override { return false; }

private:
    int              _w, _h, _at, _ab;
    nlohmann::json   _cfg;
    WeatherAnimator* _animator;
    float            _x, _y, _vx;
    bool             _right;
    std::vector<TrailPoint> _trail;
    size_t           _trailMax = 18;
};

extern "C" std::unique_ptr<Animation> create_airplane(
    int w, int h, const nlohmann::json& cfg, WeatherAnimator* a)
{
    return std::make_unique<AirplaneAnimation>(w, h, cfg, a);
}
