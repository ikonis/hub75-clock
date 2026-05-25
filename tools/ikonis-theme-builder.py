#!/usr/bin/env python3
import argparse
import importlib.util
import json
import os
import shlex
import shutil
import subprocess
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = ROOT / ".theme-cache" / "ikonis"
REMOTE_THEMES_DIR = "/etc/hub75-clock/themes"

SOURCE_CLOCK = "hub75-clock.local"
TARGET_CLOCKS = [
    {"host": "hub75-clock.local", "restart": False},
    {"host": "bedroom-clock.local", "restart": True},
]


def _load_theme_server():
    path = ROOT / "tools" / "theme-server.py"
    spec = importlib.util.spec_from_file_location("hub75_theme_server", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


theme_server = _load_theme_server()


def run_cmd(cmd, *, check=True):
    print("[ikonis-theme-builder] " + " ".join(str(c) for c in cmd))
    return subprocess.run(cmd, check=check)


def remote(user, host):
    return f"{user}@{host}" if user else host


def require_tool(name):
    if shutil.which(name):
        return
    raise SystemExit(f"[error] {name} not found. Install/enable Windows OpenSSH first.")


def pull_themes(user, source_host, themes_dir, cache_dir):
    require_tool("scp")
    cache_dir.mkdir(parents=True, exist_ok=True)
    for existing in cache_dir.glob("*.json"):
        existing.unlink()
    src = f"{remote(user, source_host)}:{themes_dir}/*.json"
    run_cmd(["scp", src, str(cache_dir)])


def push_theme(user, host, themes_dir, path, restart):
    require_tool("scp")
    require_tool("ssh")
    dest = remote(user, host)
    remote_theme = themes_dir + "/" + path.name

    direct = run_cmd(["scp", str(path), f"{dest}:{shlex.quote(remote_theme)}"], check=False)
    if direct.returncode == 0:
        if restart:
            run_cmd(["ssh", dest, "sudo systemctl restart hub75-clock"])
        return

    remote_tmp = f"/tmp/hub75-theme-{path.name}"
    run_cmd(["scp", str(path), f"{dest}:{shlex.quote(remote_tmp)}"])

    install_cmd = (
        "sudo install -m 0644 "
        f"{shlex.quote(remote_tmp)} "
        f"{shlex.quote(remote_theme)} && "
        f"rm -f {shlex.quote(remote_tmp)}"
    )
    run_cmd(["ssh", dest, install_cmd])

    if restart:
        run_cmd(["ssh", dest, "sudo systemctl restart hub75-clock"])


class IkonisThemeHandler(theme_server.ThemeBuilderHandler):
    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path != "/api/theme":
            return self.send_error(404, "Not found")

        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
            name = payload.get("file") or ""
            data = payload.get("theme")
            if not isinstance(data, dict):
                raise ValueError("theme must be an object")

            path = theme_server._safe_theme_path(self.themes_dir, name)
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(path.suffix + ".tmp")
            tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            os.replace(tmp, path)

            failures = []
            for target in self.server.targets:
                try:
                    push_theme(
                        self.server.ssh_user,
                        target["host"],
                        self.server.remote_themes_dir,
                        path,
                        target["restart"],
                    )
                except subprocess.CalledProcessError as exc:
                    failures.append(f"{target['host']}: exit {exc.returncode}")

            if failures:
                return theme_server._json_response(
                    self,
                    500,
                    {"ok": False, "file": path.name, "error": "; ".join(failures)},
                )
        except Exception as exc:
            return theme_server._json_response(self, 400, {"ok": False, "error": str(exc)})

        return theme_server._json_response(self, 200, {"ok": True, "file": path.name})


def main():
    parser = argparse.ArgumentParser(
        description="Ikonis-local theme builder: pull from Pi 4, edit locally, push to both clocks."
    )
    parser.add_argument("--user", default="ikonis")
    parser.add_argument("--source", default=SOURCE_CLOCK)
    parser.add_argument("--themes-dir", default=REMOTE_THEMES_DIR)
    parser.add_argument("--cache-dir", default=str(CACHE_DIR))
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-pull", action="store_true")
    parser.add_argument("--no-restart", action="store_true",
                        help="Do not restart the Pi Zero/C++ clock after pushing.")
    args = parser.parse_args()

    cache_dir = Path(args.cache_dir).expanduser().resolve()
    targets = [
        {**target, "restart": target["restart"] and not args.no_restart}
        for target in TARGET_CLOCKS
    ]

    if not args.no_pull:
        pull_themes(args.user, args.source, args.themes_dir, cache_dir)

    httpd = ThreadingHTTPServer((args.host, args.port), IkonisThemeHandler)
    httpd.themes_dir = cache_dir
    httpd.ssh_user = args.user
    httpd.remote_themes_dir = args.themes_dir
    httpd.targets = targets

    print(f"[ikonis-theme-builder] serving http://{args.host}:{args.port}/")
    print(f"[ikonis-theme-builder] local cache: {cache_dir}")
    print(f"[ikonis-theme-builder] source: {args.source}:{args.themes_dir}")
    for target in targets:
        suffix = " + restart" if target["restart"] else ""
        print(f"[ikonis-theme-builder] push target: {target['host']}{suffix}")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[ikonis-theme-builder] stopping")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
