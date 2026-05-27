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
        _cols = std::max(1, _w / CELL_SIZE);
        _rows = std::max(1, _playH / CELL_SIZE);
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
            drawBlock(canvas, c, {170, 0, 35}, {255, 45, 60}, true);
        }

        bool crash = _crashFrames > 0 && (_frame % 2 == 0);
        int n = int(_snake.size());
        for (int rev = 0; rev < n; ++rev) {
            const auto& cell = _snake[n - 1 - rev];
            if (crash) {
                drawBlock(canvas, cell, {220, 30, 30});
            } else if (rev == n - 1) {
                drawBlock(canvas, cell, {210, 255, 120});
            } else {
                int shade = 100 + int(85.0f * (float(rev) / float(std::max(1, n - 1))));
                drawBlock(canvas, cell, {35, shade, 55});
            }
        }
    }

    bool isDone() const override { return false; }

    const std::string& name() const override { static std::string n = "snake"; return n; }
    const std::string& layer() const override { static std::string l = "foreground"; return l; }
    bool persistent() const override { return true; }

private:
    using Pt = std::pair<int, int>;
    using Color = std::array<int, 3>;
    static constexpr int CELL_SIZE = 3;
    static constexpr int CHERRY_COUNT = 4;

    int rndInt(int lo, int hi) {
        if (hi < lo) hi = lo;
        std::uniform_int_distribution<int> dist(lo, hi);
        return dist(_rng);
    }

    float rnd01() {
        std::uniform_real_distribution<float> dist(0.0f, 1.0f);
        return dist(_rng);
    }

    Pt wrapCell(int x, int y) const {
        return {((x % _cols) + _cols) % _cols, ((y % _rows) + _rows) % _rows};
    }

    Pt cellToPixel(const Pt& cell) const {
        return {cell.first * CELL_SIZE, _at + cell.second * CELL_SIZE};
    }

    void drawBlock(rgb_matrix::FrameCanvas* canvas, const Pt& cell, Color color,
                   Color highlight = {0, 0, 0}, bool useHighlight = false) {
        Pt origin = cellToPixel(cell);
        for (int dy = 0; dy < CELL_SIZE; ++dy) {
            for (int dx = 0; dx < CELL_SIZE; ++dx) {
                int px = origin.first + dx;
                int py = origin.second + dy;
                if (px < 0 || px >= _w || py < _at || py > _ab) continue;
                const Color& c = (useHighlight && dx == 1 && dy == 1) ? highlight : color;
                render::SetPixel(canvas, px, py, c[0], c[1], c[2]);
            }
        }
    }

    void reset() {
        static const Pt dirs[] = {{1, 0}, {-1, 0}, {0, 1}, {0, -1}};
        _dir = dirs[rndInt(0, 3)];

        int length = rndInt(6, 9);
        int margin = std::min(length + 1, std::max(1, std::min(_cols, _rows) / 2));
        int x, y;
        if (_dir.first != 0) {
            x = rndInt(margin, std::max(margin, _cols - margin - 1));
            y = rndInt(1, std::max(1, _rows - 2));
        } else {
            x = rndInt(1, std::max(1, _cols - 2));
            y = rndInt(margin, std::max(margin, _rows - margin - 1));
        }

        _snake.clear();
        for (int i = 0; i < length; ++i) {
            _snake.push_back(wrapCell(x - _dir.first * i, y - _dir.second * i));
        }
        _grow = 0;
        _cherries.clear();
        spawnCherries();
    }

    void spawnCherries() {
        int attempts = 0;
        while (int(_cherries.size()) < CHERRY_COUNT && attempts < 300) {
            ++attempts;
            Pt pos{rndInt(0, _cols - 1), rndInt(0, _rows - 1)};
            if (std::find(_snake.begin(), _snake.end(), pos) != _snake.end()) continue;
            if (std::find(_cherries.begin(), _cherries.end(), pos) != _cherries.end()) continue;

            bool tooClose = false;
            for (const auto& c : _cherries) {
                if (torusDistance(pos.first, pos.second, c.first, c.second) < 3) {
                    tooClose = true;
                    break;
                }
            }
            if (!tooClose) _cherries.push_back(pos);
        }
    }

    int torusDistance(int x, int y, int tx, int ty) const {
        int dx = std::abs(x - tx);
        dx = std::min(dx, _cols - dx);
        int dy = std::abs(y - ty);
        dy = std::min(dy, _rows - dy);
        return dx + dy;
    }

    Pt nearestCherry(int x, int y) const {
        Pt best{_cols / 2, _rows / 2};
        int bestDist = 9999;
        for (const auto& c : _cherries) {
            int dist = torusDistance(x, y, c.first, c.second);
            if (dist < bestDist) {
                bestDist = dist;
                best = c;
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

        Pt target = nearestCherry(head.first, head.second);
        std::set<Pt> body;
        int bodyLimit = int(_snake.size()) - (_grow <= 0 ? 1 : 0);
        for (int i = 0; i < bodyLimit; ++i) body.insert(_snake[i]);

        struct Scored { int score; float tie; Pt dir; };
        std::vector<Scored> scored;
        for (const auto& d : choices) {
            Pt next = wrapCell(head.first + d.first, head.second + d.second);
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

    void eatCherryAt(const Pt& cell) {
        auto it = std::find(_cherries.begin(), _cherries.end(), cell);
        if (it == _cherries.end()) return;
        _cherries.erase(it);
        _grow += 3;
        if (_cherries.empty()) spawnCherries();
    }

    void step() {
        _dir = chooseDirection();
        Pt head = _snake.front();
        Pt next = wrapCell(head.first + _dir.first, head.second + _dir.second);

        std::set<Pt> body;
        int bodyLimit = int(_snake.size()) - (_grow <= 0 ? 1 : 0);
        for (int i = 0; i < bodyLimit; ++i) body.insert(_snake[i]);
        if (body.find(next) != body.end()) {
            _crashFrames = 10;
            return;
        }

        _snake.insert(_snake.begin(), next);
        eatCherryAt(next);
        if (_grow > 0) {
            --_grow;
        } else {
            _snake.pop_back();
        }
    }

    int _w, _h, _at = 0, _ab = 0, _playH = 1, _cols = 1, _rows = 1;
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
