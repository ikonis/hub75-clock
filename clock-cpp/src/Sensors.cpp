// Sensors.cpp — Linux userspace sensor implementations.
#include "Sensors.h"

#include <algorithm>
#include <cerrno>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <iostream>
#include <string>

// POSIX / Linux platform headers
#include <fcntl.h>
#include <unistd.h>
#include <sys/ioctl.h>

// I2C userspace API (libi2c-dev / linux-headers)
#include <linux/i2c-dev.h>
#include <linux/i2c.h>
#include <gpiod.h>

// Defined in Serial.cpp
int openSerialPort(const char* port, unsigned baud);

// which are needed for the non-POSIX 256000 baud rate.

// ═══════════════════════════════════════════════════════════════════════════
// VEML7700 lux sensor
// ═══════════════════════════════════════════════════════════════════════════

static constexpr int     VEML7700_ADDR    = 0x10;
static constexpr uint8_t VEML7700_REG_CFG = 0x00;
static constexpr uint8_t VEML7700_REG_ALS = 0x04;

VEML7700Sensor::VEML7700Sensor(SensorPublish pub,
                                const std::string& topic,
                                double intervalSec)
    : _pub(std::move(pub)), _topic(topic), _intervalSec(intervalSec)
{
    if (!_init())
        std::cerr << "[veml7700] sensor not available — skipping\n";
}

VEML7700Sensor::~VEML7700Sensor() { stop(); }

bool VEML7700Sensor::_init() {
    _fd = open("/dev/i2c-1", O_RDWR);
    if (_fd < 0) return false;

    // Write config register 0x00 = 0x0000: 1x gain, 100 ms IT, ALS enabled.
    uint8_t cfgbuf[3] = {VEML7700_REG_CFG, 0x00, 0x00};
    struct i2c_msg wmsg;
    wmsg.addr  = static_cast<__u16>(VEML7700_ADDR);
    wmsg.flags = 0;
    wmsg.len   = 3;
    wmsg.buf   = cfgbuf;
    struct i2c_rdwr_ioctl_data wrdwr;
    wrdwr.msgs  = &wmsg;
    wrdwr.nmsgs = 1;
    if (ioctl(_fd, I2C_RDWR, &wrdwr) < 0) {
        close(_fd);
        _fd = -1;
        return false;
    }

    usleep(200'000); // 200 ms sensor warmup
    std::cout << "[veml7700] initialized on /dev/i2c-1\n";
    return true;
}

void VEML7700Sensor::start() {
    if (_fd < 0) return;
    _running = true;
    _thread  = std::thread([this] { _run(); });
}

void VEML7700Sensor::stop() {
    _running = false;
    if (_thread.joinable()) _thread.join();
    if (_fd >= 0) { close(_fd); _fd = -1; }
}

double VEML7700Sensor::_readLux() {
    // Combined write (register pointer) + read (2 bytes ALS data)
    // using I2C_RDWR for correct repeated-start behaviour.
    uint8_t reg = VEML7700_REG_ALS;
    uint8_t buf[2] = {};

    struct i2c_msg msgs[2];
    msgs[0].addr  = static_cast<__u16>(VEML7700_ADDR);
    msgs[0].flags = 0;
    msgs[0].len   = 1;
    msgs[0].buf   = &reg;
    msgs[1].addr  = static_cast<__u16>(VEML7700_ADDR);
    msgs[1].flags = I2C_M_RD;
    msgs[1].len   = 2;
    msgs[1].buf   = buf;

    struct i2c_rdwr_ioctl_data rdwr;
    rdwr.msgs  = msgs;
    rdwr.nmsgs = 2;

    if (ioctl(_fd, I2C_RDWR, &rdwr) < 0) return -1.0;

    uint16_t raw = static_cast<uint16_t>(buf[0]) |
                   (static_cast<uint16_t>(buf[1]) << 8);
    double lux = raw * 0.0576; // resolution: 1x gain, 100 ms IT

    // Adafruit non-linear correction for high lux values (> 1000 lx)
    if (lux > 1000.0) {
        lux = 6.0135e-13 * (lux * lux * lux * lux)
            - 9.3924e-9  * (lux * lux * lux)
            + 8.1488e-5  * (lux * lux)
            + 1.0023     *  lux;
    }
    return lux;
}

void VEML7700Sensor::_run() {
    while (_running) {
        double lux = _readLux();
        if (lux >= 0.0) {
            char payload[64];
            std::snprintf(payload, sizeof(payload), "{\"lux\": %.2f}", lux);
            _pub(_topic, payload, true);
        } else {
            std::cerr << "[veml7700] read error\n";
        }
        // Interruptible sleep: check _running every 100 ms.
        auto deadline = std::chrono::steady_clock::now() +
                        std::chrono::milliseconds(static_cast<int>(_intervalSec * 1000.0));
        while (_running && std::chrono::steady_clock::now() < deadline)
            std::this_thread::sleep_for(std::chrono::milliseconds(100));
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// PIR motion sensor
// ═══════════════════════════════════════════════════════════════════════════

PIRSensor::PIRSensor(SensorPublish pub, const std::string& topic,
                     int gpioPin, double pollSec, bool invert)
    : _pub(std::move(pub)), _topic(topic),
      _pin(gpioPin), _pollSec(pollSec), _invert(invert)
{
    if (!_init())
        std::cerr << "[pir] sensor not available on GPIO" << _pin << " — skipping\n";
}

PIRSensor::~PIRSensor() { stop(); }

bool PIRSensor::_init() {
    errno = 0;
    struct gpiod_chip* chip = gpiod_chip_open("/dev/gpiochip0");
    int pathErrno = errno;
    if (!chip) {
        errno = 0;
        chip = gpiod_chip_open_by_name("gpiochip0");
    }
    int nameErrno = errno;
    if (!chip) {
        std::cerr << "[pir] failed to open /dev/gpiochip0: "
                  << std::strerror(pathErrno)
                  << "; by-name gpiochip0: " << std::strerror(nameErrno) << "\n";
        return false;
    }
    std::cout << "[pir] opened gpiochip0 for GPIO" << _pin << "\n";

    errno = 0;
    struct gpiod_line* line = gpiod_chip_get_line(chip, _pin);
    if (!line) {
        std::cerr << "[pir] failed to get GPIO line " << _pin
                  << ": " << std::strerror(errno) << "\n";
        gpiod_chip_close(chip);
        return false;
    }
    errno = 0;
    if (gpiod_line_request_input(line, "hub75_clock") < 0) {
        std::cerr << "[pir] failed to request GPIO" << _pin
                  << " as input: " << std::strerror(errno) << "\n";
        gpiod_chip_close(chip);
        return false;
    }
    _chip = chip;
    _line = line;
    std::cout << "[pir] initialized on GPIO" << _pin << "\n";
    return true;
}

void PIRSensor::start() {
    if (!_line) return;
    _running = true;
    _thread  = std::thread([this] { _run(); });
}

void PIRSensor::stop() {
    _running = false;
    if (_thread.joinable()) _thread.join();
}

bool PIRSensor::_readPin() const {
    if (!_line) return false;
    int val = gpiod_line_get_value(static_cast<struct gpiod_line*>(_line));
    if (val < 0) return false;
    bool raw = (val == 1);
    return _invert ? !raw : raw;
}

void PIRSensor::_run() {
    // Mirror Python debounce logic exactly:
    //   track raw state + timestamp of last change;
    //   only publish when stable for >= 500 ms.
    bool rawState  = _readPin();
    bool lastState = rawState;
    auto rawChangedAt = std::chrono::steady_clock::now();

    while (_running) {
        bool raw = _readPin();

        if (raw != rawState) {
            rawState     = raw;
            rawChangedAt = std::chrono::steady_clock::now();
        }

        double stable = std::chrono::duration<double>(
            std::chrono::steady_clock::now() - rawChangedAt).count();

        if (rawState != lastState && stable >= 0.5) {
            lastState = rawState;
            _pub(_topic,
                 rawState ? "{\"motion\": true}" : "{\"motion\": false}",
                 true);
        }

        // Interruptible poll sleep.
        auto sleepMs = static_cast<int>(_pollSec * 1000.0);
        auto deadline = std::chrono::steady_clock::now() +
                        std::chrono::milliseconds(sleepMs);
        while (_running && std::chrono::steady_clock::now() < deadline)
            std::this_thread::sleep_for(std::chrono::milliseconds(10));
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// LD2410C mmWave radar
// ═══════════════════════════════════════════════════════════════════════════

// Open a serial port at an arbitrary baud rate using termios2 + BOTHER.
// This avoids the absence of B256000 in POSIX termios baud-rate constants.
static int openSerialCustomBaud(const std::string& port, unsigned baud) {
    return openSerialPort(port.c_str(), baud);
}

LD2410Sensor::LD2410Sensor(SensorPublish pub,
                            const std::string& presenceTopic,
                            const std::string& motionTopic,
                            const std::string& port,
                            unsigned baud)
    : _pub(std::move(pub))
    , _presenceTopic(presenceTopic)
    , _motionTopic(motionTopic)
    , _port(port)
    , _baud(baud)
{
    if (!_init())
        std::cerr << "[ld2410] sensor not available on " << _port << " — skipping\n";
}

LD2410Sensor::~LD2410Sensor() { stop(); }

bool LD2410Sensor::_init() {
    _fd = openSerialCustomBaud(_port, _baud);
    if (_fd < 0) return false;
    std::cout << "[ld2410] opened " << _port << " at " << _baud << " baud\n";
    return true;
}

void LD2410Sensor::start() {
    if (_fd < 0) return;
    _running = true;
    usleep(100'000);
    _thread = std::thread([this] { _run(); });
}

void LD2410Sensor::stop() {
    _running = false;
    if (_thread.joinable()) _thread.join();
    {
        std::lock_guard<std::mutex> lk(_commandThreadsMtx);
        for (auto& t : _commandThreads) {
            if (t.joinable()) t.join();
        }
        _commandThreads.clear();
    }
    if (_fd >= 0) { close(_fd); _fd = -1; }
}

void LD2410Sensor::_sendCmd(const uint8_t* cmdWord, size_t cwLen,
                             const uint8_t* data,    size_t dataLen)
{
    if (_fd < 0) return;
    size_t payloadLen = cwLen + dataLen;
    std::vector<uint8_t> frame;
    frame.reserve(4 + 2 + payloadLen + 4);
    frame.insert(frame.end(), CMD_HEAD, CMD_HEAD + 4);
    frame.push_back(static_cast<uint8_t>(payloadLen & 0xFF));
    frame.push_back(static_cast<uint8_t>((payloadLen >> 8) & 0xFF));
    frame.insert(frame.end(), cmdWord, cmdWord + cwLen);
    if (data && dataLen > 0) frame.insert(frame.end(), data, data + dataLen);
    frame.insert(frame.end(), CMD_TAIL, CMD_TAIL + 4);
    {
        std::lock_guard<std::mutex> lk(_writeMtx);
        write(_fd, frame.data(), frame.size());
    }
    usleep(50'000); // 50 ms inter-command gap
}

std::vector<uint8_t> LD2410Sensor::_sendCmdWait(const uint8_t* cmdWord, size_t cwLen,
                                                const uint8_t* data, size_t dataLen)
{
    {
        std::lock_guard<std::mutex> lk(_cmdResponseMtx);
        _cmdResponses.clear();
    }
    _sendCmd(cmdWord, cwLen, data, dataLen);
    auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(1);
    std::unique_lock<std::mutex> lk(_cmdResponseMtx);
    while (std::chrono::steady_clock::now() < deadline) {
        while (!_cmdResponses.empty()) {
            auto payload = std::move(_cmdResponses.front());
            _cmdResponses.pop_front();
            if (payload.size() >= 2 && payload[0] == cmdWord[0] &&
                payload[1] == static_cast<uint8_t>(cmdWord[1] + 1)) {
                return payload;
            }
        }
        _cmdResponseCv.wait_until(lk, deadline);
    }
    return {};
}

void LD2410Sensor::_enableEngineeringModeImpl(bool enable) {
    static const uint8_t ENTER_CFG[] = {0xFF, 0x00};
    static const uint8_t END_CFG[]   = {0xFE, 0x00};
    static const uint8_t ENG_ON[]    = {0x62, 0x00};
    static const uint8_t ENG_OFF[]   = {0x63, 0x00};

    _sendCmd(ENTER_CFG, 2);
    usleep(100'000);
    if (enable) _sendCmd(ENG_ON,  2);
    else        _sendCmd(ENG_OFF, 2);
    usleep(100'000);
    _sendCmd(END_CFG, 2);
    _engineeringMode = enable;
    std::cout << "[ld2410] engineering mode " << (enable ? "enabled" : "disabled") << "\n";
}

void LD2410Sensor::enableEngineeringMode(bool enable) {
    bool expected = false;
    if (!_engineeringCommandRunning.compare_exchange_strong(expected, true)) return;

    std::lock_guard<std::mutex> lk(_commandThreadsMtx);
    _commandThreads.emplace_back([this, enable] {
        try {
            _enableEngineeringModeImpl(enable);
        } catch (...) {
        }
        _engineeringCommandRunning = false;
    });
}

void LD2410Sensor::_run() {
    std::vector<uint8_t> buf;
    buf.reserve(512);

    while (_running) {
        uint8_t tmp[128];
        ssize_t n = read(_fd, tmp, sizeof(tmp));
        if (n > 0) {
            buf.insert(buf.end(), tmp, tmp + n);
            _process(buf);
        } else {
            usleep(20'000); // 20 ms idle back-off
        }
    }
}

void LD2410Sensor::_process(std::vector<uint8_t>& buf) {
    while (true) {
        auto cmdIt = std::search(buf.begin(), buf.end(), CMD_HEAD, CMD_HEAD + 4);
        auto dataIt = std::search(buf.begin(), buf.end(), HEAD, HEAD + 4);
        if (cmdIt != buf.end() && (dataIt == buf.end() || cmdIt < dataIt)) {
            if (cmdIt != buf.begin()) buf.erase(buf.begin(), cmdIt);
            if (buf.size() < 10) return;
            size_t dl = static_cast<size_t>(buf[4]) | (static_cast<size_t>(buf[5]) << 8);
            if (dl > 512) {
                buf.clear();
                return;
            }
            size_t total = 4 + 2 + dl + 4;
            if (buf.size() < total) return;
            if (std::memcmp(buf.data() + total - 4, CMD_TAIL, 4) != 0) {
                buf.erase(buf.begin());
                continue;
            }
            std::vector<uint8_t> payload(buf.begin() + 6, buf.begin() + 6 + static_cast<std::ptrdiff_t>(dl));
            {
                std::lock_guard<std::mutex> lk(_cmdResponseMtx);
                _cmdResponses.push_back(std::move(payload));
            }
            _cmdResponseCv.notify_all();
            buf.erase(buf.begin(), buf.begin() + static_cast<std::ptrdiff_t>(total));
            continue;
        }

        // Find the 4-byte data frame header.
        auto it = dataIt;
        if (it == buf.end()) {
            if (buf.size() > 1024) buf.erase(buf.begin(), buf.end() - 4);
            return;
        }
        if (it != buf.begin()) buf.erase(buf.begin(), it);
        if (buf.size() < 10) return; // need at least head(4) + len(2) + tail(4)

        size_t dl    = static_cast<size_t>(buf[4]) | (static_cast<size_t>(buf[5]) << 8);
        if (dl > 512) {
            buf.clear();
            return;
        }
        size_t total = 4 + 2 + dl + 4;
        if (buf.size() < total) return;

        // Verify TAIL.
        if (std::memcmp(buf.data() + total - 4, TAIL, 4) != 0) {
            buf.erase(buf.begin()); // corrupt — advance one byte and re-scan
            continue;
        }

        const uint8_t* data = buf.data() + 6;
        if (dl > 0) {
            if      (data[0] == 0x01) _parseEngineering(data, dl);
            else if (data[0] == 0x02) _parseBasic(data, dl);
        }
        buf.erase(buf.begin(), buf.begin() + static_cast<std::ptrdiff_t>(total));
    }
}

void LD2410Sensor::_parseBasic(const uint8_t* data, size_t len) {
    // data[0]=0x02, data[1]=0xAA, data[2]=target, data[3:5]=move_dist,
    // data[5]=move_e, data[6:8]=still_dist, data[8]=still_e
    if (len < 13 || data[1] != 0xAA) return;

    auto now = std::chrono::steady_clock::now();
    if (std::chrono::duration<double>(now - _lastPub).count() < 0.5) return;
    _lastPub = now;

    uint8_t  target    = data[2];
    uint16_t moveDist  = static_cast<uint16_t>(data[3]) | (static_cast<uint16_t>(data[4]) << 8);
    uint8_t  moveE     = data[5];
    uint16_t stillDist = static_cast<uint16_t>(data[6]) | (static_cast<uint16_t>(data[7]) << 8);
    uint8_t  stillE    = data[8];

    char presenceBuf[128];
    std::snprintf(presenceBuf, sizeof(presenceBuf),
        "{\"presence\": %s, \"target_state\": %d"
        ", \"move_distance\": %d, \"still_distance\": %d}",
        (target != 0x00) ? "true" : "false",
        static_cast<int>(target),
        static_cast<int>(moveDist),
        static_cast<int>(stillDist));
    _pub(_presenceTopic, presenceBuf, true);

    char motionBuf[64];
    std::snprintf(motionBuf, sizeof(motionBuf),
        "{\"move_energy\": %d, \"still_energy\": %d}",
        static_cast<int>(moveE), static_cast<int>(stillE));
    _pub(_motionTopic, motionBuf, false);
}

void LD2410Sensor::_parseEngineering(const uint8_t* data, size_t len) {
    // data[0]=0x01, data[1]=0xAA, data[2]=target, data[3:5]=move_dist,
    // data[5]=move_e, data[6:8]=still_dist, data[8]=still_e,
    // data[9:11]=detect_distance, data[11]=max_move_gate,
    // data[12]=max_still_gate, data[13:22]=9 move gate energies,
    // data[22:31]=9 still gate energies.
    if (len < 31 || data[1] != 0xAA) return;

    auto now = std::chrono::steady_clock::now();
    if (std::chrono::duration<double>(now - _lastPub).count() < 0.5) return;
    _lastPub = now;

    uint8_t  target    = data[2];
    uint16_t moveDist  = static_cast<uint16_t>(data[3]) | (static_cast<uint16_t>(data[4]) << 8);
    uint8_t  moveE     = data[5];
    uint16_t stillDist = static_cast<uint16_t>(data[6]) | (static_cast<uint16_t>(data[7]) << 8);
    uint8_t  stillE    = data[8];
    const uint8_t* moveGates  = data + 13; // 9 bytes, gates 0-8
    const uint8_t* stillGates = data + 22; // 9 bytes, gates 0-8

    char presenceBuf[128];
    std::snprintf(presenceBuf, sizeof(presenceBuf),
        "{\"presence\": %s, \"target_state\": %d"
        ", \"move_distance\": %d, \"still_distance\": %d}",
        (target != 0x00) ? "true" : "false",
        static_cast<int>(target),
        static_cast<int>(moveDist),
        static_cast<int>(stillDist));
    _pub(_presenceTopic, presenceBuf, true);

    // Build motion payload; include gate arrays only when engineering mode is active.
    std::string motion;
    motion.reserve(128);
    motion  = "{\"move_energy\": ";
    motion += std::to_string(static_cast<int>(moveE));
    motion += ", \"still_energy\": ";
    motion += std::to_string(static_cast<int>(stillE));
    if (_engineeringMode.load()) {
        motion += ", \"move_gates\": [";
        for (int i = 0; i < 9; ++i) {
            if (i > 0) motion += ", ";
            motion += std::to_string(static_cast<int>(moveGates[i]));
        }
        motion += "], \"still_gates\": [";
        for (int i = 0; i < 9; ++i) {
            if (i > 0) motion += ", ";
            motion += std::to_string(static_cast<int>(stillGates[i]));
        }
        motion += "]";
    }
    motion += "}";
    _pub(_motionTopic, motion, false);
}
