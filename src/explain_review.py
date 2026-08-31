"""Trace one review through the whole pipeline and print what happens at each step.

Answers "why did / didn't this review affect the dashboard?".

    ../.venv/Scripts/python explain_review.py "the biryani was great but the naan was cold"
    ../.venv/Scripts/python explain_review.py --find "Goff"
"""
import csv
import sys
import pickle

import spacy
from spacy.matcher import PhraseMatcher

from config import TOP3_REVIEWS, GAZETTEER, OUT, MIN_MENTIONS
from build_corpus import structural_clean, normalise, label_of
from build_slice import (split_clauses, longest_non_overlapping,
                         normalise_for_match, MIN_CHARS)

csv.field_size_limit(min(sys.maxsize, 2**31 - 1))


def load():
    with open(GAZETTEER, "r", encoding="utf-8", newline="") as f:
        terms = [r["dish"] for r in csv.DictReader(f)]
    with open(OUT / "models" / "sentiment_tfidf_lr.pkl", "rb") as f:
        b = pickle.load(f)
    nlp = spacy.load("en_core_web_sm")
    m = PhraseMatcher(nlp.vocab, attr="LOWER")
    m.add("DISH", list(nlp.tokenizer.pipe(terms)))
    return nlp, m, {nlp.vocab.strings[t]: t for t in terms}, b, set(terms)


def find_in_csv(needle):
    for r in csv.DictReader(open(TOP3_REVIEWS, encoding="utf-8", newline="")):
        if needle.lower() in r["review_text"].lower():
            return r
    return None


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return
    rating = None
    if args[0] == "--find":
        row = find_in_csv(" ".join(args[1:]))
        if not row:
            print("no review found containing that text")
            return
        text = row["review_text"]
        rating = float(row["review_rating"]) if row["review_rating"] else None
        print("found in %s" % TOP3_REVIEWS.name)
        print("restaurant : %s" % row["restaurant_name"])
        print("star rating: %s" % row["review_rating"])
    else:
        text = " ".join(args)

    nlp, matcher, by_hash, bundle, gaz = load()
    vec, clf = bundle["vectorizer"], bundle["classifier"]

    print("\n" + "=" * 66)
    print("RAW           : %r" % text[:200])

    clean = structural_clean(text)
    print("AFTER CLEANING: %r" % clean[:200])

    print("\nSTEP 1  length filter (must be >= %d characters)" % MIN_CHARS)
    if len(clean) < MIN_CHARS:
        print("  %d chars -> DROPPED. Stops here, appears nowhere." % len(clean))
        return
    print("  %d chars -> kept" % len(clean))

    if rating is not None:
        print("\nSTEP 2  restaurant-level sentiment (from the star rating)")
        print("  %.1f stars -> %s" % (rating, label_of(rating)))
        print("  This ALWAYS counts toward the restaurant's overall bar,")
        print("  whether or not the review names a dish.")

    doc = nlp(clean)
    clauses = split_clauses(doc)
    print("\nSTEP 3  split into clauses (at sentences, and at but/however/although)")
    for c in clauses:
        print("  - %r" % c[:120])

    print("\nSTEP 4  look for dish names in each clause")
    any_dish = False
    for c in clauses:
        cdoc = nlp.tokenizer(normalise_for_match(c))
        found = longest_non_overlapping(matcher(cdoc))
        dishes = sorted({by_hash.get(cdoc[s:e].text) or cdoc[s:e].text.lower()
                         for _, s, e in found})
        if dishes:
            any_dish = True
            pred = clf.predict(vec.transform([normalise(c)]))[0]
            print("  clause : %r" % c[:100])
            print("    dishes found : %s" % ", ".join(dishes))
            print("    model says   : %s" % pred.upper())
            print("    -> counts toward %s" % ", ".join(dishes))
        else:
            print("  clause : %r" % c[:100])
            print("    dishes found : NONE")
            print("    -> not classified, does not appear in any dish panel")

    print("\n" + "=" * 66)
    if any_dish:
        print("RESULT: this review affects the dish ratings above.")
        print("Note: a dish still needs >= %d total comments to be listed." % MIN_MENTIONS)
    else:
        print("RESULT: no dish name found, so this review affects ONLY the")
        print("restaurant's overall sentiment, not any individual dish.")
        print("\nWhy: the words in it are not in the %d-term dish dictionary." % len(gaz))
        print("This is intentional. A comment about delivery or service is not")
        print("evidence about a dish, so it is routed to the restaurant panel")
        print("instead of being deleted or wrongly attributed.")


if __name__ == "__main__":
    main()
