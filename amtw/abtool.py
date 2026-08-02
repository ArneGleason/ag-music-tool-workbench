"""A/B listening tool.

Serves N supposedly-aligned audio files to a local page that plays them all
in lockstep and switches which one you hear by crossfading gains — so
toggling is instant and sample-aligned, not a stop/reload. Markers and notes
are saved back to disk as JSON so listening verdicts become structured data
instead of chat messages.

    amtw ab a.wav b.wav c.wav
"""
from __future__ import annotations

import json
import mimetypes
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from .paths import OUTPUT_DIR

HERE = Path(__file__).resolve().parent


def _make_handler(files: list[Path], notes_path: Path):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # keep the console quiet
            pass

        def _send(self, code, body: bytes, ctype="application/json"):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            path = unquote(urlparse(self.path).path)

            if path in ("/", "/index.html"):
                html = (HERE / "ab.html").read_bytes()
                return self._send(200, html, "text/html; charset=utf-8")

            if path == "/api/files":
                payload = [
                    {"index": i, "name": f.name, "path": str(f)}
                    for i, f in enumerate(files)
                ]
                return self._send(200, json.dumps(payload).encode())

            if path == "/api/notes":
                if notes_path.exists():
                    return self._send(200, notes_path.read_bytes())
                return self._send(200, b"{}")

            if path.startswith("/audio/"):
                try:
                    idx = int(path.rsplit("/", 1)[1])
                    f = files[idx]
                except (ValueError, IndexError):
                    return self._send(404, b'{"error":"no such file"}')
                ctype = mimetypes.guess_type(f.name)[0] or "application/octet-stream"
                return self._send(200, f.read_bytes(), ctype)

            return self._send(404, b'{"error":"not found"}')

        def do_POST(self):
            path = unquote(urlparse(self.path).path)
            if path != "/api/notes":
                return self._send(404, b'{"error":"not found"}')
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            notes_path.parent.mkdir(parents=True, exist_ok=True)
            notes_path.write_bytes(body)
            return self._send(200, json.dumps({"saved": str(notes_path)}).encode())

    return Handler


def serve(file_args: list[str], port: int = 8731, notes: str | None = None) -> int:
    files = []
    for a in file_args:
        p = Path(a).resolve()
        if not p.exists():
            print(f"not found: {p}")
            return 2
        files.append(p)

    if notes:
        notes_path = Path(notes).resolve()
    else:
        stamp = time.strftime("%Y%m%d-%H%M%S")
        notes_path = OUTPUT_DIR / "ab_notes" / f"{stamp}.json"

    handler = _make_handler(files, notes_path)
    httpd = ThreadingHTTPServer(("127.0.0.1", port), handler)

    url = f"http://127.0.0.1:{port}/"
    print(f"A/B tool: {url}")
    for i, f in enumerate(files):
        print(f"  [{i + 1}] {f.name}")
    print(f"notes -> {notes_path}")
    print("Ctrl+C to stop.")

    threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped.")
    finally:
        httpd.server_close()
    return 0
