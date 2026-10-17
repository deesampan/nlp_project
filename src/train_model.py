"""Make the sentiment model that run_pipeline.py uses.

    python src/train_model.py

Three steps, one section each below:
  1. Clean    the full Kaggle file (1.3M review entries) -> output_project/data/reviews_clean.csv
  2. Pick     the 3 restaurants with the most reviews   -> output_project/data/site_reviews.csv
                                                           + site_restaurants.json
  3. Train    TF-IDF + logistic regression, and test it against two simple baselines
              -> output_project/models/, results/model_metrics.json, results/confusion_matrix.png

Steps 1-2 need data_raw/zomato.csv (548 MB, download it from Kaggle; it is not in git).
Without it they are skipped, and step 3 trains from the reviews_clean.csv already in the repo.
"""
import ast
import csv
import hashlib
import html
import json
import pickle
import re
import unicodedata
from collections import Counter, defaultdict

import ftfy
import matplotlib
matplotlib.use("Agg")
from langdetect import DetectorFactory, LangDetectException, detect
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import ConfusionMatrixDisplay, accuracy_score, classification_report, f1_score
from sklearn.model_selection import train_test_split
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from run_pipeline import DATA, MODEL_FILE, ROOT, normalise

ZOMATO = ROOT / "data_raw" / "zomato.csv"
CORPUS = DATA / "reviews_clean.csv"
RESULTS = ROOT / "output_project" / "results"
FIGURE = RESULTS / "confusion_matrix.png"
LABELS = ["negative", "neutral", "positive"]

csv.field_size_limit(2**31 - 1)
DetectorFactory.seed = 0          # language detection gives the same answer every run


def zomato_rows():
    """Every row of the Kaggle file, with its key (name, address) and its (rating, text) reviews."""
    with open(ZOMATO, encoding="utf-8", errors="replace", newline="") as f:
        for row in csv.DictReader(f):
            key = ((row.get("name") or "").strip().lower(), (row.get("address") or "").strip().lower())
            try:
                reviews = ast.literal_eval(row.get("reviews_list") or "[]")
            except Exception:
                continue
            pairs = []
            for item in reviews:
                try:
                    rating, text = item[0], item[1]
                except Exception:
                    continue
                if text:
                    m = re.search(r"Rated\s+([\d.]+)", str(rating))
                    pairs.append((float(m.group(1)) if m else None, text))
            yield row, key, pairs


def text_id(text):
    return hashlib.md5(text.encode("utf-8", "replace")).digest()[:8]


# =========================================================================================
# 1. CLEAN THE FULL CORPUS
# =========================================================================================
def label_of(stars):
    """Training label from the review's own star rating."""
    if stars is None:
        return None
    return "positive" if stars >= 4 else "neutral" if stars >= 3 else "negative"


def fix_text(t):
    t = unicodedata.normalize("NFKC", html.unescape(ftfy.fix_text(t)))   # broken encoding, &amp; etc.
    t = t[5:] if t.startswith("RATED") else t                             # Zomato's prefix
    t = t.replace("\\n", " ").replace("\n", " ").replace("\\t", " ")
    t = re.sub(r"https?://\S+|www\.\S+", " ", t)                          # links
    t = re.sub(r"\S+@\S+\.\S+", " ", t)                                   # e-mails
    t = re.sub(r"(?<!\d)(?:\+?\d[\d\s-]{7,}\d)(?!\d)", " ", t)            # phone numbers
    return re.sub(r"\s+", " ", t).strip()


def is_english(t):
    if sum(ord(c) > 127 for c in t) / len(t) > 0.25:
        return False
    try:
        return detect(t) == "en"
    except LangDetectException:
        return False


def clean_corpus():
    funnel = {"csv_rows": 0, "review_tuples": 0}
    seen, restaurants_of, reviews = set(), defaultdict(set), []
    with open(ZOMATO, encoding="utf-8", errors="replace", newline="") as f:
        funnel["csv_rows"] = sum(1 for _ in csv.DictReader(f))
    for row, key, pairs in zomato_rows():
        for stars, text in pairs:
            funnel["review_tuples"] += 1
            h = text_id(text)
            restaurants_of[h].add(key)
            if (key, h) not in seen:                                      # same review listed twice
                seen.add((key, h))
                reviews.append((key, (row.get("name") or "").strip(), stars, text, h))
    funnel["after_dedup"] = len(reviews)
    # the same text at more than 5 restaurants is spam / boilerplate
    reviews = [r for r in reviews if len(restaurants_of[r[4]]) <= 5]
    funnel["after_boilerplate"] = len(reviews)
    reviews = [(k, n, s, fix_text(t)) for k, n, s, t, _ in reviews]
    reviews = [r for r in reviews if 15 <= len(r[3]) <= 5000 and any(c.isalpha() for c in r[3])]
    funnel["after_length_quality"] = len(reviews)
    reviews = [r for r in reviews if is_english(r[3])]
    funnel["after_language"] = len(reviews)
    reviews = [r for r in reviews if label_of(r[2])]                       # no star rating = no label
    funnel["after_labelling"] = len(reviews)

    with open(CORPUS, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["restaurant_name", "restaurant_key", "rating", "label", "text_clean", "text_norm"])
        for key, name, stars, text in reviews:
            w.writerow([name, key[0] + "|" + key[1], stars, label_of(stars), text, normalise(text)])
    with open(RESULTS / "cleaning_funnel.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["stage", "rows", "dropped_here", "pct_of_tuples"])
        prev = None
        for stage, n in funnel.items():
            dropped = "" if prev is None or stage == "review_tuples" else prev - n
            w.writerow([stage, n, dropped, round(100 * n / funnel["review_tuples"], 2)])
            prev = n
    for stage, n in funnel.items():
        print(f"  {stage:<22} {n:>10,}")


# =========================================================================================
# 2. PICK THE WEBSITE'S RESTAURANTS
# =========================================================================================
def pick_restaurants(how_many=3):
    unique = defaultdict(set)
    for _, key, pairs in zomato_rows():
        unique[key].update(text_id(t) for _, t in pairs)
    top = sorted(unique, key=lambda k: len(unique[k]), reverse=True)[:how_many]
    rank = {k: i + 1 for i, k in enumerate(top)}

    reviews, seen, info = [], set(), {}
    for row, key, pairs in zomato_rows():
        if key not in rank:
            continue
        r = info.setdefault(key, {"rank": rank[key], "name": row["name"].strip(), "location": row["location"],
                                  "address": row["address"], "type": row["rest_type"],
                                  "cuisines": row["cuisines"], "cost_for_two": row["approx_cost(for two people)"],
                                  "zomato_rate": row["rate"].replace(" ", ""), "votes": 0,
                                  "dish_liked": [d.strip() for d in (row["dish_liked"] or "").split(",") if d.strip()],
                                  "menu": set()})
        r["votes"] = max(r["votes"], int(row["votes"]))
        try:
            menu = ast.literal_eval(row["menu_item"])
        except (ValueError, SyntaxError):
            menu = []
        r["menu"] |= {re.sub(r"\s*\[.*?\]", "", m).strip() for m in menu}
        for stars, text in pairs:
            if (key, text_id(text)) not in seen:                          # same review listed twice
                seen.add((key, text_id(text)))
                reviews.append([r["name"], stars, text])                  # kept in the Kaggle file's order

    with open(DATA / "site_reviews.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["restaurant", "rating", "text"])
        w.writerows(reviews)
    rests = sorted(info.values(), key=lambda r: r["rank"])
    for r in rests:
        r["menu"] = sorted(r["menu"])
    (DATA / "site_restaurants.json").write_text(json.dumps(rests, ensure_ascii=False, indent=1) + "\n",
                                                encoding="utf-8")
    print("  picked:", ", ".join(r["name"] for r in rests), f"({len(reviews)} reviews)")


# =========================================================================================
# 3. TRAIN AND TEST THE MODEL
# =========================================================================================
# sklearn's stopword list contains "not", "no", "never": removing them turns "not good" into "good".
KEEP_WORDS = {"no", "not", "nor", "never", "none", "nothing", "cannot", "cant", "but", "however", "although",
              "though", "very", "too", "only", "against", "without", "hardly", "barely", "least", "less", "worst"}


def load_corpus():
    """reviews_clean.csv minus the website's restaurants, so the model never scores a review it trained on."""
    with open(DATA / "site_reviews.csv", encoding="utf-8", newline="") as f:
        site = {r["restaurant"] for r in csv.DictReader(f)}
    X, y = [], []
    with open(CORPUS, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            if row["restaurant_name"] not in site and row["text_norm"]:
                X.append(row["text_norm"])
                y.append(row["label"])
    return X, y


def train(stop_words, X, y):
    vec = TfidfVectorizer(ngram_range=(1, 2), min_df=3, max_features=200000, stop_words=stop_words,
                          sublinear_tf=True)
    clf = LogisticRegression(max_iter=1000, C=4.0, class_weight="balanced", n_jobs=-1)
    clf.fit(vec.fit_transform(X), y)
    return vec, clf


def vader(texts):
    """The ready-made baseline: a word list with scores, no training."""
    an = SentimentIntensityAnalyzer()
    scores = [an.polarity_scores(t)["compound"] for t in texts]
    return ["positive" if c >= 0.05 else "negative" if c <= -0.05 else "neutral" for c in scores]


def train_and_test():
    X, y = load_corpus()
    # 80% to learn from, 20% to test on. 15% of the learning part is kept aside as a validation
    # set for trying ideas, so the test set is only used for the final numbers.
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
    X_train, X_val, y_train, y_val = train_test_split(X_train, y_train, test_size=0.15, random_state=42,
                                                      stratify=y_train)

    def score(pred):
        return {"accuracy": round(accuracy_score(y_test, pred), 4),
                "macro_f1": round(f1_score(y_test, pred, average="macro", zero_division=0), 4)}

    vec, clf = train(sorted(ENGLISH_STOP_WORDS - KEEP_WORDS), X_train, y_train)
    pred = clf.predict(vec.transform(X_test))
    vec2, clf2 = train(sorted(ENGLISH_STOP_WORDS), X_train, y_train)          # same, but "not" removed
    majority = Counter(y_train).most_common(1)[0][0]
    systems = {
        "always say the most common label": score([majority] * len(y_test)),
        "VADER (ready-made, no training)": score(vader(X_test)),
        "our model: TF-IDF + logistic regression": score(pred),
        "our model, but stopwords include not/no/never": score(clf2.predict(vec2.transform(X_test))),
    }
    words = vec.get_feature_names_out()
    metrics = {
        "reviews": {"train": len(X_train), "validation": len(X_val), "test": len(X_test)},
        "systems": systems,
        "per_class": classification_report(y_test, pred, labels=LABELS, output_dict=True, zero_division=0),
        "top_words": {lab: [f"{words[j]} {clf.coef_[i][j]:+.2f}" for j in clf.coef_[i].argsort()[::-1][:10]]
                      for i, lab in enumerate(clf.classes_)},
    }
    (RESULTS / "model_metrics.json").write_text(json.dumps(metrics, indent=1), encoding="utf-8")
    shown = ConfusionMatrixDisplay.from_predictions(y_test, pred, labels=LABELS, cmap="Blues", values_format=",")
    shown.ax_.set_title("Confusion matrix - TF-IDF + logistic regression")
    shown.figure_.savefig(FIGURE, dpi=160, bbox_inches="tight")
    with open(MODEL_FILE, "wb") as f:
        pickle.dump({"vectorizer": vec, "classifier": clf}, f)

    print(f"  train {len(X_train):,} / validation {len(X_val):,} / test {len(X_test):,} reviews")
    for name, s in systems.items():
        print(f"  {name:<48} accuracy {s['accuracy']:.1%}   macro-F1 {s['macro_f1']:.1%}")
    for lab, top in metrics["top_words"].items():
        print(f"  {lab:<9} <- {', '.join(top[:6])}")


if __name__ == "__main__":
    for folder in (RESULTS, MODEL_FILE.parent):
        folder.mkdir(parents=True, exist_ok=True)
    if ZOMATO.exists():
        print("1. Cleaning the full corpus ...")
        clean_corpus()
        print("2. Picking the website's restaurants ...")
        pick_restaurants()
    else:
        print(f"{ZOMATO} not found: skipping steps 1-2, using the committed reviews_clean.csv")
    print("3. Training and testing ...")
    train_and_test()
    print("saved", MODEL_FILE)
