"""Write the reviews the noise filters removed to web/removed.js, so each restaurant
page can list what was left out and why.

Needs only the review CSV and the preprocessing step, so it can run on its own
without rebuilding data.js:

    python -m src.export_removed
"""
import json
import pandas as pd
from . import load_data, preprocess
from .common import WEB


def write(removed: pd.DataFrame) -> None:
    rows = [{"id": int(r.review_id), "restaurant": r.restaurant_name, "reason": r.reason,
             "rating": None if pd.isna(r.review_rating) else float(r.review_rating),
             "raw": r.review_text_raw, "clean": r.clean_text} for r in removed.itertuples()]
    WEB.mkdir(parents=True, exist_ok=True)
    (WEB / "removed.js").write_text(
        "window.RESREC_REMOVED = " + json.dumps(rows, ensure_ascii=False, separators=(",", ":")) + ";\n",
        encoding="utf-8")


if __name__ == "__main__":
    _, funnel, removed = preprocess.run(load_data.load_reviews())
    write(removed)
    for f in funnel:
        print(f"{f['step']:<30} -{f['removed']:<4} -> {f['remaining']}")
    print(removed.groupby(["restaurant_name", "reason"]).size().to_string())
