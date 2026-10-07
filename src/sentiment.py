"""Stage 4 - dish-level sentiment with VADER + clause attribution.

A review is split into clauses on contrast markers and sentence punctuation; each
dish inherits the VADER compound score of the clause it appears in, so
"The salad was amazing, but the chicken was cold" gives two different opinions.

When the dish's own clause only names it ("We ordered biryani and kulcha."), the
opinion is read from the next clause instead ("All good."), as long as that clause
is not about a different dish.
"""
import re
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

VADER = SentimentIntensityAnalyzer()
# Food-review words VADER's general lexicon misses.
VADER.lexicon.update({"tasty": 2.0, "yummy": 2.2, "delicious": 2.7, "bland": -1.8, "stale": -2.0,
                      "cold": -1.0, "soggy": -1.8, "oily": -1.5, "greasy": -1.6, "undercooked": -2.0,
                      "overcooked": -1.6, "raw": -1.2, "tasteless": -2.2, "rubbery": -1.8, "worms": -3.0,
                      "hair": -1.5, "spoilt": -2.5, "spoiled": -2.5, "juicy": 1.8,
                      "flavourful": 2.2, "flavorful": 2.2, "crispy": 1.2, "fresh": 1.5, "worst": -3.1,
                      # second pass: words found in dish clauses that were scored as "no opinion"
                      "dry": -1.5, "dried": -1.5, "burnt": -2.0, "burned": -2.0, "uncooked": -2.0,
                      "smelly": -2.0, "chewy": -1.3, "watery": -1.3, "lukewarm": -1.0, "inedible": -2.5,
                      "flavourless": -2.0, "flavorless": -2.0, "mediocre": -1.5, "overpriced": -1.5,
                      "yum": 2.2, "gud": 1.9, "awsm": 2.8, "favourite": 2.0, "favourites": 2.0,
                      "mouthwatering": 2.5, "tender": 1.5, "soft": 1.3, "authentic": 1.5, "decent": 1.2,
                      "addictive": 2.0, "scrumptious": 2.5, "awsome": 2.8, "awesum": 2.8,
                      "salty": -1.3, "salted": -1.0, "sour": -1.3, "smell": -1.0, "smelling": -1.5,
                      "smelled": -1.5, "smelt": -1.5})
# VADER scores one word at a time, so each phrase is joined into one made-up word before scoring.
PHRASES = {
    r"must[- ]tr(?:y|ied)|must[- ]have": ("must_try", 2.0),
    r"(?:do|should|have to|got to|gotta|definitely|please) try": ("do_try", 1.8),
    r"worth (?:a try|trying)": ("worth_trying", 1.8),
    r"(?:was|were|is|are) the stars?\b|star of": ("the_star", 2.5),
    r"out of (?:the|this) world": ("out_of_world", 3.0),
    r"(?:mouth|lip|finger)[- ]?(?:watering|smacking|licking)": ("mouth_watering", 2.5),
    r"value for money|worth (?:the|every) (?:money|penny|rupee)": ("value_for_money", 2.0),
    r"too (?:much |much of )?(?:spicy|salty|sweet|oily|dry|hard|sour|masala|oil|salt)": ("too_much", -1.8),
    r"(?:half|not|not properly|not well|barely) cooked": ("not_cooked", -2.0),
    r"no taste|without (?:any )?taste": ("no_taste", -2.2),
    r"below average|not up ?to the mark": ("below_average", -2.0),
    r"(?:not|wasn'?t|weren'?t|isn'?t) (?:at all |that |so |very |even )?hot": ("not_hot", -1.5),
    # "tastes like plain rice" is a comparison, not liking: score 0 keeps VADER from reading "like" as praise
    r"(?:tast\w*|smell\w*|fe[el]\w*|looks?|looked|seems?|more|just|was|is) like": ("is_like", 0.0),
    # VADER reads "improve" and "better" as praise; in a review they are a complaint
    r"(?:needs?|have|has|should|must|can|could) (?:to )?(?:be )?improved?|needs? improvement"
    r"|could(?:'ve| have)? been better|can be better": ("needs_work", -1.5),
}
for _token, _score in PHRASES.values():
    VADER.lexicon[_token] = _score
PHRASE_RE = [(re.compile(rf"\b(?:{pat})", re.I), tok) for pat, (tok, _) in PHRASES.items()]

POS, NEG = 0.05, -0.05
# A next clause that is only about delivery or service says nothing about the dish.
SERVICE = re.compile(r"\b(?:deliver\w*|service|staff|rider|pack\w*|please|plz|open)\b", re.I)
FOOD = re.compile(r"\b(?:food|meal|dish\w*|tast\w*|flavou?r\w*|quality|quantity|portion\w*|fresh|hot|cold)\b", re.I)
SPLIT = re.compile(r"(?<=[.!?;])\s+|\s+(?=\b(?:but|however|although|though|whereas|except|while)\b)", re.I)


def label(c: float) -> str:
    return "positive" if c >= POS else "negative" if c <= NEG else "neutral"


def score(text: str) -> float:
    for rx, token in PHRASE_RE:
        text = rx.sub(token, text)
    return VADER.polarity_scores(text)["compound"]


def clauses(text: str) -> list[dict]:
    out, pos = [], 0
    for part in SPLIT.split(text):
        if not part.strip():
            continue
        start = text.find(part, pos)
        pos = start + len(part)
        c = score(part)
        out.append({"start": start, "end": pos, "text": part, "compound": round(c, 3), "label": label(c)})
    return out


def review_score(text: str) -> float:
    return score(text)


def about_food(clause: dict) -> bool:
    return not SERVICE.search(clause["text"]) or bool(FOOD.search(clause["text"]))


def attribute(mentions: list[dict], cls: list[dict]) -> list[dict]:
    """Give every dish mention an opinion: its own clause's, or the next clause's
    when its own says nothing and the next one names no dish. `source` records which."""
    def clause_at(pos):
        return next((i for i, c in enumerate(cls) if c["start"] <= pos < c["end"]), None)

    has_dish = {clause_at(m["start"]) for m in mentions}
    for m in mentions:
        i = clause_at(m["start"])
        cl = cls[i] if i is not None else None
        c, source = (cl["compound"] if cl else 0.0), "own"
        if cl and label(c) == "neutral" and i + 1 < len(cls) and i + 1 not in has_dish \
                and cls[i + 1]["label"] != "neutral" and about_food(cls[i + 1]):
            c, source = cls[i + 1]["compound"], "next"
        m["compound"], m["label"], m["source"] = c, label(c), source
        m["clause"] = cl["text"] if cl else ""
    return mentions


def vote(mentions: list[dict]) -> dict:
    """One review's opinion of one dish, given all its mentions of that dish:
    the last mention that takes a side, or the last mention if none does."""
    return next((m for m in reversed(mentions) if m["label"] != "neutral"), mentions[-1])
