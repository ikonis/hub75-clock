#include "Animation.h"
#include "WeatherAnimator.h"
#include <nlohmann/json.hpp>
#include <algorithm>

class JackOLanternAnimation : public Animation {
public:
    JackOLanternAnimation(int width, int height, const nlohmann::json& cfg,
                           WeatherAnimator* animator)
        : _w(width), _h(height), _cfg(cfg), _animator(animator)
    {
        _at      = animator->animTop;
        _ab      = animator->animBottom;
        _ox      = width - 12;
        _oy      = _ab - 8;
        _frame   = 0;
        _flicker = 0;
        _total   = 30 + 90 + 30;
    }

    void update() override {
        ++_frame;
        _flicker = (_frame / 7) % 3;
    }

    void draw(rgb_matrix::FrameCanvas* canvas) override {
        static const struct Pixel { int dx, dy, r, g, b; } BODY[] = {
            {3,0,200,100,0},{4,0,220,110,0},{5,0,200,100,0},
            {1,1,180,80,0},{2,1,210,105,0},{3,1,230,115,0},{4,1,240,120,0},
            {5,1,230,115,0},{6,1,210,105,0},{7,1,180,80,0},
            {0,2,160,70,0},{1,2,200,100,0},{2,2,220,110,0},{3,2,235,118,0},
            {4,2,240,120,0},{5,2,235,118,0},{6,2,220,110,0},{7,2,200,100,0},{8,2,160,70,0},
            {0,3,160,70,0},{1,3,200,100,0},{2,3,220,110,0},{3,3,235,118,0},
            {4,3,240,120,0},{5,3,235,118,0},{6,3,220,110,0},{7,3,200,100,0},{8,3,160,70,0},
            {1,4,180,80,0},{2,4,210,105,0},{3,4,225,112,0},{4,4,230,115,0},
            {5,4,225,112,0},{6,4,210,105,0},{7,4,180,80,0},
            {2,5,180,80,0},{3,5,200,100,0},{4,5,200,100,0},{5,5,200,100,0},{6,5,180,80,0},
            {3,6,160,70,0},{4,6,160,70,0},{5,6,160,70,0},
            {4,-1,80,120,20},  // stem
        };
        static const struct { int dx, dy; } EYES[] = {
            {2,1},{1,2},{2,2},{3,2},
            {6,1},{5,2},{6,2},{7,2},
        };
        static const struct { int dx, dy; } NOSE[] = {{4,3},{3,4},{4,4},{5,4}};
        static const struct { int dx, dy; } MOUTH[] = {
            {1,5},{2,4},{3,5},{4,4},{5,5},{6,4},{7,5}
        };

        float alpha = _alpha();
        alpha = std::max(0.0f, std::min(1.0f, alpha));
        int ox = _ox, oy = _oy;

        for (const auto& p : BODY) {
            int px = ox + p.dx, py = oy + p.dy;
            if (px >= 0 && px < _w && py >= _at && py <= _ab)
                canvas->SetPixel(px, py, int(p.r*alpha), int(p.g*alpha), int(p.b*alpha));
        }
        int eye_r = int((200 + _flicker * 20) * alpha);
        int eye_g = int((160 + _flicker * 15) * alpha);
        for (const auto& e : EYES) {
            int px = ox + e.dx, py = oy + e.dy;
            if (px >= 0 && px < _w && py >= _at && py <= _ab)
                canvas->SetPixel(px, py, eye_r, eye_g, 0);
        }
        int nose_r = int(180 * alpha), nose_g = int(140 * alpha);
        for (const auto& n : NOSE) {
            int px = ox + n.dx, py = oy + n.dy;
            if (px >= 0 && px < _w && py >= _at && py <= _ab)
                canvas->SetPixel(px, py, nose_r, nose_g, 0);
        }
        for (const auto& m : MOUTH) {
            int px = ox + m.dx, py = oy + m.dy;
            if (px >= 0 && px < _w && py >= _at && py <= _ab)
                canvas->SetPixel(px, py, 0, 0, 0);
        }
    }

    bool isDone() const override { return _frame >= _total; }

    const std::string& name()       const override { static std::string n = "jack_o_lantern"; return n; }
    const std::string& layer()      const override { static std::string l = "foreground";      return l; }
    bool               persistent() const override { return false; }

private:
    int              _w, _h, _at, _ab;
    nlohmann::json   _cfg;
    WeatherAnimator* _animator;
    int _ox = 0, _oy = 0, _frame = 0, _flicker = 0, _total = 150;

    float _alpha() const {
        int f = _frame;
        if (f < 30)  return float(f) / 30.0f;
        if (f < 120) return 1.0f;
        return 1.0f - float(f - 120) / 30.0f;
    }
};

extern "C" std::unique_ptr<Animation> create_jack_o_lantern(
    int w, int h, const nlohmann::json& cfg, WeatherAnimator* a)
{
    return std::make_unique<JackOLanternAnimation>(w, h, cfg, a);
}
