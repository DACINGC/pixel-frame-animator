#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""帧动画浏览器 - 本地服务。

    python serve.py              启动并自动打开浏览器（推荐）
    python serve.py --port 9000  指定端口
    python serve.py --scan-only  只重新生成 data.js（离线兜底数据）

接口：
    GET  /api/scan            实时扫描，返回索引 JSON
    GET  /files/<相对路径>     读取工作区文件（图片/图集）
    POST /api/open            在系统文件管理器里定位某个动画集
    GET  /api/gif             把当前动作导出成 GIF（需要 Pillow）
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import threading
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import quote, unquote, urlparse, parse_qs

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scan as scanner  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ROOT = os.path.dirname(HERE)
DEFAULT_PORT = 8765

MIME = {
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".svg": "image/svg+xml",
    ".md": "text/markdown; charset=utf-8",
    ".txt": "text/plain; charset=utf-8",
}

EXPORTS = os.path.join(HERE, "exports")


def log(msg: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def safe_join(root: str, rel: str):
    """把 URL 里的相对路径安全地映射到磁盘路径。"""
    rel = unquote(rel).lstrip("/")
    target = os.path.abspath(os.path.join(root, rel.replace("/", os.sep)))
    root_abs = os.path.abspath(root)
    if os.path.commonpath([target, root_abs]) != root_abs:
        return None
    return target


def make_gif(root: str, frames, fps: float, scale: int, bg: str):
    """优先用零依赖的 gif.py，失败再退回 Pillow。"""
    os.makedirs(EXPORTS, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    name = f"{frames[0]['clip'] or 'anim'}-{stamp}.gif"
    path = os.path.join(EXPORTS, name)
    files = [f["file"] for f in frames]

    try:
        import gif as gifmod
        gifmod.export_gif(path, root, files, fps, scale, bg)
    except Exception as pure_err:  # noqa: BLE001
        try:
            from PIL import Image
        except ImportError:
            raise pure_err
        bg_rgba = {"dark": (24, 24, 30, 255), "light": (246, 246, 250, 255),
                   "green": (0, 195, 65, 255), "magenta": (255, 0, 212, 255)}.get(bg)
        duration = max(20, int(round(1000.0 / max(0.5, fps))))
        out = []
        for rel in files:
            im = Image.open(os.path.join(root, rel.replace("/", os.sep))).convert("RGBA")
            if scale > 1:
                im = im.resize((im.width * scale, im.height * scale), Image.NEAREST)
            if bg_rgba is None:
                alpha = im.getchannel("A")
                p = im.convert("RGB").convert("P", palette=Image.ADAPTIVE, colors=255)
                p.paste(255, Image.eval(alpha, lambda a: 255 if a <= 128 else 0))
                p.info["transparency"] = 255
                out.append(p)
            else:
                canvas = Image.new("RGBA", im.size, bg_rgba)
                canvas.alpha_composite(im)
                out.append(canvas.convert("RGB").convert("P", palette=Image.ADAPTIVE, colors=255))
        kwargs = {"save_all": True, "append_images": out[1:], "duration": duration,
                  "loop": 0, "disposal": 2, "optimize": False}
        if bg_rgba is None:
            kwargs["transparency"] = 255
        out[0].save(path, **kwargs)

    return os.path.relpath(path, DEFAULT_ROOT).replace("\\", "/"), path


class Handler(BaseHTTPRequestHandler):
    root: str = DEFAULT_ROOT
    include_archive: bool = False
    server_version = "PixelFrameViewer/1.0"

    def log_message(self, fmt, *args):  # 精简访问日志
        pass

    # ---- helpers ----
    def send_bytes(self, body: bytes, ctype: str, status=200):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionAbortedError):
            pass

    def send_json(self, obj, status=200):
        self.send_bytes(json.dumps(obj, ensure_ascii=False).encode("utf-8"),
                        "application/json; charset=utf-8", status)

    def send_file(self, path: str):
        ctype = MIME.get(os.path.splitext(path)[1].lower(), "application/octet-stream")
        try:
            with open(path, "rb") as fh:
                body = fh.read()
        except OSError:
            self.send_bytes(b"not found", "text/plain; charset=utf-8", 404)
            return
        self.send_bytes(body, ctype)

    # ---- routes ----
    def do_GET(self):
        u = urlparse(self.path)
        path = u.path
        qs = parse_qs(u.query)

        if path in ("/", "/index.html"):
            self.send_file(os.path.join(HERE, "index.html"))
            return
        if path in ("/viewer.js", "/viewer.css", "/data.js"):
            self.send_file(os.path.join(HERE, path.lstrip("/")))
            return
        if path == "/api/scan":
            flag = str((qs.get("archive") or [""])[0]).lower()
            want_archive = self.include_archive or flag in ("1", "true", "yes", "on")
            try:
                self.send_json(scanner.scan(self.root, include_archive=want_archive))
            except Exception as exc:  # noqa: BLE001
                self.send_json({"error": str(exc)}, 500)
            return
        if path == "/api/gif":
            self.handle_gif(qs)
            return
        if path.startswith("/files/"):
            target = safe_join(self.root, path[len("/files/"):])
            if not target or not os.path.isfile(target):
                self.send_bytes(b"not found", "text/plain; charset=utf-8", 404)
                return
            self.send_file(target)
            return
        self.send_bytes(b"not found", "text/plain; charset=utf-8", 404)

    def do_POST(self):
        u = urlparse(self.path)
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8"))
        except Exception:  # noqa: BLE001
            payload = {}

        if u.path == "/api/open":
            self.handle_open(payload)
        elif u.path == "/api/refresh":
            self.send_json({"ok": True})
        else:
            self.send_json({"error": "unknown endpoint"}, 404)

    def handle_open(self, payload):
        target = payload.get("path") or ""
        disk = safe_join(self.root, target) if target else self.root
        if not disk or not os.path.exists(disk):
            disk = self.root
        if os.path.isfile(disk):
            disk = os.path.dirname(disk)
        try:
            if sys.platform.startswith("win"):
                os.startfile(disk)  # noqa: S606
            elif sys.platform == "darwin":
                subprocess.Popen(["open", disk])
            else:
                subprocess.Popen(["xdg-open", disk])
            self.send_json({"ok": True, "path": disk})
        except Exception as exc:  # noqa: BLE001
            self.send_json({"ok": False, "error": str(exc)}, 500)

    def handle_gif(self, qs):
        set_id = (qs.get("set") or [""])[0]
        clip = (qs.get("clip") or [""])[0]
        fps = float((qs.get("fps") or ["12"])[0])
        scale = max(1, min(16, int((qs.get("scale") or ["4"])[0])))
        bg = (qs.get("bg") or ["transparent"])[0]

        data = scanner.scan(self.root)
        target = next((s for s in data["sets"] if s["id"] == set_id), None)
        if not target:
            self.send_json({"error": "找不到该动画集"}, 404)
            return
        frames = target["frames"]
        if clip and clip != "__all__":
            frames = [f for f in frames if f["clip"] == clip]
        if not frames:
            self.send_json({"error": "没有可导出的帧"}, 400)
            return
        try:
            rel, abs_path = make_gif(self.root, frames, fps, scale, bg)
            self.send_json({"ok": True, "file": "/files/" + quote(rel),
                            "name": os.path.basename(abs_path)})
        except Exception as exc:  # noqa: BLE001
            self.send_json({"error": str(exc)}, 500)


def start_server(port: int, max_tries: int = 20) -> ThreadingHTTPServer:
    """从指定端口开始尝试绑定，被占用就自动换下一个端口。"""
    last_err: OSError | None = None
    for p in range(port, port + max_tries):
        try:
            return ThreadingHTTPServer(("127.0.0.1", p), Handler)
        except OSError as exc:  # 端口被占用 / 权限不足
            last_err = exc
            log(f"端口 {p} 不可用（{exc.winerror if hasattr(exc, 'winerror') else exc}），尝试下一个…")
    raise last_err  # type: ignore[misc]


def main():
    ap = argparse.ArgumentParser(description="帧动画浏览器本地服务")
    ap.add_argument("root", nargs="?", default=None, help="扫描根目录，默认 viewer 的上一级")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--no-browser", action="store_true", help="不自动打开浏览器")
    ap.add_argument("--scan-only", action="store_true", help="只生成 data.js 然后退出")
    ap.add_argument("--include-archive", action="store_true", help="连 _archive 等归档目录一起扫描")
    args = ap.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass

    root = os.path.abspath(args.root or DEFAULT_ROOT)

    if args.scan_only:
        sys.argv = [sys.argv[0], root, "--static"]
        if args.include_archive:
            sys.argv.append("--include-archive")
        scanner.main()
        return

    Handler.root = root
    Handler.include_archive = args.include_archive
    data = scanner.scan(root, include_archive=args.include_archive)
    log(f"扫描根目录: {root}")
    log(f"发现 {data['setCount']} 个动画集 / {data['frameCount']} 帧"
        f"（默认显示 {data['visibleCount']} 个：隐藏重复 {data['dupCount']} 个 / 旧版本 {data['oldCount']} 个）")

    server = start_server(args.port)
    port = server.server_address[1]
    if port != args.port:
        log(f"端口 {args.port} 被占用，已自动改用 {port}")
    url = f"http://127.0.0.1:{port}/"
    log(f"服务已就绪: {url}   (Ctrl+C 停止)")

    if not args.no_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log("已停止")
        server.shutdown()


if __name__ == "__main__":
    main()
