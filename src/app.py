"""Serves the dashboard and analyses uploaded CSV files.

    cd src
    ../.venv/Scripts/python app.py          # http://localhost:8000
    ../.venv/Scripts/python app.py 8080     # different port

Two jobs:

  1. Serve output_project/web with caching off, so a refresh always shows the
     latest build instead of a stale one.
  2. POST /api/analyze -- take a restaurant name and a CSV of reviews, run the
     real trained model over them, and return the same JSON shape the built-in
     restaurants use.

The upload is analysed in memory and never written to disk. Refreshing the page
forgets it, which keeps demos clean and leaves nothing to tidy up afterwards.
"""
import csv
import io
import sys
import time

from flask import Flask, jsonify, request, send_from_directory

from config import OUT_WEB
from analyze import get_analyzer

MAX_ROWS = 2000
MAX_BYTES = 8 * 1024 * 1024
TEXT_HEADERS = {"review", "reviews", "text", "comment", "comments",
                "review_text", "body", "feedback"}

app = Flask(__name__, static_folder=None)


@app.after_request
def no_cache(resp):
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    return resp


# ------------------------------------------------------------------ static
@app.route("/")
def index():
    return send_from_directory(OUT_WEB, "index.html")


@app.route("/<path:path>")
def static_files(path):
    return send_from_directory(OUT_WEB, path)


# ------------------------------------------------------------------- upload
def parse_reviews(raw):
    """Pull review text out of an uploaded CSV.

    Deliberately forgiving: the file may have one column or many, with or
    without a header row. We take the column that looks like review text, or
    the first column if nothing looks obvious.
    """
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("latin-1", errors="replace")

    rows = list(csv.reader(io.StringIO(text)))
    rows = [r for r in rows if any((c or "").strip() for c in r)]
    if not rows:
        return [], "The file has no rows."

    col = 0
    start = 0
    head = [(c or "").strip().lower() for c in rows[0]]
    named = [i for i, h in enumerate(head) if h in TEXT_HEADERS]
    if named:
        col, start = named[0], 1
    elif len(head) == 1 and head[0] in TEXT_HEADERS:
        col, start = 0, 1
    elif len(rows) > 1 and len(head[0]) < 25 and " " not in head[0].strip():
        # a short single-word first cell is far more likely a header than a review
        start = 1
    else:
        # no header: pick the column with the longest average text
        widths = []
        for i in range(len(rows[0])):
            vals = [len((r[i] or "")) for r in rows[:50] if i < len(r)]
            widths.append(sum(vals) / max(len(vals), 1))
        col = widths.index(max(widths)) if widths else 0

    out = []
    for r in rows[start:]:
        if col < len(r):
            t = (r[col] or "").strip()
            if t:
                out.append({"text": t, "rating": None})
        if len(out) >= MAX_ROWS:
            break
    return out, None


@app.route("/api/analyze", methods=["POST"])
def analyze_upload():
    name = (request.form.get("name") or "").strip()
    if not name:
        return jsonify(error="Please enter a restaurant name."), 400
    if len(name) > 80:
        name = name[:80]

    f = request.files.get("file")
    if f is None or not f.filename:
        return jsonify(error="Please choose a CSV file."), 400

    raw = f.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        return jsonify(error="That file is larger than 8 MB."), 400
    if not raw.strip():
        return jsonify(error="That file is empty."), 400

    reviews, err = parse_reviews(raw)
    if err:
        return jsonify(error=err), 400
    if not reviews:
        return jsonify(error="No review text found. The CSV needs at least one "
                             "column containing the review text."), 400

    # Uploaded files get different settings from the built-in restaurants:
    #  - min_mentions=1, because an uploaded file is small and hiding every dish
    #    under 5 comments leaves the page empty
    #  - discover=True, because the dish dictionary was built from the Zomato
    #    data and will not contain the cuisine someone uploads
    t0 = time.time()
    rest, funnel = get_analyzer().analyse_restaurant(
        name, reviews, min_mentions=1, discover=True)
    took = time.time() - t0

    if rest is None:
        return jsonify(error="None of those %d rows survived cleaning. Reviews "
                             "shorter than 20 characters are dropped."
                             % len(reviews)), 400

    rest["uploaded"] = True
    return jsonify(restaurant=rest, funnel=funnel,
                   seconds=round(took, 1), rows_read=len(reviews))


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    print("Loading the model ...")
    get_analyzer()
    print("Dashboard ready at  http://localhost:%d" % port)
    print("Folder: %s" % OUT_WEB)
    print("Press Ctrl+C to stop.")
    app.run(host="127.0.0.1", port=port, debug=False)
