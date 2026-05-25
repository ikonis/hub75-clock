#include "Animation.h"
#include "WeatherAnimator.h"
#include <nlohmann/json.hpp>
#include <cmath>
#include <random>

class CometAnimation : public Animation {
public:
    CometAnimation(int width, int height, const nlohmann::json& cfg,
                   WeatherAnimator* animator)
        : _w(width), _h(height), _cfg(cfg), _animator(animator)
    {
        static std::mt19937 rng{std::random_device{}()};
        std::uniform_real_distribution<float> rnd01(0.0f, 1.0f);
        std::uniform_int_distribution<int>    rndTail(10, 14);
        std::uniform_int_distribution<int>    rndY(1, 6);

        _at       = animator->animTop;
        _ab       = animator->animBottom;
        _tailLen  = rndTail(rng);

        float _speedMult = 1.0f;
        if (cfg.contains("animation_settings") && cfg["animation_settings"].contains("comet"))
            _speedMult = cfg["animation_settings"]["comet"].value("speed", 1.0f);

        float speed = (0.35f + rnd01(rng) * 0.25f) * _speedMult;
        float steep = (0.20f + rnd01(rng) * 0.15f) * _speedMult;

        if (rnd01(rng) < 0.5f) {
            _vx = speed;
            _x  = float(-_tailLen - 2);
        } else {
            _vx = -speed;
            _x  = float(width + _tailLen + 2);
        }
        _y  = float(_at + rndY(rng));
        _vy = steep;
        _frame = 0;
    }

    void update() override {
        ++_frame;
        _x += _vx;
        _y += _vy;
    }

    void draw(rgb_matrix::FrameCanvas* canvas) override {
        int hx = int(std::round(_x));
        int hy = int(std::round(_y));

        float vlen = std::sqrt(_vx * _vx + _vy * _vy);
        float tdx  = -_vx / vlen;
        float tdy  = -_vy / vlen;

        for (int i = 1; i <= _tailLen; ++i) {
            int tx = hx + int(std::round(tdx * i));
            int ty = hy + int(std::round(tdy * i));
            if (!(tx >= 0 && tx < _w && ty >= _at && ty <= _ab)) continue;
            float t = float(i) / float(_tailLen);
            int r = int(180 * (1.0f - t));
            int g = int(200 * (1.0f - t * 0.6f));
            int b = int(255 * (1.0f - t * 0.3f));
            canvas->SetPixel(tx, ty, r, g, b);
            if (i < _tailLen / 2) {
                int dim = int((1.0f - t) * 80.0f);
                for (int off : {-1, 1}) {
                    int ny = ty + off;
                    if (ny >= _at && ny <= _ab)
                        canvas->SetPixel(tx, ny, dim / 2, dim / 2, dim);
                }
            }
        }

        // Bright head
        if (hx >= 0 && hx < _w && hy >= _at && hy <= _ab)
            canvas->SetPixel(hx, hy, 220, 240, 255);
        static const int DDX[] = {-1, 1, 0, 0};
        static const int DDY[] = {0, 0, -1, 1};
        for (int i = 0; i < 4; ++i) {
            int gx = hx + DDX[i], gy = hy + DDY[i];
            if (gx >= 0 && gx < _w && gy >= _at && gy <= _ab)
                canvas->SetPixel(gx, gy, 120, 160, 220);
        }
    }

    bool isDone() const override {
        return (_x < float(-_tailLen - 4) ||
                _x > float(_w + _tailLen + 4) ||
                _y > float(_ab + 2));
    }

    const std::string& name()       const override { static std::string n = "comet";    return n; }
    const std::string& layer()      const override { static std::string l = "celestial"; return l; }
    bool               persistent() const override { return false; }

private:
    int              _w, _h, _at, _ab;
    nlohmann::json   _cfg;
    WeatherAnimator* _animator;
    float _x = 0.0f, _y = 0.0f, _vx = 0.0f, _vy = 0.0f;
    int   _tailLen = 12, _frame = 0;
};

extern "C" std::unique_ptr<Animation> create_comet(
    int w, int h, const nlohmann::json& cfg, WeatherAnimator* a)
{
    return std::make_unique<CometAnimation>(w, h, cfg, a);
}
