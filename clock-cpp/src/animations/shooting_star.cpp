#include "Animation.h"
#include "WeatherAnimator.h"
#include <nlohmann/json.hpp>

// Chance-based shooting star animation.
// Port target: animations/shooting_star.py
// Key features to implement:
//   - Only spawns under CLEAR or PARTLYCLOUDY conditions
//   - Single star with vx (± random), vy (positive), fading trail
//   - isDone() returns true when life reaches 0

class ShootingStarAnimation : public Animation {
public:
    ShootingStarAnimation(int width, int height, const nlohmann::json& cfg,
                           WeatherAnimator* animator)
        : _w(width), _h(height), _cfg(cfg), _animator(animator) {}

    void update() override {}
    void draw(rgb_matrix::FrameCanvas* canvas) override { (void)canvas; }
    bool isDone() const override { return true; }

    const std::string& name()       const override { static std::string n = "shooting_star"; return n; }
    const std::string& layer()      const override { static std::string l = "celestial";      return l; }
    bool               persistent() const override { return false; }

private:
    int              _w, _h;
    nlohmann::json   _cfg;
    WeatherAnimator* _animator;
};

extern "C" std::unique_ptr<Animation> createAnimation(
    int w, int h, const nlohmann::json& cfg, WeatherAnimator* a)
{
    return std::make_unique<ShootingStarAnimation>(w, h, cfg, a);
}
