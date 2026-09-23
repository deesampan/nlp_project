"""Stage 4 - dish-level sentiment with VADER + clause attribution.

A review is split into clauses on contrast markers and sentence punctuation; each
dish inherits the VADER compound score of the clause it appears in, so
"The salad was amazing, but the chicken was cold" gives two different opinions.
"""
import re
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

VADER = SentimentIntensityAnalyzer()
# Food-review words VADER's general lexicon misses.
VADER.lexicon.update({"tasty": 2.0, "yummy": 2.2, "delicious": 2.7, "bland": -1.8, "stale": -2.0,
                      "cold": -1.0, "soggy": -1.8, "oily": -1.5, "greasy": -1.6, "undercooked": -2.0,
                      "overcooked": -1.6, "raw": -1.2, "tasteless": -2.2, "rubbery": -1.8, "worms": -3.0,
                      "hair": -1.5, "spoilt": -2.5, "spoiled": -2.5, "must try": 2.0, "juicy": 1.8,
                      "flavourful": 2.2, "flavorful": 2.2, "crispy": 1.2, "fresh": 1.5, "worst": -3.1})
POS, NEG = 0.05, -0.05
SPLIT = re.compile(r"(?<=[.!?;])\s+|\s+(?=\b(?:but|however|although|though|whereas|except|while)\b)", re.I)


def label(c: float) -> str:
    return "positive" if c >= POS else "negative" if c <= NEG else "neutral"


def clauses(text: str) -> list[dict]:
    out, pos = [], 0
    for part in SPLIT.split(text):
        if not part.strip():
            continue
        start = text.find(part, pos)
        pos = start + len(part)
        c = VADER.polarity_scores(part)["compound"]
        out.append({"start": start, "end": pos, "text": part, "compound": round(c, 3), "label": label(c)})
    return out


def review_score(text: str) -> float:
    return VADER.polarity_scores(text)["compound"]


def attribute(mentions: list[dict], cls: list[dict]) -> list[dict]:
    for m in mentions:
        cl = next((c for c in cls if c["start"] <= m["start"] < c["end"]), None)
        c = cl["compound"] if cl else 0.0
        m["compound"], m["label"] = c, label(c)
        m["clause"] = cl["text"] if cl else ""
    return mentions
