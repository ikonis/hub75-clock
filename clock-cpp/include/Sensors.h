#pragma once
// Sensors.h — VEML7700 (I2C lux), LD2410C (mmWave UART), PIR (GPIO) sensors.
// All run in background std::thread threads. Linux/Raspberry Pi only.

#include <atomic>
#include <chrono>
#include <condition_variable>
#include <cstdint>
#include <deque>
#include <functional>
#include <mutex>
#include <string>
#include <thread>
#include <vector>

// Publish callback: topic, payload, retain. mosquitto_publish is thread-safe
// in async mode so sensors call this directly from their background threads.
using SensorPublish = std::function<void(const std::string& topic,
                                          const std::string& payload,
                                          bool retain)>;

// ── VEML7700 lux sensor ───────────────────────────────────────────────────────
// I2C address 0x10 on /dev/i2c-1.  Reads ALS register every lux_interval
// seconds and publishes {"lux": X.XX} to the configured topic.

class VEML7700Sensor {
public:
    VEML7700Sensor(SensorPublish pub, const std::string& topic, double intervalSec);
    ~VEML7700Sensor();
    void start();
    void stop();

private:
    SensorPublish     _pub;
    std::string       _topic;
    double            _intervalSec;
    int               _fd = -1;
    std::atomic<bool> _running{false};
    std::thread       _thread;

    bool   _init();
    double _readLux();
    void   _run();
};

// ── PIR motion sensor ─────────────────────────────────────────────────────────
// GPIO via /sys/class/gpio.  Polls every pir_poll_interval seconds with a
// 500 ms debounce and publishes {"motion": true/false} to the configured topic.

class PIRSensor {
public:
    PIRSensor(SensorPublish pub, const std::string& topic,
              int gpioPin, double pollSec, bool invert);
    ~PIRSensor();
    void start();
    void stop();

private:
    SensorPublish     _pub;
    std::string       _topic;
    int               _pin;
    double            _pollSec;
    bool              _invert;
    void*             _chip = nullptr;
    void*             _line = nullptr;
    std::atomic<bool> _running{false};
    std::thread       _thread;

    bool _init();
    bool _readPin() const;
    void _run();
};

// ── LD2410C mmWave radar ──────────────────────────────────────────────────────
// UART on /dev/serial0 at 256000 baud.  Parses data frames (basic type 0x02
// and engineering type 0x01), throttles publishes to ≥ 500 ms apart.
// Engineering mode can be toggled via MQTT. Threshold tuning lives in the
// standalone direct-UART web tuner.

class LD2410Sensor {
public:
    LD2410Sensor(SensorPublish pub,
                 const std::string& presenceTopic,
                 const std::string& motionTopic,
                 const std::string& port,
                 unsigned baud);
    ~LD2410Sensor();
    void start();
    void stop();

    // Thread-safe: runs command writes off the MQTT callback thread.
    void enableEngineeringMode(bool enable);

    bool engineeringMode() const { return _engineeringMode.load(); }

private:
    SensorPublish     _pub;
    std::string       _presenceTopic, _motionTopic;
    std::string       _port;
    unsigned          _baud;
    int               _fd = -1;
    std::atomic<bool> _running{false};
    std::atomic<bool> _engineeringMode{false};
    std::atomic<bool> _engineeringCommandRunning{false};
    std::thread       _thread;
    std::vector<std::thread> _commandThreads;
    std::mutex        _writeMtx;
    std::mutex        _commandThreadsMtx;
    std::mutex        _cmdResponseMtx;
    std::condition_variable _cmdResponseCv;
    std::deque<std::vector<uint8_t>> _cmdResponses;
    std::chrono::steady_clock::time_point _lastPub{};

    // Frame magic bytes (Python HEAD/TAIL/CMD_HEAD/CMD_TAIL)
    static constexpr uint8_t HEAD[4]     = {0xF4, 0xF3, 0xF2, 0xF1};
    static constexpr uint8_t TAIL[4]     = {0xF8, 0xF7, 0xF6, 0xF5};
    static constexpr uint8_t CMD_HEAD[4] = {0xFD, 0xFC, 0xFB, 0xFA};
    static constexpr uint8_t CMD_TAIL[4] = {0x04, 0x03, 0x02, 0x01};

    bool _init();
    void _sendCmd(const uint8_t* cmdWord, size_t cwLen,
                  const uint8_t* data = nullptr, size_t dataLen = 0);
    void _enableEngineeringModeImpl(bool enable);
    std::vector<uint8_t> _sendCmdWait(const uint8_t* cmdWord, size_t cwLen,
                                      const uint8_t* data = nullptr, size_t dataLen = 0);
    void _run();
    void _process(std::vector<uint8_t>& buf);
    void _parseBasic(const uint8_t* data, size_t len);
    void _parseEngineering(const uint8_t* data, size_t len);
};
