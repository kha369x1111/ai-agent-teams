"""Static preview server for the Ghaith film page (HTTP Range aware).

Why not `python -m http.server`?  The stdlib handler ignores Range requests, so
it answers `200 OK` with the whole film (≈87 MB) on every video request: the
browser cannot seek and playback only starts after the full download.  This
handler implements single-range `206 Partial Content`, `HEAD`, correct MIME
types and headers that keep the page embeddable in the preview iframe.

    python3 tools/serve.py --port 8080 --dir .
"""

from __future__ import annotations

import argparse
import email.utils
import os
import re
import socket
from functools import partial
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

CHUNK = 256 * 1024
RANGE_RE = re.compile(r"^bytes=(\d*)-(\d*)$")

EXTRA_TYPES = {
    ".mp4": "video/mp4", ".m4v": "video/mp4", ".webm": "video/webm",
    ".mp3": "audio/mpeg", ".wav": "audio/wav",
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
    ".ttf": "font/ttf", ".woff2": "font/woff2", ".svg": "image/svg+xml",
    ".js": "text/javascript; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".md": "text/markdown; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".html": "text/html; charset=utf-8",
}


class RangeHandler(SimpleHTTPRequestHandler):
    server_version = "GhaithPreview/1.0"
    protocol_version = "HTTP/1.1"

    def guess_type(self, path):  # noqa: N802 (stdlib naming)
        ext = os.path.splitext(str(path))[1].lower()
        return EXTRA_TYPES.get(ext) or super().guess_type(path)

    def end_headers(self):
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", "no-cache, must-revalidate")
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()

    def log_message(self, fmt, *args):
        print(f"{self.address_string()} {fmt % args}", flush=True)

    def _resolve(self) -> Path | None:
        rel = unquote(urlsplit(self.path).path)
        if rel.endswith("/"):
            rel += "index.html"
        root = Path(self.directory).resolve()
        target = (root / rel.lstrip("/")).resolve()
        if not str(target).startswith(str(root)):
            self.send_error(HTTPStatus.FORBIDDEN, "Path outside root")
            return None
        return target

    def _send_file(self, path: Path, with_body: bool):
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

            start, end, partial = 0, size - 1, False
            header = self.headers.get("Range")
            if header:
                m = RANGE_RE.match(header.strip())
                if m and (m.group(1) or m.group(2)):
                    g1, g2 = m.group(1), m.group(2)
                    if g1:
                        start = int(g1)
                        end = int(g2) if g2 else size - 1
                    else:  # suffix range: bytes=-500
                        start = max(0, size - int(g2))
                    if start >= size or start > end:
                        self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                        self.send_header("Content-Range", f"bytes */{size}")
                        self.send_header("Content-Length", "0")
                        self.end_headers()
                        return
                    end = min(end, size - 1)
                    partial = True

            self.send_response(HTTPStatus.PARTIAL_CONTENT if partial else HTTPStatus.OK)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(end - start + 1))
            self.send_header("Last-Modified", mtime)
            if partial:
                self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            self.end_headers()
            if not with_body:
                return

            fh.seek(start)
            remaining = end - start + 1
            try:
                while remaining > 0:
                    chunk = fh.read(min(CHUNK, remaining))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    remaining -= len(chunk)
            except (BrokenPipeError, ConnectionResetError):
                pass  # client seeked away or closed the tab

    def do_GET(self):  # noqa: N802
        path = self._resolve()
        if path is None:
            return
        if path.is_dir() or not path.exists():
            self.send_error(HTTPStatus.NOT_FOUND, "File not found")
            return
        self._send_file(path, with_body=True)

    def do_HEAD(self):  # noqa: N802
        path = self._resolve()
        if path is None or not path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND, "File not found")
            return
        self._send_file(path, with_body=False)


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def server_bind(self):
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        super().server_bind()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--dir", default=str(Path(__file__).resolve().parent.parent))
    a = ap.parse_args()
    root = Path(a.dir).resolve()
    httpd = Server(("0.0.0.0", a.port), partial(RangeHandler, directory=str(root)))
    print(f"serving {root} on http://0.0.0.0:{a.port} (Range enabled)", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
