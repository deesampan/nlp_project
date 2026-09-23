"""Stage 5 - aggregate dish-level opinions into menu analytics + recommendations."""
import re
from collections import Counter, defaultdict

MIN_MENTIONS = 4
SIG_LOVE, SIG_NEG = 0.25, 0.15
CRIT_NEG = 0.25
POLAR = 0.20

ASPECTS = {
    "Taste": ["taste", "tasty", "delicious", "yummy", "flavour", "flavor", "bland", "spicy", "salty", "tasteless"],
    "Delivery": ["delivery", "delivered", "late", "delay", "delayed", "hour", "hours", "time", "rider", "cancel"],
    "Packaging": ["packaging", "packed", "package", "spill", "spilled", "leaked", "container", "box"],
    "Price": ["price", "cost", "expensive", "cheap", "worth", "money", "overpriced", "rupees", "rs"],
    "Quantity": ["quantity", "portion", "less", "small", "enough", "pieces", "piece"],
    "Hygiene": ["hair", "worms", "insect", "stale", "smell", "spoilt", "spoiled", "sick", "hygiene", "cockroach"],
}


def classify(d: dict) -> str:
    if d["mentions"] < MIN_MENTIONS:
        return "low-data"
    if d["pos_rate"] >= POLAR and d["neg_rate"] >= POLAR and abs(d["love_score"]) < SIG_LOVE:
        return "polarising"
    if d["love_score"] >= SIG_LOVE and d["neg_rate"] <= SIG_NEG:
        return "signature"
    if d["neg_rate"] >= CRIT_NEG:
        return "needs-improvement"
    return "steady"


def dishes(reviews: list[dict]) -> list[dict]:
    acc = defaultdict(lambda: {"mentions": 0, "pos": 0, "neg": 0, "neu": 0, "sum": 0.0, "stars": [], "review_ids": []})
    for r in reviews:
        for m in {x["dish"]: x for x in r["dishes"]}.values():   # one vote per dish per review
            a = acc[(r["restaurant"], m["dish"])]
            a["mentions"] += 1
            a[{"positive": "pos", "negative": "neg", "neutral": "neu"}[m["label"]]] += 1
            a["sum"] += m["compound"]
            a["stars"].append(r["rating"])
            a["review_ids"].append(r["id"])
    out = []
    for (rest, dish), a in acc.items():
        n = a["mentions"]
        d = {"restaurant": rest, "dish": dish, "mentions": n, "positive": a["pos"], "negative": a["neg"],
             "neutral": a["neu"], "pos_rate": round(a["pos"] / n, 3), "neg_rate": round(a["neg"] / n, 3),
             "love_score": round(a["sum"] / n, 3), "avg_stars": round(sum(a["stars"]) / n, 2),
             "review_ids": a["review_ids"]}
        d["category"] = classify(d)
        out.append(d)
    return sorted(out, key=lambda d: (-d["mentions"], -d["love_score"]))


def restaurant_stats(reviews: list[dict]) -> dict:
    by = defaultdict(list)
    for r in reviews:
        by[r["restaurant"]].append(r)
    out = {}
    for rest, rs in by.items():
        n = len(rs)
        name = set(re.findall(r"[a-z]+", rest.lower()))   # "biriyani nights" is the venue, not an opinion
        words = Counter(w for r in rs for w in r["tokens_nostop"] if w.isalpha() and len(w) > 2 and w not in name)
        asp = {}
        for a, kws in ASPECTS.items():
            hit = [r for r in rs if any(k in r["tokens"] for k in kws)]
            asp[a] = {"mentions": len(hit),
                      "negative": sum(r["sentiment"] == "negative" for r in hit),
                      "positive": sum(r["sentiment"] == "positive" for r in hit)}
        out[rest] = {
            "reviews": n,
            "avg_stars": round(sum(r["rating"] for r in rs) / n, 2),
            "sentiment": dict(Counter(r["sentiment"] for r in rs)),
            "stars": {str(k): v for k, v in sorted(Counter(r["rating"] for r in rs).items())},
            "with_dish": sum(bool(r["dishes"]) for r in rs),
            "top_words": words.most_common(25),
            "aspects": asp,
        }
    return out


def weak_label_eval(reviews: list[dict]) -> dict:
    """VADER review polarity vs star rating (>=4 positive, <=2 negative; 3 dropped)."""
    tp = fp = fn = tn = 0
    for r in reviews:
        if 2 < r["rating"] < 4:
            continue
        gold = r["rating"] >= 4
        pred = r["compound"] >= 0.05
        tp += gold and pred; tn += (not gold) and (not pred)
        fp += (not gold) and pred; fn += gold and (not pred)
    n = tp + tn + fp + fn
    prec = tp / max(tp + fp, 1); rec = tp / max(tp + fn, 1)
    return {"n": n, "accuracy": round((tp + tn) / n, 3), "precision": round(prec, 3), "recall": round(rec, 3),
            "f1": round(2 * prec * rec / max(prec + rec, 1e-9), 3),
            "confusion": {"tp": tp, "fp": fp, "fn": fn, "tn": tn}}
