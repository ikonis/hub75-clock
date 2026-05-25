#include "Animation.h"
#include "WeatherAnimator.h"
#include <nlohmann/json.hpp>
#include <algorithm>

class SnowmanAnimation : public Animation {
public:
    SnowmanAnimation(int width, int height, const nlohmann::json& cfg,
                     WeatherAnimator* animator)
        : _w(width), _h(height), _cfg(cfg), _animator(animator)
    {
        _at       = animator->animTop;
        _ab       = animator->animBottom;
        _ox       = width - 10;
        _oy       = _ab - 8;
        _frame    = 0;
        _fadeIn   = 20;
        _hold     = 90;
        _fadeOut  = 20;
        _total    = _fadeIn + _hold + _fadeOut;
    }

    void update() override { ++_frame; }

    void draw(rgb_matrix::FrameCanvas* canvas) override {
        static const struct Pixel { int dx, dy, r, g, b; } SPRITE[] = {
            // Hat brim
            {2,0,50,50,50},{3,0,50,50,50},{4,0,50,50,50},{5,0,50,50,50},{6,0,50,50,50},
            // Hat top
            {3,-2,40,40,40},{4,-2,40,40,40},{5,-2,40,40,40},
            {3,-1,40,40,40},{4,-1,40,40,40},{5,-1,40,40,40},
            // Head
            {3,1,200,220,240},{4,1,220,240,255},{5,1,200,220,240},
            {3,2,220,240,255},{4,2,240,255,255},{5,2,220,240,255},
            {3,3,200,220,240},{4,3,220,240,255},{5,3,200,220,240},
            // Eyes (overwrite head pixels)
            {3,2,30,30,30},{5,2,30,30,30},
            // Carrot nose (overwrite)
            {4,2,255,120,0},
            // Body
            {2,4,180,200,220},{3,4,200,220,240},{4,4,210,230,255},{5,4,200,220,240},{6,4,180,200,220},
            {1,5,190,210,230},{2,5,210,230,250},{3,5,220,240,255},{4,5,230,250,255},
            {5,5,220,240,255},{6,5,210,230,250},{7,5,190,210,230},
            {2,6,200,220,240},{3,6,210,230,255},{4,6,220,240,255},{5,6,210,230,255},{6,6,200,220,240},
            {3,7,190,210,230},{4,7,200,220,240},{5,7,190,210,230},
            // Button (overwrite)
            {4,5,30,30,30},
            // Arms
            {0,5,120,80,40},{8,5,120,80,40},
        };

        float alpha = _alpha();
        alpha = std::max(0.0f, std::min(1.0f, alpha));
        for (const auto& p : SPRITE) {
            int px = _ox + p.dx, py = _oy + p.dy;
            if (px >= 0 && px < _w && py >= _at && py <= _ab)
                render::BlendPixel(canvas, px, py, p.r, p.g, p.b, alpha);
        }
    }

    bool isDone() const override { return _frame >= _total; }

    const std::string& name()       const override { static std::string n = "snowman";    return n; }
    const std::string& layer()      const override { static std::string l = "foreground"; return l; }
    bool               persistent() const override { return false; }

private:
    int              _w, _h, _at, _ab;
    nlohmann::json   _cfg;
    WeatherAnimator* _animator;
    int _ox = 0, _oy = 0, _frame = 0;
    int _fadeIn = 20, _hold = 90, _fadeOut = 20, _total = 130;

    float _alpha() const {
        int f = _frame;
        if (f < _fadeIn) return float(f) / float(_fadeIn);
        if (f < _fadeIn + _hold) return 1.0f;
        return 1.0f - float(f - _fadeIn - _hold) / float(_fadeOut);
    }
};

extern "C" std::unique_ptr<Animation> create_snowman(
    int w, int h, const nlohmann::json& cfg, WeatherAnimator* a)
{
    return std::make_unique<SnowmanAnimation>(w, h, cfg, a);
}
