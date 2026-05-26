#!/usr/bin/env python3
import argparse
import json
import mimetypes
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse


ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "tools" / "theme-builder.html"
SPRITE_BUILDER = ROOT / "tools" / "sprite-builder.html"


def _json_response(handler, status, payload):
    body = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _safe_theme_path(themes_dir, name):
    if not name or "/" in name or "\\" in name:
        raise ValueError("invalid theme filename")
    path = (themes_dir / name).resolve()
    if path.parent != themes_dir.resolve() or path.suffix.lower() != ".json":
        raise ValueError("invalid theme filename")
    return path


def _safe_json_path(base_dir, name, label):
    if not name or "/" in name or "\\" in name:
        raise ValueError(f"invalid {label} filename")
    path = (base_dir / name).resolve()
    if path.parent != base_dir.resolve() or path.suffix.lower() != ".json":
        raise ValueError(f"invalid {label} filename")
    return path


class ThemeBuilderHandler(BaseHTTPRequestHandler):
    server_version = "Hub75ThemeBuilder/0.1"

    def log_message(self, fmt, *args):
        print("[theme-builder] " + fmt % args)

    @property
    def themes_dir(self):
        return self.server.themes_dir

    @property
    def sprites_dir(self):
        return self.server.sprites_dir

    def do_GET(self):
        parsed = urlparse(self.path)
        path = unquote(parsed.path)

        if path in ("/", "/theme-builder.html"):
            return self._send_file(BUILDER)
        if path == "/sprite-builder.html":
            return self._send_file(SPRITE_BUILDER)
        if path == "/api/themes":
            return self._list_themes()
        if path == "/api/theme":
            qs = parse_qs(parsed.query)
            return self._read_theme(qs.get("file", [""])[0])
        if path == "/api/sprites":
            return self._list_sprites()
        if path == "/api/sprite":
            qs = parse_qs(parsed.query)
            return self._read_sprite(qs.get("file", [""])[0])
        return self.send_error(404, "Not found")

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/theme":
            return self._write_theme()
        if parsed.path == "/api/sprite":
            return self._write_sprite()
        return self.send_error(404, "Not found")

    def _write_theme(self):
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
            name = payload.get("file") or ""
            data = payload.get("theme")
            if not isinstance(data, dict):
                raise ValueError("theme must be an object")
            path = _safe_theme_path(self.themes_dir, name)
            self._write_json_file(path, data)
        except Exception as exc:
            return _json_response(self, 400, {"ok": False, "error": str(exc)})

        return _json_response(
            self,
            200,
            {"ok": True, "file": path.name, "saved_to": [str(path)]},
        )

    def _write_sprite(self):
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
            name = payload.get("file") or ""
            data = payload.get("sprite")
            if not isinstance(data, dict):
                raise ValueError("sprite must be an object")
            path = _safe_json_path(self.sprites_dir, name, "sprite")
            self._write_json_file(path, data)
        except Exception as exc:
            return _json_response(self, 400, {"ok": False, "error": str(exc)})

        return _json_response(
            self,
            200,
            {"ok": True, "file": path.name, "saved_to": [str(path)]},
        )

    def _write_json_file(self, path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp, path)

    def _send_file(self, path):
        try:
            body = path.read_bytes()
        except OSError:
            return self.send_error(404, "Not found")
        ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _list_themes(self):
        try:
            files = sorted(p.name for p in self.themes_dir.glob("*.json") if p.is_file())
        except OSError as exc:
            return _json_response(self, 500, {"ok": False, "error": str(exc)})
        return _json_response(self, 200, {"ok": True, "themes": files})

    def _read_theme(self, name):
        try:
            path = _safe_theme_path(self.themes_dir, name)
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            return _json_response(self, 400, {"ok": False, "error": str(exc)})
        return _json_response(self, 200, {"ok": True, "file": path.name, "theme": data})

    def _list_sprites(self):
        try:
            files = sorted(p.name for p in self.sprites_dir.glob("*.json") if p.is_file())
        except OSError as exc:
            return _json_response(self, 500, {"ok": False, "error": str(exc)})
        return _json_response(self, 200, {"ok": True, "sprites": files})

    def _read_sprite(self, name):
        try:
            path = _safe_json_path(self.sprites_dir, name, "sprite")
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            return _json_response(self, 400, {"ok": False, "error": str(exc)})
        return _json_response(self, 200, {"ok": True, "file": path.name, "sprite": data})


def main():
    parser = argparse.ArgumentParser(description="Serve the HUB75 theme builder with local save support.")
    parser.add_argument("--themes-dir", default=str(ROOT / "themes"),
                        help="Directory containing theme JSON files.")
    parser.add_argument("--sprites-dir", default=str(ROOT / "sprites"),
                        help="Directory containing sprite JSON files.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    themes_dir = Path(args.themes_dir).expanduser().resolve()
    sprites_dir = Path(args.sprites_dir).expanduser().resolve()
    themes_dir.mkdir(parents=True, exist_ok=True)
    sprites_dir.mkdir(parents=True, exist_ok=True)

    httpd = ThreadingHTTPServer((args.host, args.port), ThemeBuilderHandler)
    httpd.themes_dir = themes_dir
    httpd.sprites_dir = sprites_dir
    print(f"[theme-builder] serving http://{args.host}:{args.port}/")
    print(f"[theme-builder] themes dir: {themes_dir}")
    print(f"[theme-builder] sprites dir: {sprites_dir}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[theme-builder] stopping")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
