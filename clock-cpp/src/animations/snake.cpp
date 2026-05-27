#include "Animation.h"
#include "WeatherAnimator.h"

#include <algorithm>
#include <cmath>
#include <memory>
#include <nlohmann/json.hpp>
#include <random>
#include <set>
#include <utility>
#include <vector>

class SnakeAnimation : public Animation {
public:
    SnakeAnimation(int width, int height, const nlohmann::json& cfg,
                   WeatherAnimator* animator)
        : _w(width), _h(height), _animator(animator)
    {
        _at = animator->animTop;
        _ab = animator->animBottom;
        _playH = _ab - _at + 1;
        if (cfg.contains("animation") && cfg["animation"].is_object())
            _fps = std::max(1, cfg["animation"].value("fps", 15));
        if (cfg.contains("animation_settings") &&
            cfg["animation_settings"].contains("snake") &&
            cfg["animation_settings"]["snake"].is_object()) {
            _speedMult = cfg["animation_settings"]["snake"].value("speed", 1.0f);
        }
        _stepEvery = std::max(1, int(std::round(float(_fps) / std::max(1.0f, 8.0f * _speedMult))));
        reset();
    }

    void update() override {
        ++_frame;
        if (_crashFrames > 0) {
            --_crashFrames;
            if (_crashFrames == 0) reset();
            return;
        }
        if (_frame % _stepEvery == 0) step();
    }

    void draw(rgb_matrix::FrameCanvas* canvas) override {
        for (const auto& c : _cherries) {
            for (int dy = 0; dy < CHERRY_SIZE; ++dy) {
                for (int dx = 0; dx < CHERRY_SIZE; ++dx) {
                    int px = c.first + dx;
                    int py = c.second + dy;
                    if (px < 0 || px >= _w || py < _at || py > _ab) continue;
                    if (dx == 1 && dy == 1)
                        render::SetPixel(canvas, px, py, 255, 45, 60);
                    else
                        render::SetPixel(canvas, px, py, 170, 0, 35);
                }
            }
        }

        bool crash = _crashFrames > 0 && (_frame % 2 == 0);
        int n = int(_snake.size());
        for (int rev = 0; rev < n; ++rev) {
            const auto& p = _snake[n - 1 - rev];
            int x = p.first;
            int y = p.second;
            if (x < 0 || x >= _w || y < _at || y > _ab) continue;
            if (crash) {
                render::SetPixel(canvas, x, y, 220, 30, 30);
            } else if (rev == n - 1) {
                render::SetPixel(canvas, x, y, 210, 255, 120);
            } else {
                int shade = 100 + int(85.0f * (float(rev) / float(std::max(1, n - 1))));
                render::SetPixel(canvas, x, y, 35, shade, 55);
            }
        }
    }

    bool isDone() const override { return false; }

    const std::string& name() const override { static std::string n = "snake"; return n; }
    const std::string& layer() const override { static std::string l = "foreground"; return l; }
    bool persistent() const override { return true; }

private:
    using Pt = std::pair<int, int>;
    static constexpr int CHERRY_COUNT = 4;
    static constexpr int CHERRY_SIZE = 3;

    int rndInt(int lo, int hi) {
        if (hi < lo) hi = lo;
        std::uniform_int_distribution<int> dist(lo, hi);
        return dist(_rng);
    }

    float rnd01() {
        std::uniform_real_distribution<float> dist(0.0f, 1.0f);
        return dist(_rng);
    }

    Pt wrap(int x, int y) const {
        int wx = ((x % _w) + _w) % _w;
        int localY = y - _at;
        int wy = _at + (((localY % _playH) + _playH) % _playH);
        return {wx, wy};
    }

    void reset() {
        static const Pt dirs[] = {{1, 0}, {-1, 0}, {0, 1}, {0, -1}};
        _dir = dirs[rndInt(0, 3)];

        int length = rndInt(8, 12);
        int margin = length + 2;
        int x, y;
        if (_dir.first != 0) {
            x = rndInt(margin, std::max(margin, _w - margin - 1));
            y = _at + rndInt(3, std::max(3, _playH - 4));
        } else {
            x = rndInt(4, std::max(4, _w - 5));
            y = _at + rndInt(margin, std::max(margin, _playH - margin - 1));
        }

        _snake.clear();
        for (int i = 0; i < length; ++i) {
            _snake.push_back({x - _dir.first * i, y - _dir.second * i});
        }
        _grow = 0;
        _cherries.clear();
        spawnCherries();
    }

    void spawnCherries() {
        int attempts = 0;
        while (int(_cherries.size()) < CHERRY_COUNT && attempts < 300) {
            ++attempts;
            int x = rndInt(0, std::max(0, _w - CHERRY_SIZE));
            int y = rndInt(_at, std::max(_at, _ab - CHERRY_SIZE + 1));

            bool blocked = false;
            for (int dy = 0; dy < CHERRY_SIZE && !blocked; ++dy) {
                for (int dx = 0; dx < CHERRY_SIZE; ++dx) {
                    if (std::find(_snake.begin(), _snake.end(), Pt{x + dx, y + dy}) != _snake.end()) {
                        blocked = true;
                        break;
                    }
                }
            }
            if (blocked) continue;

            bool tooClose = false;
            for (const auto& c : _cherries) {
                if (std::abs(x - c.first) < 5 && std::abs(y - c.second) < 5) {
                    tooClose = true;
                    break;
                }
            }
            if (!tooClose) _cherries.push_back({x, y});
        }
    }

    int torusDistance(int x, int y, int tx, int ty) const {
        int dx = std::abs(x - tx);
        dx = std::min(dx, _w - dx);
        int dy = std::abs((y - _at) - (ty - _at));
        dy = std::min(dy, _playH - dy);
        return dx + dy;
    }

    Pt nearestCherryCenter(int x, int y) const {
        Pt best{_w / 2, _at + _playH / 2};
        int bestDist = 9999;
        for (const auto& c : _cherries) {
            Pt center{c.first + CHERRY_SIZE / 2, c.second + CHERRY_SIZE / 2};
            int dist = torusDistance(x, y, center.first, center.second);
            if (dist < bestDist) {
                bestDist = dist;
                best = center;
            }
        }
        return best;
    }

    Pt chooseDirection() {
        Pt head = _snake.front();
        std::vector<Pt> choices = {
            _dir,
            {-_dir.second, _dir.first},
            {_dir.second, -_dir.first},
        };

        if (_cherries.empty()) {
            std::shuffle(choices.begin(), choices.end(), _rng);
            return choices.front();
        }

        Pt target = nearestCherryCenter(head.first, head.second);
        std::set<Pt> body;
        int bodyLimit = int(_snake.size()) - (_grow <= 0 ? 1 : 0);
        for (int i = 0; i < bodyLimit; ++i) body.insert(_snake[i]);

        struct Scored { int score; float tie; Pt dir; };
        std::vector<Scored> scored;
        for (const auto& d : choices) {
            Pt next = wrap(head.first + d.first, head.second + d.second);
            bool crash = body.find(next) != body.end();
            int score = torusDistance(next.first, next.second, target.first, target.second) + (crash ? 999 : 0);
            scored.push_back({score, rnd01(), d});
        }
        std::sort(scored.begin(), scored.end(), [](const Scored& a, const Scored& b) {
            if (a.score != b.score) return a.score < b.score;
            return a.tie < b.tie;
        });

        if (rnd01() < 0.12f) {
            std::vector<Pt> safe;
            for (const auto& s : scored) {
                if (s.score < 999) safe.push_back(s.dir);
            }
            if (!safe.empty()) return safe[rndInt(0, int(safe.size()) - 1)];
        }
        return scored.front().dir;
    }

    void eatCherryAt(int x, int y) {
        for (auto it = _cherries.begin(); it != _cherries.end(); ++it) {
            if (x >= it->first && x < it->first + CHERRY_SIZE &&
                y >= it->second && y < it->second + CHERRY_SIZE) {
                _cherries.erase(it);
                _grow += 5;
                if (_cherries.empty()) spawnCherries();
                return;
            }
        }
    }

    void step() {
        _dir = chooseDirection();
        Pt head = _snake.front();
        Pt next = wrap(head.first + _dir.first, head.second + _dir.second);

        std::set<Pt> body;
        int bodyLimit = int(_snake.size()) - (_grow <= 0 ? 1 : 0);
        for (int i = 0; i < bodyLimit; ++i) body.insert(_snake[i]);
        if (body.find(next) != body.end()) {
            _crashFrames = 10;
            return;
        }

        _snake.insert(_snake.begin(), next);
        eatCherryAt(next.first, next.second);
        if (_grow > 0) {
            --_grow;
        } else {
            _snake.pop_back();
        }
    }

    int _w, _h, _at = 0, _ab = 0, _playH = 1;
    WeatherAnimator* _animator;
    std::mt19937 _rng{std::random_device{}()};
    std::vector<Pt> _snake;
    std::vector<Pt> _cherries;
    Pt _dir{1, 0};
    int _frame = 0;
    int _fps = 15;
    int _stepEvery = 2;
    int _grow = 0;
    int _crashFrames = 0;
    float _speedMult = 1.0f;
};

extern "C" std::unique_ptr<Animation> create_snake(
    int w, int h, const nlohmann::json& cfg, WeatherAnimator* a)
{
    return std::make_unique<SnakeAnimation>(w, h, cfg, a);
}
