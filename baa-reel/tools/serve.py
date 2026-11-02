"""HTTP Range-aware static preview server for the Sovereign Baa Reel Studio.

Binds to 0.0.0.0, permits all preview proxy hosts/origins, and implements
RFC 7233 206 Partial Content so vertical 1080×1920 MP4 playback seeks instantly.
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
}


class RangeHandler(SimpleHTTPRequestHandler):
    server_version = "BaaReelStudio/1.0"
    protocol_version = "HTTP/1.1"

    def guess_type(self, path):
        ext = os.path.splitext(str(path))[1].lower()
        return MIME_MAP.get(ext) or super().guess_type(path)

    def end_headers(self):
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", "no-cache, must-revalidate")
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()

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

            start, end, partial_req = 0, size - 1, False
            header = self.headers.get("Range")
            if header:
                m = RANGE_RE.match(header.strip())
                if m and (m.group(1) or m.group(2)):
                    g1, g2 = m.group(1), m.group(2)
                    if g1:
                        start = int(g1)
                        end = int(g2) if g2 else size - 1
                    else:
                        start = max(0, size - int(g2))
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
        p = self._resolve()
        if p is None:
            return
        if p.is_dir() or not p.exists():
            self.send_error(HTTPStatus.NOT_FOUND, "File not found")
            return
        self._send_file(p, with_body=True)

    def do_HEAD(self):
        p = self._resolve()
        if p is None or not p.is_file():
            self.send_error(HTTPStatus.NOT_FOUND, "File not found")
            return
        self._send_file(p, with_body=False)


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def server_bind(self):
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        super().server_bind()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8088)
    ap.add_argument("--dir", default=str(Path(__file__).resolve().parent.parent))
    args = ap.parse_args()
    root = Path(args.dir).resolve()
    httpd = Server(("0.0.0.0", args.port), partial(RangeHandler, directory=str(root)))
    print(f"Serving Sovereign Baa Reel Studio on http://0.0.0.0:{args.port}", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
