#include "WeatherAnimator.h"
#include "Theme.h"
#include "Sensors.h"

#include <led-matrix.h>
#include <graphics.h>

#include <yaml-cpp/yaml.h>
#include <nlohmann/json.hpp>
#include <mosquitto.h>

#include <algorithm>
#include <array>
#include <atomic>
#include <cctype>
#include <cstdlib>
#include <cstdint>
#include <cstring>
#include <ctime>
#include <csignal>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <mutex>
#include <stdexcept>
#include <string>
#include <thread>
#include <chrono>
#include <unordered_map>
#include <vector>

using namespace rgb_matrix;
using json = nlohmann::json;
namespace fs = std::filesystem;

static const std::vector<std::pair<std::string, std::string>>& animationDefaultBlocks() {
    static const std::vector<std::pair<std::string, std::string>> blocks = {
        {"rocket", "  speed: 0.25\n"},
        {"meteor", "  speed: 0.3\n"},
        {"hot_air_balloon", "  speed: 0.5\n"},
        {"santa", "  speed: 0.5\n"},
        {"tumbleweed", "  speed: 0.5\n"},
        {"fireworks", "  speed: 1.0\n"},
        {"flutterflies", "  speed: 1.0\n"},
        {"snake", "  speed: 1.0\n"},
        {"clouds",
         "  speed: 1.0\n"
         "  particle_speed: 1.0\n"
         "  rain_speed: 1.0\n"
         "  heavy_rain_speed: 1.0\n"
         "  snow_speed: 1.0\n"
         "  sleet_fast_speed: 1.0\n"
         "  sleet_slow_speed: 1.0\n"},
    };
    return blocks;
}

static void ensureAnimationSettingsDefaults(const std::string& path) {
    try {
        fs::path p(path);
        if (!p.parent_path().empty()) fs::create_directories(p.parent_path());

        if (!fs::exists(path)) {
            std::ofstream out(path);
            out << "# Per-animation speed multipliers.\n"
                << "# Added automatically; edit these values to tune runtime speed.\n";
            for (const auto& block : animationDefaultBlocks()) {
                out << "\n" << block.first << ":\n" << block.second;
            }
            std::cout << "[config] created " << path << "\n";
            return;
        }

        YAML::Node existing = YAML::LoadFile(path);
        if (!existing.IsMap()) return;

        std::vector<const std::pair<std::string, std::string>*> missing;
        for (const auto& block : animationDefaultBlocks()) {
            if (!existing[block.first]) missing.push_back(&block);
        }
        if (missing.empty()) return;

        std::ofstream out(path, std::ios::app);
        out << "\n# Added automatically for new animation defaults.\n";
        for (const auto* block : missing) {
            out << "\n" << block->first << ":\n" << block->second;
        }
        std::cout << "[config] added missing animation defaults to " << path << "\n";
    } catch (const std::exception& e) {
        std::cerr << "[config] Failed to update animation defaults: " << e.what() << "\n";
    }
}

// ── Defaults (mirror Python DEFAULTS dict) ────────────────────────────────────

static json defaults() {
    return {
        {"mqtt", {
            {"broker", ""},
            {"port", 1883},
            {"username", ""},
            {"password", ""},
            {"client_id", "hub75_clock"},
            {"topics", {
                {"weather",          "clock/weather"},
                {"config",           "clock/config"},
                {"alert",            "clock/alert"},
                {"lux",              "hub75_clock/lux"},
                {"presence",         "hub75_clock/presence"},
                {"motion",           "hub75_clock/motion"},
                {"pir",              "hub75_clock/pir"},
                {"availability",     "hub75_clock/status"},
                {"fonts_available",  "hub75_clock/fonts_available"},
                {"gates",            "hub75_clock/gates"},
                {"engineering_mode", "hub75_clock/engineering_mode"},
                {"bucket",           "hub75_clock/bucket"},
                {"theme",            "hub75_clock/theme/set"},
                {"theme_state",      "hub75_clock/theme/state"},
                {"themes_available", "hub75_clock/themes/available"},
                {"ld2410_params",    "hub75_clock/ld2410/params"},
                {"ld2410_read",      "hub75_clock/ld2410/read"},
            }},
        }},
        {"ha_discovery", {
            {"enabled",            true},
            {"prefix",             "homeassistant"},
            {"ha_discovery_name",  "HUB75 Clock"},
            {"ha_discovery_area",  ""},
        }},
        {"theme_builder", {
            {"mode", "off"},
            {"service_name", "hub75-theme-builder"},
            {"host", "0.0.0.0"},
            {"port", 8765},
            {"url", ""},
        }},
        {"ld2410_tuner", {
            {"mode", "off"},
            {"service_name", "hub75-ld2410-tuner"},
            {"host", "0.0.0.0"},
            {"port", 8766},
            {"url", ""},
        }},
        {"panel", {
            {"hardware_mapping",    "regular"},
            {"gpio_slowdown",       2},
            {"led_rgb_sequence",    "RBG"},
            {"pwm_bits",            11},
            {"pwm_lsb_nanoseconds", 130},
            {"brightness",          60},
        }},
        {"fonts", {
            {"fonts_dir",   "/home/pi/rpi-rgb-led-matrix/fonts"},
            {"banner_name", "4x6.bdf"},
            {"banner_w",    4},
            {"banner_h",    6},
            {"time_name",   "spleen-12x24.bdf"},
            {"time_w",      12},
            {"time_h",      24},
            {"alert_name",  "4x6.bdf"},
            {"alert_w",     4},
            {"alert_h",     6},
        }},
        {"colors", {
            {"time_day",        "#F0F0F0"},
            {"low_temp_day",    "#00CCFF"},
            {"high_temp_day",   "#FF8C00"},
            {"condition_day",   "#909090"},
            {"alert_text",      "#FFFFFF"},
            {"alert_bg",        "#CC0000"},
            {"cloud_day",       {70, 70, 70}},
            {"sun_day",         {220, 160, 30}},
            {"ice_day",         {80, 140, 160}},
            {"outline",         {0, 0, 0}},
            {"sky_day",         "#000820"},
        }},
        {"animation", {
            {"fps",                        90},
            {"rain_count",                 {5, 8}},
            {"snow_count",                 {6, 10}},
            {"sleet_count",                {6, 10}},
            {"tstorm_rain_count",          {5, 8}},
            {"tstorm_lightning_chance",    0.015},
            {"tstorm_lightning_duration",  2},
        }},
        {"alert", {
            {"scroll_speed", 1},
            {"scroll_gap",   8},
            {"flash",        false},
            {"flash_period", 10},
            {"fill_region",  true},
        }},
        {"sensors", {
            {"lux_interval",      10.0},
            {"pir_poll_interval",  0.1},
            {"veml7700_enabled",  true},
            {"ld2410_enabled",    true},
            {"ld2410_port",       "/dev/serial0"},
            {"ld2410_baud",       256000},
            {"pir_enabled",       true},
            {"pir_gpio",          6},
            {"pir_invert",        false},
        }},
        {"time_format", {
            {"use_24h",     false},
            {"blink_colon", false},
        }},
        {"themes", {
            {"themes_dir",    "/etc/hub75-clock/themes"},
            {"default_theme", "Day"},
        }},
        {"animations", {
            {"animations_dir", "/etc/hub75-clock/animations"},
            {"sprites_dir", "/etc/hub75-clock/sprites"},
            {"sprite_animations_dir", "/etc/hub75-clock/sprite-animations"},
            {"settings_path", "/etc/hub75-clock/animations.yaml"},
        }},
    };
}

// ── Config loader ─────────────────────────────────────────────────────────────

// Recursively merge overlay into base (overlay wins on conflicts).
static json deepMerge(const json& base, const json& overlay) {
    json out = base;
    for (auto it = overlay.begin(); it != overlay.end(); ++it) {
        if (out.contains(it.key()) && out[it.key()].is_object() && it.value().is_object()) {
            out[it.key()] = deepMerge(out[it.key()], it.value());
        } else {
            out[it.key()] = it.value();
        }
    }
    return out;
}

static json yamlToJson(const YAML::Node& node) {
    switch (node.Type()) {
        case YAML::NodeType::Map: {
            json obj = json::object();
            for (const auto& kv : node) obj[kv.first.as<std::string>()] = yamlToJson(kv.second);
            return obj;
        }
        case YAML::NodeType::Sequence: {
            json arr = json::array();
            for (const auto& v : node) arr.push_back(yamlToJson(v));
            return arr;
        }
        case YAML::NodeType::Scalar: {
            const std::string s = node.as<std::string>();
            // Try int, then double, then bool, then string.
            try { return node.as<int>(); }    catch (...) {}
            try { return node.as<double>(); } catch (...) {}
            try { return node.as<bool>(); }   catch (...) {}
            return s;
        }
        default: return nullptr;
    }
}

static json loadConfig(const std::string& path) {
    json cfg = defaults();
    if (!fs::exists(path)) {
        std::cerr << "[config] " << path << " not found — using defaults\n";
        cfg["animation"]["fps"] = std::max(1, cfg["animation"].value("fps", 90));
        return cfg;
    }
    try {
        YAML::Node y    = YAML::LoadFile(path);
        json       user = yamlToJson(y);
        cfg = deepMerge(cfg, user);
        std::cout << "[config] loaded " << path << "\n";
    } catch (const std::exception& e) {
        std::cerr << "[config] Failed to parse " << path << ": " << e.what() << "\n";
    }
    cfg["animation"]["fps"] = std::max(1, cfg["animation"].value("fps", 90));
    return cfg;
}

static std::uint64_t themeDirSignature(const std::string& themesDir) {
    std::uint64_t sig = 1469598103934665603ull;
    std::error_code ec;
    for (const auto& entry : fs::directory_iterator(themesDir, ec)) {
        if (entry.path().extension() != ".json") continue;
        auto stamp = fs::last_write_time(entry.path(), ec).time_since_epoch().count();
        if (ec) {
            ec.clear();
            continue;
        }
        auto size = fs::file_size(entry.path(), ec);
        if (ec) {
            ec.clear();
            size = 0;
        }
        std::string name = entry.path().filename().string();
        for (unsigned char ch : name) {
            sig ^= ch;
            sig *= 1099511628211ull;
        }
        sig ^= static_cast<std::uint64_t>(stamp);
        sig *= 1099511628211ull;
        sig ^= static_cast<std::uint64_t>(size);
        sig *= 1099511628211ull;
    }
    return sig;
}

// ── Signal handling ───────────────────────────────────────────────────────────

static std::atomic<bool> g_running{true};
static std::atomic<int>  g_fps{90};

static void onSignal(int) { g_running = false; }

// ── Clock state ───────────────────────────────────────────────────────────────

struct ClockState {
    std::string lowTemp       = "--";
    std::string highTemp      = "--";
    std::string condition     = "CLEAR";
    bool        mqttConnected = false;
    std::string bucket        = "Day";
    std::string alertMessage;
};

// ── Color helpers ─────────────────────────────────────────────────────────────

// Mirrors Python _col(key): checks theme.colors[key], then cfg["colors"][key+"_day"],
// then cfg["colors"][key]. The key passed in has no suffix (e.g. "time", "low_temp").
static rgb_matrix::Color resolveTextColor(
    const std::string& key,
    const WeatherAnimator& animator,
    const json& cfg)
{
    if (animator.currentTheme) {
        auto it = animator.currentTheme->colors.find(key);
        if (it != animator.currentTheme->colors.end()) {
            auto c = resolveColor(it->second);
            return rgb_matrix::Color(c[0], c[1], c[2]);
        }
    }
    const auto& colors = cfg["colors"];
    std::string dayKey = key + "_day";
    if (colors.contains(dayKey)) {
        auto c = resolveColor(parseColorValue(colors[dayKey]));
        return rgb_matrix::Color(c[0], c[1], c[2]);
    }
    if (colors.contains(key)) {
        auto c = resolveColor(parseColorValue(colors[key]));
        return rgb_matrix::Color(c[0], c[1], c[2]);
    }
    return rgb_matrix::Color(200, 200, 200);
}

// ── Condition display text ────────────────────────────────────────────────────

static std::string displayCondition(const std::string& cond) {
    static const std::unordered_map<std::string, std::string> MAP = {
        {"SUNNY",            "SUNNY"},
        {"CLEAR",            "CLEAR"},
        {"PARTLYCLOUDY",     "CLOUDY"},
        {"CLOUDY",           "CLOUDY"},
        {"FOG",              "CLOUDY"},
        {"RAIN",             "RAIN"},
        {"SNOW",             "SNOW"},
        {"SLEET",            "SLEET"},
        {"TSTORM",           "TSTORM"},
        {"ICE",              "ICE"},
        {"BLIZZARD",         "BLIZZARD"},
        {"HURRICANE",        "HURRCN"},
        {"TROPICAL_STORM",   "T-STORM"},
        {"FLOOD",            "FLOOD"},
        {"FREEZING_RAIN",    "FRZRAIN"},
        {"FREEZING_DRIZZLE", "FRZDRIZ"},
        {"DUST",             "DUSTY"},
        {"SMOKE",            "SMOKY"},
        {"WINDY",            "WINDY"},
    };
    auto it = MAP.find(cond);
    return (it != MAP.end()) ? it->second : cond;
}

// ── Banner draw ───────────────────────────────────────────────────────────────

// Layout: banner rows 1–7 (top=1, bottom=7), font 4x6 (banner_w=4, banner_h=6).
// Baseline math: banner_top + (region_h - font_h) / 2 + font_h - 1
//   = 1 + (7 - 6) / 2 + 6 - 1 = 6
static void drawBanner(
    FrameCanvas* canvas,
    const ClockState& state,
    const WeatherAnimator& animator,
    const json& cfg,
    rgb_matrix::Font& font)
{
    const int BANNER_TOP    = 1;
    const int BANNER_BOTTOM = 7;
    const int FONT_W        = cfg["fonts"].value("banner_w", 4);
    const int FONT_H        = cfg["fonts"].value("banner_h", 6);
    const int PANEL_W       = animator.width;

    int regionH  = BANNER_BOTTOM - BANNER_TOP + 1;
    int baseline = BANNER_TOP + (regionH - FONT_H) / 2 + FONT_H - 1;

    if (!state.mqttConnected) {
        const char* msg = "Connecting...";
        int x = std::max(0, (PANEL_W - int(std::strlen(msg)) * FONT_W) / 2);
        rgb_matrix::DrawText(canvas, font, x, baseline, rgb_matrix::Color(80, 80, 80), msg);
        return;
    }

    // Degree sign: U+00B0 encoded as Latin-1 0xB0 — BDF fonts use codepoint directly.
    std::string lowText  = state.lowTemp  + "\xC2\xB0";
    std::string highText = state.highTemp + "\xC2\xB0";
    std::string condText = displayCondition(state.condition);

    auto colLow  = resolveTextColor("low_temp",  animator, cfg);
    auto colHigh = resolveTextColor("high_temp", animator, cfg);
    auto colCond = resolveTextColor("condition", animator, cfg);

    // Low temp: left-aligned at x=1.
    rgb_matrix::DrawText(canvas, font, 1, baseline, colLow, lowText.c_str());

    // High temp: right-aligned.
    int highX = PANEL_W - (int(highText.size()) - 1) * FONT_W;
    rgb_matrix::DrawText(canvas, font, highX, baseline, colHigh, highText.c_str());

    // Condition: centered.
    int condX = std::max(0, (PANEL_W - int(condText.size()) * FONT_W) / 2);
    rgb_matrix::DrawText(canvas, font, condX, baseline, colCond, condText.c_str());
}

// ── Time draw ─────────────────────────────────────────────────────────────────

// Layout: time rows 8–31 (top=8, bottom=31), font 12x24 (time_w=12, time_h=24).
// Baseline math: top + (region_h + font_h) / 2 - 4
//   = 8 + (24 + 24) / 2 - 4 = 28
// 1px black outline drawn to all 8 neighbours before foreground text.
static void drawTime(
    FrameCanvas* canvas,
    const WeatherAnimator& animator,
    const json& cfg,
    rgb_matrix::Font& font)
{
    const int TIME_TOP    = 8;
    const int TIME_BOTTOM = 31;
    const int FONT_W      = cfg["fonts"].value("time_w",  12);
    const int FONT_H      = cfg["fonts"].value("time_h",  24);
    const int PANEL_W     = animator.width;
    const int ZONE_LEFT   = 0;
    const int ZONE_RIGHT  = PANEL_W - 1;

    // Build time string.
    std::time_t now_t  = std::time(nullptr);
    std::tm*    tm_ptr = std::localtime(&now_t);
    char buf[16];

    bool use24h     = cfg["time_format"].value("use_24h",     false);
    bool blinkColon = cfg["time_format"].value("blink_colon", false);

    if (use24h) {
        std::strftime(buf, sizeof(buf), "%H:%M", tm_ptr);
    } else {
        std::strftime(buf, sizeof(buf), "%I:%M", tm_ptr);
        // Strip leading zero (mirrors Python's lstrip("0") or "12:00").
        if (buf[0] == '0') std::memmove(buf, buf + 1, std::strlen(buf));
    }
    std::string timeStr(buf);

    if (blinkColon && (tm_ptr->tm_sec % 2 == 1)) {
        for (char& c : timeStr) if (c == ':') c = ' ';
    }

    // Centred horizontally in the zone.
    int zoneW    = ZONE_RIGHT - ZONE_LEFT + 1;
    int textW    = int(timeStr.size()) * FONT_W;
    int x        = ZONE_LEFT + std::max(0, (zoneW - textW) / 2);
    int regionH  = TIME_BOTTOM - TIME_TOP + 1;
    int baseline = TIME_TOP + (regionH + FONT_H) / 2 - 4;

    // 1px outline in all 8 directions.
    auto& colors = cfg["colors"];
    std::array<int, 3> olRgb = {0, 0, 0};
    if (colors.contains("outline")) {
        olRgb = resolveColor(parseColorValue(colors["outline"]));
    }
    rgb_matrix::Color olCol(olRgb[0], olRgb[1], olRgb[2]);
    for (int dx : {-1, 0, 1}) {
        for (int dy : {-1, 0, 1}) {
            if (dx == 0 && dy == 0) continue;
            rgb_matrix::DrawText(canvas, font, x + dx, baseline + dy, olCol, timeStr.c_str());
        }
    }

    auto colTime = resolveTextColor("time", animator, cfg);
    rgb_matrix::DrawText(canvas, font, x, baseline, colTime, timeStr.c_str());
}

// ── MQTT callbacks ────────────────────────────────────────────────────────────

struct MqttCtx {
    WeatherAnimator* animator;
    ThemeLoader*     themeLoader;
    ClockState*      clockState;
    json*            cfg;
    std::mutex*      mtx;
    RGBMatrix*       matrix;
    LD2410Sensor*    ld2410 = nullptr;
};

static std::string themeBuilderStateTopic(const json& cfg) {
    std::string cid = cfg["mqtt"].value("client_id", "hub75_clock");
    return cid + "/theme_builder/state";
}

static std::string themeBuilderUrlTopic(const json& cfg) {
    std::string cid = cfg["mqtt"].value("client_id", "hub75_clock");
    return cid + "/theme_builder/url";
}

static std::string themeBuilderUrl(const json& cfg) {
    const auto& tb = cfg["theme_builder"];
    std::string configured = tb.value("url", "");
    if (!configured.empty()) return configured;
    std::string cid = cfg["mqtt"].value("client_id", "hub75_clock");
    int port = tb.value("port", 8765);
    return "http://" + cid + ".local:" + std::to_string(port) + "/";
}

static bool themeBuilderActive(const json& cfg) {
    std::string service = cfg["theme_builder"].value("service_name", "hub75-theme-builder");
    std::string cmd = "systemctl is-active --quiet " + service;
    return std::system(cmd.c_str()) == 0;
}

static void publishThemeBuilderState(mosquitto* mosq, const json& cfg) {
    if (cfg["theme_builder"].value("mode", "off") == "off") return;
    std::string state = themeBuilderActive(cfg) ? "on" : "off";
    std::string stateTopic = themeBuilderStateTopic(cfg);
    std::string urlTopic = themeBuilderUrlTopic(cfg);
    std::string url = themeBuilderUrl(cfg);
    mosquitto_publish(mosq, nullptr, stateTopic.c_str(), int(state.size()), state.c_str(), 0, 1);
    mosquitto_publish(mosq, nullptr, urlTopic.c_str(), int(url.size()), url.c_str(), 0, 1);
}

static void setThemeBuilderService(mosquitto* mosq, const json& cfg, bool enable) {
    if (cfg["theme_builder"].value("mode", "off") == "off") return;
    std::string service = cfg["theme_builder"].value("service_name", "hub75-theme-builder");
    std::string cmd = std::string("systemctl ") + (enable ? "start " : "stop ") + service;
    std::system(cmd.c_str());
    publishThemeBuilderState(mosq, cfg);
}

static void ensureThemeBuilderStartupState(const json& cfg) {
    if (cfg["theme_builder"].value("mode", "off") != "ha") return;
    std::string service = cfg["theme_builder"].value("service_name", "hub75-theme-builder");
    std::string cmd = "systemctl stop " + service + " >/dev/null 2>&1";
    std::system(cmd.c_str());
}

static std::string ld2410TunerStateTopic(const json& cfg) {
    std::string cid = cfg["mqtt"].value("client_id", "hub75_clock");
    return cid + "/ld2410_tuner/state";
}

static std::string ld2410TunerUrlTopic(const json& cfg) {
    std::string cid = cfg["mqtt"].value("client_id", "hub75_clock");
    return cid + "/ld2410_tuner/url";
}

static std::string ld2410TunerUrl(const json& cfg) {
    const auto& lt = cfg["ld2410_tuner"];
    std::string configured = lt.value("url", "");
    if (!configured.empty()) return configured;
    std::string cid = cfg["mqtt"].value("client_id", "hub75_clock");
    int port = lt.value("port", 8766);
    return "http://" + cid + ".local:" + std::to_string(port) + "/";
}

static bool ld2410TunerActive(const json& cfg) {
    std::string service = cfg["ld2410_tuner"].value("service_name", "hub75-ld2410-tuner");
    std::string cmd = "systemctl is-active --quiet " + service;
    return std::system(cmd.c_str()) == 0;
}

static void publishLd2410TunerState(mosquitto* mosq, const json& cfg) {
    if (cfg["ld2410_tuner"].value("mode", "off") == "off") return;
    std::string state = ld2410TunerActive(cfg) ? "on" : "off";
    std::string stateTopic = ld2410TunerStateTopic(cfg);
    std::string urlTopic = ld2410TunerUrlTopic(cfg);
    std::string url = ld2410TunerUrl(cfg);
    mosquitto_publish(mosq, nullptr, stateTopic.c_str(), int(state.size()), state.c_str(), 0, 1);
    mosquitto_publish(mosq, nullptr, urlTopic.c_str(), int(url.size()), url.c_str(), 0, 1);
}

static void setLd2410TunerService(mosquitto* mosq, const json& cfg, bool enable) {
    if (cfg["ld2410_tuner"].value("mode", "off") == "off") return;
    std::string service = cfg["ld2410_tuner"].value("service_name", "hub75-ld2410-tuner");
    std::string cmd = std::string("systemctl ") + (enable ? "start " : "stop ") + service;
    std::system(cmd.c_str());
    publishLd2410TunerState(mosq, cfg);
}

static void ensureLd2410TunerStartupState(const json& cfg) {
    if (cfg["ld2410_tuner"].value("mode", "off") != "ha") return;
    std::string service = cfg["ld2410_tuner"].value("service_name", "hub75-ld2410-tuner");
    std::string cmd = "systemctl stop " + service + " >/dev/null 2>&1";
    std::system(cmd.c_str());
}

static void publishHomeAssistantDiscovery(mosquitto* mosq, const json& cfg,
                                          const std::vector<std::string>& themes) {
    if (!cfg["ha_discovery"].value("enabled", true)) return;

    const auto& topics = cfg["mqtt"]["topics"];
    std::string cid = cfg["mqtt"].value("client_id", "hub75_clock");
    std::string prefix = cfg["ha_discovery"].value("prefix", "homeassistant");
    std::string devName = cfg["ha_discovery"].value("ha_discovery_name", "HUB75 Clock");

    json device = {
        {"identifiers", json::array({cid})},
        {"name", devName},
        {"model", "HUB75 Smart Clock"},
        {"manufacturer", "DIY"},
    };
    std::string area = cfg["ha_discovery"].value("ha_discovery_area", "");
    if (!area.empty()) device["suggested_area"] = area;

    json availability = json::array({
        {{"topic", topics.value("availability", cid + "/status")}}
    });

    auto pub = [&](const std::string& topic, const json& payload) {
        std::string body = payload.dump();
        mosquitto_publish(mosq, nullptr, topic.c_str(), int(body.size()), body.c_str(), 0, 1);
    };
    auto clearDiscovery = [&](const std::string& topic) {
        mosquitto_publish(mosq, nullptr, topic.c_str(), 0, nullptr, 0, 1);
    };

    auto base = [&](const std::string& name, const std::string& uniqueId) {
        return json{
            {"name", name},
            {"unique_id", uniqueId},
            {"device", device},
            {"availability", availability},
            {"has_entity_name", true},
        };
    };

    json themeSelect = base("Theme", cid + "_theme");
    themeSelect["state_topic"] = topics.value("theme_state", cid + "/theme/state");
    themeSelect["command_topic"] = topics.value("theme", cid + "/theme/set");
    themeSelect["options"] = themes;
    themeSelect["icon"] = "mdi:palette";
    pub(prefix + "/select/" + cid + "_theme/config", themeSelect);

    json brightness = base("Brightness", cid + "_brightness");
    brightness["command_topic"] = topics.value("config", cid + "/config");
    brightness["command_template"] = "{\"brightness\": {{ value }}}";
    brightness["state_topic"] = cid + "/brightness/state";
    brightness["min"] = 1;
    brightness["max"] = 100;
    brightness["step"] = 1;
    brightness["mode"] = "slider";
    brightness["icon"] = "mdi:brightness-6";
    pub(prefix + "/number/" + cid + "_brightness/config", brightness);

    const std::string luxDiscoveryTopic = prefix + "/sensor/" + cid + "_lux/config";
    if (cfg["sensors"].value("veml7700_enabled", true)) {
        json lux = base("Lux", cid + "_lux");
        lux["state_topic"] = topics.value("lux", cid + "/lux");
        lux["value_template"] = "{{ value_json.lux }}";
        lux["unit_of_measurement"] = "lx";
        lux["device_class"] = "illuminance";
        lux["state_class"] = "measurement";
        pub(luxDiscoveryTopic, lux);
    } else {
        clearDiscovery(luxDiscoveryTopic);
    }

    json moveDistance = base("Move Distance", cid + "_move_distance");
    moveDistance["state_topic"] = topics.value("presence", cid + "/presence");
    moveDistance["value_template"] = "{{ value_json.move_distance }}";
    moveDistance["unit_of_measurement"] = "cm";
    moveDistance["state_class"] = "measurement";
    pub(prefix + "/sensor/" + cid + "_move_distance/config", moveDistance);

    json stillDistance = base("Still Distance", cid + "_still_distance");
    stillDistance["state_topic"] = topics.value("presence", cid + "/presence");
    stillDistance["value_template"] = "{{ value_json.still_distance }}";
    stillDistance["unit_of_measurement"] = "cm";
    stillDistance["state_class"] = "measurement";
    pub(prefix + "/sensor/" + cid + "_still_distance/config", stillDistance);

    json pir = base("PIR", cid + "_pir");
    pir["state_topic"] = topics.value("pir", cid + "/pir");
    pir["value_template"] = "{{ value_json.motion }}";
    pir["payload_on"] = "True";
    pir["payload_off"] = "False";
    pir["device_class"] = "motion";
    pub(prefix + "/binary_sensor/" + cid + "_pir/config", pir);

    json presence = base("Presence", cid + "_presence");
    presence["state_topic"] = topics.value("presence", cid + "/presence");
    presence["value_template"] = "{{ value_json.presence }}";
    presence["payload_on"] = "True";
    presence["payload_off"] = "False";
    presence["device_class"] = "occupancy";
    pub(prefix + "/binary_sensor/" + cid + "_presence/config", presence);

    if (cfg["sensors"].value("ld2410_enabled", true)) {
        json em = base("LD2410 Engineering Mode", cid + "_engineering_mode");
        em["command_topic"] = topics.value("engineering_mode", cid + "/engineering_mode");
        em["payload_on"] = "{\"engineering_mode\": true}";
        em["payload_off"] = "{\"engineering_mode\": false}";
        em["state_topic"] = topics.value("engineering_mode", cid + "/engineering_mode") + "/state";
        em["state_on"] = "on";
        em["state_off"] = "off";
        em["entity_category"] = "config";
        em["icon"] = "mdi:radar";
        pub(prefix + "/switch/" + cid + "_engineering_mode/config", em);
    } else {
        clearDiscovery(prefix + "/switch/" + cid + "_engineering_mode/config");
    }

    if (cfg["theme_builder"].value("mode", "off") == "ha") {
        json sw = base("Theme Builder", cid + "_theme_builder");
        sw["command_topic"] = topics.value("config", cid + "/config");
        sw["payload_on"] = "{\"theme_builder\": true}";
        sw["payload_off"] = "{\"theme_builder\": false}";
        sw["state_topic"] = themeBuilderStateTopic(cfg);
        sw["state_on"] = "on";
        sw["state_off"] = "off";
        sw["entity_category"] = "config";
        sw["icon"] = "mdi:palette-outline";
        pub(prefix + "/switch/" + cid + "_theme_builder/config", sw);

        json sensor = base("Theme Builder URL", cid + "_theme_builder_url");
        sensor["state_topic"] = themeBuilderUrlTopic(cfg);
        sensor["entity_category"] = "diagnostic";
        sensor["icon"] = "mdi:web";
        pub(prefix + "/sensor/" + cid + "_theme_builder_url/config", sensor);
    }

    if (cfg["ld2410_tuner"].value("mode", "off") == "ha") {
        json sw = base("LD2410 Tuner", cid + "_ld2410_tuner");
        sw["command_topic"] = topics.value("config", cid + "/config");
        sw["payload_on"] = "{\"ld2410_tuner\": true}";
        sw["payload_off"] = "{\"ld2410_tuner\": false}";
        sw["state_topic"] = ld2410TunerStateTopic(cfg);
        sw["state_on"] = "on";
        sw["state_off"] = "off";
        sw["entity_category"] = "config";
        sw["icon"] = "mdi:radar";
        pub(prefix + "/switch/" + cid + "_ld2410_tuner/config", sw);

        json sensor = base("LD2410 Tuner URL", cid + "_ld2410_tuner_url");
        sensor["state_topic"] = ld2410TunerUrlTopic(cfg);
        sensor["entity_category"] = "diagnostic";
        sensor["icon"] = "mdi:web";
        pub(prefix + "/sensor/" + cid + "_ld2410_tuner_url/config", sensor);
    }

    for (const auto& entry : std::vector<std::pair<std::string, std::string>>{
             {"sensor", cid + "_move_energy"},
             {"sensor", cid + "_still_energy"},
             {"binary_sensor", cid + "_update_available"},
             {"sensor", cid + "_update_info"},
             {"button", cid + "_update_check"},
             {"button", cid + "_update_install"},
         }) {
        clearDiscovery(prefix + "/" + entry.first + "/" + entry.second + "/config");
    }
    for (int gate = 0; gate < 9; ++gate) {
        for (const auto& kind : {"move", "still"}) {
            clearDiscovery(prefix + "/sensor/" + cid + "_g" + std::to_string(gate) + "_" + kind + "_energy/config");
            clearDiscovery(prefix + "/number/" + cid + "_g" + std::to_string(gate) + "_" + kind + "_thresh/config");
        }
    }

    std::cout << "[mqtt] HA discovery published\n";
}

static void mqttOnConnect(mosquitto* mosq, void* obj, int rc) {
    if (rc != 0) {
        std::cerr << "[mqtt] connect failed: " << mosquitto_connack_string(rc) << "\n";
        return;
    }
    auto* ctx = static_cast<MqttCtx*>(obj);
    {
        std::lock_guard<std::mutex> lk(*ctx->mtx);
        ctx->clockState->mqttConnected = true;
    }

    auto& topics   = (*ctx->cfg)["mqtt"]["topics"];
    std::string cid = (*ctx->cfg)["mqtt"].value("client_id", "hub75_clock");

    auto pub = [&](const std::string& topic, const std::string& payload, bool retain) {
        mosquitto_publish(mosq, nullptr, topic.c_str(),
                          int(payload.size()), payload.c_str(), 0, retain ? 1 : 0);
    };
    auto sub = [&](const std::string& key, const std::string& fallback = "") {
        std::string t = topics.value(key, fallback);
        if (!t.empty()) mosquitto_subscribe(mosq, nullptr, t.c_str(), 0);
    };

    // Publish availability (mirrors Python: client.publish(topic_avail, "online"))
    pub(topics.value("availability", "hub75_clock/status"), "online", true);

    sub("weather");
    sub("config");
    sub("alert");
    sub("theme");
    sub("gates",            cid + "/gates");
    sub("engineering_mode", cid + "/engineering_mode");
    sub("bucket",           cid + "/bucket");
    sub("ld2410_read",      cid + "/ld2410/read");

    // Gate threshold wildcard topics: {client_id}/gate/+/move_thresh etc.
    mosquitto_subscribe(mosq, nullptr, (cid + "/gate/+/move_thresh").c_str(),  0);
    mosquitto_subscribe(mosq, nullptr, (cid + "/gate/+/still_thresh").c_str(), 0);

    // Publish available themes.
    std::vector<std::string> themeNames;
    {
        json arr = json::array();
        themeNames = ctx->themeLoader->availableThemes();
        for (const auto& n : themeNames) arr.push_back(n);
        pub(topics.value("themes_available", "hub75_clock/themes/available"), arr.dump(), true);
    }

    if (ctx->animator->currentTheme) {
        std::string name = ctx->animator->currentTheme->name;
        pub(topics.value("theme_state", cid + "/theme/state"), name, true);
    }

    // Publish initial brightness state.
    {
        int b = (*ctx->cfg)["panel"].value("brightness", 60);
        pub(cid + "/brightness/state", std::to_string(b), true);
    }

    // Publish initial engineering mode state.
    if (ctx->ld2410) {
        std::string emStateTopic =
            topics.value("engineering_mode", cid + "/engineering_mode") + "/state";
        pub(emStateTopic, ctx->ld2410->engineeringMode() ? "on" : "off", true);
    }
    publishThemeBuilderState(mosq, *ctx->cfg);
    publishLd2410TunerState(mosq, *ctx->cfg);
    publishHomeAssistantDiscovery(mosq, *ctx->cfg, themeNames);

    std::cout << "[mqtt] connected and subscribed\n";
}

static void mqttOnMessage(mosquitto* mosq, void* obj,
                          const mosquitto_message* msg)
{
    auto* ctx = static_cast<MqttCtx*>(obj);
    std::lock_guard<std::mutex> lk(*ctx->mtx);
    auto& topics = (*ctx->cfg)["mqtt"]["topics"];
    std::string cid = (*ctx->cfg)["mqtt"].value("client_id", "hub75_clock");

    std::string topic(msg->topic);
    std::string raw(static_cast<char*>(msg->payload),
                    static_cast<std::size_t>(msg->payloadlen));

    // ── Gate threshold wildcard: {cid}/gate/{n}/move_thresh or still_thresh ──
    // Payload is a plain numeric value, not JSON.
    {
        // Split topic on '/'
        std::vector<std::string> parts;
        {
            std::string seg;
            for (char c : topic) {
                if (c == '/') { parts.push_back(seg); seg.clear(); }
                else seg += c;
            }
            parts.push_back(seg);
        }
        if (parts.size() == 4 && parts[0] == cid && parts[1] == "gate" &&
            (parts[3] == "move_thresh" || parts[3] == "still_thresh"))
        {
            if (ctx->ld2410) {
                try {
                    int gate  = std::stoi(parts[2]);
                    int value = static_cast<int>(std::stod(raw));
                    auto& gt = ctx->ld2410->gateThresholds[gate];
                    if (parts[3] == "move_thresh") gt.move  = value;
                    else                            gt.still = value;
                    ctx->ld2410->writeGateConfig(gate, gt.move, gt.still);
                    // Echo back (mirrors Python publish(msg.topic, str(value), retain=True))
                    mosquitto_publish(mosq, nullptr, topic.c_str(),
                                      int(raw.size()), raw.c_str(), 0, 1);
                } catch (...) {}
            }
            return;
        }
    }

    // ── Parse JSON payload (all remaining topics use JSON) ────────────────
    json payload;
    try {
        payload = json::parse(raw);
    } catch (...) {
        // Some topics (e.g. theme) may carry a plain string.
        payload = raw;
    }

    // ── weather ───────────────────────────────────────────────────────────
    if (topic == topics.value("weather", "")) {
        if (!payload.is_object()) return;
        try {
            if (payload.contains("low_temp"))
                ctx->clockState->lowTemp =
                    std::to_string(static_cast<int>(payload["low_temp"].get<double>()));
            if (payload.contains("high_temp"))
                ctx->clockState->highTemp =
                    std::to_string(static_cast<int>(payload["high_temp"].get<double>()));
            if (payload.contains("condition")) {
                std::string c = payload["condition"].get<std::string>();
                for (auto& ch : c)
                    ch = static_cast<char>(std::toupper(static_cast<unsigned char>(ch)));
                ctx->clockState->condition = c;
                ctx->animator->setCondition(c);
            }
        } catch (const std::exception& e) {
            std::cerr << "[mqtt] weather parse error: " << e.what() << "\n";
        }

    // ── theme ─────────────────────────────────────────────────────────────
    } else if (topic == topics.value("theme", "")) {
        std::string name = payload.is_string() ? payload.get<std::string>()
                         : (payload.is_object() && payload.contains("theme"))
                           ? payload["theme"].get<std::string>() : "";
        if (!name.empty()) {
            ctx->animator->setTheme(name, *ctx->themeLoader);
            std::string stateT = topics.value("theme_state", "hub75_clock/theme/state");
            mosquitto_publish(mosq, nullptr, stateT.c_str(),
                              int(name.size()), name.c_str(), 0, 1);
        }

    // ── config ────────────────────────────────────────────────────────────
    } else if (topic == topics.value("config", "")) {
        if (!payload.is_object()) return;
        try {
            if (payload.contains("brightness")) {
                int b = std::max(1, std::min(100, payload["brightness"].get<int>()));
                (*ctx->cfg)["panel"]["brightness"] = b;
                ctx->matrix->SetBrightness(b);
                std::string bStr = std::to_string(b);
                mosquitto_publish(mosq, nullptr, (cid + "/brightness/state").c_str(),
                                  int(bStr.size()), bStr.c_str(), 0, 1);
            }
            if (payload.contains("fps")) {
                int f = std::max(1, std::min(120, payload["fps"].get<int>()));
                (*ctx->cfg)["animation"]["fps"] = f;
                g_fps.store(f);
            }
            if (payload.contains("theme")) {
                std::string name = payload["theme"].get<std::string>();
                ctx->animator->setTheme(name, *ctx->themeLoader);
                std::string stateT = topics.value("theme_state", "hub75_clock/theme/state");
                mosquitto_publish(mosq, nullptr, stateT.c_str(),
                                  int(name.size()), name.c_str(), 0, 1);
            }
            if (payload.contains("engineering_mode") && ctx->ld2410) {
                bool em = payload["engineering_mode"].get<bool>();
                ctx->ld2410->enableEngineeringMode(em);
                std::string emStateT =
                    topics.value("engineering_mode", cid + "/engineering_mode") + "/state";
                const char* s = em ? "on" : "off";
                mosquitto_publish(mosq, nullptr, emStateT.c_str(),
                                  static_cast<int>(std::strlen(s)), s, 0, 1);
            }
            if (payload.contains("theme_builder")) {
                if (msg->retain) {
                    std::cout << "[theme_builder] ignored retained command\n";
                    publishThemeBuilderState(mosq, *ctx->cfg);
                } else {
                    setThemeBuilderService(mosq, *ctx->cfg, payload["theme_builder"].get<bool>());
                }
            }
            if (payload.contains("ld2410_tuner")) {
                if (msg->retain) {
                    std::cout << "[ld2410_tuner] ignored retained command\n";
                    publishLd2410TunerState(mosq, *ctx->cfg);
                } else {
                    setLd2410TunerService(mosq, *ctx->cfg, payload["ld2410_tuner"].get<bool>());
                }
            }
        } catch (...) {}

    // ── alert ─────────────────────────────────────────────────────────────
    } else if (topic == topics.value("alert", "")) {
        if (!payload.is_object()) return;
        if (payload.value("clear", false) || !payload.contains("message")) {
            ctx->clockState->alertMessage.clear();
        } else {
            ctx->clockState->alertMessage = payload.value("message", "");
        }

    // ── gates (bulk gate configuration) ───────────────────────────────────
    } else if (topic == topics.value("gates", cid + "/gates")) {
        if (!payload.is_object() || !ctx->ld2410) return;
        if (payload.contains("gates")) {
            for (const auto& g : payload["gates"]) {
                int gate = g["gate"].get<int>();
                int mv   = g.value("move",  50);
                int st   = g.value("still", 30);
                ctx->ld2410->gateThresholds[gate] = {mv, st};
                ctx->ld2410->writeGateConfig(gate, mv, st);
            }
        } else if (payload.contains("gate")) {
            int gate = payload["gate"].get<int>();
            int mv   = payload.value("move",  50);
            int st   = payload.value("still", 30);
            ctx->ld2410->gateThresholds[gate] = {mv, st};
            ctx->ld2410->writeGateConfig(gate, mv, st);
        }
        if (payload.contains("engineering_mode") && ctx->ld2410) {
            bool em = payload["engineering_mode"].get<bool>();
            ctx->ld2410->enableEngineeringMode(em);
            std::string emStateT =
                topics.value("engineering_mode", cid + "/engineering_mode") + "/state";
            const char* s = em ? "on" : "off";
            mosquitto_publish(mosq, nullptr, emStateT.c_str(),
                              static_cast<int>(std::strlen(s)), s, 0, 1);
        }

    // ── engineering_mode ──────────────────────────────────────────────────
    } else if (topic == topics.value("engineering_mode", cid + "/engineering_mode")) {
        if (!payload.is_object() || !ctx->ld2410) return;
        if (payload.contains("engineering_mode")) {
            bool em = payload["engineering_mode"].get<bool>();
            ctx->ld2410->enableEngineeringMode(em);
            std::string emStateT = topic + "/state";
            const char* s = em ? "on" : "off";
            mosquitto_publish(mosq, nullptr, emStateT.c_str(),
                              static_cast<int>(std::strlen(s)), s, 0, 1);
        }

    // ── bucket ────────────────────────────────────────────────────────────
    } else if (topic == topics.value("bucket", cid + "/bucket")) {
        if (payload.is_object() && payload.contains("bucket"))
            ctx->clockState->bucket = payload["bucket"].get<std::string>();
        else if (payload.is_string())
            ctx->clockState->bucket = payload.get<std::string>();

    } else if (topic == topics.value("ld2410_read", cid + "/ld2410/read")) {
        if (ctx->ld2410 && !msg->retain) {
            ctx->ld2410->readParametersAndPublish(
                topics.value("ld2410_params", cid + "/ld2410/params"));
        }
    }
}

// ── Main ──────────────────────────────────────────────────────────────────────

int main(int argc, char* argv[]) {
    std::string configPath = "/etc/hub75-clock/config.yaml";
    if (argc > 1) configPath = argv[1];

    json cfg = loadConfig(configPath);

    // Load per-animation speed settings from a separate YAML file.
    {
        const std::string animPath = "/etc/hub75-clock/animations.yaml";
        ensureAnimationSettingsDefaults(animPath);
        if (fs::exists(animPath)) {
            try {
                YAML::Node ay = YAML::LoadFile(animPath);
                cfg["animation_settings"] = yamlToJson(ay);
                std::cout << "[config] loaded " << animPath << "\n";
            } catch (const std::exception& e) {
                std::cerr << "[config] Failed to parse " << animPath << ": " << e.what() << "\n";
                cfg["animation_settings"] = json::object();
            }
        } else {
            cfg["animation_settings"] = json::object();
        }
    }

    // ── Matrix init ───────────────────────────────────────────────────────
    RGBMatrix::Options opts;
    RuntimeOptions rtopts;
    opts.hardware_mapping    = "regular";
    opts.rows                = 32;
    opts.cols                = 64;
    opts.chain_length        = 1;
    opts.parallel            = 1;
    opts.brightness          = cfg["panel"].value("brightness", 60);
    opts.pwm_bits            = cfg["panel"].value("pwm_bits", 11);
    opts.pwm_lsb_nanoseconds = cfg["panel"].value("pwm_lsb_nanoseconds", 130);
    rtopts.gpio_slowdown     = cfg["panel"].value("gpio_slowdown", 2);
    std::string ledRgbSequence = cfg["panel"].value("led_rgb_sequence", std::string("RBG"));
    opts.led_rgb_sequence    = ledRgbSequence.c_str();
    rtopts.drop_privileges   = 0;

    auto* matrix = CreateMatrixFromOptions(opts, rtopts);
    if (!matrix) {
        std::cerr << "[init] Failed to create RGB matrix\n";
        return 1;
    }

    // ── Font loading ──────────────────────────────────────────────────────
    std::string fontsDir   = cfg["fonts"].value("fonts_dir",   "/home/pi/rpi-rgb-led-matrix/fonts");
    std::string bannerPath = fontsDir + "/" + cfg["fonts"].value("banner_name", "4x6.bdf");
    std::string timePath   = fontsDir + "/" + cfg["fonts"].value("time_name",   "spleen-12x24.bdf");

    rgb_matrix::Font fontBanner, fontTime;
    if (!fontBanner.LoadFont(bannerPath.c_str()))
        std::cerr << "[init] Failed to load banner font: " << bannerPath << "\n";
    if (!fontTime.LoadFont(timePath.c_str()))
        std::cerr << "[init] Failed to load time font: " << timePath << "\n";

    // ── Theme loader ──────────────────────────────────────────────────────
    std::string themesDir = cfg["themes"].value("themes_dir", "/etc/hub75-clock/themes");
    ThemeLoader themeLoader(themesDir);

    // ── Weather animator ──────────────────────────────────────────────────
    WeatherAnimator animator(matrix->width(), matrix->height(), cfg, matrix);
    ensureThemeBuilderStartupState(cfg);
    ensureLd2410TunerStartupState(cfg);

    std::string defaultTheme = cfg["themes"].value("default_theme", "Day");
    animator.setTheme(defaultTheme, themeLoader);
    animator.setCondition("CLEAR");

    // ── Clock display state ───────────────────────────────────────────────
    ClockState clockState;

    // ── MQTT ──────────────────────────────────────────────────────────────
    mosquitto_lib_init();
    std::mutex animMtx;
    MqttCtx mqttCtx{&animator, &themeLoader, &clockState, &cfg, &animMtx, matrix};

    std::string clientId = cfg["mqtt"].value("client_id", "hub75_clock");
    auto* mosq = mosquitto_new(clientId.c_str(), true, &mqttCtx);
    if (!mosq) {
        std::cerr << "[mqtt] failed to create client\n";
        delete matrix;
        mosquitto_lib_cleanup();
        return 1;
    }
    mosquitto_connect_callback_set(mosq, mqttOnConnect);
    mosquitto_message_callback_set(mosq, mqttOnMessage);

    auto& topics = cfg["mqtt"]["topics"];
    std::string availabilityTopic = topics.value("availability", "hub75_clock/status");
    mosquitto_will_set(mosq, availabilityTopic.c_str(), 7, "offline", 0, true);

    std::string broker = cfg["mqtt"].value("broker", "");
    int         port   = cfg["mqtt"].value("port", 1883);
    if (!broker.empty()) {
        mosquitto_connect_async(mosq, broker.c_str(), port, 60);
        mosquitto_loop_start(mosq);
    }

    // ── Sensors ───────────────────────────────────────────────────────────
    // Publish helper: mosquitto_publish is thread-safe with loop_start.
    auto sensorPub = [mosq](const std::string& t, const std::string& p, bool retain) {
        mosquitto_publish(mosq, nullptr, t.c_str(),
                          int(p.size()), p.c_str(), 0, retain ? 1 : 0);
    };

    auto& sc = cfg["sensors"];

    std::unique_ptr<VEML7700Sensor> veml;
    if (sc.value("veml7700_enabled", true)) {
        veml = std::make_unique<VEML7700Sensor>(
            sensorPub,
            topics.value("lux", "hub75_clock/lux"),
            sc.value("lux_interval", 10.0));
    }

    std::unique_ptr<PIRSensor> pir;
    if (sc.value("pir_enabled", true)) {
        pir = std::make_unique<PIRSensor>(
            sensorPub,
            topics.value("pir", "hub75_clock/pir"),
            sc.value("pir_gpio",          6),
            sc.value("pir_poll_interval", 0.1),
            sc.value("pir_invert",        false));
    }

    std::unique_ptr<LD2410Sensor> ld2410;
    if (sc.value("ld2410_enabled", true)) {
        ld2410 = std::make_unique<LD2410Sensor>(
            sensorPub,
            topics.value("presence", "hub75_clock/presence"),
            topics.value("motion",   "hub75_clock/motion"),
            sc.value("ld2410_port", std::string("/dev/serial0")),
            static_cast<unsigned>(sc.value("ld2410_baud", 256000)));
    }

    // Wire LD2410 into MQTT context so gate/engineering_mode handlers work.
    mqttCtx.ld2410 = ld2410.get();

    if (veml)   veml->start();
    if (pir)    pir->start();
    if (ld2410) ld2410->start();

    // ── Signal handlers ───────────────────────────────────────────────────
    std::signal(SIGINT,  onSignal);
    std::signal(SIGTERM, onSignal);

    // ── Render loop ───────────────────────────────────────────────────────
    auto* canvas = matrix->CreateFrameCanvas();
    g_fps.store(std::max(1, cfg["animation"].value("fps", 90)));
    auto lastThemeCheck = std::chrono::steady_clock::now();
    std::uint64_t lastThemeSig = themeDirSignature(themesDir);

    while (g_running) {
        auto t0      = std::chrono::steady_clock::now();
        auto frameUs = std::chrono::microseconds(1'000'000 / std::max(1, g_fps.load()));

        if (t0 - lastThemeCheck >= std::chrono::seconds(1)) {
            lastThemeCheck = t0;
            std::uint64_t sig = themeDirSignature(themesDir);
            if (sig != lastThemeSig) {
                lastThemeSig = sig;
                std::lock_guard<std::mutex> lk(animMtx);
                std::string activeTheme = animator.currentTheme
                    ? animator.currentTheme->name
                    : cfg["themes"].value("default_theme", "Day");
                themeLoader.loadAll();
                animator.setTheme(activeTheme, themeLoader);

                auto themeNames = themeLoader.availableThemes();
                std::string themeList = json(themeNames).dump();
                mosquitto_publish(mosq, nullptr,
                                  topics.value("themes_available", clientId + "/themes/available").c_str(),
                                  int(themeList.size()), themeList.c_str(), 0, 1);
                if (animator.currentTheme) {
                    std::string name = animator.currentTheme->name;
                    mosquitto_publish(mosq, nullptr,
                                      topics.value("theme_state", clientId + "/theme/state").c_str(),
                                      int(name.size()), name.c_str(), 0, 1);
                }
                publishHomeAssistantDiscovery(mosq, cfg, themeNames);
                std::cout << "[theme_loader] reloaded themes\n";
            }
        }

        canvas->Clear();
        {
            std::lock_guard<std::mutex> lk(animMtx);
            animator.update();
            animator.draw(canvas);
            drawBanner(canvas, clockState, animator, cfg, fontBanner);
            drawTime(canvas, animator, cfg, fontTime);
        }
        canvas = matrix->SwapOnVSync(canvas);

        auto elapsed = std::chrono::steady_clock::now() - t0;
        if (elapsed < frameUs) std::this_thread::sleep_for(frameUs - elapsed);
    }

    // ── Cleanup ───────────────────────────────────────────────────────────
    // Stop sensors before MQTT loop_stop to avoid publishing after disconnect.
    if (veml)   veml->stop();
    if (pir)    pir->stop();
    if (ld2410) ld2410->stop();

    matrix->Clear();
    mosquitto_publish(mosq, nullptr, availabilityTopic.c_str(), 7, "offline", 0, true);
    mosquitto_loop_stop(mosq, false);
    mosquitto_destroy(mosq);
    mosquitto_lib_cleanup();
    delete matrix;

    return 0;
}
