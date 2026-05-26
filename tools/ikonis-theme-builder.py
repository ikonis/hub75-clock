#!/usr/bin/env python3
import argparse
import getpass
import importlib.util
import json
import os
import shlex
import shutil
import subprocess
import sys
import webbrowser
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


if getattr(sys, "frozen", False):
    APP_DIR = Path(sys.executable).resolve().parent
    BUNDLE_DIR = Path(getattr(sys, "_MEIPASS", APP_DIR))
    ROOT = APP_DIR
else:
    APP_DIR = Path(__file__).resolve().parents[1]
    BUNDLE_DIR = APP_DIR
    ROOT = APP_DIR

CACHE_DIR = APP_DIR / ".theme-cache" / "ikonis"
SPRITE_CACHE_DIR = APP_DIR / ".theme-cache" / "sprites"
ANIMATION_CACHE_DIR = APP_DIR / ".theme-cache" / "sprite-animations"
AUTH_FILE = APP_DIR / ".theme-cache" / "ikonis-auth.json"
REMOTE_THEMES_DIR = "/etc/hub75-clock/themes"
REMOTE_SPRITES_DIR = "/etc/hub75-clock/sprites"
REMOTE_ANIMATIONS_DIR = "/etc/hub75-clock/sprite-animations"

SOURCE_CLOCK = "hub75-clock.local"
TARGET_CLOCKS = [
    {"host": "hub75-clock.local", "restart": False},
    {"host": "bedroom-clock.local", "restart": True},
]


def _load_theme_server():
    path = BUNDLE_DIR / "tools" / "theme-server.py"
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


def load_auth(path):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except Exception as exc:
        print(f"[ikonis-theme-builder] warning: could not read saved auth: {exc}")
        return {}
    return data if isinstance(data, dict) else {}


def save_auth(path, user, password):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"user": user, "password": password}, indent=2) + "\n",
        encoding="utf-8",
    )
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def load_paramiko():
    try:
        import paramiko
    except ImportError:
        return None
    return paramiko


def ssh_connect(paramiko, user, host, password):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        host,
        username=user or None,
        password=password or None,
        look_for_keys=True,
        allow_agent=True,
        timeout=15,
    )
    return client


def run_ssh(client, command):
    print("[ikonis-theme-builder] ssh " + command)
    stdin, stdout, stderr = client.exec_command(command)
    rc = stdout.channel.recv_exit_status()
    err = stderr.read().decode("utf-8", errors="replace").strip()
    if rc != 0:
        raise RuntimeError(err or f"remote command failed with exit {rc}")


def run_sudo(client, password, command):
    print("[ikonis-theme-builder] sudo " + command)
    quoted = shlex.quote(command)
    stdin, stdout, stderr = client.exec_command(f"sudo -S -p '' sh -c {quoted}", get_pty=True)
    if password:
        stdin.write(password + "\n")
        stdin.flush()
    rc = stdout.channel.recv_exit_status()
    err = stderr.read().decode("utf-8", errors="replace").strip()
    if rc != 0:
        raise RuntimeError(err or f"sudo command failed with exit {rc}")


def pull_json_dir_paramiko(paramiko, user, source_host, password, remote_dir, cache_dir, label):
    cache_dir.mkdir(parents=True, exist_ok=True)
    for existing in cache_dir.glob("*.json"):
        existing.unlink()

    print(f"[ikonis-theme-builder] pull {source_host}:{remote_dir}/*.json")
    client = ssh_connect(paramiko, user, source_host, password)
    try:
        sftp = client.open_sftp()
        try:
            for attr in sftp.listdir_attr(remote_dir):
                name = attr.filename
                if name.lower().endswith(".json"):
                    sftp.get(f"{remote_dir}/{name}", str(cache_dir / name))
        except FileNotFoundError:
            print(f"[ikonis-theme-builder] warning: remote {label} dir not found: {remote_dir}")
        finally:
            sftp.close()
    finally:
        client.close()


def push_json_paramiko(paramiko, user, host, password, remote_dir, path, restart, label):
    remote_path = remote_dir + "/" + path.name
    remote_tmp = f"/tmp/hub75-{label}-upload-{os.getpid()}.json"

    print(f"[ikonis-theme-builder] push {path.name} -> {host}:{remote_path}")
    client = ssh_connect(paramiko, user, host, password)
    try:
        sftp = client.open_sftp()
        try:
            sftp.put(str(path), remote_tmp)
        finally:
            sftp.close()

        run_sudo(
            client,
            password,
            f"install -D -m 0644 {shlex.quote(remote_tmp)} {shlex.quote(remote_path)} && rm -f {shlex.quote(remote_tmp)}",
        )

        if restart:
            run_sudo(client, password, "systemctl restart hub75-clock")
    finally:
        client.close()


def pull_json_dir_scp(user, source_host, remote_dir, cache_dir, label):
    require_tool("scp")
    cache_dir.mkdir(parents=True, exist_ok=True)
    for existing in cache_dir.glob("*.json"):
        existing.unlink()
    src = f"{remote(user, source_host)}:{remote_dir}/*.json"
    try:
        run_cmd(["scp", src, str(cache_dir)])
    except subprocess.CalledProcessError as exc:
        print(f"[ikonis-theme-builder] warning: could not pull {label} from {remote_dir}: exit {exc.returncode}")


def push_json_scp(user, host, remote_dir, path, restart, label):
    require_tool("scp")
    require_tool("ssh")
    dest = remote(user, host)
    remote_path = remote_dir + "/" + path.name
    remote_tmp = f"/tmp/hub75-{label}-upload-{os.getpid()}.json"

    run_cmd(["scp", str(path), f"{dest}:{remote_tmp}"])

    install_cmd = (
        "sudo install -D -m 0644 "
        f"{shlex.quote(remote_tmp)} "
        f"{shlex.quote(remote_path)} && "
        f"rm -f {shlex.quote(remote_tmp)}"
    )
    run_cmd(["ssh", "-t", dest, install_cmd])

    if restart:
        run_cmd(["ssh", "-t", dest, "sudo systemctl restart hub75-clock"])


class IkonisThemeHandler(theme_server.ThemeBuilderHandler):
    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/theme":
            return self._write_remote_json("theme", self.themes_dir, self.server.remote_themes_dir)
        if parsed.path == "/api/sprite":
            return self._write_remote_json("sprite", self.sprites_dir, self.server.remote_sprites_dir)
        if parsed.path == "/api/animation":
            return self._write_remote_json("animation", self.animations_dir, self.server.remote_animations_dir)
        return super().do_POST()

    def _write_remote_json(self, label, local_dir, remote_dir):
        if label == "theme":
            payload_key = "theme"
            safe_path = theme_server._safe_theme_path
        elif label == "sprite":
            payload_key = "sprite"
            safe_path = lambda base, name: theme_server._safe_json_path(base, name, "sprite")
        else:
            payload_key = "animation"
            safe_path = lambda base, name: theme_server._safe_json_path(base, name, "animation")

        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
            name = payload.get("file") or ""
            data = payload.get(payload_key)
            if not isinstance(data, dict):
                raise ValueError(f"{label} must be an object")

            path = safe_path(local_dir, name)
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(path.suffix + ".tmp")
            tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            os.replace(tmp, path)
        except Exception as exc:
            return theme_server._json_response(self, 400, {"ok": False, "error": str(exc)})

        failures = []
        saved_to = []
        for target in self.server.targets:
            restart = target["restart"] if label == "theme" else False
            try:
                if self.server.paramiko:
                    push_json_paramiko(
                        self.server.paramiko,
                        self.server.ssh_user,
                        target["host"],
                        self.server.ssh_password,
                        remote_dir,
                        path,
                        restart,
                        label,
                    )
                else:
                    push_json_scp(
                        self.server.ssh_user,
                        target["host"],
                        remote_dir,
                        path,
                        restart,
                        label,
                    )
                target_label = target["host"]
                if restart:
                    target_label += " + restart"
                saved_to.append(target_label)
            except subprocess.CalledProcessError as exc:
                failures.append(f"{target['host']}: exit {exc.returncode}")
            except Exception as exc:
                failures.append(f"{target['host']}: {exc}")

        if failures:
            return theme_server._json_response(
                self,
                500,
                {"ok": False, "file": path.name, "error": "; ".join(failures)},
            )

        return theme_server._json_response(
            self,
            200,
            {"ok": True, "file": path.name, "saved_to": saved_to},
        )


def main():
    parser = argparse.ArgumentParser(
        description="Ikonis-local theme builder: pull from Pi 4, edit locally, push to both clocks."
    )
    parser.add_argument("--user", default="ikonis")
    parser.add_argument("--source", default=SOURCE_CLOCK)
    parser.add_argument("--themes-dir", default=REMOTE_THEMES_DIR)
    parser.add_argument("--sprites-dir", default=REMOTE_SPRITES_DIR)
    parser.add_argument("--animations-dir", default=REMOTE_ANIMATIONS_DIR)
    parser.add_argument("--cache-dir", default=str(CACHE_DIR))
    parser.add_argument("--sprite-cache-dir", default=str(SPRITE_CACHE_DIR))
    parser.add_argument("--animation-cache-dir", default=str(ANIMATION_CACHE_DIR))
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-pull", action="store_true")
    parser.add_argument("--open-browser", action=argparse.BooleanOptionalAction, default=True,
                        help="Open the theme builder in the default browser.")
    parser.add_argument("--use-paramiko", action=argparse.BooleanOptionalAction, default=True,
                        help="Use Paramiko password auth when available instead of scp/ssh.")
    parser.add_argument("--save-password", action="store_true",
                        help="Prompt once and save the password in .theme-cache/ikonis-auth.json.")
    parser.add_argument("--forget-password", action="store_true",
                        help="Delete the saved password and exit.")
    parser.add_argument("--no-restart", action="store_true",
                        help="Do not restart the Pi Zero/C++ clock after pushing.")
    args = parser.parse_args()

    cache_dir = Path(args.cache_dir).expanduser().resolve()
    sprite_cache_dir = Path(args.sprite_cache_dir).expanduser().resolve()
    animation_cache_dir = Path(args.animation_cache_dir).expanduser().resolve()
    auth_file = AUTH_FILE
    if args.forget_password:
        try:
            auth_file.unlink()
            print(f"[ikonis-theme-builder] removed saved auth: {auth_file}")
        except FileNotFoundError:
            print("[ikonis-theme-builder] no saved auth to remove")
        return

    saved_auth = load_auth(auth_file)
    ssh_user = args.user or saved_auth.get("user") or "ikonis"
    ssh_password = saved_auth.get("password")
    paramiko = load_paramiko() if args.use_paramiko else None

    if args.save_password:
        ssh_password = getpass.getpass(f"SSH password for {ssh_user}: ")
        save_auth(auth_file, ssh_user, ssh_password)
        print(f"[ikonis-theme-builder] saved auth: {auth_file}")

    if args.use_paramiko and not paramiko:
        print("[ikonis-theme-builder] Paramiko not installed; falling back to scp/ssh.")
        print("[ikonis-theme-builder] Install with: python -m pip install paramiko")

    targets = [
        {**target, "restart": target["restart"] and not args.no_restart}
        for target in TARGET_CLOCKS
    ]

    if not args.no_pull:
        if paramiko:
            pull_json_dir_paramiko(paramiko, ssh_user, args.source, ssh_password, args.themes_dir, cache_dir, "themes")
            pull_json_dir_paramiko(paramiko, ssh_user, args.source, ssh_password, args.sprites_dir, sprite_cache_dir, "sprites")
            pull_json_dir_paramiko(paramiko, ssh_user, args.source, ssh_password, args.animations_dir, animation_cache_dir, "sprite animations")
        else:
            pull_json_dir_scp(ssh_user, args.source, args.themes_dir, cache_dir, "themes")
            pull_json_dir_scp(ssh_user, args.source, args.sprites_dir, sprite_cache_dir, "sprites")
            pull_json_dir_scp(ssh_user, args.source, args.animations_dir, animation_cache_dir, "sprite animations")

    httpd = ThreadingHTTPServer((args.host, args.port), IkonisThemeHandler)
    httpd.themes_dir = cache_dir
    sprite_cache_dir.mkdir(parents=True, exist_ok=True)
    animation_cache_dir.mkdir(parents=True, exist_ok=True)
    httpd.sprites_dir = sprite_cache_dir
    httpd.animations_dir = animation_cache_dir
    httpd.ssh_user = ssh_user
    httpd.ssh_password = ssh_password
    httpd.paramiko = paramiko
    httpd.remote_themes_dir = args.themes_dir
    httpd.remote_sprites_dir = args.sprites_dir
    httpd.remote_animations_dir = args.animations_dir
    httpd.targets = targets

    url = f"http://{args.host}:{args.port}/"
    print(f"[ikonis-theme-builder] serving {url}")
    print(f"[ikonis-theme-builder] local theme cache: {cache_dir}")
    print(f"[ikonis-theme-builder] local sprite cache: {sprite_cache_dir}")
    print(f"[ikonis-theme-builder] local animation cache: {animation_cache_dir}")
    print(f"[ikonis-theme-builder] source: {args.source}:{args.themes_dir}")
    print(f"[ikonis-theme-builder] sprite source: {args.source}:{args.sprites_dir}")
    print(f"[ikonis-theme-builder] animation source: {args.source}:{args.animations_dir}")
    print(f"[ikonis-theme-builder] auth backend: {'paramiko' if paramiko else 'scp/ssh'}")
    for target in targets:
        suffix = " + restart" if target["restart"] else ""
        print(f"[ikonis-theme-builder] push target: {target['host']}{suffix}")

    if args.open_browser:
        webbrowser.open(url)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[ikonis-theme-builder] stopping")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
