"""Stage 4 - dish-level sentiment with our trained model + clause attribution.

The model is the TF-IDF + logistic regression classifier from train_sentiment.py,
trained on Zomato reviews labelled by their star rating (the website's own
restaurants are held out of training). A review is split into clauses on contrast
markers and sentence punctuation; the model labels each clause positive, neutral or
negative, and each dish inherits the label of the clause it appears in, so
"The salad was amazing, but the chicken was cold" gives two different opinions.

When the dish's own clause says nothing but the dish ("We ordered biryani and kulcha."),
the opinion is read from the next clause instead ("All good."), as long as that clause
is not about a different dish.
"""
import pickle
import re
from .common import OUT, normalise

with open(OUT / "models" / "sentiment_tfidf_lr.pkl", "rb") as f:
    MODEL = pickle.load(f)
VEC, CLF = MODEL["vectorizer"], MODEL["classifier"]
POS_COL = list(CLF.classes_).index("positive")
NEG_COL = list(CLF.classes_).index("negative")

# A next clause that is only about delivery or service says nothing about the dish.
SERVICE = re.compile(r"\b(?:deliver\w*|service|staff|rider|pack\w*|please|plz|open)\b", re.I)
FOOD = re.compile(r"\b(?:food|meal|dish\w*|tast\w*|flavou?r\w*|quality|quantity|portion\w*|fresh|hot|cold)\b", re.I)
SPLIT = re.compile(r"(?<=[.!?;])\s+|\s+(?=\b(?:but|however|although|though|whereas|except|while)\b)", re.I)
# Hidden from the model before it reads a clause, so it judges what is said about a dish:
#  - a leading "but": the model learned it as a sign of a mixed 3-star review
#  - the dish names: "veg biryani" carries the reputation it has across all of Bangalore
#  - words about ordering: complaints often start "I ordered ...", so the model learned
#    "ordered" as a negative word, and "I ordered veg biryani." would count as a complaint
LEAD = re.compile(r"^(?:but|however|although|though|whereas|except|while)\b[\s,]*", re.I)
ORDERING = re.compile(r"\b(?:order|orders|ordered|ordering|tried|got)\b", re.I)
# A clause is shorter than the reviews the model learned from, so it takes a side only when
# the model is clearly on it: P(positive) - P(negative) at least 0.4 either way. Checked
# against star ratings on the website's reviews, this cuts dishes "liked" in 1-star reviews
# or "disliked" in 5-star ones from 52 to 21. Whole reviews use the model's answer as is.
CLAUSE_MARGIN = 0.4


def classify(texts: list[str]) -> list[tuple[str, float, bool]]:
    """The model's label for each text, a score from -1 to +1 (P(positive) - P(negative),
    so +0.9 means "surely positive"), and whether the text held any word the model knows.
    A text with no such word has no opinion."""
    if not texts:
        return []
    X = VEC.transform([normalise(t) for t in texts])
    proba = CLF.predict_proba(X)
    out = []
    for p, known in zip(proba, X.getnnz(axis=1)):
        if not known:
            out.append(("neutral", 0.0, False))
            continue
        if MODEL["mode"] == "binary_band":   # two-class model: unsure in the middle = neutral
            band = MODEL["band"]
            lab = "positive" if p[POS_COL] >= band["band_high"] else \
                  "negative" if p[POS_COL] <= band["band_low"] else "neutral"
        else:
            lab = CLF.classes_[p.argmax()]
        out.append((str(lab), round(float(p[POS_COL] - p[NEG_COL]), 3), True))
    return out


def clauses(text: str, mentions: list[dict]) -> list[dict]:
    out, pos = [], 0
    for part in SPLIT.split(text):
        if not part.strip():
            continue
        start = text.find(part, pos)
        pos = start + len(part)
        out.append({"start": start, "end": pos, "text": part})
    hidden = list(text)
    for m in mentions:
        hidden[m["start"]:m["end"]] = " " * (m["end"] - m["start"])
    hidden = "".join(hidden)
    seen = [ORDERING.sub(" ", LEAD.sub("", hidden[c["start"]:c["end"]].strip())) for c in out]
    for c, (_, score, known) in zip(out, classify(seen)):
        c["label"] = "positive" if score >= CLAUSE_MARGIN else "negative" if score <= -CLAUSE_MARGIN else "neutral"
        c["score"], c["says_something"] = score, known
    return out


def review(text: str) -> tuple[str, float]:
    """The whole review's label and score."""
    return classify([text])[0][:2]


def about_food(clause: dict) -> bool:
    return not SERVICE.search(clause["text"]) or bool(FOOD.search(clause["text"]))


def attribute(mentions: list[dict], cls: list[dict]) -> list[dict]:
    """Give every dish mention an opinion: its own clause's, or the next clause's
    when its own says nothing at all (only the dish name, "I ordered ...") and the next
    one names no dish. A clause the model reads as neutral ("it was ok") did say
    something, so it keeps its own opinion. `source` records which."""
    def clause_at(pos):
        return next((i for i, c in enumerate(cls) if c["start"] <= pos < c["end"]), None)

    has_dish = {clause_at(m["start"]) for m in mentions}
    for m in mentions:
        i = clause_at(m["start"])
        cl = cls[i] if i is not None else {"label": "neutral", "score": 0.0, "text": "", "says_something": False}
        pick, source = cl, "own"
        if i is not None and not cl["says_something"] and i + 1 < len(cls) and i + 1 not in has_dish \
                and cls[i + 1]["label"] != "neutral" and about_food(cls[i + 1]):
            pick, source = cls[i + 1], "next"
        m["label"], m["score"], m["source"] = pick["label"], pick["score"], source
        m["clause"] = cl["text"]
    return mentions


def vote(mentions: list[dict]) -> dict:
    """One review's opinion of one dish, given all its mentions of that dish:
    the last mention that takes a side, or the last mention if none does."""
    return next((m for m in reversed(mentions) if m["label"] != "neutral"), mentions[-1])
