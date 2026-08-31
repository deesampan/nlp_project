"""Proper vocabulary measurement for the noise analysis.

The first attempt compared two already-lowercased token sets, so it could not
show the casing collapse and reported a meaningless 1.1%. This decomposes the
reduction stage by stage instead, which is what makes it evidence.
"""
import csv
import re
import sys
import ast
import hashlib
import collections

from config import ZOMATO_CSV, OUT_RESULTS, ensure_dirs
from build_corpus import structural_clean, normalise

csv.field_size_limit(min(sys.maxsize, 2**31 - 1))

_tok_cs = re.compile(r"[A-Za-z][A-Za-z']+")
_tok_ci = re.compile(r"[a-z][a-z']+")


def main():
    ensure_dirs()
    seen = set()
    v_raw, v_lower, v_clean, v_norm = set(), set(), set(), set()
    n = 0
    tok_raw = tok_norm = 0

    with open(ZOMATO_CSV, "r", encoding="utf-8", errors="replace", newline="") as f:
        for row in csv.DictReader(f):
            key = ((row.get("name") or "").strip().lower(),
                   (row.get("address") or "").strip().lower())
            try:
                lst = ast.literal_eval(row.get("reviews_list") or "[]")
            except Exception:
                continue
            for item in lst:
                try:
                    tx = item[1]
                except Exception:
                    continue
                if not tx:
                    continue
                h = hashlib.md5(tx.encode("utf-8", "replace")).digest()[:8]
                if (key, h) in seen:
                    continue
                seen.add((key, h))
                n += 1

                raw_tokens = _tok_cs.findall(tx)
                v_raw.update(raw_tokens)
                v_lower.update(t.lower() for t in raw_tokens)
                tok_raw += len(raw_tokens)

                c = structural_clean(tx)
                v_clean.update(_tok_cs.findall(c.lower()) if False else
                               (t.lower() for t in _tok_cs.findall(c)))

                nm = normalise(c)
                nt = _tok_ci.findall(nm)
                v_norm.update(nt)
                tok_norm += len(nt)

    stages = [
        ("raw text, case sensitive", len(v_raw), ""),
        ("after lowercasing", len(v_lower), "casing collapse"),
        ("after structural cleaning", len(v_clean), "encoding repair, marker and URL removal"),
        ("after normalisation", len(v_norm), "elongations collapsed, contractions expanded"),
    ]

    with open(OUT_RESULTS / "vocab_before_after.txt", "w", encoding="utf-8") as f:
        f.write("Vocabulary reduction, measured over %d deduplicated reviews\n" % n)
        f.write("(token = alphabetic word, apostrophes allowed)\n\n")
        f.write("%-32s %10s %10s  %s\n" % ("stage", "vocab", "cut", "what it removes"))
        base = len(v_raw)
        prev = base
        for name, size, note in stages:
            cut = "" if prev == size and name.startswith("raw") else "-%.1f%%" % (100.0 * (prev - size) / prev)
            f.write("%-32s %10d %10s  %s\n" % (name, size, cut, note))
            prev = size
        f.write("\ntotal reduction: %d -> %d  (-%.1f%%)\n" % (
            base, len(v_norm), 100.0 * (1 - len(v_norm) / base)))
        f.write("token count: %d -> %d\n" % (tok_raw, tok_norm))

    print("reviews measured: %d" % n)
    print("%-32s %10s %8s" % ("stage", "vocab", "cut"))
    prev = len(v_raw)
    for name, size, note in stages:
        cut = "" if name.startswith("raw") else "-%.1f%%" % (100.0 * (prev - size) / prev)
        print("%-32s %10d %8s" % (name, size, cut))
        prev = size
    print("\ntotal: %d -> %d  (-%.1f%%)" % (
        len(v_raw), len(v_norm), 100.0 * (1 - len(v_norm) / len(v_raw))))


if __name__ == "__main__":
    main()
