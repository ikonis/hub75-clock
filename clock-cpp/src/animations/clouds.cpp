#include "Animation.h"
#include "WeatherAnimator.h"
#include <nlohmann/json.hpp>
#include <cmath>
#include <random>
#include <vector>
#include <string>
#include <array>

static constexpr int   COLOR_RAIN_R        = 22,  COLOR_RAIN_G        = 42,  COLOR_RAIN_B        = 115;
static constexpr int   COLOR_HEAVY_RAIN_R  = 10,  COLOR_HEAVY_RAIN_G  = 18,  COLOR_HEAVY_RAIN_B  = 80;
static constexpr int   COLOR_SNOW_R        = 180, COLOR_SNOW_G        = 180, COLOR_SNOW_B        = 200;
static constexpr int   COLOR_SLEET_R       = 120, COLOR_SLEET_G       = 160, COLOR_SLEET_B       = 180;
static constexpr int   COLOR_LIGHTNING_R   = 232, COLOR_LIGHTNING_G   = 232, COLOR_LIGHTNING_B   = 64;
static constexpr int   COLOR_FLASH_R       = 20,  COLOR_FLASH_G       = 20,  COLOR_FLASH_B       = 60;

struct CloudCircle { int dx, dy, r; };
struct CloudSpan   { int spanL, spanR, spanH; };

static const CloudCircle SMALL_CIRCLES[]  = { {0,0,3}, {-4,1,2}, {4,1,2} };
static const CloudCircle MEDIUM_CIRCLES[] = { {0,0,4}, {-5,1,3}, {5,1,3}, {0,-2,2} };
static const CloudCircle LARGE_CIRCLES[]  = { {0,0,5}, {-6,1,4}, {6,1,4}, {-2,-2,3}, {3,-2,3} };

static CloudSpan getSpan(const std::string& size) {
    if (size == "small")  return {-5,  5, 5};
    if (size == "large")  return {-10, 10, 8};
    return {-8, 8, 6}; // medium
}

struct Particle {
    float lx, y, vy, wobble;
    std::string type; // rain, heavy_rain, snow, sleet_fast, sleet_slow
};

struct Cloud {
    float x, y, vx;
    std::string size;
    int cr, cg, cb;
    std::vector<Particle> particles;
};

static std::array<int,3> parseHex(const std::string& h) {
    std::string s = h;
    if (!s.empty() && s[0] == '#') s = s.substr(1);
    int r = std::stoi(s.substr(0,2), nullptr, 16);
    int g = std::stoi(s.substr(2,2), nullptr, 16);
    int b = std::stoi(s.substr(4,2), nullptr, 16);
    return {r, g, b};
}

class CloudsAnimation : public Animation {
public:
    CloudsAnimation(int width, int height, const nlohmann::json& cfg,
                    WeatherAnimator* animator)
        : _w(width), _cfg(cfg), _animator(animator)
    {
        static std::mt19937 rng{std::random_device{}()};

        _at = animator->animTop;
        _ab = animator->animBottom;

        auto* theme = animator->currentTheme;
        std::string density   = theme ? theme->cloudDensity  : "medium";
        std::string speedKey  = theme ? theme->cloudSpeed    : "medium";
        _precip               = theme ? theme->precipitation  : "none";
        _fps = cfg.value("/animation/fps"_json_pointer, 15);

        float baseSpeed = 0.4f;
        if (speedKey == "slow") baseSpeed = 0.2f;
        else if (speedKey == "fast") baseSpeed = 0.7f;

        int count = 4;
        if (density == "sparse") count = 2;
        else if (density == "dense") count = 7;

        // Cloud color from theme or default #646464
        int cloudR = 100, cloudG = 100, cloudB = 100;
        if (theme) {
            auto it = theme->colors.find("cloud_day");
            if (it != theme->colors.end()) {
                auto col = resolveColor(it->second);
                cloudR = col[0]; cloudG = col[1]; cloudB = col[2];
            }
        }

        // Sun blend parameters
        _sunEnabled = theme && theme->sunEnabled;
        if (_sunEnabled) {
            _sunOx = width - 1;
            _sunOy = animator->animTop;
            _sunR  = 12;
            _sunGlow = 20;
            std::array<int,3> sc = {220, 160, 30};
            if (theme) {
                auto it = theme->colors.find("sun_day");
                if (it != theme->colors.end()) sc = resolveColor(it->second);
            }
            _sunR_col = sc[0]; _sunG_col = sc[1]; _sunB_col = sc[2];
        }

        // Lightning state
        _boltLife  = 0;
        _flashLife = 0;
        _nextBolt  = _randBoltInterval(rng);

        std::uniform_real_distribution<float> rndW(0.0f, float(width));
        std::uniform_int_distribution<int>    rndY(_at + 1, std::max(_at + 1, _ab - 12));
        std::uniform_real_distribution<float> rnd08(0.0f, 0.08f);

        for (int i = 0; i < count; ++i) {
            Cloud c;
            c.x    = rndW(rng);
            c.y    = float(rndY(rng));
            c.vx   = -(baseSpeed + rnd08(rng));
            c.size = _pickSize(density, rng);
            c.cr   = cloudR; c.cg = cloudG; c.cb = cloudB;
            c.particles = _makeParticles(c.x, c.y, c.size, rng);
            _clouds.push_back(std::move(c));
        }
    }

    void update() override {
        static std::mt19937 rng{std::random_device{}()};
        std::uniform_int_distribution<int> rndY(_at + 1, std::max(_at + 1, _ab - 12));

        for (auto& c : _clouds) {
            c.x += c.vx;
            auto span = getSpan(c.size);
            if (c.x + span.spanR < 0) {
                c.x = float(_w + std::abs(span.spanL) + 4);
                c.y = float(rndY(rng));
                c.particles = _makeParticles(c.x, c.y, c.size, rng);
            }
            for (auto& p : c.particles) {
                p.wobble += 0.15f;
                if (p.type == "snow" || p.type == "sleet_slow")
                    p.lx += std::sin(p.wobble) * 0.25f;
                p.y += p.vy;
                if (p.y > _ab)
                    _respawn(p, c.x, c.y, c.size, rng);
            }
        }

        if (_precip == "tstorm") {
            if (_boltLife  > 0) --_boltLife;
            if (_flashLife > 0) --_flashLife;
            --_nextBolt;
            if (_nextBolt <= 0 && !_clouds.empty()) {
                std::uniform_int_distribution<int> rndC(0, int(_clouds.size()) - 1);
                auto& lc = _clouds[rndC(rng)];
                _makeBolt(lc.x, lc.y, lc.size, rng);
                std::uniform_int_distribution<int> rndBL(2, 3), rndFL(1, 2);
                _boltLife  = rndBL(rng);
                _flashLife = rndFL(rng);
                _nextBolt  = _randBoltInterval(rng);
            }
        }
    }

    void draw(rgb_matrix::FrameCanvas* canvas) override {
        if (_flashLife > 0) {
            for (int y = _at; y <= _ab; ++y)
                for (int x = 0; x < _w; ++x)
                    canvas->SetPixel(x, y, COLOR_FLASH_R, COLOR_FLASH_G, COLOR_FLASH_B);
        }

        for (const auto& c : _clouds) {
            int cx = int(std::round(c.x));
            int cy = int(std::round(c.y));

            const CloudCircle* circles = nullptr;
            int circleCount = 0;
            int maxR = 0;
            if (c.size == "small")  { circles = SMALL_CIRCLES;  circleCount = 3; }
            else if (c.size == "large") { circles = LARGE_CIRCLES; circleCount = 5; }
            else                    { circles = MEDIUM_CIRCLES; circleCount = 4; }
            for (int i = 0; i < circleCount; ++i)
                maxR = std::max(maxR, circles[i].r);

            for (int i = 0; i < circleCount; ++i) {
                int diff = maxR - circles[i].r;
                float scale = (diff == 0) ? 1.0f : (diff == 1 ? 0.85f : 0.70f);
                _fillCircle(canvas,
                    cx + circles[i].dx, cy + circles[i].dy, circles[i].r,
                    int(c.cr * scale), int(c.cg * scale), int(c.cb * scale));
            }

            for (const auto& p : c.particles) {
                int px = int(std::round(c.x + p.lx));
                int py = int(std::round(p.y));
                if (p.type == "rain")
                    _vline(canvas, px, py, 3, COLOR_RAIN_R, COLOR_RAIN_G, COLOR_RAIN_B);
                else if (p.type == "heavy_rain")
                    _vline(canvas, px, py, 3, COLOR_HEAVY_RAIN_R, COLOR_HEAVY_RAIN_G, COLOR_HEAVY_RAIN_B);
                else if (p.type == "snow")
                    _dot(canvas, px, py, COLOR_SNOW_R, COLOR_SNOW_G, COLOR_SNOW_B);
                else if (p.type == "sleet_fast")
                    _vline(canvas, px, py, 2, COLOR_SLEET_R, COLOR_SLEET_G, COLOR_SLEET_B);
                else if (p.type == "sleet_slow")
                    _dot(canvas, px, py, COLOR_SNOW_R, COLOR_SNOW_G, COLOR_SNOW_B);
            }
        }

        if (_boltLife > 0 && !_bolt.empty()) {
            float fade = float(_boltLife) / 3.0f;
            int lr = int(COLOR_LIGHTNING_R * fade);
            int lg = int(COLOR_LIGHTNING_G * fade);
            int lb = int(COLOR_LIGHTNING_B * fade);
            _drawBolt(canvas, _bolt, lr, lg, lb);
            for (const auto& br : _boltBranches)
                _drawBolt(canvas, br, lr/2, lg/2, lb/2);
        }
    }

    bool isDone() const override { return false; }
    const std::string& name()       const override { static std::string n = "clouds";     return n; }
    const std::string& layer()      const override { static std::string l = "foreground"; return l; }
    bool               persistent() const override { return true; }

private:
    int              _w, _at, _ab;
    nlohmann::json   _cfg;
    WeatherAnimator* _animator;
    std::string      _precip;
    int              _fps;

    bool _sunEnabled = false;
    int  _sunOx = 0, _sunOy = 0, _sunR = 12, _sunGlow = 20;
    int  _sunR_col = 220, _sunG_col = 160, _sunB_col = 30;

    std::vector<Cloud> _clouds;

    std::vector<std::pair<int,int>> _bolt;
    std::vector<std::vector<std::pair<int,int>>> _boltBranches;
    int _boltLife = 0, _flashLife = 0, _nextBolt = 0;

    int _randBoltInterval(std::mt19937& rng) {
        std::uniform_int_distribution<int> d(8 * _fps, 15 * _fps);
        return d(rng);
    }

    std::string _pickSize(const std::string& density, std::mt19937& rng) {
        if (density == "sparse") {
            static const char* opts[] = {"small","medium"};
            return opts[std::uniform_int_distribution<int>(0,1)(rng)];
        } else if (density == "dense") {
            static const char* opts[] = {"medium","large"};
            return opts[std::uniform_int_distribution<int>(0,1)(rng)];
        }
        // medium density: small, medium, medium, large
        static const char* opts[] = {"small","medium","medium","large"};
        return opts[std::uniform_int_distribution<int>(0,3)(rng)];
    }

    Particle _newParticle(int spanL, int spanR, float cloudBottom, const std::string& ptype, float vy, std::mt19937& rng) {
        std::uniform_real_distribution<float> rndLX(float(spanL), float(spanR));
        std::uniform_real_distribution<float> rndY(cloudBottom, float(_ab));
        std::uniform_real_distribution<float> rndW(0.0f, 6.2832f);
        return { rndLX(rng), rndY(rng), vy, rndW(rng), ptype };
    }

    std::vector<Particle> _makeParticles(float cx, float cy, const std::string& size, std::mt19937& rng) {
        if (_precip == "none") return {};
        auto span = getSpan(size);
        float bottom = cy + span.spanH;
        std::vector<Particle> particles;

        std::uniform_int_distribution<int> rnd24(2,4), rnd46(4,6), rnd23(2,3), rnd35(3,5);
        std::uniform_real_distribution<float> rndVsnow(0.3f, 0.5f);

        if (_precip == "rain") {
            int n = rnd24(rng);
            for (int i = 0; i < n; ++i)
                particles.push_back(_newParticle(span.spanL, span.spanR, bottom, "rain", 1.5f, rng));
        } else if (_precip == "heavy_rain" || _precip == "tstorm") {
            int n = rnd46(rng);
            for (int i = 0; i < n; ++i)
                particles.push_back(_newParticle(span.spanL, span.spanR, bottom, "heavy_rain", 2.5f, rng));
        } else if (_precip == "snow") {
            int n = rnd23(rng);
            for (int i = 0; i < n; ++i)
                particles.push_back(_newParticle(span.spanL, span.spanR, bottom, "snow", rndVsnow(rng), rng));
        } else if (_precip == "sleet") {
            int n = rnd35(rng);
            std::uniform_real_distribution<float> rndVsl(0.4f, 0.6f);
            for (int i = 0; i < n; ++i) {
                if (i % 2 == 0)
                    particles.push_back(_newParticle(span.spanL, span.spanR, bottom, "sleet_fast", 1.5f, rng));
                else
                    particles.push_back(_newParticle(span.spanL, span.spanR, bottom, "sleet_slow", rndVsl(rng), rng));
            }
        }
        return particles;
    }

    void _respawn(Particle& p, float cx, float cy, const std::string& size, std::mt19937& rng) {
        auto span = getSpan(size);
        std::uniform_real_distribution<float> rndLX(float(span.spanL), float(span.spanR));
        p.lx = rndLX(rng);
        p.y  = cy + span.spanH;
    }

    void _makeBolt(float cx, float cy, const std::string& size, std::mt19937& rng) {
        _bolt.clear();
        _boltBranches.clear();
        auto span = getSpan(size);
        std::uniform_real_distribution<float> rndBX(span.spanL * 0.5f, span.spanR * 0.5f);
        std::uniform_int_distribution<int> rndLen(10,16), rndDx(-2,2), rndDy(2,3), rndBLen(1,3);

        int x = int(cx + rndBX(rng));
        int y = int(cy + span.spanH);
        _bolt.push_back({x, y});
        int targetY = std::min(_ab, y + rndLen(rng));

        std::uniform_real_distribution<float> rndBranch(0.0f, 1.0f);
        while (y < targetY) {
            x = std::max(1, std::min(_w - 2, x + rndDx(rng)));
            y = std::min(targetY, y + rndDy(rng));
            _bolt.push_back({x, y});
            if (rndBranch(rng) < 0.4f && _bolt.size() > 1) {
                int bx = x, by = y;
                std::vector<std::pair<int,int>> branch = {{bx, by}};
                int bl = rndBLen(rng);
                for (int i = 0; i < bl; ++i) {
                    bx = std::max(0, std::min(_w - 1, bx + rndDx(rng)));
                    by += std::uniform_int_distribution<int>(1,2)(rng);
                    if (by > _ab) break;
                    branch.push_back({bx, by});
                }
                if (branch.size() > 1)
                    _boltBranches.push_back(std::move(branch));
            }
        }
    }

    void _fillCircle(rgb_matrix::FrameCanvas* canvas, int cx, int cy, int r, int cr, int cg, int cb) {
        for (int dy = -r; dy <= r; ++dy) {
            for (int dx = -r; dx <= r; ++dx) {
                if (dx*dx + dy*dy <= r*r) {
                    int px = cx + dx, py = cy + dy;
                    if (px < 0 || px >= _w || py < _at || py > _ab) continue;
                    int pr = cr, pg = cg, pb = cb;
                    if (_sunEnabled) {
                        int sdx = px - _sunOx, sdy = py - _sunOy;
                        float dist = std::sqrt(float(sdx*sdx + sdy*sdy));
                        if (dist < _sunGlow) {
                            float t = std::min(0.35f, (1.0f - dist / _sunGlow) * (1.0f - dist / _sunGlow));
                            pr = int(pr * (1.0f - t) + _sunR_col * t);
                            pg = int(pg * (1.0f - t) + _sunG_col * t);
                            pb = int(pb * (1.0f - t) + _sunB_col * t);
                        }
                    }
                    canvas->SetPixel(px, py, pr, pg, pb);
                }
            }
        }
    }

    void _vline(rgb_matrix::FrameCanvas* canvas, int x, int y, int length, int cr, int cg, int cb) {
        for (int i = 0; i < length; ++i) {
            int py = y + i;
            if (x >= 0 && x < _w && py >= _at && py <= _ab)
                canvas->SetPixel(x, py, cr, cg, cb);
        }
    }

    void _dot(rgb_matrix::FrameCanvas* canvas, int x, int y, int cr, int cg, int cb) {
        if (x >= 0 && x < _w && y >= _at && y <= _ab)
            canvas->SetPixel(x, y, cr, cg, cb);
    }

    void _drawBolt(rgb_matrix::FrameCanvas* canvas,
                   const std::vector<std::pair<int,int>>& points,
                   int cr, int cg, int cb)
    {
        for (int i = 0; i + 1 < int(points.size()); ++i) {
            int x1 = points[i].first,   y1 = points[i].second;
            int x2 = points[i+1].first, y2 = points[i+1].second;
            int adx = std::abs(x2 - x1), ady = std::abs(y2 - y1);
            int sx = (x1 < x2) ? 1 : -1;
            int sy = (y1 < y2) ? 1 : -1;
            int err = adx - ady;
            while (true) {
                if (x1 >= 0 && x1 < _w && y1 >= _at && y1 <= _ab)
                    canvas->SetPixel(x1, y1, cr, cg, cb);
                if (x1 == x2 && y1 == y2) break;
                int e2 = 2 * err;
                if (e2 > -ady) { err -= ady; x1 += sx; }
                if (e2 <  adx) { err += adx; y1 += sy; }
            }
        }
    }
};

extern "C" std::unique_ptr<Animation> create_clouds(
    int w, int h, const nlohmann::json& cfg, WeatherAnimator* a)
{
    return std::make_unique<CloudsAnimation>(w, h, cfg, a);
}
