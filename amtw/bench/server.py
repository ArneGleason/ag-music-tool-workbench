"""The workbench: a local page that runs the tools so you don't have to type them.

Same shape as the A/B tool — stdlib http.server on localhost, one HTML page, no
dependencies. It reads the discovered tool catalog, renders a form per tool, and
runs the real CLI in a subprocess, streaming its output back to the page.

    amtw workbench
"""
from __future__ import annotations

import json
import mimetypes
import os
import re
import subprocess
import sys
import threading
import time
import webbrowser
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from .. import registry
from ..core.paths import INPUT_DIR, OUTPUT_DIR, PROJECT_ROOT, subprocess_env
from ..spec import build_argv

HERE = Path(__file__).resolve().parent

# Everything the file browser is allowed to see. Anything outside these is
# refused, so a stray path in a request can't read the rest of the disk.
def _browse_roots() -> dict[str, Path]:
    home = Path.home()
    roots = {
        "input": INPUT_DIR,
        "output": OUTPUT_DIR,
        "ab_notes": OUTPUT_DIR / "ab_notes",
        "project": PROJECT_ROOT,
        "downloads": home / "Downloads",
        "music": home / "Music",
        "desktop": home / "Desktop",
    }
    return {k: v for k, v in roots.items() if v.exists() or k in ("input", "output")}


ROOTS = _browse_roots()

# paths the tools print that are worth offering as results
RESULT_RE = re.compile(r"(?:[A-Za-z]:\\|\.\\|/)[^\r\n\"']*?\.(?:wav|mp3|flac|png|html|mid|json)",
                       re.IGNORECASE)


@dataclass
class Run:
    id: int
    tool: str
    argv: list[str]
    started: float
    lines: list[str] = field(default_factory=list)
    status: str = "running"          # running | done | failed | stopped
    rc: int | None = None
    ended: float | None = None
    proc: subprocess.Popen | None = None

    def summary(self) -> dict:
        return {
            "id": self.id, "tool": self.tool, "argv": self.argv,
            "started": self.started, "ended": self.ended,
            "status": self.status, "rc": self.rc,
            "cmd": "amtw " + " ".join(_quote(a) for a in self.argv),
        }


def _quote(a: str) -> str:
    return f'"{a}"' if " " in a else a


class Runner:
    def __init__(self) -> None:
        self.runs: dict[int, Run] = {}
        # files a tool actually produced. They are openable even when they land
        # outside the browsable roots (an --outdir on another drive, say);
        # anything else outside the roots stays refused.
        self.produced: set[str] = set()
        self._next = 1
        self._lock = threading.Lock()

    def start(self, tool: str, values: dict) -> Run:
        argv = build_argv(registry.by_name(tool), values)
        with self._lock:
            run = Run(id=self._next, tool=tool, argv=argv, started=time.time())
            self._next += 1
            self.runs[run.id] = run

        env = subprocess_env()
        env["PYTHONUNBUFFERED"] = "1"
        cmd = [sys.executable, "-m", "amtw", *argv]
        run.lines.append("$ amtw " + " ".join(_quote(a) for a in argv))
        try:
            run.proc = subprocess.Popen(
                cmd, cwd=str(PROJECT_ROOT), env=env,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace", bufsize=1,
            )
        except Exception as e:  # noqa: BLE001
            run.lines.append(f"failed to start: {e}")
            run.status = "failed"
            run.ended = time.time()
            return run

        threading.Thread(target=self._pump, args=(run,), daemon=True).start()
        return run

    def _pump(self, run: Run) -> None:
        assert run.proc and run.proc.stdout
        for line in run.proc.stdout:
            run.lines.append(line.rstrip("\n"))
        rc = run.proc.wait()
        run.rc = rc
        if run.status != "stopped":
            run.status = "done" if rc == 0 else "failed"
        run.ended = time.time()

    def stop(self, run_id: int) -> bool:
        run = self.runs.get(run_id)
        if not run or not run.proc or run.proc.poll() is not None:
            return False
        run.status = "stopped"
        run.proc.terminate()
        return True

    def results(self, run: Run) -> list[dict]:
        """Existing files the run mentioned, newest-looking first."""
        seen: list[str] = []
        for line in run.lines:
            for m in RESULT_RE.finditer(line):
                p = m.group(0).strip().strip("\"'")
                if p not in seen:
                    seen.append(p)
        out = []
        for p in seen:
            path = Path(p)
            if not path.is_absolute():
                path = (PROJECT_ROOT / path).resolve()
            if path.exists() and path.is_file():
                self.produced.add(str(path))
                out.append({"name": path.name, "path": str(path),
                            "kind": path.suffix.lower().lstrip(".")})
        return out


RUNNER = Runner()


# --------------------------------------------------------------------------- #
# path safety
# --------------------------------------------------------------------------- #


def _openable(path: Path) -> bool:
    """Browsable roots, plus anything a tool in this session actually wrote."""
    try:
        return _inside_roots(path) or str(path.resolve()) in RUNNER.produced
    except OSError:
        return False


def _inside_roots(path: Path) -> bool:
    try:
        rp = path.resolve()
    except OSError:
        return False
    for root in ROOTS.values():
        try:
            rp.relative_to(root.resolve())
            return True
        except ValueError:
            continue
    return False


def _listing(path: Path, accept: list[str] | None, dirs_only: bool) -> dict:
    dirs, files = [], []
    try:
        for entry in sorted(path.iterdir(), key=lambda p: p.name.lower()):
            if entry.name.startswith(".") or entry.name == "__pycache__":
                continue
            try:
                if entry.is_dir():
                    dirs.append({"name": entry.name, "path": str(entry)})
                elif not dirs_only:
                    ext = entry.suffix.lower().lstrip(".")
                    if accept and ext not in accept:
                        continue
                    st = entry.stat()
                    files.append({"name": entry.name, "path": str(entry),
                                  "size": st.st_size, "mtime": st.st_mtime})
            except OSError:
                continue
    except OSError as e:
        return {"error": str(e), "path": str(path), "dirs": [], "files": []}

    files.sort(key=lambda f: f["mtime"], reverse=True)
    parent = str(path.parent) if _inside_roots(path.parent) and path.parent != path else None
    return {"path": str(path), "parent": parent, "dirs": dirs, "files": files}


# --------------------------------------------------------------------------- #
# http
# --------------------------------------------------------------------------- #


def _make_handler():
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # keep the console quiet
            pass

        def _send(self, code: int, body: bytes, ctype="application/json") -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionAbortedError):
                pass

        def _json(self, obj, code=200) -> None:
            self._send(code, json.dumps(obj).encode())

        def _body(self) -> dict:
            length = int(self.headers.get("Content-Length", 0))
            if not length:
                return {}
            return json.loads(self.rfile.read(length) or b"{}")

        # ---------------- GET ---------------- #

        def do_GET(self):  # noqa: N802
            url = urlparse(self.path)
            path = unquote(url.path)
            q = parse_qs(url.query)

            if path in ("/", "/index.html"):
                return self._send(200, (HERE / "workbench.html").read_bytes(),
                                  "text/html; charset=utf-8")

            if path == "/api/catalog":
                return self._json({
                    "tools": registry.catalog_json(),
                    "roots": {k: str(v) for k, v in ROOTS.items()},
                    "project": str(PROJECT_ROOT),
                })

            if path == "/api/browse":
                raw = q.get("path", [None])[0]
                root = q.get("root", ["input"])[0]
                target = Path(raw) if raw else ROOTS.get(root, INPUT_DIR)
                if not _inside_roots(target):
                    return self._json({"error": "outside the allowed folders"}, 403)
                if not target.exists():
                    target.mkdir(parents=True, exist_ok=True)
                accept = [a.lower() for a in q.get("accept", [""])[0].split(",") if a]
                dirs_only = q.get("dirs", ["0"])[0] == "1"
                return self._json(_listing(target, accept or None, dirs_only))

            if path == "/api/runs":
                runs = sorted(RUNNER.runs.values(), key=lambda r: r.id, reverse=True)
                return self._json([r.summary() for r in runs[:40]])

            if path.startswith("/api/runs/"):
                parts = path.strip("/").split("/")
                try:
                    run = RUNNER.runs[int(parts[2])]
                except (KeyError, ValueError, IndexError):
                    return self._json({"error": "no such run"}, 404)
                offset = int(q.get("offset", ["0"])[0])
                payload = run.summary()
                payload["lines"] = run.lines[offset:]
                payload["offset"] = len(run.lines)
                payload["results"] = RUNNER.results(run) if run.status != "running" else []
                return self._json(payload)

            if path == "/file":
                raw = q.get("path", [None])[0]
                if not raw:
                    return self._json({"error": "no path"}, 400)
                target = Path(raw)
                if not _openable(target) or not target.is_file():
                    return self._json({"error": "not available"}, 403)
                ctype = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
                return self._send(200, target.read_bytes(), ctype)

            return self._json({"error": "not found"}, 404)

        # ---------------- POST ---------------- #

        def do_POST(self):  # noqa: N802
            path = unquote(urlparse(self.path).path)

            if path == "/api/run":
                body = self._body()
                tool = body.get("tool")
                if tool not in {t.name for t in registry.catalog()}:
                    return self._json({"error": "unknown tool"}, 400)
                try:
                    run = RUNNER.start(tool, body.get("values") or {})
                except ValueError as e:
                    return self._json({"error": str(e)}, 400)
                return self._json(run.summary())

            if path == "/api/stop":
                return self._json({"stopped": RUNNER.stop(int(self._body().get("id", 0)))})

            if path == "/api/reveal":
                target = Path(self._body().get("path", ""))
                if not _openable(target):
                    return self._json({"error": "not available"}, 403)
                if target.is_file():
                    subprocess.Popen(["explorer", "/select,", str(target)])
                else:
                    subprocess.Popen(["explorer", str(target)])
                return self._json({"ok": True})

            if path == "/api/midi-tracks":
                # the merge form needs to know what's in a file before you pick tracks
                from ..tools.midi import midi

                out = []
                for raw in self._body().get("paths", []):
                    target = Path(raw)
                    if not _inside_roots(target) or not target.is_file():
                        continue
                    try:
                        out.append(midi.describe(target))
                    except Exception as e:  # noqa: BLE001
                        out.append({"path": str(target), "error": str(e)})
                return self._json(out)

            return self._json({"error": "not found"}, 404)

    return Handler


class _Server(ThreadingHTTPServer):
    # Default is on, which on Windows lets a SECOND workbench bind the same
    # port instead of failing. Two servers then answer unpredictably and the
    # page goes stale -- indistinguishable, from the outside, from "it broke".
    # Off means the second start fails loudly and we can handle it below.
    allow_reuse_address = False


def _already_serving(port: int) -> bool:
    """Is a workbench (not something else) already on this port?"""
    import urllib.error
    import urllib.request

    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/catalog", timeout=2) as r:
            return b'"tools"' in r.read(4096)
    except (urllib.error.URLError, OSError):
        return False


def serve(port: int = 8730, open_browser: bool = True) -> int:
    for name in ("input", "output"):
        ROOTS[name].mkdir(parents=True, exist_ok=True)

    url = f"http://127.0.0.1:{port}/"
    try:
        httpd = _Server(("127.0.0.1", port), _make_handler())
    except OSError as e:
        # The common case by far: the bench is already open, usually in a
        # console window minimised out of sight. Closing the browser tab does
        # not stop the server, so double-clicking Workbench.cmd again lands
        # here. Reuse it rather than dying with a traceback nobody sees.
        if _already_serving(port):
            print(f"workbench already running at {url} — opening that one.")
            print("(its console window is the server; close that window to stop it)")
            if open_browser:
                webbrowser.open(url)
            return 0
        print(f"cannot bind port {port}: {e}", file=sys.stderr)
        print(f"something else is using it — try:  amtw workbench --port {port + 1}",
              file=sys.stderr)
        return 1

    print(f"AG Music Tool Workbench: {url}")
    print(f"  {len(registry.catalog())} tools · project {PROJECT_ROOT}")
    print("Ctrl+C to stop.")

    if open_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped.")
    finally:
        for run in RUNNER.runs.values():
            if run.proc and run.proc.poll() is None:
                run.proc.terminate()
        httpd.server_close()
    return 0
