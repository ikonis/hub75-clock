#include "WeatherAnimator.h"
#include "Theme.h"

#include <led-matrix.h>
#include <graphics.h>

#include <yaml-cpp/yaml.h>
#include <nlohmann/json.hpp>
#include <mosquitto.h>

#include <atomic>
#include <csignal>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <mutex>
#include <string>
#include <thread>
#include <chrono>

using json = nlohmann::json;
namespace fs = std::filesystem;

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
            }},
        }},
        {"ha_discovery", {
            {"enabled",            true},
            {"prefix",             "homeassistant"},
            {"ha_discovery_name",  "HUB75 Clock"},
            {"ha_discovery_area",  ""},
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
            {"time_night",      "#505050"},
            {"low_temp_day",    "#00CCFF"},
            {"low_temp_night",  "#004455"},
            {"high_temp_day",   "#FF8C00"},
            {"high_temp_night", "#553300"},
            {"condition_day",   "#909090"},
            {"condition_night", "#404040"},
            {"alert_text",      "#FFFFFF"},
            {"alert_bg",        "#CC0000"},
            {"rain_day",        {22, 42, 115}},
            {"rain_night",      {10, 18, 50}},
            {"snow_day",        {180, 180, 200}},
            {"snow_night",      {50, 50, 70}},
            {"sleet_day",       {120, 160, 180}},
            {"sleet_night",     {40, 55, 70}},
            {"lightning",       {200, 200, 40}},
            {"cloud_day",       {70, 70, 70}},
            {"cloud_night",     {25, 25, 25}},
            {"sun_day",         {220, 160, 30}},
            {"sun_night",       {70, 50, 10}},
            {"ice_day",         {80, 140, 160}},
            {"ice_night",       {25, 45, 55}},
            {"outline",         {0, 0, 0}},
            {"sky_day",         "#000820"},
            {"separator",       "#1A1A1A"},
            {"evening_top",     "#0F0019"},
            {"evening_bottom",  "#3C1400"},
            {"night_bg",        "#020005"},
            {"late_evening_bg", "#05000F"},
        }},
        {"animation", {
            {"fps",                        15},
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
    };
}

// ── Config loader ─────────────────────────────────────────────────────────────

static json loadConfig(const std::string& path) {
    json cfg = defaults();
    if (!fs::exists(path)) {
        std::cerr << "[config] " << path << " not found — using defaults\n";
        return cfg;
    }
    try {
        YAML::Node y = YAML::LoadFile(path);
        // Deep-merge: cfg values overridden by file values where present.
        // TODO: implement recursive merge helper.
        (void)y;
    } catch (const std::exception& e) {
        std::cerr << "[config] Failed to parse " << path << ": " << e.what() << "\n";
    }
    return cfg;
}

// ── Signal handling ───────────────────────────────────────────────────────────

static std::atomic<bool> g_running{true};

static void onSignal(int) {
    g_running = false;
}

// ── MQTT callbacks ────────────────────────────────────────────────────────────

struct MqttCtx {
    WeatherAnimator* animator;
    ThemeLoader*     themeLoader;
    json*            cfg;
    std::mutex*      mtx;
};

static void mqttOnConnect(mosquitto* /*mosq*/, void* obj, int rc) {
    if (rc != 0) {
        std::cerr << "[mqtt] connect failed: " << mosquitto_connack_string(rc) << "\n";
        return;
    }
    auto* ctx = static_cast<MqttCtx*>(obj);
    auto& topics = (*ctx->cfg)["mqtt"]["topics"];

    auto sub = [&](const std::string& key) {
        mosquitto_subscribe(nullptr, nullptr,
                            topics.value(key, "").c_str(), 0);
    };
    // Subscribe to inbound control topics.
    sub("weather");
    sub("config");
    sub("alert");
    sub("theme");
    sub("gates");
    sub("engineering_mode");
    sub("bucket");

    std::cout << "[mqtt] connected and subscribed\n";
}

static void mqttOnMessage(mosquitto* mosq, void* obj,
                           const mosquitto_message* msg) {
    auto* ctx     = static_cast<MqttCtx*>(obj);
    std::lock_guard<std::mutex> lk(*ctx->mtx);
    auto& topics  = (*ctx->cfg)["mqtt"]["topics"];
    std::string topic(msg->topic);
    std::string payload(static_cast<char*>(msg->payload),
                        static_cast<std::size_t>(msg->payloadlen));

    if (topic == topics.value("weather", "")) {
        // TODO: parse weather JSON, call animator->setCondition().
        (void)mosq;
    } else if (topic == topics.value("theme", "")) {
        ctx->animator->setTheme(payload, *ctx->themeLoader);
    }
    // TODO: handle config, alert, gates, engineering_mode, bucket topics.
}

// ── Main ──────────────────────────────────────────────────────────────────────

int main(int argc, char* argv[]) {
    std::string configPath = "/etc/hub75-clock/config.yaml";
    if (argc > 1) configPath = argv[1];

    json cfg = loadConfig(configPath);

    // ── Matrix init ───────────────────────────────────────────────────────
    rgb_matrix::RGBMatrixOptions opts;
    opts.hardware_mapping   = "regular";
    opts.rows               = 32;
    opts.cols               = 64;
    opts.chain_length       = 1;
    opts.parallel           = 1;
    opts.gpio_slowdown      = cfg["panel"].value("gpio_slowdown", 2);
    opts.brightness         = cfg["panel"].value("brightness", 60);
    opts.pwm_bits           = cfg["panel"].value("pwm_bits", 11);
    opts.pwm_lsb_nanoseconds = cfg["panel"].value("pwm_lsb_nanoseconds", 130);

    rgb_matrix::RuntimeOptions rtopts;
    rtopts.gpio_slowdown    = opts.gpio_slowdown;
    rtopts.drop_privileges  = 1;

    auto* matrix = rgb_matrix::CreateMatrixFromOptions(opts, rtopts);
    if (!matrix) {
        std::cerr << "[init] Failed to create RGB matrix\n";
        return 1;
    }

    // ── Theme loader ──────────────────────────────────────────────────────
    std::string themesDir = cfg["themes"].value("themes_dir", "/etc/hub75-clock/themes");
    ThemeLoader themeLoader(themesDir);

    // ── Weather animator ──────────────────────────────────────────────────
    WeatherAnimator animator(matrix->width(), matrix->height(), cfg, matrix);

    std::string defaultTheme = cfg["themes"].value("default_theme", "Day");
    animator.setTheme(defaultTheme, themeLoader);
    animator.setCondition("CLEAR");

    // ── MQTT ──────────────────────────────────────────────────────────────
    mosquitto_lib_init();
    std::mutex animMtx;
    MqttCtx mqttCtx{&animator, &themeLoader, &cfg, &animMtx};

    std::string clientId = cfg["mqtt"].value("client_id", "hub75_clock");
    auto* mosq = mosquitto_new(clientId.c_str(), true, &mqttCtx);
    mosquitto_connect_callback_set(mosq, mqttOnConnect);
    mosquitto_message_callback_set(mosq, mqttOnMessage);

    std::string broker = cfg["mqtt"].value("broker", "");
    int         port   = cfg["mqtt"].value("port", 1883);
    if (!broker.empty()) {
        mosquitto_connect_async(mosq, broker.c_str(), port, 60);
        mosquitto_loop_start(mosq);
    }

    // ── Signal handlers ───────────────────────────────────────────────────
    std::signal(SIGINT,  onSignal);
    std::signal(SIGTERM, onSignal);

    // ── Render loop ───────────────────────────────────────────────────────
    auto* canvas = matrix->CreateFrameCanvas();
    int fps    = cfg["animation"].value("fps", 15);
    auto frame_us = std::chrono::microseconds(1'000'000 / fps);

    while (g_running) {
        auto t0 = std::chrono::steady_clock::now();

        canvas->Clear();
        {
            std::lock_guard<std::mutex> lk(animMtx);
            animator.update();
            animator.draw(canvas);
        }
        canvas = matrix->SwapOnVSync(canvas);

        auto elapsed = std::chrono::steady_clock::now() - t0;
        if (elapsed < frame_us) {
            std::this_thread::sleep_for(frame_us - elapsed);
        }
    }

    // ── Cleanup ───────────────────────────────────────────────────────────
    matrix->Clear();
    mosquitto_loop_stop(mosq, true);
    mosquitto_destroy(mosq);
    mosquitto_lib_cleanup();
    delete matrix;

    return 0;
}
