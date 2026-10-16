"""One-off repair of output_project/data/top3_restaurants_raw.csv.

The file was once saved through Excel, which cuts any cell at about 32,767
characters. Each long reviews_list cell was cut, and the rest of it spilled
into a junk row underneath, split on every comma. The record's last three
columns (menu_item, listed_in(type), listed_in(city)) ended up as the last
three cells of that junk row.

This script glues each record back to its junk row and writes a clean
17-column file. Menus and metadata come back exactly. reviews_list is lossy:
Excel dropped one character at each cut. Nothing reads that column (reviews
come from top3_restaurants_reviews.csv). Running it on a clean file does nothing.

    python -m src.repair_raw_csv
"""
import csv
import sys
from .common import RAW_CSV

csv.field_size_limit(min(sys.maxsize, 2**31 - 1))
N_COLS = 17


def filled(row: list[str]) -> int:
    return sum(1 for c in row if c)


def repair(rows: list[list[str]]) -> list[list[str]]:
    header, body = rows[0][:N_COLS], rows[1:]
    out, i = [], 0
    while i < len(body):
        rec = body[i][:N_COLS]
        nxt = body[i + 1] if i + 1 < len(body) else None
        if nxt and filled(nxt) > N_COLS:               # junk row = overflow of this record
            last = max(j for j, c in enumerate(nxt) if c)
            rec[13] += "," + ",".join(nxt[:last - 2])    # rest of reviews_list
            rec[14:17] = nxt[last - 2:last + 1]          # menu_item, listed_in(type), listed_in(city)
            i += 2
        else:
            i += 1
        out.append(rec)
    return [header] + out


def main():
    with open(RAW_CSV, encoding="utf-8", newline="") as f:
        rows = list(csv.reader(f))
    if len(rows[0]) == N_COLS:
        print(f"{RAW_CSV.name} already has {N_COLS} columns - nothing to do")
        return
    fixed = repair(rows)
    with open(RAW_CSV, "w", encoding="utf-8", newline="") as f:
        csv.writer(f, lineterminator="\n").writerows(fixed)
    print(f"{RAW_CSV.name}: {len(rows) - 1} rows x {len(rows[0])} cols -> {len(fixed) - 1} rows x {N_COLS} cols")
    for r in fixed[1:]:
        print(f"  {r[2]:<18} votes {r[6]:<4} {r[16]:<14} menu cell {len(r[14])} chars")


if __name__ == "__main__":
    main()
