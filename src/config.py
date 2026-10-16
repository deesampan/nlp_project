"""Shared paths. Everything generated resolves under output_project/."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DATA_RAW = ROOT / "data_raw"
ZOMATO_CSV = DATA_RAW / "zomato.csv"

OUT = ROOT / "output_project"
OUT_DATA = OUT / "data"
OUT_RESULTS = OUT / "results"
OUT_FIGURES = OUT / "figures"
OUT_WEB = OUT / "web"
OUT_REPORTS = OUT / "reports"
OUT_LOGS = OUT / "logs"

# Whichever restaurants the dashboard currently shows. Regenerate with
# make_subset.py --rank 4 5 6 (or any ranks you want).
SUBSET_CSV = OUT_DATA / "selected_restaurants_reviews.csv"
TOP3_REVIEWS = SUBSET_CSV  # backwards-compatible alias

# Duplicate copies discarded at export, kept so the website can show its work.
DROPPED_DUPES_CSV = OUT_DATA / "dropped_duplicates.csv"
GAZETTEER = OUT_DATA / "dish_gazetteer.csv"


def ensure_dirs():
    for d in (OUT_DATA, OUT_RESULTS, OUT_FIGURES, OUT_WEB,
              OUT_REPORTS, OUT_LOGS):
        d.mkdir(parents=True, exist_ok=True)
