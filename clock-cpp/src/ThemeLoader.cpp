#include "Theme.h"
#include <algorithm>
#include <filesystem>
#include <fstream>
#include <iostream>

namespace fs = std::filesystem;

// ── JSON → Theme ──────────────────────────────────────────────────────────────

Theme themeFromJson(const nlohmann::json& j) {
    Theme t;

    t.name        = j.value("name", "");
    t.description = j.value("description", "");

    t.backgroundType              = j.value("background_type",               "solid");
    t.backgroundColor             = j.value("background_color",              "#000820");
    t.backgroundTop               = j.value("background_top",                "#0F0019");
    t.backgroundBottom            = j.value("background_bottom",             "#3C1400");
    t.backgroundSplit             = j.value("background_split",              0.5f);
    t.backgroundGradientDirection = j.value("background_gradient_direction", "sunset");

    if (j.contains("colors") && j["colors"].is_object()) {
        for (auto& [k, v] : j["colors"].items()) {
            t.colors[k] = parseColorValue(v);
        }
    }

    t.starsEnabled         = j.value("stars_enabled",          false);
    t.shootingStarsEnabled = j.value("shooting_stars_enabled", false);

    if (j.contains("cameos") && j["cameos"].is_array()) {
        for (const auto& ce : j["cameos"]) {
            CameoEntry entry;
            entry.name            = ce.value("name",              "");
            entry.chancePerMinute = ce.value("chance_per_minute", 0);
            entry.raw             = ce.is_object() ? ce : nlohmann::json::object({{"name", entry.name}});
            t.cameos.push_back(entry);
        }
    }

    // Backward compat: shooting_stars_enabled → cameo entry (mirrors Python).
    if (t.shootingStarsEnabled) {
        bool hasEntry = false;
        for (const auto& c : t.cameos) {
            if (c.name == "shooting_star") { hasEntry = true; break; }
        }
        if (!hasEntry) {
            t.cameos.push_back({"shooting_star", 8, nlohmann::json::object({
                {"name", "shooting_star"},
                {"chance_per_minute", 8},
            })});
        }
    }

    if (t.starsEnabled) {
        bool hasEntry = false;
        for (const auto& c : t.cameos) {
            if (c.name == "stars") { hasEntry = true; break; }
        }
        if (!hasEntry) {
            t.cameos.insert(t.cameos.begin(), {"stars", 0, nlohmann::json::object({
                {"name", "stars"},
            })});
        }
    }

    t.cloudDensity = j.value("cloud_density", "medium");
    t.cloudSpeed   = j.value("cloud_speed",   "medium");
    t.sunEnabled   = j.value("sun_enabled",   true);
    t.moonEnabled  = j.value("moon_enabled",  false);
    t.precipitation = j.value("precipitation", "none");

    if (j.contains("condition_overrides") && j["condition_overrides"].is_object()) {
        for (auto& [k, v] : j["condition_overrides"].items()) {
            t.conditionOverrides[k] = v;
        }
    }

    return t;
}

// ── ThemeLoader ───────────────────────────────────────────────────────────────

ThemeLoader::ThemeLoader(std::string themesDir)
    : _themesDir(std::move(themesDir))
{
    fs::create_directories(_themesDir);
    loadAll();
}

ThemeLoader::~ThemeLoader() = default;

void ThemeLoader::loadAll() {
    _themes.clear();
    std::error_code ec;
    for (const auto& entry : fs::directory_iterator(_themesDir, ec)) {
        if (entry.path().extension() != ".json") continue;
        try {
            std::ifstream f(entry.path());
            nlohmann::json j = nlohmann::json::parse(f);
            if (!j.contains("name")) {
                j["name"] = entry.path().stem().string();
            }
            Theme theme = themeFromJson(j);
            _themes[theme.name] = std::move(theme);
        } catch (const std::exception& e) {
            std::cerr << "[theme_loader] Warning: skipping "
                      << entry.path().filename() << ": " << e.what() << "\n";
        }
    }
    if (ec) {
        std::cerr << "[theme_loader] Warning: " << _themesDir << ": " << ec.message() << "\n";
    }
}

std::optional<Theme> ThemeLoader::getTheme(const std::string& name) const {
    auto it = _themes.find(name);
    if (it == _themes.end()) return std::nullopt;
    return it->second;
}

std::vector<std::string> ThemeLoader::availableThemes() const {
    std::vector<std::string> names;
    names.reserve(_themes.size());
    for (const auto& [k, _] : _themes) names.push_back(k);
    std::sort(names.begin(), names.end());
    return names;
}
