"""Serves the website on localhost with caching turned off.

    cd src
    ../.venv/Scripts/python app.py          # http://localhost:8000
    ../.venv/Scripts/python app.py 8080     # different port

Caching is off so a refresh always shows the latest build of data.js instead of
a stale one. Rebuild the data with `python run_pipeline.py` from the project root.
"""
import sys

from flask import Flask, send_from_directory

from config import OUT_WEB

app = Flask(__name__, static_folder=None)


@app.after_request
def no_cache(resp):
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    return resp


@app.route("/")
def index():
    return send_from_directory(OUT_WEB, "index.html")


@app.route("/<path:path>")
def static_files(path):
    return send_from_directory(OUT_WEB, path)


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    print("Website ready at  http://localhost:%d" % port)
    print("Folder: %s" % OUT_WEB)
    print("Press Ctrl+C to stop.")
    app.run(host="127.0.0.1", port=port, debug=False)
