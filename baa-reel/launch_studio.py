#!/usr/bin/env python3
"""Zero-dependency local launcher & HTTP Range download/streaming server for Baa Reel Studio.

Works out-of-the-box with Python 3.10+ standard library ONLY (no pip install required to view/play/download).
"""

from __future__ import annotations

import argparse
import email.utils
import os
import re
import socket
import threading
import time
import urllib.parse
import webbrowser
from functools import partial
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

STUDIO_DIR = Path(__file__).resolve().parent
CHUNK = 256 * 1024
RANGE_RE = re.compile(r"^bytes=(\d*)-(\d*)$")

GITHUB_BRANCH = "arena/0b6566ab-ai-agent-teams"
GITHUB_REPO = "kha369x1111/ai-agent-teams"
GITHUB_FULL_ZIP = f"https://codeload.github.com/{GITHUB_REPO}/zip/refs/heads/{GITHUB_BRANCH}"
GITHUB_LIGHT_ZIP = f"https://github.com/{GITHUB_REPO}/raw/{GITHUB_BRANCH}/baa-reel/downloads/baa-reel-light-runnable.zip"
GITHUB_MP4_RAW = f"https://github.com/{GITHUB_REPO}/raw/{GITHUB_BRANCH}/baa-reel/deliver/baa_secret_reel_1080x1920.mp4"

MIME_MAP = {
    ".mp4": "video/mp4",
    ".webm": "video/webm",
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".ttf": "font/ttf",
    ".woff2": "font/woff2",
    ".svg": "image/svg+xml",
    ".js": "text/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".md": "text/markdown; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".html": "text/html; charset=utf-8",
    ".zip": "application/zip",
    ".bat": "text/plain; charset=utf-8",
    ".sh": "text/plain; charset=utf-8",
}

DOWNLOAD_HUB_HTML = f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>مركز التحميل المباشر — مشروع ريلز حرف الباء (ب)</title>
<style>
  @font-face{{font-family:"Amiri";src:url("/docs/Amiri-Bold.ttf") format("truetype");font-weight:700;font-display:swap}}
  @font-face{{font-family:"Tajawal";src:url("/docs/Tajawal-Regular.ttf") format("truetype");font-weight:400;font-display:swap}}
  @font-face{{font-family:"Tajawal";src:url("/docs/Tajawal-Bold.ttf") format("truetype");font-weight:700;font-display:swap}}
  :root{{--bg:#09080c;--gold:#d8b162;--gold-hi:#f6deb0;--text:#efe6d5;--muted:#a6957b;--border:rgba(216,177,98,.28)}}
  *{{box-sizing:border-box}}
  body{{
    margin:0; font-family:"Tajawal",system-ui,sans-serif; color:var(--text);
    background:radial-gradient(900px 500px at 50% -10%,rgba(216,177,98,.16),transparent 65%), #09080c;
    min-height:100vh; padding:28px 18px 70px;
  }}
  .wrap{{max-width:980px; margin:0 auto}}
  header{{text-align:center; margin-bottom:26px}}
  h1{{font-family:"Amiri",serif; font-size:clamp(26px,4vw,42px); color:var(--gold-hi); margin:0 0 8px}}
  .sub{{color:var(--muted); font-size:15.5px; line-height:1.8}}
  .notice{{
    background:rgba(216,177,98,.10); border:1px solid var(--border); border-radius:16px;
    padding:16px 20px; margin-bottom:22px; line-height:1.85; font-size:14.5px;
  }}
  .grid{{display:grid; grid-template-columns:repeat(auto-fit,minmax(280px,1fr)); gap:18px}}
  .card{{
    background:rgba(20,16,20,.94); border:1px solid var(--border); border-radius:20px;
    padding:22px; display:flex; flex-direction:column; gap:10px;
  }}
  .card h2{{font-family:"Amiri",serif; color:var(--gold-hi); margin:0; font-size:22px}}
  .card p{{color:var(--muted); font-size:14px; line-height:1.8; margin:0}}
  .btn{{
    display:block; text-align:center; padding:13px 16px; border-radius:12px;
    text-decoration:none; font-weight:700; font-size:14.5px; margin-top:6px;
    background:linear-gradient(135deg,#e7c47a,#b88740); color:#171006;
  }}
  .btn.alt{{background:rgba(255,255,255,.06); color:var(--gold-hi); border:1px solid var(--border)}}
  pre{{
    background:#050407; border:1px solid rgba(255,255,255,.1); padding:14px 16px;
    border-radius:12px; direction:ltr; text-align:left; overflow:auto; color:#f2dfba; font-size:13px;
  }}
  a{{color:var(--gold)}}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>⬇ مركز التحميل المباشر وتشغيل المشروع</h1>
    <div class="sub">حرف الباء (ب) — أكاديمية مفتاح الأسرار السبعة · جاهز للتشغيل الفوري على Windows و macOS و Linux</div>
  </header>

  <div class="notice">
    💡 <b>ملاحظة مهمة لضمان التحميل من المتصفح:</b> إذا كنت تفتح هذه الصفحة داخل نافذة المعاينة المدمجة ومنع متصفحك التحميل المباشر، اضغط على أزرار <b>«تحميل مباشر عبر GitHub ↗»</b> (تفتح في تبويب مستقل وتبدأ التنزيل فوراً).
  </div>

  <div class="grid">
    <section class="card">
      <h2>1) المشروع الكامل + الفيديو (ZIP)</h2>
      <p>يشمل كل ملفات المشروع + الفيديو النهائي 1080×1920 + مشغّل ويندوز الفوري <code>START_WINDOWS.bat</code> (يعمل فوراً بدون تثبيت مكتبات).</p>
      <a class="btn" href="{GITHUB_FULL_ZIP}" target="_blank" rel="noopener">⬇ تحميل المشروع الكامل عبر GitHub ↗</a>
    </section>

    <section class="card">
      <h2>2) حزمة المشروع الخفيفة (4.2 MB)</h2>
      <p>حزمة مضغوطة سريعة تشمل الكود، الاستوديو، اللوحات الـ10، المقاطع الصوتية الـ7، الخطوط العربية، وملفات التشغيل.</p>
      <a class="btn" href="{GITHUB_LIGHT_ZIP}" target="_blank" rel="noopener">⬇ تحميل الحزمة الخفيفة عبر GitHub ↗</a>
      <a class="btn alt" href="/downloads/baa-reel-light-runnable.zip?download=1" download="baa-reel-light-runnable.zip">تحميل من الخادم المحلي</a>
    </section>

    <section class="card">
      <h2>3) الفيديو النهائي وحده (MP4)</h2>
      <p>ملف الفيديو العمودي الكامل <code>1080×1920 · 30fps · 73.8s</code> جاهز للنشر على Reels و TikTok و Shorts.</p>
      <a class="btn" href="{GITHUB_MP4_RAW}" target="_blank" rel="noopener">⬇ تحميل الفيديو MP4 عبر GitHub ↗</a>
      <a class="btn alt" href="/deliver/baa_secret_reel_1080x1920.mp4?download=1" download="baa_secret_reel_1080x1920.mp4">تحميل من الخادم المحلي</a>
    </section>
  </div>

  <div class="notice" style="margin-top:22px">
    <b>طريقة التشغيل بعد فك ضغط ملف الـ ZIP على جهازك:</b>
    <ul>
      <li><b>على ويندوز (Windows 10/11):</b> افتح مجلد <code>baa-reel</code> واضغط مرتين على <code>START_WINDOWS.bat</code> — سيفتح الاستوديو فوراً على <code>http://127.0.0.1:8088</code>!</li>
      <li><b>على macOS أو Linux:</b> شغّل الأمر <code>./START_MAC_LINUX.sh</code> داخل مجلد <code>baa-reel</code>.</li>
    </ul>
    <div style="margin-top:10px"><a href="/">← العودة إلى استوديو العرض السينمائي التفاعلي</a></div>
  </div>
</div>
</body>
</html>
"""


class StudioHandler(SimpleHTTPRequestHandler):
    server_version = "BaaReelStudio/1.1"
    protocol_version = "HTTP/1.1"

    def guess_type(self, path):
        ext = os.path.splitext(str(path))[1].lower()
        return MIME_MAP.get(ext) or super().guess_type(path)

    def end_headers(self):
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", "no-cache, must-revalidate")
        self.send_header("X-Content-Type-Options", "nosniff")
        super().end_headers()

    def _resolve(self) -> tuple[Path | None, dict[str, list[str]]]:
        parsed = urllib.parse.urlsplit(self.path)
        qs = urllib.parse.parse_qs(parsed.query)
        raw_path = parsed.path
        if "\x00" in raw_path or "%00" in raw_path.lower() or "%2e%2e" in raw_path.lower() or ".." in raw_path:
            self.send_error(HTTPStatus.FORBIDDEN, "Forbidden path")
            return None, qs
        rel = urllib.parse.unquote(raw_path)
        if "\x00" in rel or ".." in Path(rel).parts:
            self.send_error(HTTPStatus.FORBIDDEN, "Forbidden path")
            return None, qs
        if rel in ("", "/"):
            rel = "/index.html"
        root = Path(self.directory).resolve()
        target = (root / rel.lstrip("/")).resolve()
        try:
            target.relative_to(root)
        except ValueError:
            self.send_error(HTTPStatus.FORBIDDEN, "Path outside root")
            return None, qs
        return target, qs

    def _serve_download_hub(self, with_body: bool):
        body = DOWNLOAD_HUB_HTML.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if with_body:
            self.wfile.write(body)

    def _send_file(self, path: Path, qs: dict[str, list[str]], with_body: bool):
        try:
            fh = path.open("rb")
        except OSError:
            self.send_error(HTTPStatus.NOT_FOUND, "File not found")
            return
        with fh:
            st = os.fstat(fh.fileno())
            size = st.st_size
            ctype = self.guess_type(path)
            mtime = email.utils.formatdate(st.st_mtime, usegmt=True)
            force_dl = path.suffix.lower() == ".zip" or qs.get("download") == ["1"]

            start, end, partial_req = 0, size - 1, False
            header = self.headers.get("Range")
            if header:
                m = RANGE_RE.match(header.strip())
                if not m or (not m.group(1) and not m.group(2)):
                    self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                    self.send_header("Content-Range", f"bytes */{size}")
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                g1, g2 = m.group(1), m.group(2)
                if g1:
                    start = int(g1)
                    end = int(g2) if g2 else size - 1
                else:
                    suf = int(g2)
                    if suf <= 0:
                        self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                        self.send_header("Content-Range", f"bytes */{size}")
                        self.send_header("Content-Length", "0")
                        self.end_headers()
                        return
                    start = max(0, size - suf)
                    end = size - 1
                if start >= size or start > end:
                    self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                    self.send_header("Content-Range", f"bytes */{size}")
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                end = min(end, size - 1)
                partial_req = True

            self.send_response(HTTPStatus.PARTIAL_CONTENT if partial_req else HTTPStatus.OK)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(end - start + 1))
            self.send_header("Last-Modified", mtime)
            if force_dl:
                self.send_header("Content-Disposition", f'attachment; filename="{path.name}"')
            if partial_req:
                self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            self.end_headers()
            if not with_body:
                return

            fh.seek(start)
            rem = end - start + 1
            try:
                while rem > 0:
                    chunk = fh.read(min(CHUNK, rem))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    rem -= len(chunk)
            except (BrokenPipeError, ConnectionResetError):
                pass

    def do_GET(self):
        parsed_path = urllib.parse.urlsplit(self.path).path.rstrip("/")
        if parsed_path == "/download":
            self._serve_download_hub(with_body=True)
            return
        p, qs = self._resolve()
        if p is None:
            return
        if p.is_dir() or not p.exists():
            self.send_error(HTTPStatus.NOT_FOUND, "File not found")
            return
        self._send_file(p, qs, with_body=True)

    def do_HEAD(self):
        parsed_path = urllib.parse.urlsplit(self.path).path.rstrip("/")
        if parsed_path == "/download":
            self._serve_download_hub(with_body=False)
            return
        p, qs = self._resolve()
        if p is None or not p.is_file():
            self.send_error(HTTPStatus.NOT_FOUND, "File not found")
            return
        self._send_file(p, qs, with_body=False)


class ReusableServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def server_bind(self):
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        super().server_bind()


def main():
    ap = argparse.ArgumentParser(description="Launch Baa Reel Studio local server")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8088)
    ap.add_argument("--open-browser", action="store_true")
    args = ap.parse_args()

    url = f"http://127.0.0.1:{args.port}"
    print(f"✓ استوديو حرف الباء يعمل الآن على: {url}", flush=True)
    print(f"✓ مركز التحميل المباشر: {url}/download", flush=True)

    if args.open_browser:
        def _open():
            time.sleep(1.0)
            webbrowser.open(url)
        threading.Thread(target=_open, daemon=True).start()

    handler = partial(StudioHandler, directory=str(STUDIO_DIR))
    with ReusableServer((args.host, args.port), handler) as httpd:
        httpd.serve_forever()


if __name__ == "__main__":
    main()
