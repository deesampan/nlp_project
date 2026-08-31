"""Build the dashboard payload for the selected restaurants.

Thin wrapper now: it reads the CSV, groups reviews by restaurant, and hands each
group to analyze.py. All the actual analysis lives there, shared with the live
upload endpoint in app.py.
"""
import csv
import json
import collections
import sys
from datetime import datetime, timezone

from config import (TOP3_REVIEWS, DASHBOARD_JSON, OUT_RESULTS, MIN_MENTIONS,
                    DROPPED_DUPES_CSV, ensure_dirs)
from analyze import get_analyzer, slugify

csv.field_size_limit(min(sys.maxsize, 2**31 - 1))


def load_rows():
    with open(TOP3_REVIEWS, "r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def duplicates_by_restaurant():
    """Duplicates were discarded earlier, by make_subset.py."""
    out = collections.defaultdict(list)
    if DROPPED_DUPES_CSV.exists():
        with open(DROPPED_DUPES_CSV, "r", encoding="utf-8", newline="") as f:
            for d in csv.DictReader(f):
                out[d["restaurant_name"]].append(d["text"])
    return out


def main():
    ensure_dirs()
    az = get_analyzer()
    rows = load_rows()
    dupes = duplicates_by_restaurant()

    grouped = collections.OrderedDict()
    meta = {}
    for r in rows:
        name = r["restaurant_name"]
        if name not in grouped:
            grouped[name] = []
            meta[name] = {
                "address": r.get("address", ""),
                "location": r.get("location", ""),
                "rest_type": r.get("rest_type", ""),
                "cuisines": r.get("cuisines", ""),
                "approx_cost": r.get("approx_cost_for_two", ""),
                "rate": (r.get("restaurant_rate") or "").replace(" ", ""),
                "votes": int(r.get("restaurant_votes") or 0),
                "dish_liked": [d.strip() for d in (r.get("dish_liked") or "").split(",") if d.strip()],
            }
        try:
            rating = float(r["review_rating"]) if r.get("review_rating") else None
        except ValueError:
            rating = None
        grouped[name].append({
            "text": r.get("review_text_raw") or r.get("review_text") or "",
            "rating": rating,
        })

    metrics = {}
    p = OUT_RESULTS / "model_metrics.json"
    if p.exists():
        metrics = json.load(open(p, encoding="utf-8"))

    out = {
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        "source": TOP3_REVIEWS.name,
        "sentiment_method": "clause-level TF-IDF + logistic regression",
        "min_mentions": MIN_MENTIONS,
        "quality": collections.Counter(),
        "model": {"metrics": metrics},
        "restaurants": [],
    }

    for name, reviews in grouped.items():
        rest, funnel = az.analyse_restaurant(
            name, reviews, meta=meta[name],
            extra_dropped={"duplicate": dupes.get(name, [])})
        if rest is None:
            print("  %-20s no usable reviews, skipped" % name[:20])
            continue
        out["restaurants"].append(rest)
        for k, v in funnel.items():
            out["quality"][k] += v

    # roll the per-restaurant drop counts up so the site's funnel panel has totals
    for r in out["restaurants"]:
        for k, v in r["dropped"]["counts"].items():
            out["quality"]["dropped_" + k] += v

    out["quality"] = dict(out["quality"])
    out["restaurants"].sort(key=lambda r: -r["review_count"])

    DASHBOARD_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(DASHBOARD_JSON, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    with open(OUT_RESULTS / "slice_funnel.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["stage", "count"])
        for k, v in out["quality"].items():
            w.writerow([k, v])

    print("=== FUNNEL ===")
    for k, v in out["quality"].items():
        print("  %-24s %6d" % (k, v))
    print("\n=== RESTAURANTS ===")
    for r in out["restaurants"]:
        print("  %-20s reviews=%-4d pos=%.2f dishes=%d  (sentiment from %s)" % (
            r["name"][:20], r["review_count"], r["positive_rate"],
            r["dishes_ranked"], r["sentiment_source"]))
        for d in r["dishes"][:3]:
            print("      + %-20s %3d comments  %3d%% liked" % (
                d["dish"], d["mentions"], round(d["positive_rate"] * 100)))
    print("\nwrote %s" % DASHBOARD_JSON)


if __name__ == "__main__":
    main()
