"""Shared paths and text-normalisation helpers for the ResRec pipeline."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output_project"
DATA = OUT / "data"
RESULTS = OUT / "results"
WEB = OUT / "web"
LOGS = OUT / "logs"

REVIEWS_CSV = DATA / "top3_restaurants_reviews.csv"
RAW_CSV = DATA / "top3_restaurants_raw.csv"

# Spelling variants seen in Zomato reviews -> one canonical token.
# Applied to BOTH the gazetteer and review tokens so matching is symmetric.
SPELLING = {
    "biriyani": "biryani", "briyani": "biryani", "biriani": "biryani", "biryanis": "biryani",
    "birayani": "biryani", "briyani's": "biryani", "biryaani": "biryani",
    "kabab": "kebab", "kababs": "kebab", "kebabs": "kebab", "kabob": "kebab",
    "jamoon": "jamun", "jamuns": "jamun", "jamoons": "jamun",
    "makhani": "makhni", "makhanwala": "makhni",
    "chilli": "chilly", "chili": "chilly",
    "panneer": "paneer", "panner": "paneer",
    "lollipop": "lollypop", "lollypops": "lollypop", "lollipops": "lollypop",
    "manchuri": "manchurian",
    "nan": "naan", "rotis": "roti", "parathas": "paratha", "paratas": "paratha", "parotta": "paratha",
    "brownies": "brownie", "salads": "salad", "wraps": "wrap", "sandwiches": "sandwich",
    "noodle": "noodles", "wings": "wings", "fries": "fries",
    "ricebox": "rice box",
}


def norm_token(t: str) -> str:
    t = t.lower()
    return SPELLING.get(t, t)


WORD_RE = re.compile(r"[a-z0-9]+(?:'[a-z]+)?")


def simple_words(text: str) -> list[str]:
    return [norm_token(w) for w in WORD_RE.findall(text.lower())]


# The sentiment model was trained on text passed through normalise(), so every text it
# classifies goes through the same function (build_corpus.py and sentiment.py both use it).
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
_elong = re.compile(r"(.)\1{2,}")


def normalise(t: str) -> str:
    """Collapse elongations ("soooo" -> "soo") and expand contractions ("wasn't" -> "was not")."""
    t = _elong.sub(r"\1\1", t)
    return _contr.sub(lambda m: CONTRACTIONS[m.group(1)], t.lower())
