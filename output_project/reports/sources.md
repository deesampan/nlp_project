# Sources and Licences

Where every downloaded component of this project came from. Compiled 2026-09-10.
Versions are the pinned versions in [`requirements.txt`](../../requirements.txt); licences were
read from the installed package metadata in `.venv/`, not from memory.

## The short version

We downloaded **one dataset**, **one pre-trained model**, and **eleven software libraries**.
We did **not** download a sentiment model — that one we trained ourselves. The distinction
that matters:

| | Downloaded | Built by us |
|---|---|---|
| Review data | ✔ Kaggle | |
| Sentence splitting / tokenizing | ✔ spaCy `en_core_web_sm` | |
| **Sentiment classifier (decides good/bad)** | | **✔ trained on 134,612 reviews** |
| Dish name dictionary (2,774 terms) | | ✔ built from the dataset |
| Clause-splitting rule | | ✔ our own rule |
| Cleaning pipeline (9 stages) | | ✔ ours |

---

## 1. Dataset — the only data we downloaded

| Field | Value |
|---|---|
| Title | **Zomato Bangalore Restaurants** |
| Subtitle | "Restaurants of Bengaluru" |
| Author | Himanshu Poddar (`himanshupoddar`) |
| Host | Kaggle |
| URL | https://www.kaggle.com/datasets/himanshupoddar/zomato-bangalore-restaurants |
| Version | 1 |
| Last updated | 2019-03-31 |
| Size | 574,072,999 bytes (548 MB), 1 file: `zomato.csv` |
| Shape | 51,717 rows × 17 columns |
| Licence | **"Data files © Original Authors"** |
| Local path | `data_raw/zomato.csv` |

**Provenance check.** Kaggle's API reports `totalBytes: 574072999`. Our local
`data_raw/zomato.csv` is **574,072,999 bytes** — an exact match, so the file we trained on is
the unmodified file Kaggle serves. (Verified against
`https://www.kaggle.com/api/v1/datasets/view/himanshupoddar/zomato-bangalore-restaurants`.)

**What the licence means for us.** "Data files © Original Authors" is *not* an open licence
like CC0 or ODbL. The data stays under the original authors' copyright. Using it for
non-commercial university coursework with attribution is the intended use, but **we may not
redistribute `zomato.csv`**. This is why `data_raw/` is excluded from version control and why
the repository ships the pipeline that regenerates our derived files rather than the raw data
itself. Anyone reproducing this work downloads the CSV from Kaggle themselves.

**Provenance of the data itself.** The dataset was scraped from Zomato's Bengaluru listings
around 15 March 2019 by the Kaggle author. We did not scrape anything — see the scope note in
[report.md](report.md). Reviews are therefore Indian-English restaurant reviews from one city
in 2019, which is a stated limitation of the project, not a hidden one.

---

## 2. Pre-trained model — downloaded, but not for sentiment

| Field | Value |
|---|---|
| Model | **`en_core_web_sm`** |
| Version | 3.8.0 |
| Publisher | Explosion AI (https://explosion.ai) |
| Release page | https://github.com/explosion/spacy-models/releases/tag/en_core_web_sm-3.8.0 |
| Install command | `python -m spacy download en_core_web_sm` |
| Licence | MIT |

**What we use it for:** splitting reviews into sentences, tokenizing, and finding noun phrases
(the last one only for dish discovery on uploaded files).

**What we do NOT use it for:** sentiment, and dish recognition. Its built-in named-entity
recogniser has no food category and mislabels dish names, so dish detection is done by
dictionary matching against our own gazetteer instead. This correction is documented in
[report.md](report.md) §4 — the original proposal said "NER".

---

## 3. Downloaded, evaluated, and deliberately not shipped

| Field | Value |
|---|---|
| Tool | **VADER** (`vaderSentiment`) |
| Version | 3.3.2 |
| URL | https://pypi.org/project/vaderSentiment/3.3.2/ · https://github.com/cjhutto/vaderSentiment |
| Licence | MIT |

VADER is a ready-made, rule-based sentiment lexicon — the obvious "just download a sentiment
tool" option. We ran it on the same held-out test set as our own model:

| System | Accuracy | Macro-F1 |
|---|---|---|
| VADER (downloaded, untrained) | 72.2% | 0.537 |
| **Ours (trained)** | **82.1%** | **0.773** |

Full table: [`../results/model_comparison.csv`](../results/model_comparison.csv). It is in
`requirements.txt` because [`src/train_sentiment.py`](../../src/train_sentiment.py) imports it
to produce that comparison. It is **not** part of the shipped pipeline —
[`src/analyze.py`](../../src/analyze.py) never imports it.

---

## 4. Software libraries — tools, not models

All installed from PyPI with `pip`. Licences read from each package's `METADATA` in `.venv/`.

| Package | Version | Licence | Used for |
|---|---|---|---|
| [scikit-learn](https://pypi.org/project/scikit-learn/1.5.2/) | 1.5.2 | BSD 3-Clause | TF-IDF + logistic regression, metrics, train/test split |
| [spaCy](https://pypi.org/project/spacy/3.8.2/) | 3.8.2 | MIT | sentence splitting, tokenizing, `PhraseMatcher` |
| [pandas](https://pypi.org/project/pandas/2.2.3/) | 2.2.3 | BSD 3-Clause | tabular data handling |
| [numpy](https://pypi.org/project/numpy/1.26.4/) | 1.26.4 | BSD 3-Clause | arrays, coefficient sorting |
| [matplotlib](https://pypi.org/project/matplotlib/3.9.2/) | 3.9.2 | PSF-based (matplotlib licence) | confusion matrix and report figures |
| [ftfy](https://pypi.org/project/ftfy/6.3.0/) | 6.3.0 | Apache-2.0 | repairing mojibake / broken Unicode during cleaning |
| [langdetect](https://pypi.org/project/langdetect/1.0.9/) | 1.0.9 | see note below | dropping non-English reviews |
| [vaderSentiment](https://pypi.org/project/vaderSentiment/3.3.2/) | 3.3.2 | MIT | baseline comparison only (§3) |
| [Flask](https://pypi.org/project/flask/3.1.3/) | 3.1.3 | BSD 3-Clause | serving the dashboard on localhost |
| [click](https://pypi.org/project/click/) | ≥8.1 | BSD 3-Clause | command-line arguments |
| [Chart.js](https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js) | 4.4.1 | MIT | the dashboard's bar chart (loaded from cdnjs CDN) |

**Note on langdetect:** its own package metadata disagrees with itself — the `License:` field
says `MIT` while the classifier says `Apache Software License`. Upstream, langdetect is a Python
port of Google's `language-detection` library, which is Apache-2.0. Both are permissive and
neither restricts academic use; we flag the inconsistency rather than pick the convenient one.

---

## 5. What we built ourselves

Nothing in this list was downloaded.

| Component | File | Notes |
|---|---|---|
| Cleaning pipeline (9 stages) | [`src/build_corpus.py`](../../src/build_corpus.py) | produces `reviews_clean.csv`, 134,612 rows |
| Training labels | same file, `label_of()` | derived from each review's own star rating: ≥4.0 positive, ≥3.0 neutral, else negative. No hand-labelling, no external label source. |
| Dish gazetteer (2,774 terms) | [`src/build_gazetteer.py`](../../src/build_gazetteer.py) | extracted from the dataset's own `dish_liked` column |
| Negation-preserving stopword list | [`src/train_sentiment.py`](../../src/train_sentiment.py) `KEEP_WORDS` | 23 words removed from scikit-learn's default list so `"not good"` survives |
| **Sentiment classifier** | [`src/train_sentiment.py`](../../src/train_sentiment.py) | TF-IDF + logistic regression, trained by us. Run log: [`../logs/train_sentiment.log`](../logs/train_sentiment.log) |
| Clause-splitting rule | [`src/analyze.py`](../../src/analyze.py) `split_clauses()` | sentence split, then split again at contrastive conjunctions |
| Aggregation + dashboard | `src/build_slice.py`, `src/app.py`, `output_project/web/` | |

---

## 6. Citations for the report

**Dataset**

> Poddar, H. (2019). *Zomato Bangalore Restaurants* [Data set]. Kaggle.
> https://www.kaggle.com/datasets/himanshupoddar/zomato-bangalore-restaurants
> (Data files © Original Authors. Accessed 2026-08-28.)

**Software**

> Pedregosa, F., Varoquaux, G., Gramfort, A., et al. (2011). Scikit-learn: Machine Learning in
> Python. *Journal of Machine Learning Research*, 12, 2825–2830.

> Honnibal, M., Montani, I., Van Landeghem, S., & Boyd, A. (2020). *spaCy: Industrial-strength
> Natural Language Processing in Python.* Zenodo. https://doi.org/10.5281/zenodo.1212303

**Baseline we compared against**

> Hutto, C. J., & Gilbert, E. (2014). VADER: A Parsimonious Rule-based Model for Sentiment
> Analysis of Social Media Text. *Proceedings of the Eighth International AAAI Conference on
> Weblogs and Social Media (ICWSM-14)*, Ann Arbor, MI.

---

## 7. Nothing else was downloaded

No pre-trained sentiment model, no transformer checkpoint, no HuggingFace model, no external
API, and no borrowed analysis code. `transformers` and `datasets` appear in the tech-stack
section of `CLAUDE.md` as options that were considered; they are **not** in
`requirements.txt` and are **not** installed. The project runs entirely on the packages listed
in §4.
