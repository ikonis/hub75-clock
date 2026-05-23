#include "Animation.h"
#include "WeatherAnimator.h"

#include <algorithm>
#include <cmath>
#include <memory>
#include <nlohmann/json.hpp>
#include <random>
#include <vector>

class StarsAnimation : public Animation {
public:
    StarsAnimation(int width, int height, const nlohmann::json& cfg,
                   WeatherAnimator* animator)
        : _w(width), _h(height), _cfg(cfg), _animator(animator)
    {
        static std::mt19937 rng{std::random_device{}()};
        std::uniform_int_distribution<int> distX(0, width - 1);
        std::uniform_int_distribution<int> distY(animator->animTop, animator->animBottom);
        std::uniform_real_distribution<float> distPhase(0.0f, 6.2832f);
        std::uniform_real_distribution<float> distSpeed(0.05f, 0.15f);
        static const int brightnessChoices[] = {60, 80, 100, 140, 200};
        std::uniform_int_distribution<int> distBIdx(0, 4);

        float speed = 1.0f;
        if (cfg.contains("animation_settings") && cfg["animation_settings"].contains("stars"))
            speed = cfg["animation_settings"]["stars"].value("speed", 1.0f);

        int animH = animator->animBottom - animator->animTop + 1;
        int count = std::max(8, (width * animH) / 30);

        _stars.reserve(count);
        for (int i = 0; i < count; ++i) {
            _stars.push_back({
                distX(rng),
                distY(rng),
                distPhase(rng),
                distSpeed(rng) * speed,
                brightnessChoices[distBIdx(rng)],
            });
        }
    }

    void update() override {
        ++_frame;
    }

    void draw(rgb_matrix::FrameCanvas* canvas) override {
        const int at = _animator->animTop;
        const int ab = _animator->animBottom;
        for (const auto& s : _stars) {
            float phase = s.phase + float(_frame) * s.speed;
            float level = (std::sin(phase) + 1.0f) * 0.5f;
            int b = int(float(s.maxBrightness) * level);
            if (b > 5 && s.x >= 0 && s.x < _w && s.y >= at && s.y <= ab)
                canvas->SetPixel(s.x, s.y, b, b, b);
        }
    }

    bool isDone() const override { return false; }

    const std::string& name() const override { static std::string n = "stars"; return n; }
    const std::string& layer() const override { static std::string l = "celestial"; return l; }
    bool persistent() const override { return true; }

private:
    struct Star {
        int x, y;
        float phase;
        float speed;
        int maxBrightness;
    };

    int _w, _h;
    nlohmann::json _cfg;
    WeatherAnimator* _animator;
    std::vector<Star> _stars;
    int _frame = 0;
};

extern "C" std::unique_ptr<Animation> create_stars(
    int w, int h, const nlohmann::json& cfg, WeatherAnimator* a)
{
    return std::make_unique<StarsAnimation>(w, h, cfg, a);
}
