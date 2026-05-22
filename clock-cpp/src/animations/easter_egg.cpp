#include "Animation.h"
#include "WeatherAnimator.h"
#include <nlohmann/json.hpp>

class EasterEggAnimation : public Animation {
public:
    EasterEggAnimation(int width, int height, const nlohmann::json& cfg,
                       WeatherAnimator* animator)
        : _w(width), _h(height), _cfg(cfg), _animator(animator) {}

    void update() override {}
    void draw(rgb_matrix::FrameCanvas* canvas) override { (void)canvas; }
    bool isDone() const override { return false; }

    const std::string& name()       const override { static std::string n = "easter_egg"; return n; }
    const std::string& layer()      const override { static std::string l = "foreground"; return l; }
    bool               persistent() const override { return false; }

private:
    int              _w, _h;
    nlohmann::json   _cfg;
    WeatherAnimator* _animator;
};

extern "C" std::unique_ptr<Animation> create_easter_egg(
    int w, int h, const nlohmann::json& cfg, WeatherAnimator* a)
{
    return std::make_unique<EasterEggAnimation>(w, h, cfg, a);
}
