"""ResRec: turn restaurant reviews into a "which dishes are good?" website.

    python src/run_pipeline.py

Six stages, one section each below:
  1. Load     the reviews and the restaurants' menus         (output_project/data/)
  2. Clean    fix the text, then drop noise reviews N1-N4
  3. Dishes   find the menu items each review mentions
  4. Opinion  split each review into clauses; our trained model reads each clause
  5. Count    per dish: how many reviews liked it, how many did not
  6. Export   everything the page needs -> output_project/web/data.js

The sentiment model itself is trained by src/train_model.py.
"""
import csv
import json
import pickle
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

from rapidfuzz import fuzz

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "output_project" / "data"
MODEL_FILE = ROOT / "output_project" / "models" / "sentiment_tfidf_lr.pkl"
WEB = ROOT / "output_project" / "web"

# ---- settings: every number you may want to change ------------------------------------
MIN_OPINIONS = 4                    # a dish is ranked once this many reviews take a side on it
LOVE_IT = 0.80                      # 8 in 10 or more liked it  -> "Customers love it"
MIXED_LOW, MIXED_HIGH = 0.40, 0.60  # about half liked it       -> "Mixed opinions" (40% or less: "Needs work")
CLAUSE_MARGIN = 0.4                 # a clause takes a side only if P(positive) - P(negative) is +-0.4 or more
FUZZ_MIN = 88                       # spelling similarity (0-100) for long words to count as the same word
MIN_LATIN = 0.7                     # a review needs 70% Latin letters to count as English


# =========================================================================================
# 1. LOAD
# =========================================================================================
def load():
    with open(DATA / "site_reviews.csv", encoding="utf-8", newline="") as f:
        reviews = [{"id": i, "restaurant": r["restaurant"], "rating": float(r["rating"]),
                    # git on Windows may turn \n into \r\n inside the file; undo it
                    "raw": r["text"].replace("\r\n", "\n")}
                   for i, r in enumerate(csv.DictReader(f))]
    restaurants = json.loads((DATA / "site_restaurants.json").read_text(encoding="utf-8"))
    return reviews, restaurants


# =========================================================================================
# 2. CLEAN
# =========================================================================================
# Broken characters from text decoded 2-3 times (Ã\x83Ã\x82...). Between two letters it was an apostrophe.
MOJIBAKE = re.compile(r"(?<=[A-Za-z])([ÃÂ\x80-\xff]+)(?=[a-z]\b)|[ÃÂ\x80-\xff]+")


def clean_text(raw):
    t = re.sub(r"^\s*RATED\s*", "", raw)                       # Zomato's "RATED" prefix
    t = MOJIBAKE.sub(lambda m: "'" if m.group(1) else " ", t)  # broken characters
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode()  # emoji, accents
    t = re.sub(r"https?://\S+|www\.\S+", " ", t)               # links
    t = re.sub(r"([!?.])\1+", r"\1", t)                        # "!!!" -> "!"
    t = re.sub(r"(\w)\1{2,}", r"\1\1", t)                      # "soooo" -> "soo"
    t = re.sub(r"\s*\n+\s*", " ", t)                           # line breaks
    t = re.sub(r"(?<=[a-z])([.,!?])(?=[A-Za-z])", r"\1 ", t)   # "food.even" -> "food. even"
    t = re.sub(r"\s+([.,!?])", r"\1", t)                       # "combo ," -> "combo,"
    return re.sub(r"\s+", " ", t).strip()


def latin_share(raw):
    s = re.sub(r"\s", "", MOJIBAKE.sub("", raw))
    return sum(c.isascii() for c in s) / max(len(s), 1)


def remove_noise(reviews):
    """Clean every review, then apply the four noise rules in order.
    Returns the kept reviews and the removed ones (each with its reason)."""
    for r in reviews:
        r["text"] = clean_text(r["raw"])
    seen = set()

    def first_copy(r):
        key = (r["restaurant"], r["text"])
        new = key not in seen
        seen.add(key)
        return new

    rules = [("N1", "Empty", lambda r: r["text"] != ""),
             ("N2", "Duplicate", first_copy),
             ("N3", "Too short", lambda r: len(r["text"].split()) >= 2),
             ("N4", "Not English", lambda r: latin_share(r["raw"]) >= MIN_LATIN)]
    removed = []
    print(f"   {'Reviews loaded':<14}       {len(reviews)}")
    for code, reason, ok in rules:
        kept = []
        for r in reviews:
            if ok(r):
                kept.append(r)
            else:
                removed.append({**r, "reason": reason})
        print(f"{code} {reason:<14} -{len(reviews) - len(kept):<4} -> {len(kept)}")
        reviews = kept
    return reviews, removed


# =========================================================================================
# 3. DISHES
# =========================================================================================
# Spellings seen in the reviews -> one form, used on both the menu and the review side.
SPELLING = {
    "biriyani": "biryani", "briyani": "biryani", "biriani": "biryani", "biryanis": "biryani",
    "birayani": "biryani", "briyani's": "biryani", "biryaani": "biryani",
    "kabab": "kebab", "kababs": "kebab", "kebabs": "kebab", "kabob": "kebab",
    "jamoon": "jamun", "jamuns": "jamun", "jamoons": "jamun",
    "makhani": "makhni", "makhanwala": "makhni", "chilli": "chilly", "chili": "chilly",
    "panneer": "paneer", "panner": "paneer",
    "lollipop": "lollypop", "lollypops": "lollypop", "lollipops": "lollypop", "manchuri": "manchurian",
    "nan": "naan", "rotis": "roti", "parathas": "paratha", "paratas": "paratha", "parotta": "paratha",
    "brownies": "brownie", "salads": "salad", "wraps": "wrap", "sandwiches": "sandwich",
    "noodle": "noodles", "ricebox": "rice box",
}
# Dishes people name without the menu's exact wording.
COMMON_DISHES = ["Biryani", "Chicken Biryani", "Kebab", "Fried Rice", "Noodles", "Paratha", "Brownie", "Salad",
                 "Gulab Jamun", "Naan", "Roti", "Paneer", "Wrap", "Sandwich", "Raita", "Dal", "Rajma",
                 "Tandoori Chicken", "Chicken Kebab", "Butter Chicken"]


def words(text):
    """Lower-case words with spellings unified: "Biriyani Kababs" -> ["biryani", "kebab"]."""
    return [SPELLING.get(w, w) for w in re.findall(r"[a-z0-9]+(?:'[a-z]+)?", text.lower())]


def dish_list(restaurant):
    """The restaurant's dish dictionary: word tuple -> display name."""
    found = {}
    for item in restaurant["menu"] + restaurant["dish_liked"] + COMMON_DISHES:
        if re.search(r"combo|water|coke|sprite|pepsi", item, re.I):
            continue
        name = item.split()
        while len(name) > 1 and name[-1].lower() in {"meal", "box"}:   # "Chicken Biryani Meal" -> "Chicken Biryani"
            name = name[:-1]
        name = " ".join(w.capitalize() if w.islower() else w for w in name)
        found.setdefault(tuple(words(name)), name)
    found.pop((), None)
    return found


def same_word(a, b):
    """Exact match, or for words of 6+ letters a near match ("biryanni" ~ "biryani")."""
    return a == b or (len(a) >= 6 and len(b) >= 6 and fuzz.ratio(a, b) >= FUZZ_MIN)


def find_dishes(text, dishes, restaurant_name):
    """Every dish mention in the text, with its character position. Longest name wins."""
    spans = [(m.start(), m.end(), SPELLING.get(m.group().lower(), m.group().lower()))
             for m in re.finditer(r"[A-Za-z0-9]+(?:'[a-z]+)?", text)]
    toks = [s[2] for s in spans]
    used = [False] * len(toks)
    own = tuple(words(re.sub(r"[-\d]+", " ", restaurant_name)))   # "Biriyani Nights" is the venue, not a dish
    if len(own) > 1:
        for i in range(len(toks) - len(own) + 1):
            if all(same_word(toks[i + j], own[j]) for j in range(len(own))):
                used[i:i + len(own)] = [True] * len(own)
    found = []
    longest_first = sorted(dishes, key=len, reverse=True)
    for i in range(len(toks)):
        for key in longest_first:
            n = len(key)
            if not used[i] and i + n <= len(toks) and not any(used[i:i + n]) \
                    and all(same_word(toks[i + j], key[j]) for j in range(n)):
                used[i:i + n] = [True] * n
                found.append({"dish": dishes[key], "start": spans[i][0], "end": spans[i + n - 1][1]})
                break
    return found


# =========================================================================================
# 4. OPINION
# =========================================================================================
# The model was trained on text passed through normalise(), so everything it reads goes through it too.
CONTRACTIONS = {
    "don't": "do not", "doesn't": "does not", "didn't": "did not", "isn't": "is not", "wasn't": "was not",
    "aren't": "are not", "weren't": "were not", "won't": "will not", "wouldn't": "would not",
    "can't": "cannot", "couldn't": "could not", "shouldn't": "should not", "haven't": "have not",
    "hasn't": "has not", "hadn't": "had not", "it's": "it is", "that's": "that is", "there's": "there is",
    "i'm": "i am", "i've": "i have", "we've": "we have", "they're": "they are",
}
CONTRACTION_RE = re.compile(r"\b(" + "|".join(map(re.escape, CONTRACTIONS)) + r")\b")


def normalise(t):
    """Lower-case, "soooo" -> "soo", "wasn't" -> "was not"."""
    t = re.sub(r"(.)\1{2,}", r"\1\1", t).lower()
    return CONTRACTION_RE.sub(lambda m: CONTRACTIONS[m.group(1)], t)


SPLIT = re.compile(r"(?<=[.!?;])\s+|\s+(?=\b(?:but|however|although|though|whereas|except|while)\b)", re.I)
# Hidden from the model before it reads a clause, so it judges what is said about the dish:
LEADING_BUT = re.compile(r"^(?:but|however|although|though|whereas|except|while)\b[\s,]*", re.I)  # reads as "mixed review"
ORDERING = re.compile(r"\b(?:order|orders|ordered|ordering|tried|got)\b", re.I)  # "I ordered..." reads as a complaint
# A next clause about delivery or service says nothing about the dish.
SERVICE = re.compile(r"\b(?:deliver\w*|service|staff|rider|pack\w*|please|plz|open)\b", re.I)
FOOD = re.compile(r"\b(?:food|meal|dish\w*|tast\w*|flavou?r\w*|quality|quantity|portion\w*|fresh|hot|cold)\b", re.I)


def load_model():
    with open(MODEL_FILE, "rb") as f:
        m = pickle.load(f)
    return m["vectorizer"], m["classifier"]


def classify(model, texts):
    """For each text: the model's label, a score from -1 to +1 (P(positive) - P(negative)),
    and whether the text held any word the model knows (if not, it has no opinion)."""
    vec, clf = model
    if not texts:
        return []
    X = vec.transform([normalise(t) for t in texts])
    pos, neg = list(clf.classes_).index("positive"), list(clf.classes_).index("negative")
    out = []
    for p, known in zip(clf.predict_proba(X), X.getnnz(axis=1)):
        out.append((str(clf.classes_[p.argmax()]), round(float(p[pos] - p[neg]), 3), True) if known
                   else ("neutral", 0.0, False))
    return out


def clauses(model, text, mentions):
    """Split the review into clauses and label each one positive / negative / neutral."""
    out, pos = [], 0
    for part in SPLIT.split(text):
        if part.strip():
            start = text.find(part, pos)
            pos = start + len(part)
            out.append({"start": start, "end": pos, "text": part})
    hidden = list(text)
    for m in mentions:                                     # hide the dish names
        hidden[m["start"]:m["end"]] = " " * (m["end"] - m["start"])
    hidden = "".join(hidden)
    seen = [ORDERING.sub(" ", LEADING_BUT.sub("", hidden[c["start"]:c["end"]].strip())) for c in out]
    for c, (_, score, known) in zip(out, classify(model, seen)):
        c["label"] = "positive" if score >= CLAUSE_MARGIN else "negative" if score <= -CLAUSE_MARGIN else "neutral"
        c["says_something"] = known
    return out


def attribute(mentions, cls):
    """Each dish mention takes the label of its own clause. If its clause says nothing but the
    dish ("We ordered biryani."), it takes the next clause's label ("All good."), as long as
    that clause names no other dish and is about the food."""
    def clause_at(pos):
        return next((i for i, c in enumerate(cls) if c["start"] <= pos < c["end"]), None)

    with_dish = {clause_at(m["start"]) for m in mentions}
    for m in mentions:
        i = clause_at(m["start"])
        label = cls[i]["label"] if i is not None else "neutral"
        if i is not None and not cls[i]["says_something"] and i + 1 < len(cls) and i + 1 not in with_dish:
            nxt = cls[i + 1]
            if nxt["label"] != "neutral" and (not SERVICE.search(nxt["text"]) or FOOD.search(nxt["text"])):
                label = nxt["label"]
        m["label"] = label
    return mentions


# =========================================================================================
# 5. COUNT
# =========================================================================================
def vote(mentions):
    """One review's opinion of one dish: its last mention that takes a side."""
    return next((m["label"] for m in reversed(mentions) if m["label"] != "neutral"), "neutral")


def tag(d):
    if d["opinions"] < MIN_OPINIONS:
        return "low-data"
    share = d["positive"] / d["opinions"]
    if share >= LOVE_IT:
        return "signature"
    if share <= MIXED_LOW:
        return "needs-improvement"
    return "polarising" if share < MIXED_HIGH else "steady"


def count_dishes(reviews):
    """Per (restaurant, dish): one vote per review. Reviews that name the dish without taking
    a side are kept out of the counts."""
    acc = defaultdict(lambda: {"positive": 0, "negative": 0, "neutral": 0, "review_ids": []})
    for r in reviews:
        by_dish = defaultdict(list)
        for m in r["dishes"]:
            by_dish[m["dish"]].append(m)
        for dish, ms in by_dish.items():
            a = acc[(r["restaurant"], dish)]
            a[vote(ms)] += 1
            a["review_ids"].append(r["id"])
    out = []
    for (rest, dish), a in acc.items():
        d = {"restaurant": rest, "dish": dish, "positive": a["positive"], "negative": a["negative"],
             "opinions": a["positive"] + a["negative"], "review_ids": a["review_ids"]}
        d["category"] = tag(d)
        out.append(d)
    return sorted(out, key=lambda d: (-d["opinions"], -d["positive"] / max(d["opinions"], 1), d["dish"]))


def star_check(reviews):
    """How often the model's whole-review label agrees with the star rating
    (4-5 stars = positive, 1-2 = negative, 3 left out). Fair because these restaurants
    were held out of training."""
    pairs = [(r["rating"] >= 4, r["sentiment"] == "positive") for r in reviews if not 2 < r["rating"] < 4]
    right = sum(star == said for star, said in pairs)
    return f"model agrees with the stars on {right} of {len(pairs)} reviews ({right / len(pairs):.1%})"


# =========================================================================================
# 6. EXPORT
# =========================================================================================
def dish_photos(dish_names):
    """Match the photos in web/img to dishes by their words: biryani_veg.webp -> "Veg Biryani"."""
    photos = {frozenset(words(p.stem.replace("_", " "))): f"img/{p.name}" for p in sorted((WEB / "img").glob("*.webp"))}
    return {n: photos[frozenset(words(n))] for n in sorted(dish_names) if frozenset(words(n)) in photos}


def export(restaurants, reviews, removed, dishes):
    def shown(r):   # what the page shows for a removed review
        if r["text"]:
            return r["text"], False
        return ("Only emoji or broken characters" if re.sub(r"^\s*RATED\s*", "", r["raw"]).strip() else "No text"), True

    data = {
        "restaurants": [{**{k: r[k] for k in ("name", "location", "type", "cuisines", "cost_for_two", "zomato_rate")},
                         "reviews": sum(x["restaurant"] == r["name"] for x in reviews),
                         "positive_reviews": sum(x["restaurant"] == r["name"] and x["sentiment"] == "positive"
                                                 for x in reviews)}
                        for r in sorted(restaurants, key=lambda r: r["rank"])],
        "dishes": dishes,
        "reviews": [{"id": r["id"], "rating": r["rating"], "text": r["text"],
                     "dishes": [{k: m[k] for k in ("dish", "start", "end", "label")} for m in r["dishes"]]}
                    for r in reviews if r["dishes"]],
        "removed": [{"restaurant": r["restaurant"], "rating": r["rating"], "reason": r["reason"],
                     "text": shown(r)[0], "note": shown(r)[1]} for r in removed],
        "photos": dish_photos({d["dish"] for d in dishes}),
        "min_opinions": MIN_OPINIONS,
    }
    (WEB / "data.js").write_text("window.DATA = " + json.dumps(data, ensure_ascii=False, separators=(",", ":"))
                                 + ";\n", encoding="utf-8")


# =========================================================================================
def main():
    reviews, restaurants = load()                                       # 1
    reviews, removed = remove_noise(reviews)                            # 2
    model = load_model()
    dish_lists = {r["name"]: dish_list(r) for r in restaurants}
    for r in reviews:
        mentions = find_dishes(r["text"], dish_lists[r["restaurant"]], r["restaurant"])   # 3
        r["dishes"] = attribute(mentions, clauses(model, r["text"], mentions))            # 4
        r["sentiment"] = classify(model, [r["text"]])[0][0]
    dishes = count_dishes(reviews)                                      # 5
    export(restaurants, reviews, removed, dishes)                       # 6

    print(f"\nreviews naming a dish: {sum(bool(r['dishes']) for r in reviews)} / {len(reviews)}")
    print(star_check(reviews))
    for d in dishes[:10]:
        print(f"  {d['restaurant'][:16]:<16} {d['dish']:<22} liked {d['positive']}/{d['opinions']}  {d['category']}")
    print("wrote", WEB / "data.js")


if __name__ == "__main__":
    main()
