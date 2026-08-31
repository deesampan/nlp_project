"""The analysis engine, shared by the batch pipeline and the upload endpoint.

There is exactly one implementation of "turn reviews into dish ratings". Both
build_slice.py (the three built-in restaurants) and app.py (a CSV the user
uploads live) call into here, so the two can never drift apart.

Input to analyse_restaurant() is a plain list of dicts:

    [{"text": "the biryani was great but the naan was cold", "rating": 5.0}, ...]

"rating" is optional. When it is missing -- which is the case for an uploaded
text-only CSV -- the model classifies whole reviews to produce the restaurant's
overall sentiment, instead of reading it off star ratings. That makes an
uploaded restaurant a purer demonstration: every number on the page is model
output, with no star ratings helping.
"""
import csv
import collections
import hashlib
import pickle
import re
import sys
import unicodedata

import spacy
from spacy.matcher import PhraseMatcher

from config import GAZETTEER, OUT, MIN_MENTIONS, DROPPED_SAMPLE
from build_gazetteer import VARIANTS, GENERIC_SINGLE
from build_corpus import structural_clean, normalise, label_of

# Never a dish, however it is phrased. "the whole plate" is judged on its head
# word, "plate", so it is caught here too.
STOP_SUBJECTS = {
    "food", "order", "restaurant", "place", "menu", "bite", "plate", "bowl",
    "problem", "diet", "mom", "dad", "friend", "family", "people", "everyone",
    "everybody", "someone", "somebody", "whoever", "everything", "anything",
    "nothing", "thing", "one", "lot", "time", "day", "night", "week", "money",
    "waiter", "waitress", "owner", "guy", "girl", "man", "woman", "kid",
    "review", "self", "control", "civilization", "holiday", "theory", "therapy",
    "price", "service", "delivery", "staff", "quality", "quantity", "portion",
    "taste", "flavour", "flavor", "packaging", "stick", "sugar",
}
# Bare ingredients: not dishes on their own, but fine inside a longer name.
# "rice" is generic, "mango sticky rice" is a dish -- same rule the gazetteer uses.
SOFT_STOP = set(GENERIC_SINGLE)
# Deliberately NOT filtering by spaCy entity type. Its NER is trained on English
# news, so unfamiliar food words get labelled as people and places: "Khao" is
# tagged PERSON, "Tom" (of tom yum) PERSON, "Mango" LOC, "Pudthai" GPE. Filtering
# on entity type therefore deletes precisely the dishes we are trying to find.
# A short list of actual place words is cheaper and safer.
STOP_PLACES = {"thailand", "india", "china", "japan", "korea", "america",
               "bangkok", "delhi", "mumbai", "bangalore", "london", "zomato",
               "swiggy", "google", "uber"}
_leading_det = re.compile(r"^(the|a|an|my|our|this|that|their|his|her|its|your)\s+")
_letters_only = re.compile(r"^[a-z][a-z' -]*[a-z]$")

csv.field_size_limit(min(sys.maxsize, 2**31 - 1))

MODEL_PKL = OUT / "models" / "sentiment_tfidf_lr.pkl"
MIN_CHARS = 20
MIN_CLAUSE_CHARS = 12

_word = re.compile(r"[a-z']+")
_contrast = re.compile(r"\b(but|however|although|though|whereas|yet)\b", re.I)


def slugify(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower() or "restaurant"


def normalise_for_match(t):
    return _word.sub(lambda m: VARIANTS.get(m.group(0), m.group(0)), t.lower())


def longest_non_overlapping(matches):
    """Prefer 'chicken biryani' over 'biryani' when both match the same span."""
    matches = sorted(matches, key=lambda m: (-(m[2] - m[1]), m[1]))
    taken, out = [], []
    for mid, start, end in matches:
        if any(start < e and end > s for s, e in taken):
            continue
        taken.append((start, end))
        out.append((mid, start, end))
    return out


class Analyzer:
    """Loads the model, spaCy and the dish dictionary once, then reuses them."""

    def __init__(self):
        with open(MODEL_PKL, "rb") as f:
            bundle = pickle.load(f)
        self.vec = bundle["vectorizer"]
        self.clf = bundle["classifier"]
        self.mode = bundle.get("mode", "three_class")
        self.band = bundle.get("band") or {}

        self.nlp = spacy.load("en_core_web_sm")
        with open(GAZETTEER, "r", encoding="utf-8", newline="") as f:
            self.terms = [r["dish"] for r in csv.DictReader(f)]
        self.matcher = PhraseMatcher(self.nlp.vocab, attr="LOWER")
        self.matcher.add("DISH", list(self.nlp.tokenizer.pipe(self.terms)))
        self.term_by_hash = {self.nlp.vocab.strings[t]: t for t in self.terms}
        self.term_set = set(self.terms)

    # ---------------------------------------------------------------- model
    def predict(self, texts):
        """The shipped model may be binary with an uncertainty band, in which
        case 'neutral' means the classifier was not confident either way."""
        if not texts:
            return []
        Xv = self.vec.transform(texts)
        if self.mode != "binary_band":
            return list(self.clf.predict(Xv))
        lo, hi = self.band["band_low"], self.band["band_high"]
        pi = list(self.clf.classes_).index("positive")
        return ["positive" if r[pi] >= hi else "negative" if r[pi] <= lo else "neutral"
                for r in self.clf.predict_proba(Xv)]

    def split_clauses(self, doc):
        """Sentence split, then split again on contrastive conjunctions."""
        out = []
        for sent in doc.sents:
            text = sent.text.strip()
            if not text:
                continue
            parts, last = [], 0
            for m in _contrast.finditer(text):
                seg = text[last:m.start()].strip()
                if seg:
                    parts.append(seg)
                last = m.end()
            tail = text[last:].strip()
            if tail:
                parts.append(tail)
            out.extend(parts if parts else [text])
        return [p for p in out if len(p) >= MIN_CLAUSE_CHARS]

    def dishes_in(self, clause, extra=None):
        """Dish names in this clause. `extra` is an optional (matcher, by_hash)
        pair holding names discovered from the current file."""
        cdoc = self.nlp.tokenizer(normalise_for_match(clause))
        matches = list(self.matcher(cdoc))
        lookup = dict(self.term_by_hash)
        if extra:
            matches += list(extra[0](cdoc))
            lookup.update(extra[1])
        found = longest_non_overlapping(matches)
        return {lookup.get(cdoc[s:e].text) or cdoc[s:e].text.lower()
                for _, s, e in found}

    # ------------------------------------------------------- discovery
    def discover_dishes(self, docs):
        """Learn dish names from the text itself.

        The dish dictionary is built from the Zomato dataset, so it only knows
        Indian food. For an uploaded file of, say, Thai reviews it matches
        almost nothing. The rule used here is simple enough to say out loud:
        *a dish is usually the subject of the sentence* -- "khao mun kai is too
        good", "the naan was cold". So we take subject noun phrases, throw away
        pronouns, place names and generic words, and treat what is left as
        candidate dish names.
        """
        cand = collections.Counter()
        for doc in docs:
            for chunk in doc.noun_chunks:
                if chunk.root.dep_ not in ("nsubj", "nsubjpass"):
                    continue
                if chunk.root.pos_ not in ("NOUN", "PROPN"):
                    continue
                # judge on the head noun: "the whole plate" -> "plate"
                head = chunk.root.lemma_.lower()
                if head in STOP_SUBJECTS or head in STOP_PLACES:
                    continue
                name = _leading_det.sub("", chunk.text.lower().strip())
                name = re.sub(r"\s+", " ", name).strip(" .,!?'\"")
                words = name.split()
                if not (3 <= len(name) <= 30) or len(words) > 4:
                    continue
                if not _letters_only.match(name):
                    continue
                if name in STOP_SUBJECTS or name in STOP_PLACES:
                    continue
                if len(words) == 1 and name in SOFT_STOP:
                    continue          # bare ingredient on its own
                if name in self.term_set:
                    continue          # already a known dish, the matcher has it
                cand[name] += 1
        return cand

    @staticmethod
    def merge_aliases(names):
        """Map shorter names onto longer ones that contain them.

        'khao man' -> 'khao man gai'. Containment only: a fuzzy similarity score
        cannot be used here because 'green curry' vs 'red curry' scores exactly
        as high as 'pudthai' vs 'pad thai', so any threshold that merges the
        misspelling also merges two genuinely different dishes.
        """
        ordered = sorted(names, key=len, reverse=True)
        alias = {}
        for short in ordered:
            for long in ordered:
                if short == long or long in alias:
                    continue
                if re.search(r"\b%s\b" % re.escape(short), long):
                    alias[short] = long
                    break
        return alias

    # ------------------------------------------------------------- analysis
    def analyse_restaurant(self, name, reviews, meta=None, extra_dropped=None,
                           min_mentions=MIN_MENTIONS, discover=False):
        """reviews: [{"text": str, "rating": float|None}, ...] -> restaurant dict.

        min_mentions -- how many comments a dish needs before it is ranked.
        discover     -- also learn dish names from the text (for uploaded files
                        whose cuisine the built-in dictionary does not cover).
        """
        meta = meta or {}
        rid = slugify(name)

        dropped = collections.defaultdict(list)
        counts = collections.Counter()

        def record(reason, text):
            counts[reason] += 1
            if len(dropped[reason]) < DROPPED_SAMPLE:
                dropped[reason].append((text or "(empty)")[:400])

        for reason, items in (extra_dropped or {}).items():
            for t in items:
                record(reason, t)

        # ---- clean, deduplicate, length-filter -------------------------
        seen = set()
        kept = []
        for r in reviews:
            text = structural_clean(r.get("text") or "")
            h = hashlib.md5(text.encode("utf-8", "replace")).digest()[:8]
            if h in seen:
                record("duplicate", text)
                continue
            seen.add(h)
            if len(text) < MIN_CHARS:
                record("too_short", text)
                continue
            kept.append((text, r.get("rating")))

        funnel = {"input_reviews": len(reviews), "after_cleaning": len(kept)}
        if not kept:
            return None, funnel

        docs = list(self.nlp.pipe([t for t, _ in kept], batch_size=64))

        # ---- optionally learn dish names from this file ----------------
        extra = None
        discovered = {}
        alias = {}
        if discover:
            cand = self.discover_dishes(docs)
            if cand:
                alias = self.merge_aliases(list(cand))
                merged = collections.Counter()
                for k, v in cand.items():
                    merged[alias.get(k, k)] += v
                discovered = dict(merged)
                names = list(cand)          # match on every spelling seen
                m = PhraseMatcher(self.nlp.vocab, attr="LOWER")
                m.add("NEW", list(self.nlp.tokenizer.pipe(names)))
                extra = (m, {self.nlp.vocab.strings[t]: t for t in names})

        # ---- clause level: find dishes, then classify ------------------
        jobs, clause_texts = [], []
        for idx, doc in enumerate(docs):
            for clause in self.split_clauses(doc):
                found = {alias.get(d, d) for d in self.dishes_in(clause, extra)}
                if found:
                    jobs.append((idx, clause, found))
                    clause_texts.append(normalise(clause))
        preds = self.predict(clause_texts)
        funnel["dish_clauses"] = len(jobs)

        # ---- restaurant-level sentiment --------------------------------
        # Stars when we have them; otherwise the model reads whole reviews.
        has_ratings = any(rt is not None for _, rt in kept)
        if has_ratings:
            labels = [label_of(rt) for _, rt in kept]
            source = "star ratings"
        else:
            labels = self.predict([normalise(t) for t, _ in kept])
            source = "model, on each review"
        overall = collections.Counter(l for l in labels if l)

        # ---- aggregate per dish ----------------------------------------
        agg = collections.defaultdict(collections.Counter)
        comments = collections.defaultdict(list)
        with_dish = set()
        for (idx, clause, found), pred in zip(jobs, preds):
            with_dish.add(idx)
            for d in found:
                agg[d][pred] += 1
                agg[d]["mentions"] += 1
                comments[d].append({"text": clause, "label": pred})

        for idx, (text, _) in enumerate(kept):
            if idx not in with_dish:
                record("no_dish", text)

        funnel["with_dish_mention"] = len(with_dish)
        funnel["no_dish_mention"] = len(kept) - len(with_dish)

        order = {"positive": 0, "negative": 1, "neutral": 2}
        dishes = []
        for d, c in agg.items():
            m = c["mentions"]
            if m < min_mentions:
                continue
            dishes.append({
                "dish": d, "mentions": m,
                "positive": c["positive"], "neutral": c["neutral"],
                "negative": c["negative"],
                "positive_rate": round(c["positive"] / m, 3),
                "comments": sorted(comments[d], key=lambda q: order.get(q["label"], 3)),
            })
        dishes.sort(key=lambda x: (-x["positive_rate"], -x["mentions"]))

        total = max(sum(overall.values()), 1)
        rest = {
            "id": rid, "name": name,
            "address": meta.get("address", ""),
            "location": meta.get("location", ""),
            "rest_type": meta.get("rest_type", ""),
            "cuisines": meta.get("cuisines", ""),
            "approx_cost": meta.get("approx_cost", ""),
            "rate": meta.get("rate", ""),
            "votes": meta.get("votes", 0),
            "dish_liked": meta.get("dish_liked", []),
            "review_count": len(kept),
            "sentiment": {k: overall[k] for k in ("positive", "neutral", "negative")},
            "positive_rate": round(overall["positive"] / total, 3),
            "sentiment_source": source,
            "min_mentions": min_mentions,
            "discovered_dishes": sorted(discovered, key=discovered.get, reverse=True),
            "dishes_ranked": len(dishes),
            "dishes": dishes,
            "dropped": {
                "counts": dict(counts),
                "samples": dict(dropped),
                "sample_cap": DROPPED_SAMPLE,
            },
        }
        return rest, funnel


_shared = None


def get_analyzer():
    """One shared instance -- loading spaCy and the model takes a few seconds."""
    global _shared
    if _shared is None:
        _shared = Analyzer()
    return _shared
