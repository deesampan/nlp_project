"""Build a dish gazetteer from the dish_liked column of the full Zomato dump.

dish_liked is restaurant-level weak supervision, not per-review ground truth,
so it is used here only as a vocabulary source for dictionary matching.
"""
import csv
import re
import sys
import collections

from config import ZOMATO_CSV, GAZETTEER, OUT_RESULTS, ensure_dirs

csv.field_size_limit(min(sys.maxsize, 2**31 - 1))

# Terms that appear in dish_liked but are not orderable menu items.
STOP_TERMS = {
    "food", "buffet", "lunch buffet", "dinner buffet", "breakfast buffet",
    "combo", "combos", "meal", "meals", "starters", "main course", "dessert",
    "desserts", "drinks", "beverages", "service", "ambience", "buffet spread",
}

# Bare ingredients and staples. On their own these are not orderable items, so
# attributing sentiment to them is meaningless -- "the chicken was dry" does not
# say which chicken dish. Blocked only as SINGLE words: "chicken biryani" and
# "fried rice" are real dishes and survive, "chicken" and "rice" do not.
GENERIC_SINGLE = {
    "chicken", "mutton", "fish", "beef", "pork", "lamb", "prawn", "prawns",
    "egg", "eggs", "paneer", "tofu", "meat", "seafood", "veg", "veggies",
    "vegetables", "mushroom", "mushrooms", "potato", "potatoes", "onion",
    "tomato", "corn", "cheese", "butter", "cream", "curd", "rice", "gravy",
    "curry", "sauce", "masala", "spice", "spices", "chocolate", "vanilla",
    "strawberry", "mango", "fruit", "salt", "sugar", "oil", "flour",
    "portion", "portions", "quantity", "quality", "taste", "flavour", "flavor",
    "price", "delivery", "packaging", "staff", "ambiance", "place", "menu",
}

# Spelling variants collapse onto a canonical form so counts do not fragment.
VARIANTS = {
    "panneer": "paneer", "paner": "paneer", "panner": "paneer",
    "biriyani": "biryani", "briyani": "biryani", "biryani.": "biryani",
    "chiken": "chicken", "chicke": "chicken",
    "roll": "rolls", "shake": "shakes",
    "mojito": "mojitos", "cocktail": "cocktails", "mocktail": "mocktails",
    "sandwich": "sandwiches", "burger": "burgers", "noodle": "noodles",
}

_punct = re.compile(r"[^a-z0-9\s&'-]")
_ws = re.compile(r"\s+")


def normalise(term: str) -> str:
    t = term.lower().strip()
    t = _punct.sub(" ", t)
    t = _ws.sub(" ", t).strip()
    if not t:
        return ""
    words = [VARIANTS.get(w, w) for w in t.split()]
    return " ".join(words)


def main():
    ensure_dirs()
    counts = collections.Counter()
    restaurants = collections.defaultdict(set)
    seen_rows = set()

    with open(ZOMATO_CSV, "r", encoding="utf-8", errors="replace", newline="") as f:
        for row in csv.DictReader(f):
            key = ((row.get("name") or "").strip().lower(),
                   (row.get("address") or "").strip().lower())
            raw = (row.get("dish_liked") or "").strip()
            if not raw:
                continue
            for part in raw.split(","):
                term = normalise(part)
                if not term or term in STOP_TERMS:
                    continue
                if len(term) < 3 or term.isdigit():
                    continue
                if len(term.split()) > 4:
                    continue
                if " " not in term and term in GENERIC_SINGLE:
                    continue
                if (key, term) in seen_rows:
                    continue
                seen_rows.add((key, term))
                counts[term] += 1
                restaurants[term].add(key)

    rows = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    with open(GAZETTEER, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["dish", "n_words", "restaurant_count"])
        for term, c in rows:
            w.writerow([term, len(term.split()), c])

    with open(OUT_RESULTS / "gazetteer_summary.txt", "w", encoding="utf-8") as f:
        f.write("distinct dish terms: %d\n" % len(rows))
        by_len = collections.Counter(len(t.split()) for t, _ in rows)
        for k in sorted(by_len):
            f.write("  %d-word terms: %d\n" % (k, by_len[k]))
        f.write("\ntop 30 by restaurant count:\n")
        for term, c in rows[:30]:
            f.write("  %-28s %5d\n" % (term, c))

    print("gazetteer terms: %d" % len(rows))
    print("written to: %s" % GAZETTEER)
    print("top 15: %s" % ", ".join(t for t, _ in rows[:15]))


if __name__ == "__main__":
    main()
