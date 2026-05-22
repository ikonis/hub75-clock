#include "Animation.h"
#include "WeatherAnimator.h"
#include <nlohmann/json.hpp>

// Persistent cloud + precipitation animation.
// Port target: animations/clouds.py
// Key features to implement:
//   - Multiple cloud bodies (small/medium/large circle composites)
//   - Left-to-right wrap with randomised re-entry Y
//   - Precipitation particles owned by each cloud (rain/heavy_rain/snow/sleet)
//   - Thunderstorm lightning bolt generation with branching
//   - Sun-cloud alpha blend in _fill_circle when sun_enabled

class CloudsAnimation : public Animation {
public:
    CloudsAnimation(int width, int height, const nlohmann::json& cfg,
                    WeatherAnimator* animator)
        : _w(width), _h(height), _cfg(cfg), _animator(animator) {}

    void update() override {}
    void draw(rgb_matrix::FrameCanvas* canvas) override { (void)canvas; }
    bool isDone() const override { return false; }

    const std::string& name()       const override { static std::string n = "clouds";     return n; }
    const std::string& layer()      const override { static std::string l = "foreground"; return l; }
    bool               persistent() const override { return true; }

private:
    int              _w, _h;
    nlohmann::json   _cfg;
    WeatherAnimator* _animator;
};

extern "C" std::unique_ptr<Animation> createAnimation(
    int w, int h, const nlohmann::json& cfg, WeatherAnimator* a)
{
    return std::make_unique<CloudsAnimation>(w, h, cfg, a);
}
