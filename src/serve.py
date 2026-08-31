"""Serve the dashboard on localhost with caching turned off.

Use this instead of `python -m http.server`.

Why: the plain http.server sends no cache headers, so browsers keep serving an
old dashboard.json and dashboard.js after you re-run the pipeline. The page then
shows the previous run's numbers with no error and no clue anything is stale.
This server sends no-store, so a normal refresh always shows current results.

    cd src
    ../.venv/Scripts/python serve.py          # http://localhost:8000
    ../.venv/Scripts/python serve.py 8080     # different port
"""
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

from config import OUT_WEB


class NoCacheHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def log_message(self, fmt, *args):
        pass  # quiet; the console is for the pipeline, not request spam


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    handler = partial(NoCacheHandler, directory=str(OUT_WEB))
    httpd = ThreadingHTTPServer(("127.0.0.1", port), handler)
    print("Dashboard serving at  http://localhost:%d" % port)
    print("Folder: %s" % OUT_WEB)
    print("Caching disabled, so refresh always shows the latest build.")
    print("Press Ctrl+C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")


if __name__ == "__main__":
    main()
