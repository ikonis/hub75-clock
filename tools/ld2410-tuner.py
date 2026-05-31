#!/usr/bin/env python3
import argparse
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

import yaml

try:
    import paho.mqtt.client as mqtt
except Exception as exc:
    raise SystemExit(f"paho-mqtt is required for the LD2410 tuner: {exc}")


ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "tools" / "ld2410-tuner.html"


def _json_response(handler, status, payload):
    body = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


class TunerState:
    def __init__(self, cfg):
        self.cfg = cfg
        self.lock = threading.Lock()
        self.data = {
            "move_gates": [0] * 9,
            "still_gates": [0] * 9,
            "move_thresholds": [50] * 9,
            "still_thresholds": [30] * 9,
            "presence": None,
            "target_state": None,
            "move_distance": None,
            "still_distance": None,
            "engineering": False,
            "max_gate": 8,
            "max_move_gate": 8,
            "max_still_gate": 8,
            "timeout_seconds": None,
            "updated_at": None,
        }
        self.client = None

    @property
    def mqtt_cfg(self):
        return self.cfg.get("mqtt", {})

    @property
    def client_id(self):
        return self.mqtt_cfg.get("client_id", "hub75_clock")

    @property
    def topics(self):
        return self.mqtt_cfg.get("topics", {})

    def topic(self, key, fallback):
        return self.topics.get(key, fallback)

    def start_mqtt(self):
        client = mqtt.Client(client_id=f"{self.client_id}_ld2410_tuner")
        username = self.mqtt_cfg.get("username")
        password = self.mqtt_cfg.get("password")
        if username:
            client.username_pw_set(username, password)
        client.on_connect = self._on_connect
        client.on_message = self._on_message
        client.connect(
            self.mqtt_cfg.get("broker", "localhost"),
            int(self.mqtt_cfg.get("port", 1883)),
            keepalive=30,
        )
        client.loop_start()
        self.client = client

    def stop_mqtt(self):
        if self.client:
            try:
                self.set_engineering(False)
                time.sleep(0.1)
                self.client.loop_stop()
                self.client.disconnect()
            except Exception:
                pass

    def _on_connect(self, client, userdata, flags, rc):
        cid = self.client_id
        client.subscribe(self.topic("motion", f"{cid}/motion"))
        client.subscribe(self.topic("presence", f"{cid}/presence"))
        client.subscribe(self.topic("engineering_mode", f"{cid}/engineering_mode") + "/state")
        client.subscribe(self.topic("ld2410_params", f"{cid}/ld2410/params"))
        client.subscribe(f"{cid}/gate/+/move_thresh")
        client.subscribe(f"{cid}/gate/+/still_thresh")
        self.set_engineering(True)
        self.read_parameters()

    def _on_message(self, client, userdata, msg):
        topic = msg.topic
        raw = msg.payload.decode(errors="replace")
        cid = self.client_id
        with self.lock:
            if topic == self.topic("motion", f"{cid}/motion"):
                try:
                    payload = json.loads(raw)
                except Exception:
                    return
                if isinstance(payload.get("move_gates"), list):
                    self.data["move_gates"] = [int(v) for v in payload["move_gates"][:9]]
                if isinstance(payload.get("still_gates"), list):
                    self.data["still_gates"] = [int(v) for v in payload["still_gates"][:9]]
                if "move_energy" in payload and "move_gates" not in payload:
                    self.data["move_gates"][0] = int(payload["move_energy"])
                if "still_energy" in payload and "still_gates" not in payload:
                    self.data["still_gates"][0] = int(payload["still_energy"])
                self.data["updated_at"] = time.time()
            elif topic == self.topic("presence", f"{cid}/presence"):
                try:
                    payload = json.loads(raw)
                except Exception:
                    return
                for key in ("presence", "target_state", "move_distance", "still_distance"):
                    if key in payload:
                        self.data[key] = payload[key]
            elif topic == self.topic("engineering_mode", f"{cid}/engineering_mode") + "/state":
                self.data["engineering"] = raw.strip().lower() == "on"
            elif topic == self.topic("ld2410_params", f"{cid}/ld2410/params"):
                try:
                    payload = json.loads(raw)
                except Exception:
                    return
                if isinstance(payload.get("move_thresholds"), list):
                    self.data["move_thresholds"] = [int(v) for v in payload["move_thresholds"][:9]]
                if isinstance(payload.get("still_thresholds"), list):
                    self.data["still_thresholds"] = [int(v) for v in payload["still_thresholds"][:9]]
                for key in ("max_gate", "max_move_gate", "max_still_gate", "timeout_seconds"):
                    if key in payload:
                        self.data[key] = payload[key]
            else:
                parts = topic.split("/")
                if len(parts) == 4 and parts[0] == cid and parts[1] == "gate":
                    try:
                        gate = int(parts[2])
                        value = max(0, min(100, int(float(raw))))
                    except Exception:
                        return
                    if 0 <= gate < 9 and parts[3] == "move_thresh":
                        self.data["move_thresholds"][gate] = value
                    elif 0 <= gate < 9 and parts[3] == "still_thresh":
                        self.data["still_thresholds"][gate] = value

    def snapshot(self):
        with self.lock:
            return json.loads(json.dumps(self.data))

    def set_engineering(self, enable):
        if not self.client:
            return
        topic = self.topic("engineering_mode", f"{self.client_id}/engineering_mode")
        self.client.publish(topic, json.dumps({"engineering_mode": bool(enable)}), retain=False)
        with self.lock:
            self.data["engineering"] = bool(enable)

    def read_parameters(self):
        if not self.client:
            return
        topic = self.topic("ld2410_read", f"{self.client_id}/ld2410/read")
        self.client.publish(topic, "read", retain=False)

    def set_gate(self, gate, kind, value):
        gate = int(gate)
        value = max(0, min(100, int(value)))
        if gate < 0 or gate > 8 or kind not in ("move", "still"):
            raise ValueError("invalid gate threshold")
        suffix = "move_thresh" if kind == "move" else "still_thresh"
        topic = f"{self.client_id}/gate/{gate}/{suffix}"
        self.client.publish(topic, str(value), retain=False)
        with self.lock:
            self.data[f"{kind}_thresholds"][gate] = value
        threading.Timer(1.5, self.read_parameters).start()


class Handler(BaseHTTPRequestHandler):
    server_version = "Hub75LD2410Tuner/0.1"

    def log_message(self, fmt, *args):
        print("[ld2410-tuner] " + fmt % args)

    def do_GET(self):
        path = unquote(urlparse(self.path).path)
        if path in ("/", "/ld2410-tuner.html"):
            return self._send_file(HTML)
        if path == "/api/state":
            return _json_response(self, 200, {"ok": True, "state": self.server.tuner.snapshot()})
        return self.send_error(404, "Not found")

    def do_POST(self):
        path = unquote(urlparse(self.path).path)
        length = int(self.headers.get("Content-Length", "0"))
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            if path == "/api/engineering":
                self.server.tuner.set_engineering(bool(payload.get("enable")))
                return _json_response(self, 200, {"ok": True})
            if path == "/api/read":
                self.server.tuner.read_parameters()
                return _json_response(self, 200, {"ok": True})
            if path == "/api/gate":
                self.server.tuner.set_gate(payload.get("gate"), payload.get("kind"), payload.get("value"))
                return _json_response(self, 200, {"ok": True})
        except Exception as exc:
            return _json_response(self, 400, {"ok": False, "error": str(exc)})
        return self.send_error(404, "Not found")

    def _send_file(self, path):
        try:
            body = path.read_bytes()
        except OSError:
            return self.send_error(404, "Not found")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main():
    parser = argparse.ArgumentParser(description="Serve a mobile LD2410 gate tuning UI.")
    parser.add_argument("--config", default="/etc/hub75-clock/config.yaml")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()

    with open(args.config, encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    tuner = TunerState(cfg)
    tuner.start_mqtt()

    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    httpd.tuner = tuner
    print(f"[ld2410-tuner] serving http://{args.host}:{args.port}/")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[ld2410-tuner] stopping")
    finally:
        tuner.stop_mqtt()
        httpd.server_close()


if __name__ == "__main__":
    main()
