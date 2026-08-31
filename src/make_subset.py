"""Choose which restaurants the dashboard shows.

Ranks restaurants by unique review count and exports the ones you pick.

    ../.venv/Scripts/python make_subset.py                  # ranks 1 2 3 (default)
    ../.venv/Scripts/python make_subset.py --rank 4 5 6     # 4th, 5th, 6th busiest
    ../.venv/Scripts/python make_subset.py --top 5          # ranks 1..5
    ../.venv/Scripts/python make_subset.py --list 15        # just show the ranking

Then re-run build_slice.py to rebuild the website data.
"""
import argparse
import ast
import collections
import csv
import hashlib
import re
import sys

from config import ZOMATO_CSV, SUBSET_CSV, DROPPED_DUPES_CSV, ensure_dirs

csv.field_size_limit(min(sys.maxsize, 2**31 - 1))
_rating = re.compile(r"Rated\s+([\d.]+)")


def rank_restaurants():
    """Unique review count per restaurant, biggest first."""
    uniq = collections.defaultdict(set)
    shown = {}
    with open(ZOMATO_CSV, "r", encoding="utf-8", errors="replace", newline="") as f:
        for row in csv.DictReader(f):
            key = ((row.get("name") or "").strip().lower(),
                   (row.get("address") or "").strip().lower())
            shown.setdefault(key, ((row.get("name") or "").strip(),
                                   (row.get("address") or "").strip()))
            try:
                lst = ast.literal_eval(row.get("reviews_list") or "[]")
            except Exception:
                continue
            for item in lst:
                try:
                    tx = item[1]
                except Exception:
                    continue
                if tx:
                    uniq[key].add(hashlib.md5(tx.encode("utf-8", "replace")).digest()[:8])
    ordered = sorted(uniq.items(), key=lambda kv: len(kv[1]), reverse=True)
    return [(k, shown[k], len(v)) for k, v in ordered]


def export(ranked, wanted_ranks):
    keys = {ranked[r - 1][0]: r for r in wanted_ranks}
    rows_out = seen = 0
    seen_pairs = set()
    per_rest = collections.Counter()
    dups = []          # duplicate copies we discard, kept for the audit trail

    with open(ZOMATO_CSV, "r", encoding="utf-8", errors="replace", newline="") as fin, \
         open(SUBSET_CSV, "w", encoding="utf-8", newline="") as fout:
        w = csv.writer(fout)
        w.writerow(["restaurant_rank", "restaurant_name", "address", "location",
                    "rest_type", "cuisines", "dish_liked", "approx_cost_for_two",
                    "restaurant_rate", "restaurant_votes", "listed_in_type",
                    "review_rating", "review_text_raw", "review_text"])
        for row in csv.DictReader(fin):
            key = ((row.get("name") or "").strip().lower(),
                   (row.get("address") or "").strip().lower())
            if key not in keys:
                continue
            try:
                lst = ast.literal_eval(row.get("reviews_list") or "[]")
            except Exception:
                continue
            for item in lst:
                try:
                    rt, tx = item[0], item[1]
                except Exception:
                    continue
                if not tx:
                    continue
                seen += 1
                h = (key, hashlib.md5(tx.encode("utf-8", "replace")).digest()[:8])
                clean = tx[5:] if tx.startswith("RATED") else tx
                clean = re.sub(r"\s+", " ", clean.replace("\\n", " ").replace("\n", " ")).strip()
                if h in seen_pairs:
                    dups.append([row.get("name", "").strip(), "duplicate", clean])
                    continue
                seen_pairs.add(h)
                m = _rating.search(str(rt))
                w.writerow([keys[key], row.get("name", "").strip(),
                            row.get("address", "").strip(), row.get("location"),
                            row.get("rest_type"), row.get("cuisines"),
                            row.get("dish_liked"),
                            row.get("approx_cost(for two people)"),
                            row.get("rate"), row.get("votes"),
                            row.get("listed_in(type)"),
                            m.group(1) if m else "", tx, clean])
                rows_out += 1
                per_rest[keys[key]] += 1

    with open(DROPPED_DUPES_CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["restaurant_name", "reason", "text"])
        w.writerows(dups)
    return rows_out, seen, per_rest


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--rank", nargs="+", type=int, help="specific ranks, e.g. --rank 4 5 6")
    g.add_argument("--top", type=int, help="ranks 1..N")
    ap.add_argument("--list", type=int, metavar="N", help="only print the top N ranking")
    a = ap.parse_args()

    ensure_dirs()
    print("ranking restaurants by unique review count ...")
    ranked = rank_restaurants()
    print("%d restaurants found\n" % len(ranked))

    if a.list:
        print("%-5s %-34s %-9s %s" % ("rank", "restaurant", "reviews", "area"))
        for i, (_, (name, addr), n) in enumerate(ranked[:a.list], 1):
            print("%-5d %-34s %-9d %s" % (i, name[:34], n, addr[:38]))
        return

    ranks = a.rank if a.rank else list(range(1, (a.top or 3) + 1))
    bad = [r for r in ranks if r < 1 or r > len(ranked)]
    if bad:
        print("rank out of range: %s (valid 1..%d)" % (bad, len(ranked)))
        return

    print("selected:")
    for r in ranks:
        _, (name, addr), n = ranked[r - 1]
        print("  #%-3d %-32s %5d unique reviews   %s" % (r, name[:32], n, addr[:34]))

    rows, seen, per = export(ranked, ranks)
    print("\nwrote %s" % SUBSET_CSV)
    print("  %d unique reviews (from %d raw entries, %d duplicates removed)"
          % (rows, seen, seen - rows))
    for r in sorted(per):
        print("  rank %d: %d reviews" % (r, per[r]))
    print("\nNext: ../.venv/Scripts/python build_slice.py   then refresh the website")


if __name__ == "__main__":
    main()
