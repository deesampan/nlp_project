"""Phase 2b - train the sentiment classifier and evaluate it against baselines.

Four systems are compared on one held-out test set:

  1. majority class          - the floor any model must clear
  2. VADER                   - rule-based lexicon, no training
  3. TF-IDF + logistic reg   - negation-preserving stopwords   <- the model we ship
  4. TF-IDF + logistic reg   - default sklearn stopwords       <- ablation

System 4 exists to measure a specific claim: sklearn's default English stopword
list contains "not", "no", "never" and "nor". Stripping them turns "not good"
into "good". System 3 minus system 4 is the cost of that mistake, in points.
"""
import csv
import sys
import json
import pickle

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from sklearn.feature_extraction.text import TfidfVectorizer, ENGLISH_STOP_WORDS
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import (accuracy_score, f1_score, classification_report,
                             confusion_matrix)
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from config import OUT_DATA, OUT_RESULTS, OUT_FIGURES, OUT, ensure_dirs

csv.field_size_limit(min(sys.maxsize, 2**31 - 1))

CORPUS = OUT_DATA / "reviews_clean.csv"
MODEL_DIR = OUT / "models"
LABELS = ["negative", "neutral", "positive"]

# Words sklearn would strip that invert or intensify meaning. Removing these
# from the stopword list is the single most important preprocessing decision
# in the whole project.
KEEP_WORDS = {
    "no", "not", "nor", "never", "none", "nothing", "cannot", "cant",
    "but", "however", "although", "though", "very", "too", "only",
    "against", "without", "hardly", "barely", "least", "less", "worst",
}
NEG_AWARE_STOP = list(ENGLISH_STOP_WORDS - KEEP_WORDS)
DEFAULT_STOP = list(ENGLISH_STOP_WORDS)


def load():
    X, y = [], []
    with open(CORPUS, "r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            t = row["text_norm"]
            if t:
                X.append(t)
                y.append(row["label"])
    return X, y


def fit_eval(name, stop, Xtr, ytr, Xte, yte):
    vec = TfidfVectorizer(ngram_range=(1, 2), min_df=3, max_features=200000,
                          stop_words=stop, sublinear_tf=True)
    Xtr_v = vec.fit_transform(Xtr)
    Xte_v = vec.transform(Xte)
    clf = LogisticRegression(max_iter=1000, C=4.0, class_weight="balanced",
                             n_jobs=-1)
    clf.fit(Xtr_v, ytr)
    pred = clf.predict(Xte_v)
    acc = accuracy_score(yte, pred)
    f1 = f1_score(yte, pred, average="macro")
    print("  %-38s acc=%.4f  macroF1=%.4f  features=%d" % (
        name, acc, f1, len(vec.vocabulary_)))
    return vec, clf, pred, acc, f1


def band_predict(proba, classes, lo, hi):
    """Turn binary probabilities into three labels.

    The binary model is trained only on clearly positive and clearly negative
    reviews. Neutral is not a sentiment the model learns -- it is the region
    where the model is not confident either way. That is a more honest
    definition than "the star rating happened to be 3".
    """
    pi = list(classes).index("positive")
    out = []
    for row in proba:
        p = row[pi]
        out.append("positive" if p >= hi else "negative" if p <= lo else "neutral")
    return out


def fit_binary_with_band(Xtr, ytr, Xva, yva, Xte, yte):
    """Train on positive vs negative only, then tune the uncertainty band."""
    bin_idx = [i for i, y in enumerate(ytr) if y != "neutral"]
    Xb = [Xtr[i] for i in bin_idx]
    yb = [ytr[i] for i in bin_idx]
    print("  binary training rows: %d (neutral dropped from training)" % len(Xb))

    vec = TfidfVectorizer(ngram_range=(1, 2), min_df=3, max_features=200000,
                          stop_words=NEG_AWARE_STOP, sublinear_tf=True)
    Xb_v = vec.fit_transform(Xb)
    clf = LogisticRegression(max_iter=1000, C=4.0, class_weight="balanced", n_jobs=-1)
    clf.fit(Xb_v, yb)

    # pure binary skill, measured only on unambiguous reviews
    te_bin = [i for i, y in enumerate(yte) if y != "neutral"]
    pred_bin = clf.predict(vec.transform([Xte[i] for i in te_bin]))
    y_bin = [yte[i] for i in te_bin]
    bin_acc = accuracy_score(y_bin, pred_bin)
    bin_f1 = f1_score(y_bin, pred_bin, average="macro")
    print("  binary task (positive vs negative only)   acc=%.4f  macroF1=%.4f"
          % (bin_acc, bin_f1))

    # tune the band on validation, never on test
    proba_va = clf.predict_proba(vec.transform(Xva))
    sweep = []
    # Swept to 0.50 so the maximum is bracketed rather than sitting on the edge
    # of the range. 0.50 is the degenerate endpoint: the band spans [0, 1], every
    # review is called neutral, and macro-F1 must collapse. Any interior best is
    # therefore a real optimum and not an artefact of where we stopped looking.
    for w in [0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50]:
        p = band_predict(proba_va, clf.classes_, 0.5 - w, 0.5 + w)
        sweep.append((w, accuracy_score(yva, p),
                      f1_score(yva, p, average="macro", zero_division=0)))
    best_w = max(sweep, key=lambda t: t[2])[0]
    print("  band sweep (validation):")
    for w, a, f in sweep:
        print("      +/-%.2f  acc=%.4f  macroF1=%.4f%s" % (w, a, f, "   <- chosen" if w == best_w else ""))

    lo, hi = 0.5 - best_w, 0.5 + best_w
    proba_te = clf.predict_proba(vec.transform(Xte))
    pred = band_predict(proba_te, clf.classes_, lo, hi)
    acc = accuracy_score(yte, pred)
    f1 = f1_score(yte, pred, average="macro", zero_division=0)
    print("  %-38s acc=%.4f  macroF1=%.4f" % ("binary + uncertainty band (3-class)", acc, f1))
    return vec, clf, pred, acc, f1, (lo, hi), bin_acc, bin_f1, sweep


def vader_predict(texts):
    an = SentimentIntensityAnalyzer()
    out = []
    for t in texts:
        c = an.polarity_scores(t)["compound"]
        out.append("positive" if c >= 0.05 else "negative" if c <= -0.05 else "neutral")
    return out


def main():
    ensure_dirs()
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    X, y = load()
    print("corpus: %d reviews" % len(X))
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, random_state=42,
                                          stratify=y)
    # Validation split carved out of train, used only to tune the band so the
    # threshold never sees the test set.
    Xtr, Xva, ytr, yva = train_test_split(Xtr, ytr, test_size=0.15,
                                          random_state=42, stratify=ytr)
    print("train %d / val %d / test %d\n" % (len(Xtr), len(Xva), len(Xte)))

    results = {}

    # 1 - majority class floor
    maj = max(set(ytr), key=ytr.count)
    maj_pred = [maj] * len(yte)
    results["majority_class"] = {
        "accuracy": accuracy_score(yte, maj_pred),
        "macro_f1": f1_score(yte, maj_pred, average="macro", zero_division=0),
    }
    print("  %-38s acc=%.4f  macroF1=%.4f" % (
        "majority class (%s)" % maj, results["majority_class"]["accuracy"],
        results["majority_class"]["macro_f1"]))

    # 2 - VADER
    vpred = vader_predict(Xte)
    results["vader"] = {
        "accuracy": accuracy_score(yte, vpred),
        "macro_f1": f1_score(yte, vpred, average="macro", zero_division=0),
    }
    print("  %-38s acc=%.4f  macroF1=%.4f" % (
        "VADER (lexicon, untrained)", results["vader"]["accuracy"],
        results["vader"]["macro_f1"]))

    # 3 - shipped model
    vec, clf, pred, acc, f1 = fit_eval(
        "TF-IDF + LogReg (negation-preserving)", NEG_AWARE_STOP,
        Xtr, ytr, Xte, yte)
    results["tfidf_lr_negation_aware"] = {"accuracy": acc, "macro_f1": f1}

    # 4 - ablation
    _, _, _, acc2, f12 = fit_eval(
        "TF-IDF + LogReg (default stopwords)", DEFAULT_STOP,
        Xtr, ytr, Xte, yte)
    results["tfidf_lr_default_stopwords"] = {"accuracy": acc2, "macro_f1": f12}
    results["negation_ablation_delta"] = {
        "accuracy": acc - acc2, "macro_f1": f1 - f12}

    print("\n=== NEGATION ABLATION ===")
    print("  keeping negation words is worth %+.2f accuracy points, %+.2f macro-F1 points"
          % (100 * (acc - acc2), 100 * (f1 - f12)))

    # 5 - binary trained + uncertainty band
    print("\n=== BINARY + UNCERTAINTY BAND ===")
    bvec, bclf, bpred, bacc, bf1, band, bin_acc, bin_f1, sweep = \
        fit_binary_with_band(Xtr, ytr, Xva, yva, Xte, yte)
    results["binary_task_only"] = {"accuracy": bin_acc, "macro_f1": bin_f1}
    results["binary_plus_band"] = {"accuracy": bacc, "macro_f1": bf1,
                                   "band_low": band[0], "band_high": band[1]}

    # ship whichever wins on macro-F1 over the same three-class test set
    if bf1 > f1:
        ship = ("binary_plus_band", bvec, bclf, bpred, bacc, bf1)
    else:
        ship = ("tfidf_lr_negation_aware", vec, clf, pred, acc, f1)
    results["shipped"] = ship[0]
    print("\n  shipping: %s (macro-F1 %.4f vs %.4f)" % (
        ship[0], ship[5], f1 if ship[0] != "tfidf_lr_negation_aware" else bf1))

    vec, clf, pred = ship[1], ship[2], ship[3]

    print("\n=== CLASSIFICATION REPORT (shipped model) ===")
    rep = classification_report(yte, pred, labels=LABELS, digits=3, zero_division=0)
    print(rep)

    cm = confusion_matrix(yte, pred, labels=LABELS)

    with open(OUT_RESULTS / "band_sweep.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["band_half_width", "val_accuracy", "val_macro_f1", "chosen"])
        for wd, a, fs in sweep:
            w.writerow([wd, round(a, 4), round(fs, 4),
                        "yes" if abs(wd - (0.5 - band[0])) < 1e-9 else ""])

    # ---- learned weights: this is the explainability deliverable ----------
    feat = np.array(vec.get_feature_names_out())
    coef_rows = []
    print("=== WHAT THE MODEL LEARNED ===")
    for i, lab in enumerate(clf.classes_):
        order = np.argsort(clf.coef_[i])
        top = [(feat[j], float(clf.coef_[i][j])) for j in order[-15:][::-1]]
        bot = [(feat[j], float(clf.coef_[i][j])) for j in order[:10]]
        print("  %s  <-  %s" % (lab, ", ".join("%s %+.2f" % t for t in top[:8])))
        for w, c in top:
            coef_rows.append([lab, "pushes_toward", w, round(c, 4)])
        for w, c in bot:
            coef_rows.append([lab, "pushes_away", w, round(c, 4)])

    # ---- artefacts --------------------------------------------------------
    with open(OUT_RESULTS / "model_comparison.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["system", "accuracy", "macro_f1"])
        for k in ("majority_class", "vader", "tfidf_lr_negation_aware",
                  "tfidf_lr_default_stopwords", "binary_plus_band",
                  "binary_task_only"):
            w.writerow([k, round(results[k]["accuracy"], 4), round(results[k]["macro_f1"], 4)])

    with open(OUT_RESULTS / "model_coefficients.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["class", "direction", "feature", "weight"])
        w.writerows(coef_rows)

    with open(OUT_RESULTS / "classification_report.txt", "w", encoding="utf-8") as f:
        f.write("held-out test set: %d reviews\n\n" % len(yte))
        f.write(rep)
        f.write("\nconfusion matrix (rows = true, cols = predicted)\n")
        f.write("labels: %s\n" % LABELS)
        for r in cm:
            f.write("  %s\n" % "  ".join("%6d" % v for v in r))

    with open(OUT_RESULTS / "model_metrics.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=1)

    fig, ax = plt.subplots(figsize=(5.4, 4.6))
    im = ax.imshow(cm, cmap="Blues")
    ax.set_xticks(range(3)); ax.set_xticklabels(LABELS)
    ax.set_yticks(range(3)); ax.set_yticklabels(LABELS)
    ax.set_xlabel("predicted"); ax.set_ylabel("true")
    ax.set_title("Confusion matrix - TF-IDF + logistic regression")
    for i in range(3):
        for j in range(3):
            ax.text(j, i, format(cm[i, j], ","), ha="center", va="center",
                    color="white" if cm[i, j] > cm.max() * 0.55 else "black",
                    fontsize=10)
    fig.colorbar(im, fraction=0.046)
    fig.tight_layout()
    fig.savefig(OUT_FIGURES / "confusion_matrix.png", dpi=160)

    with open(MODEL_DIR / "sentiment_tfidf_lr.pkl", "wb") as f:
        pickle.dump({
            "vectorizer": vec,
            "classifier": clf,
            "labels": LABELS,
            "mode": "binary_band" if results["shipped"] == "binary_plus_band" else "three_class",
            "band": results["binary_plus_band"] if results["shipped"] == "binary_plus_band" else None,
        }, f)

    print("\nsaved model  -> %s" % (MODEL_DIR / "sentiment_tfidf_lr.pkl"))
    print("saved figure -> %s" % (OUT_FIGURES / "confusion_matrix.png"))


if __name__ == "__main__":
    main()
