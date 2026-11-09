"""Open the recording explorer on this laptop, where every recording plays in full.

The published pages can hold only some recordings' audio. This serves one data
set's page from asr-capstone/explorer/<data set>/ (built by tools/build_explorer.py)
and adds two things only this laptop has:

    local/audio/<recording>              the recording's own audio file from D:/
    local/file?p=<path>                  any file under the corpus folders, read-only

The page sees it is on localhost and uses them. Audio is sent in pieces as the
browser asks (HTTP range requests), which is what lets it jump to any point of an
hour-long recording without loading all of it first. Only this computer can
connect: the server listens on 127.0.0.1.

    python tools/explore_local.py scotus     # then open http://127.0.0.1:8765/
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lineup  # noqa: E402

OUT = lineup.CAPSTONE / "explorer" / "scotus"   # set from the command line
#: The only folders local/file may read from: the corpora and their runs.
ROOTS = [lineup.scotus_root().resolve(), (lineup.local_path("asr_corpora")).resolve()]
SKELETON = ("<!doctype html><html><head><meta charset=utf-8>"
            "<meta name=viewport content=\"width=device-width,initial-scale=1,viewport-fit=cover\">"
            "</head><body>{}</body></html>")
mimetypes.add_type("audio/wav", ".wav")
mimetypes.add_type("application/gzip", ".gz")
mimetypes.add_type("text/plain", ".stm")
mimetypes.add_type("application/json", ".json")


class Handler(BaseHTTPRequestHandler):
    audio: dict = {}

    def do_GET(self):
        url = urlparse(self.path)
        if url.path.startswith("/local/audio/"):
            key = unquote(url.path[len("/local/audio/"):])
            path = self.audio.get(key)
            return self.send_file(Path(path)) if path else self.send_error(404, f"No audio for {key}")
        if url.path == "/local/file":
            path = Path(parse_qs(url.query).get("p", [""])[0]).resolve()
            if not any(path.is_relative_to(root) for root in ROOTS):
                return self.send_error(403, "Only files under the corpus folders are served")
            return self.send_file(path) if path.is_file() else self.send_error(404)
        if url.path in ("/", "/index.html"):
            return self.send_page()
        path = (OUT / unquote(url.path).lstrip("/")).resolve()
        if path.is_file() and path.is_relative_to(OUT):
            return self.send_file(path)
        return self.send_error(404)

    def send_page(self):
        """index.html inside the skeleton the website wraps it in when it is published
        (the file itself starts at <title>), so it lays out the same here."""
        body = (SKELETON.format((OUT / "index.html").read_text(encoding="utf-8"))).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_file(self, path: Path):
        """The file, or the part of it the browser's Range header asks for."""
        size = path.stat().st_size
        start, end = 0, size - 1
        ranged = self.headers.get("Range", "").startswith("bytes=")
        if ranged:
            first, _, last = self.headers["Range"][6:].split(",")[0].partition("-")
            if first:
                start, end = int(first), int(last) if last else size - 1
            else:  # "bytes=-500": the last 500 bytes
                start = max(0, size - int(last))
            end = min(end, size - 1)
        self.send_response(206 if ranged else 200)
        self.send_header("Content-Type", mimetypes.guess_type(path.name)[0] or "application/octet-stream")
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(end - start + 1))
        if ranged:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        with path.open("rb") as f:
            f.seek(start)
            left = end - start + 1
            try:
                while left > 0:
                    piece = f.read(min(1 << 20, left))
                    if not piece:
                        break
                    self.wfile.write(piece)
                    left -= len(piece)
            except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
                pass  # the browser jumped elsewhere and dropped this request

    def log_message(self, *args):
        pass


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("corpus", nargs="?", default="scotus", help="scotus, edacc, coraal or earnings22")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true", help="don't open the page")
    args = parser.parse_args()
    global OUT
    OUT = lineup.CAPSTONE / "explorer" / args.corpus
    if not (OUT / "index.html").exists():
        print("No explorer built yet: run tools/build_explorer.py first.")
        return 1
    Handler.audio = json.loads((OUT / "local-audio.json").read_text(encoding="utf-8"))
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    url = f"http://127.0.0.1:{args.port}/"
    print(f"Serving the explorer at {url} (Ctrl+C to stop)", flush=True)
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
