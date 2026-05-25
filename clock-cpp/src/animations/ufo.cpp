#include "Animation.h"
#include "WeatherAnimator.h"
#include <nlohmann/json.hpp>
#include <cmath>
#include <random>
#include <algorithm>

class UfoAnimation : public Animation {
public:
    UfoAnimation(int width, int height, const nlohmann::json& cfg,
                 WeatherAnimator* animator)
        : _w(width), _h(height), _cfg(cfg), _animator(animator)
    {
        static std::mt19937 rng{std::random_device{}()};
        std::uniform_int_distribution<int>    rndY(2, 8);
        std::uniform_real_distribution<float> rnd01(0.0f, 1.0f);

        _at            = animator->animTop;
        _ab            = animator->animBottom;

        float _speedMult = 1.0f;
        if (cfg.contains("animation_settings") && cfg["animation_settings"].contains("ufo"))
            _speedMult = cfg["animation_settings"]["ufo"].value("speed", 1.0f);

        _x             = float(width);
        _y             = float(_at + rndY(rng));
        _vx            = -(0.25f + rnd01(rng) * 0.2f) * _speedMult;
        _wobble        = rnd01(rng) * float(M_PI) * 2.0f;
        _lightPhase    = 0;
        _mode          = Mode::Fly;
        _beamTriggered = false;
        _beamFrame     = 0;
        _figureY       = 0.0f;
    }

    void update() override {
        static std::mt19937 rng{std::random_device{}()};
        std::uniform_real_distribution<float> rnd01(0.0f, 1.0f);

        _wobble     += 0.08f;
        _lightPhase = (_lightPhase + 1) % (3 * 6);

        if (_mode == Mode::Fly) {
            _x += _vx;
            if (!_beamTriggered &&
                _x >= float(_w) * 0.2f && _x <= float(_w) * 0.65f &&
                rnd01(rng) < 0.006f)
            {
                _mode          = Mode::BeamIn;
                _beamTriggered = true;
                _beamFrame     = 0;
                _figureY       = float(_ab - 3);
            }
        } else if (_mode == Mode::BeamIn) {
            if (++_beamFrame >= 36) {
                _mode      = Mode::Abduct;
                _beamFrame = 0;
            }
        } else if (_mode == Mode::Abduct) {
            _figureY -= 0.225f;
            ++_beamFrame;
            if (_figureY < _y + 6.0f) {
                _mode      = Mode::BeamOut;
                _beamFrame = 0;
            }
        } else if (_mode == Mode::BeamOut) {
            if (++_beamFrame >= 30)
                _mode = Mode::Fly;
        }
    }

    void draw(rgb_matrix::FrameCanvas* canvas) override {
        static const struct Pixel { int dx, dy, r, g, b; } BODY[] = {
            {3,0,120,220,140},{4,0,140,255,160},{5,0,120,220,140},
            {1,1,60,160,70},{2,1,90,200,100},{3,1,110,230,120},{4,1,120,240,130},
            {5,1,110,230,120},{6,1,90,200,100},{7,1,60,160,70},
            {0,2,40,100,50},{1,2,70,170,80},{2,2,100,210,110},{3,2,110,220,120},
            {4,2,120,230,130},{5,2,110,220,120},{6,2,100,210,110},{7,2,70,170,80},{8,2,40,100,50},
            {1,3,50,140,60},{2,3,70,170,80},{3,3,80,180,90},{4,3,90,190,100},
            {5,3,80,180,90},{6,3,70,170,80},{7,3,50,140,60},
        };
        // Beam shape: (half_width, alpha_factor) per row below UFO belly
        static const int    BEAM_HW[] = {0, 1, 1, 2, 2, 3, 3, 4};
        static const float  BEAM_AF[] = {1.0f, 0.9f, 0.85f, 0.8f, 0.75f, 0.7f, 0.65f, 0.6f};
        static const int    BEAM_N    = 8;

        int ox = int(std::round(_x));
        int oy = int(std::round(_y + std::sin(_wobble) * 1.2f));

        // Draw beam behind UFO body
        if (_mode == Mode::BeamIn || _mode == Mode::Abduct || _mode == Mode::BeamOut) {
            int intensity = 0;
            if      (_mode == Mode::BeamIn)  intensity = std::min(50, _beamFrame * 3);
            else if (_mode == Mode::Abduct)  intensity = 50;
            else if (_mode == Mode::BeamOut) intensity = std::max(0, 50 - _beamFrame * 4);

            if (intensity > 0) {
                int cx     = ox + 4;
                int base_y = oy + 5;
                for (int row = 0; row < BEAM_N; ++row) {
                    int by = base_y + row;
                    if (by > _ab) break;
                    int br = int(float(intensity) * BEAM_AF[row]);
                    for (int bx = cx - BEAM_HW[row]; bx <= cx + BEAM_HW[row]; ++bx) {
                        if (bx >= 0 && bx < _w && by >= _at && by <= _ab)
                            canvas->SetPixel(bx, by, 0, br, br / 2);
                    }
                }
            }

            // Stick figure during abduction
            if (_mode == Mode::Abduct) {
                static const struct { int ddx, ddy; } FIGURE[] = {
                    {0,0},{0,1},{-1,1},{1,1},{-1,2},{1,2}
                };
                int fx = ox + 4;
                int fy = int(std::round(_figureY));
                for (const auto& f : FIGURE) {
                    int px = fx + f.ddx, py = fy + f.ddy;
                    if (px >= 0 && px < _w && py >= _at && py <= _ab)
                        canvas->SetPixel(px, py, 200, 200, 200);
                }
            }
        }

        // Body
        for (const auto& p : BODY) {
            int px = ox + p.dx, py = oy + p.dy;
            if (px >= 0 && px < _w && py >= _at && py <= _ab)
                canvas->SetPixel(px, py, p.r, p.g, p.b);
        }

        // Cycling belly lights
        static const struct { int dx, dy; } LIGHTS[] = {{2,4},{4,4},{6,4}};
        int li = _lightPhase / 6;
        for (int i = 0; i < 3; ++i) {
            int px = ox + LIGHTS[i].dx, py = oy + LIGHTS[i].dy;
            if (px >= 0 && px < _w && py >= _at && py <= _ab) {
                if (i == li) canvas->SetPixel(px, py, 0, 255, 180);
                else         canvas->SetPixel(px, py, 0,  60,  40);
            }
        }

        // Glow trail (fly mode only)
        if (_mode == Mode::Fly) {
            for (int i = 1; i < 5; ++i) {
                int gx = ox + 9 + i;
                int gb = std::max(0, 20 - i * 5);
                if (gx >= 0 && gx < _w && oy + 2 >= _at && oy + 2 <= _ab)
                    canvas->SetPixel(gx, oy + 2, 0, gb, gb / 2);
            }
        }
    }

    bool isDone() const override { return _x < -10.0f; }

    const std::string& name()       const override { static std::string n = "ufo";        return n; }
    const std::string& layer()      const override { static std::string l = "foreground"; return l; }
    bool               persistent() const override { return false; }

private:
    enum class Mode { Fly, BeamIn, Abduct, BeamOut };

    int              _w, _h, _at, _ab;
    nlohmann::json   _cfg;
    WeatherAnimator* _animator;
    float _x = 0.0f, _y = 0.0f, _vx = 0.0f, _wobble = 0.0f, _figureY = 0.0f;
    int   _lightPhase = 0, _beamFrame = 0;
    Mode  _mode = Mode::Fly;
    bool  _beamTriggered = false;
};

extern "C" std::unique_ptr<Animation> create_ufo(
    int w, int h, const nlohmann::json& cfg, WeatherAnimator* a)
{
    return std::make_unique<UfoAnimation>(w, h, cfg, a);
}
