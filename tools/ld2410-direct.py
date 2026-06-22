#!/usr/bin/env python3
"""Direct LD2410 UART tuning helper.

Use this with hub75-clock stopped so nothing else owns the UART:
  sudo systemctl stop hub75-clock hub75-ld2410-tuner
  sudo python3 tools/ld2410-direct.py monitor
  sudo python3 tools/ld2410-direct.py set-gate 3 --move 20 --still 18
"""

from __future__ import annotations

import argparse
import struct
import sys
import time

try:
    import serial
except Exception as exc:
    raise SystemExit(f"pyserial is required: {exc}")


CMD_HEAD = b"\xFD\xFC\xFB\xFA"
CMD_TAIL = b"\x04\x03\x02\x01"
DATA_HEAD = b"\xF4\xF3\xF2\xF1"
DATA_TAIL = b"\xF8\xF7\xF6\xF5"


def clamp(value: int, low: int = 0, high: int = 100) -> int:
    return max(low, min(high, int(value)))


class LD2410:
    def __init__(self, port: str, baud: int):
        self.ser = serial.Serial(port, baud, timeout=0.25)
        self.buf = bytearray()

    def close(self) -> None:
        self.ser.close()

    def send_cmd(self, cmd: bytes, data: bytes = b"") -> None:
        payload = cmd + data
        frame = CMD_HEAD + struct.pack("<H", len(payload)) + payload + CMD_TAIL
        self.ser.write(frame)
        self.ser.flush()
        time.sleep(0.08)

    def enter_config(self) -> None:
        self.send_cmd(b"\xFF\x00")

    def end_config(self) -> None:
        self.send_cmd(b"\xFE\x00")

    def engineering(self, enable: bool) -> None:
        self.enter_config()
        self.send_cmd(b"\x62\x00" if enable else b"\x63\x00")
        self.end_config()

    def set_gate(self, gate: int, move: int, still: int) -> None:
        if not 0 <= gate <= 8:
            raise ValueError("gate must be 0-8")
        payload = struct.pack("<III", gate, clamp(move), clamp(still))
        self.enter_config()
        self.send_cmd(b"\x64\x00", payload)
        self.end_config()

    def read_available(self) -> None:
        waiting = self.ser.in_waiting
        if waiting:
            self.buf.extend(self.ser.read(waiting))
        else:
            chunk = self.ser.read(128)
            if chunk:
                self.buf.extend(chunk)

    def next_frame(self):
        while True:
            cmd_idx = self.buf.find(CMD_HEAD)
            data_idx = self.buf.find(DATA_HEAD)
            if cmd_idx >= 0 and (data_idx < 0 or cmd_idx < data_idx):
                if cmd_idx:
                    del self.buf[:cmd_idx]
                if len(self.buf) < 10:
                    return None
                dl = self.buf[4] | (self.buf[5] << 8)
                total = 10 + dl
                if len(self.buf) < total:
                    return None
                frame = bytes(self.buf[:total])
                del self.buf[:total]
                if frame[-4:] == CMD_TAIL:
                    return ("cmd", frame[6 : 6 + dl])
                continue

            if data_idx < 0:
                if len(self.buf) > 1024:
                    del self.buf[:-4]
                return None
            if data_idx:
                del self.buf[:data_idx]
            if len(self.buf) < 10:
                return None
            dl = self.buf[4] | (self.buf[5] << 8)
            total = 10 + dl
            if len(self.buf) < total:
                return None
            frame = bytes(self.buf[:total])
            del self.buf[:total]
            if frame[-4:] == DATA_TAIL:
                return ("data", frame[6 : 6 + dl])

    def wait_frame(self, seconds: float = 1.0):
        deadline = time.time() + seconds
        while time.time() < deadline:
            self.read_available()
            frame = self.next_frame()
            if frame:
                return frame
        return None


def parse_data(data: bytes):
    if len(data) < 13 or data[1] != 0xAA or data[0] not in (0x01, 0x02):
        return None
    result = {
        "type": data[0],
        "target": data[2],
        "move_distance": data[3] | (data[4] << 8),
        "move_energy": data[5],
        "still_distance": data[6] | (data[7] << 8),
        "still_energy": data[8],
        "move_gates": [],
        "still_gates": [],
    }
    if data[0] == 0x01 and len(data) >= 31:
        result["detect_distance"] = data[9] | (data[10] << 8)
        result["max_move_gate"] = data[11]
        result["max_still_gate"] = data[12]
        result["move_gates"] = list(data[13:22])
        result["still_gates"] = list(data[22:31])
    return result


def print_frame(parsed: dict) -> None:
    state = ["none", "move", "still", "both"][min(parsed["target"], 3)]
    if parsed["move_gates"]:
        print(
            f"{state:5s} move={parsed['move_distance']:3d}cm({parsed['move_energy']:3d}) "
            f"still={parsed['still_distance']:3d}cm({parsed['still_energy']:3d}) "
            f"mg={parsed['move_gates']} sg={parsed['still_gates']}",
            flush=True,
        )
    else:
        print(
            f"{state:5s} move={parsed['move_distance']:3d}cm({parsed['move_energy']:3d}) "
            f"still={parsed['still_distance']:3d}cm({parsed['still_energy']:3d})",
            flush=True,
        )


def monitor(args) -> int:
    dev = LD2410(args.port, args.baud)
    try:
        if args.engineering:
            dev.engineering(True)
        end = time.time() + args.seconds if args.seconds else None
        while end is None or time.time() < end:
            frame = dev.wait_frame(1.0)
            if not frame or frame[0] != "data":
                continue
            parsed = parse_data(frame[1])
            if parsed:
                print_frame(parsed)
    finally:
        dev.close()
    return 0


def set_gate(args) -> int:
    dev = LD2410(args.port, args.baud)
    try:
        dev.set_gate(args.gate, args.move, args.still)
        print(f"set G{args.gate}: move={clamp(args.move)} still={clamp(args.still)}")
    finally:
        dev.close()
    return 0


def set_all(args) -> int:
    dev = LD2410(args.port, args.baud)
    try:
        for gate in range(9):
            dev.set_gate(gate, args.move, args.still)
            print(f"set G{gate}: move={clamp(args.move)} still={clamp(args.still)}")
    finally:
        dev.close()
    return 0


def engineering(args) -> int:
    dev = LD2410(args.port, args.baud)
    try:
        dev.engineering(args.enable)
        print("engineering on" if args.enable else "engineering off")
    finally:
        dev.close()
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Tune an LD2410 directly over UART.")
    parser.add_argument("--port", default="/dev/serial0")
    parser.add_argument("--baud", type=int, default=256000)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("monitor", help="print live LD2410 frames")
    p.add_argument("--seconds", type=float, default=0, help="0 means run until Ctrl+C")
    p.add_argument("--engineering", action=argparse.BooleanOptionalAction, default=True)
    p.set_defaults(func=monitor)

    p = sub.add_parser("set-gate", help="set one gate threshold pair")
    p.add_argument("gate", type=int)
    p.add_argument("--move", type=int, required=True)
    p.add_argument("--still", type=int, required=True)
    p.set_defaults(func=set_gate)

    p = sub.add_parser("set-all", help="set all gates to one threshold pair")
    p.add_argument("--move", type=int, required=True)
    p.add_argument("--still", type=int, required=True)
    p.set_defaults(func=set_all)

    p = sub.add_parser("engineering", help="toggle engineering mode")
    p.add_argument("enable", choices=("on", "off"))
    p.set_defaults(func=lambda args: engineering(argparse.Namespace(**vars(args), enable=args.enable == "on")))

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        print("\nstopped")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
