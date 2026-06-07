#pragma once

#include <map>
#include <string>
#include <vector>
#include <variant>
#include <optional>
#include <functional>
#include <nlohmann/json.hpp>

// A color value in a theme: either "#RRGGBB" string or [r,g,b] array.
using ColorValue = std::variant<std::string, std::array<int, 3>>;

struct CameoEntry {
    std::string name;
    int chancePerMinute = 0;
    nlohmann::json raw = nlohmann::json::object();
};

struct Theme {
    std::string name;
    std::string description;

    // Background
    std::string backgroundType     = "solid";
    std::string backgroundColor    = "#000820";
    std::string backgroundTop      = "#0F0019";
    std::string backgroundBottom   = "#3C1400";
    float       backgroundSplit    = 0.5f;
    std::string backgroundGradientDirection = "sunset";

    // Color overrides (keyed by color name, e.g. "cloud_day", "sun_day")
    std::map<std::string, ColorValue> colors;

    // Feature flags
    bool starsEnabled        = false;
    bool shootingStarsEnabled = false;

    // Cameos: persistent (clouds) and chance-based (shooting_star, etc.)
    std::vector<CameoEntry> cameos;

    // Cloud settings
    std::string cloudDensity = "medium";
    std::string cloudSpeed   = "medium";

    // Celestial bodies
    bool sunEnabled  = true;
    bool moonEnabled = false;

    // Precipitation: "none" | "rain" | "heavy_rain" | "tstorm" | "snow" | "sleet"
    std::string precipitation = "none";

    // Per-condition overrides: condition key → partial Theme fields as JSON
    std::map<std::string, nlohmann::json> conditionOverrides;
};

// Parse a color value from JSON (string or [r,g,b] array).
inline ColorValue parseColorValue(const nlohmann::json& j) {
    if (j.is_string()) {
        return j.get<std::string>();
    }
    if (j.is_array() && j.size() == 3) {
        return std::array<int, 3>{j[0].get<int>(), j[1].get<int>(), j[2].get<int>()};
    }
    return std::string{"#F0F0F0"};
}

// Resolve a ColorValue to (r, g, b).
inline std::array<int, 3> resolveColor(const ColorValue& cv) {
    if (auto* s = std::get_if<std::string>(&cv)) {
        if (s->size() == 7 && (*s)[0] == '#') {
            int r = std::stoi(s->substr(1, 2), nullptr, 16);
            int g = std::stoi(s->substr(3, 2), nullptr, 16);
            int b = std::stoi(s->substr(5, 2), nullptr, 16);
            return {r, g, b};
        }
        return {240, 240, 240};
    }
    return std::get<std::array<int, 3>>(cv);
}

// Deserialize a Theme from a JSON object.
Theme themeFromJson(const nlohmann::json& j);

// ── ThemeLoader ───────────────────────────────────────────────────────────────

class ThemeLoader {
public:
    using ChangedCallback = std::function<void(const std::map<std::string, Theme>&)>;

    explicit ThemeLoader(std::string themesDir);
    ~ThemeLoader();

    // Load / reload all *.json files in themesDir.
    void loadAll();

    std::optional<Theme>       getTheme(const std::string& name) const;
    std::vector<std::string>   availableThemes() const;

    // Called whenever the themes directory changes (inotify-based watcher).
    ChangedCallback onThemesChanged;

private:
    std::string                  _themesDir;
    std::map<std::string, Theme> _themes;
};
