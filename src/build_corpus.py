"""Phase 2a - full corpus cleaning over the entire Zomato dump.

Nine ordered stages. Order matters: deduplicate before cleaning so we do not
pay to clean rows we are about to drop, and filter language before any English
model touches the text.

Every stage logs rows in and rows out. The funnel is the deliverable, not a
by-product -- it is what makes the cleaning auditable.
"""
import csv
import re
import sys
import ast
import html
import hashlib
import collections
import unicodedata

import ftfy
from langdetect import detect, DetectorFactory, LangDetectException

from config import ZOMATO_CSV, OUT_DATA, OUT_RESULTS, ensure_dirs

csv.field_size_limit(min(sys.maxsize, 2**31 - 1))
DetectorFactory.seed = 0          # deterministic language detection

MIN_CHARS = 15
MAX_CHARS = 5000
BOILERPLATE_RESTAURANT_LIMIT = 5   # same text at more restaurants than this = spam

OUT_CSV = OUT_DATA / "reviews_clean.csv"
FUNNEL_CSV = OUT_RESULTS / "cleaning_funnel.csv"
VOCAB_TXT = OUT_RESULTS / "vocab_before_after.txt"

_url = re.compile(r"https?://\S+|www\.\S+")
_email = re.compile(r"\S+@\S+\.\S+")
_phone = re.compile(r"(?<!\d)(?:\+?\d[\d\s-]{7,}\d)(?!\d)")
_ws = re.compile(r"\s+")
_elong = re.compile(r"(.)\1{2,}")
_rating = re.compile(r"Rated\s+([\d.]+)")
_token = re.compile(r"[a-z][a-z']+")

CONTRACTIONS = {
    "don't": "do not", "doesn't": "does not", "didn't": "did not",
    "isn't": "is not", "wasn't": "was not", "aren't": "are not",
    "weren't": "were not", "won't": "will not", "wouldn't": "would not",
    "can't": "cannot", "couldn't": "could not", "shouldn't": "should not",
    "haven't": "have not", "hasn't": "has not", "hadn't": "had not",
    "it's": "it is", "that's": "that is", "there's": "there is",
    "i'm": "i am", "i've": "i have", "we've": "we have", "they're": "they are",
}
_contr = re.compile(r"\b(" + "|".join(map(re.escape, CONTRACTIONS)) + r")\b")


def label_of(rating):
    if rating is None:
        return None
    if rating >= 4.0:
        return "positive"
    if rating >= 3.0:
        return "neutral"
    return "negative"


def structural_clean(t):
    """Stage 4: repair encoding, strip platform markers and contact details."""
    t = ftfy.fix_text(t)
    t = html.unescape(t)
    t = unicodedata.normalize("NFKC", t)
    if t.startswith("RATED"):
        t = t[5:]
    t = t.replace("\\n", " ").replace("\n", " ").replace("\\t", " ")
    t = _url.sub(" ", t)
    t = _email.sub(" ", t)
    t = _phone.sub(" ", t)
    return _ws.sub(" ", t).strip()


def normalise(t):
    """Stage 7: collapse elongations and expand contractions. Case preserved."""
    t = _elong.sub(r"\1\1", t)
    low = t.lower()
    low = _contr.sub(lambda m: CONTRACTIONS[m.group(1)], low)
    return low


def main():
    ensure_dirs()
    funnel = collections.OrderedDict()

    # ---- stage 1: parse and explode -------------------------------------
    raw = []          # (rest_key, name, rating, text)
    rows_read = 0
    with open(ZOMATO_CSV, "r", encoding="utf-8", errors="replace", newline="") as f:
        for row in csv.DictReader(f):
            rows_read += 1
            key = ((row.get("name") or "").strip().lower(),
                   (row.get("address") or "").strip().lower())
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
                m = _rating.search(str(rt))
                raw.append((key, (row.get("name") or "").strip(),
                            float(m.group(1)) if m else None, tx))
    funnel["csv_rows"] = rows_read
    funnel["review_tuples"] = len(raw)

    # ---- stage 2: deduplicate on (restaurant, text) ----------------------
    seen = set()
    text_rests = collections.defaultdict(set)
    deduped = []
    for key, name, rating, tx in raw:
        h = hashlib.md5(tx.encode("utf-8", "replace")).digest()[:8]
        text_rests[h].add(key)
        if (key, h) in seen:
            continue
        seen.add((key, h))
        deduped.append((key, name, rating, tx, h))
    funnel["after_dedup"] = len(deduped)
    del raw

    # ---- stage 3: drop boilerplate --------------------------------------
    boiler = {h for h, rs in text_rests.items() if len(rs) > BOILERPLATE_RESTAURANT_LIMIT}
    stage3 = [r for r in deduped if r[4] not in boiler]
    funnel["after_boilerplate"] = len(stage3)
    del deduped

    # ---- stage 4 + 6: structural clean, then length filter --------------
    stage4 = []
    for key, name, rating, tx, h in stage3:
        c = structural_clean(tx)
        if len(c) < MIN_CHARS or len(c) > MAX_CHARS:
            continue
        if not any(ch.isalpha() for ch in c):
            continue
        stage4.append((key, name, rating, tx, c))
    funnel["after_length_quality"] = len(stage4)
    del stage3

    # ---- stage 5: language filter ---------------------------------------
    stage5 = []
    for rec in stage4:
        c = rec[4]
        na = sum(1 for ch in c if ord(ch) > 127)
        if len(c) and na / len(c) > 0.25:
            continue
        try:
            if detect(c) != "en":
                continue
        except LangDetectException:
            continue
        stage5.append(rec)
    funnel["after_language"] = len(stage5)
    del stage4

    # ---- stage 8: label ---------------------------------------------------
    final = [(k, n, r, tx, c, label_of(r)) for k, n, r, tx, c in stage5 if label_of(r)]
    funnel["after_labelling"] = len(final)
    del stage5

    # ---- write ------------------------------------------------------------
    labels = collections.Counter()
    vocab_before, vocab_after = set(), set()
    with open(OUT_CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["restaurant_name", "restaurant_key", "rating", "label",
                    "text_clean", "text_norm"])
        for key, name, rating, tx, c, lab in final:
            n = normalise(c)
            labels[lab] += 1
            vocab_before.update(_token.findall(tx.lower()))
            vocab_after.update(_token.findall(n))
            w.writerow([name, key[0] + "|" + key[1], rating, lab, c, n])

    with open(FUNNEL_CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["stage", "rows", "dropped_here", "pct_of_tuples"])
        prev = None
        base = funnel["review_tuples"]
        for k, v in funnel.items():
            drop = "" if prev is None or k == "review_tuples" else prev - v
            w.writerow([k, v, drop, round(100.0 * v / base, 2)])
            prev = v

    with open(VOCAB_TXT, "w", encoding="utf-8") as f:
        f.write("vocabulary before normalisation: %d\n" % len(vocab_before))
        f.write("vocabulary after normalisation:  %d\n" % len(vocab_after))
        f.write("reduction: %.1f%%\n\n" % (100.0 * (1 - len(vocab_after) / max(len(vocab_before), 1))))
        for k, v in labels.items():
            f.write("%-10s %7d  %5.1f%%\n" % (k, v, 100.0 * v / len(final)))

    print("=== CLEANING FUNNEL ===")
    prev = None
    for k, v in funnel.items():
        drop = "" if prev is None else "  (-%d)" % (prev - v)
        print("  %-22s %9d%s" % (k, v, drop))
        prev = v
    print("\n=== LABELS ===")
    for k, v in labels.most_common():
        print("  %-10s %7d  %5.1f%%" % (k, v, 100.0 * v / len(final)))
    print("\nvocabulary %d -> %d  (-%.1f%%)" % (
        len(vocab_before), len(vocab_after),
        100.0 * (1 - len(vocab_after) / max(len(vocab_before), 1))))
    print("wrote %s" % OUT_CSV)


if __name__ == "__main__":
    main()
