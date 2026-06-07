// Serial.cpp — isolated serial port init for non-standard baud rates.
// Uses raw ioctl with manually defined termios2 to avoid all header conflicts.
#include <fcntl.h>
#include <unistd.h>
#include <sys/ioctl.h>
#include <cerrno>
#include <cstring>
#include <iostream>
#include <cstdint>

// Manually define termios2 and required constants to avoid
// conflicts between asm/termios.h and glibc headers.
#ifndef BOTHER
#define BOTHER 0x1000
#endif
#ifndef TCGETS2
#define TCGETS2 _IOR('T', 0x2A, struct termios2)
#endif
#ifndef TCSETS2
#define TCSETS2 _IOW('T', 0x2B, struct termios2)
#endif

struct termios2 {
    uint32_t c_iflag;
    uint32_t c_oflag;
    uint32_t c_cflag;
    uint32_t c_lflag;
    uint8_t  c_line;
    uint8_t  c_cc[19];
    uint32_t c_ispeed;
    uint32_t c_ospeed;
};

#define CBAUD   0x100f
#define CS8     0x0030
#define CLOCAL  0x0800
#define CREAD   0x0080
#define PARENB  0x0100
#define CSTOPB  0x0040
#define CRTSCTS 0x80000000

int openSerialPort(const char* port, unsigned baud) {
    int fd = open(port, O_RDWR | O_NOCTTY);
    if (fd < 0) {
        std::cerr << "[serial] open failed: " << strerror(errno) << "\n";
        return -1;
    }
    struct termios2 tty2 = {};
    if (ioctl(fd, TCGETS2, &tty2) < 0) {
        std::cerr << "[serial] TCGETS2 failed\n";
        close(fd); return -1;
    }
    tty2.c_cflag &= ~CBAUD;
    tty2.c_cflag |= BOTHER;
    tty2.c_ispeed = baud;
    tty2.c_ospeed = baud;
    tty2.c_cflag |= (CS8 | CLOCAL | CREAD);
    tty2.c_cflag &= ~(PARENB | CSTOPB | CRTSCTS);
    tty2.c_iflag = 0;
    tty2.c_oflag = 0;
    tty2.c_lflag = 0;
    tty2.c_cc[6] = 0; // VMIN
    tty2.c_cc[5] = 5; // VTIME
    if (ioctl(fd, TCSETS2, &tty2) < 0) {
        std::cerr << "[serial] TCSETS2 failed\n";
        close(fd); return -1;
    }
    return fd;
}
