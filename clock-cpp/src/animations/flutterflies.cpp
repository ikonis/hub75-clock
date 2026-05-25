#include "Animation.h"
#include "WeatherAnimator.h"
#include <nlohmann/json.hpp>
#include <algorithm>
#include <array>
#include <cmath>
#include <random>
#include <vector>

struct Flutterfly {
    float x;
    float y;
    float angle;
    float speed;
    float turn;
    float wave;
    int flapOffset;
    int cr;
    int cg;
    int cb;
};

class FlutterfliesAnimation : public Animation {
public:
    FlutterfliesAnimation(int width, int height, const nlohmann::json& cfg,
                          WeatherAnimator* animator)
        : _w(width)
    {
        static std::mt19937 rng{std::random_device{}()};
        _at = animator->animTop;
        _ab = animator->animBottom;

        float speedMult = 1.0f;
        if (cfg.contains("animation_settings") && cfg["animation_settings"].contains("flutterflies")) {
            speedMult = cfg["animation_settings"]["flutterflies"].value("speed", 1.0f);
        }

        static const std::array<std::array<int, 3>, 5> pastels = {{
            {{100, 160, 255}},
            {{255, 240, 100}},
            {{255, 130, 180}},
            {{130, 230, 140}},
            {{255, 170,  80}},
        }};
        std::array<int, 5> order = {{0, 1, 2, 3, 4}};
        std::shuffle(order.begin(), order.end(), rng);

        std::uniform_int_distribution<int> countDist(4, 6);
        std::uniform_int_distribution<int> xDist(2, std::max(2, width - 2));
        std::uniform_int_distribution<int> yDist(_at + 2, std::max(_at + 2, _ab - 2));
        std::uniform_real_distribution<float> rnd01(0.0f, 1.0f);
        std::uniform_int_distribution<int> flapDist(0, 11);

        int count = countDist(rng);
        for (int i = 0; i < count; ++i) {
            const auto& color = pastels[order[i % order.size()]];
            _flies.push_back(Flutterfly{
                float(xDist(rng)),
                float(yDist(rng)),
                rnd01(rng) * float(M_PI) * 2.0f,
                (0.18f + rnd01(rng) * 0.12f) * speedMult,
                (0.08f + rnd01(rng) * 0.06f) * speedMult,
                rnd01(rng) * float(M_PI) * 2.0f,
                flapDist(rng),
                color[0],
                color[1],
                color[2],
            });
        }
        _waveSpeed = 0.10f * speedMult;
    }

    void update() override {
        ++_frame;
        for (auto& f : _flies) {
            f.wave += _waveSpeed;
            f.angle += f.turn * std::sin(f.wave);
            f.x += f.speed * std::cos(f.angle);
            f.y += f.speed * std::sin(f.angle) * 0.5f;

            if (f.x < -2.0f) f.x = float(_w + 1);
            else if (f.x > float(_w + 1)) f.x = -1.0f;

            if (f.y < float(_at)) f.y = float(_ab);
            else if (f.y > float(_ab)) f.y = float(_at);
        }
    }

    void draw(rgb_matrix::FrameCanvas* canvas) override {
        static const struct Pixel { int dx; int dy; float brt; } open[] = {
            {-1, 0, 0.80f}, {0, 0, 1.00f}, {1, 0, 0.80f},
        };
        static const Pixel closed[] = {
            {0, 0, 1.00f}, {0, 1, 0.70f},
        };

        for (const auto& f : _flies) {
            bool isOpen = ((_frame + f.flapOffset) / 5) % 2 == 0;
            const Pixel* sprite = isOpen ? open : closed;
            int count = isOpen ? 3 : 2;
            int ox = int(std::round(f.x));
            int oy = int(std::round(f.y));

            for (int i = 0; i < count; ++i) {
                int px = ox + sprite[i].dx;
                int py = oy + sprite[i].dy;
                if (px >= 0 && px < _w && py >= _at && py <= _ab) {
                    canvas->SetPixel(px, py,
                        int(f.cr * sprite[i].brt),
                        int(f.cg * sprite[i].brt),
                        int(f.cb * sprite[i].brt));
                }
            }
        }
    }

    bool isDone() const override { return false; }
    const std::string& name() const override { static std::string n = "flutterflies"; return n; }
    const std::string& layer() const override { static std::string l = "foreground"; return l; }
    bool persistent() const override { return true; }

private:
    int _w = 0;
    int _at = 0;
    int _ab = 0;
    int _frame = 0;
    float _waveSpeed = 0.10f;
    std::vector<Flutterfly> _flies;
};

extern "C" std::unique_ptr<Animation> create_flutterflies(
    int w, int h, const nlohmann::json& cfg, WeatherAnimator* a)
{
    return std::make_unique<FlutterfliesAnimation>(w, h, cfg, a);
}
