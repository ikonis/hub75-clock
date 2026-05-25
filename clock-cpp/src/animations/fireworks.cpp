#include "Animation.h"
#include "WeatherAnimator.h"
#include <nlohmann/json.hpp>
#include <cmath>
#include <random>
#include <vector>
#include <algorithm>

static constexpr float FW_BASE_GRAVITY = 0.06f;

struct FWSpark {
    float x, y, vx, vy;
    int   life, maxLife;
    int   r, g, b;
};

struct FWRocket {
    enum class Phase { Wait, Launch, Explode, Done } phase;
    int   delay;
    float x, y, vy;
    std::vector<FWSpark> sparks;
};

class FireworksAnimation : public Animation {
public:
    FireworksAnimation(int width, int height, const nlohmann::json& cfg,
                       WeatherAnimator* animator)
        : _w(width), _h(height), _cfg(cfg), _animator(animator)
    {
        static std::mt19937 rng{std::random_device{}()};
        std::uniform_int_distribution<int>    rndN(1, 3);
        std::uniform_int_distribution<int>    rndDelay(5, 12);

        _at = animator->animTop;
        _ab = animator->animBottom;

        float _speedMult = 1.0f;
        if (cfg.contains("animation_settings") && cfg["animation_settings"].contains("fireworks"))
            _speedMult = cfg["animation_settings"]["fireworks"].value("speed", 1.0f);

        _gravity   = FW_BASE_GRAVITY * _speedMult;
        _speedMult_ = _speedMult;

        int n = rndN(rng);
        int delay = 0;
        for (int i = 0; i < n; ++i) {
            _rockets.push_back(_makeRocket(delay, rng));
            delay += rndDelay(rng);
        }
    }

    void update() override {
        static std::mt19937 rng{std::random_device{}()};
        for (auto& rk : _rockets) {
            if (rk.phase == FWRocket::Phase::Wait) {
                if (--rk.delay <= 0) rk.phase = FWRocket::Phase::Launch;
            } else if (rk.phase == FWRocket::Phase::Launch) {
                rk.vy += _gravity;
                rk.y  += rk.vy;
                if (rk.vy >= 0.0f || rk.y <= float(_at)) {
                    rk.y = std::max(rk.y, float(_at + 1));
                    _explode(rk, rng);
                }
            } else if (rk.phase == FWRocket::Phase::Explode) {
                bool alive = false;
                for (auto& sp : rk.sparks) {
                    sp.vy += _gravity;
                    sp.x  += sp.vx;
                    sp.y  += sp.vy;
                    --sp.life;
                    if (sp.life > 0) alive = true;
                }
                if (!alive) rk.phase = FWRocket::Phase::Done;
            }
        }
    }

    void draw(rgb_matrix::FrameCanvas* canvas) override {
        for (const auto& rk : _rockets) {
            if (rk.phase == FWRocket::Phase::Launch) {
                _px(canvas, rk.x, rk.y,     255, 230, 120);
                _px(canvas, rk.x, rk.y + 1, 255, 120,   0);
                _px(canvas, rk.x, rk.y + 2, 160,  50,   0);
            } else if (rk.phase == FWRocket::Phase::Explode) {
                for (const auto& sp : rk.sparks) {
                    if (sp.life <= 0) continue;
                    float alpha = float(sp.life) / float(sp.maxLife);
                    _blend(canvas, sp.x, sp.y, sp.r, sp.g, sp.b, alpha);
                    float spd = std::sqrt(sp.vx * sp.vx + sp.vy * sp.vy);
                    if (spd > 0.01f) {
                        float uvx = sp.vx / spd, uvy = sp.vy / spd;
                        _blend(canvas, sp.x - uvx, sp.y - uvy,
                            sp.r, sp.g, sp.b, alpha * 0.45f);
                        _blend(canvas, sp.x - 2*uvx, sp.y - 2*uvy,
                            sp.r, sp.g, sp.b, alpha * 0.22f);
                    }
                }
            }
        }
    }

    bool isDone() const override {
        for (const auto& rk : _rockets)
            if (rk.phase != FWRocket::Phase::Done) return false;
        return true;
    }

    const std::string& name()       const override { static std::string n = "fireworks";  return n; }
    const std::string& layer()      const override { static std::string l = "foreground"; return l; }
    bool               persistent() const override { return false; }

private:
    int              _w, _h, _at, _ab;
    nlohmann::json   _cfg;
    WeatherAnimator* _animator;
    std::vector<FWRocket> _rockets;
    float _gravity   = FW_BASE_GRAVITY;
    float _speedMult_ = 1.0f;

    void _px(rgb_matrix::FrameCanvas* canvas, float fx, float fy, int r, int g, int b) {
        int px = int(std::round(fx)), py = int(std::round(fy));
        if (px >= 0 && px < _w && py >= _at && py <= _ab)
            render::SetPixel(canvas, px, py,
                std::max(0, std::min(255, r)),
                std::max(0, std::min(255, g)),
                std::max(0, std::min(255, b)));
    }

    void _blend(rgb_matrix::FrameCanvas* canvas, float fx, float fy, int r, int g, int b, float alpha) {
        int px = int(std::round(fx)), py = int(std::round(fy));
        if (px >= 0 && px < _w && py >= _at && py <= _ab)
            render::BlendPixel(canvas, px, py, r, g, b, alpha);
    }

    FWRocket _makeRocket(int delay, std::mt19937& rng) {
        std::uniform_int_distribution<int> rndX(8, _w - 8);
        int zone     = _ab - _at;
        int target_y = _at + std::uniform_int_distribution<int>(1, std::max(1, zone / 3))(rng);
        float dist   = float(_ab - target_y);
        float vy0    = -std::sqrt(2.0f * _gravity * std::max(dist, 1.0f));
        FWRocket rk;
        rk.phase = FWRocket::Phase::Wait;
        rk.delay = delay;
        rk.x     = float(rndX(rng));
        rk.y     = float(_ab);
        rk.vy    = vy0;
        return rk;
    }

    void _explode(FWRocket& rk, std::mt19937& rng) {
        static const int COLORS[][3] = {
            {255,255,255}, {255,200,20}, {255,40,40},
            {60,120,255},  {40,255,80},  {200,60,255},
        };
        rk.phase = FWRocket::Phase::Explode;
        std::uniform_int_distribution<int>    rndN(16, 20);
        std::uniform_real_distribution<float> rndAngle(-0.3f, 0.3f);
        std::uniform_real_distribution<float> rndSpeed(0.8f, 2.4f);
        std::uniform_int_distribution<int>    rndLife(30, 42);
        std::uniform_int_distribution<int>    rndCol(0, 5);

        int n = rndN(rng);
        for (int i = 0; i < n; ++i) {
            float angle = float(2.0 * M_PI * i / n) + rndAngle(rng);
            float speed = rndSpeed(rng) * _speedMult_;
            const int* col = COLORS[rndCol(rng)];
            int life = rndLife(rng);
            FWSpark sp;
            sp.x = rk.x; sp.y = rk.y;
            sp.vx = std::cos(angle) * speed;
            sp.vy = std::sin(angle) * speed;
            sp.life = sp.maxLife = life;
            sp.r = col[0]; sp.g = col[1]; sp.b = col[2];
            rk.sparks.push_back(sp);
        }
    }
};

extern "C" std::unique_ptr<Animation> create_fireworks(
    int w, int h, const nlohmann::json& cfg, WeatherAnimator* a)
{
    return std::make_unique<FireworksAnimation>(w, h, cfg, a);
}
