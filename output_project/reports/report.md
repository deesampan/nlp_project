# Restaurant Recommendation From Reviews

**NLP Group Project**
Deesampan Vongsurit (6510766) · Wattanan Jiratriluk (6520214)

---

## Abstract

Restaurants receive hundreds of reviews monthly, but the useful information — which *dishes*
customers actually like — is buried in unstructured text. We built a pipeline that extracts
dish mentions from 134,612 restaurant reviews, classifies sentiment at the clause level, and
presents per-dish rankings in a dashboard.

The central technical claim is that **review-level sentiment is insufficient for dish-level
recommendation**. A star rating describes a whole review, so *"the biryani was great but the
paratha was stale"* credits both dishes identically. Splitting reviews into clauses and
classifying each separately disagreed with the review's own star rating on **25.8% of dish
clauses**, and identified **65 reviews** containing dishes with genuinely opposite sentiment.

Our classifier reaches **82.1% accuracy / 77.3% macro-F1** on three-class sentiment, and
**96.5% accuracy / 95.5% macro-F1** on the binary positive-versus-negative task that the
dashboard actually depends on.

---

## 1. Problem

Feedback is unstructured and does not scale to manual reading. Menu decisions get made on
intuition: weak dishes stay on the menu, strong dishes go unpromoted.

A single sentence can praise one dish and condemn another, so the unit of opinion is not the
review — it is the dish mention inside it. That is what makes this an NLP problem rather than
a spreadsheet problem.

**Objective.** Convert a corpus of restaurant reviews into a per-dish recommendation: which
dishes are signature, which are hidden gems, which need fixing or cutting.

### Scope changes from the original proposal

1. **Aspect-Based Sentiment Analysis was dropped.** It is replaced by **clause-level sentiment
   attribution**: split the review at sentence boundaries and at contrastive conjunctions,
   detect dish mentions per clause, classify that clause, attribute the result only to dishes
   inside it. This delivers dish-level sentiment without ABSA's annotation cost.
2. **No scraping.** Reviews come from an existing public dataset rather than live collection.
3. **Trend over time was dropped.** The dataset has no timestamps — see section 2.
4. **"NER" was corrected to dictionary matching.** See section 4.

---

## 2. Data

**Zomato Bangalore Restaurants** (Kaggle), 51,717 rows × 17 columns, 548 MB.

Full provenance — author, URL, version, licence, and the source and licence of every downloaded
library and pre-trained model — is recorded in [sources.md](sources.md).

| Property | Value |
|---|---|
| Unique restaurants (`name` + `address`) | 12,494 |
| Review tuples in `reviews_list` | 1,317,782 |
| Unique reviews after deduplication | 143,789 |
| Clean, labelled corpus | **134,612** |
| Restaurants with `dish_liked` | 4,608 (36.9%) |
| Distinct dish terms in `dish_liked` | 2,718 |

### Three fields that are easy to confuse

| Field | Level | What it is |
|---|---|---|
| `rate` | Restaurant | Zomato's displayed average, e.g. `4.1/5` |
| `votes` | Restaurant | How many people rated it |
| `reviews_list` | Restaurant | The scraped text reviews, each with its own star rating |

These are **not interchangeable**, and we verified it. `rate` differs from the mean of the
ratings inside `reviews_list` by **0.55 stars on average** (median 0.40, max 3.10); only 6.7%
agree within 0.05. And `votes` exceeds the review count in 87.9% of rows, with a **median
ratio of 11×** — 2,297,449 total votes against 138,645 unique review texts, so the text
reviews represent roughly **6%** of all ratings.

The reason is the same in both cases: most people tap a star and write nothing. `rate` and
`votes` describe everyone; `reviews_list` describes the small, self-selected minority who
wrote text. **This is a sampling bias in our corpus** — text reviewers skew toward strong
opinions.

**The mistake this rules out:** joining restaurant-level `rate` onto each review as a training
label. It is an average, so a furious 1-star review at a 4.5-star restaurant would be labelled
positive. We use the per-review rating inside `reviews_list` instead.

### Why there is no trend-over-time analysis

Each review tuple is `(rating, text)`. There is no date field anywhere in the schema. Trend
over time, promised in our original proposal, is **not recoverable from this dataset by any
means**, so it was removed from scope rather than faked.

### The review distribution constrains the product

Unique reviews per restaurant: min 0, p25 1, **median 3**, p75 10, p90 29, max 524.

| Threshold | Restaurants | Share |
|---|---|---|
| Zero reviews | 2,384 | 19.1% |
| ≥ 1 | 10,110 | 80.9% |
| ≥ 10 | 3,271 | 26.2% |
| ≥ 50 | 657 | 5.3% |
| ≥ 100 | 205 | 1.6% |

**The median restaurant cannot support dish-level analysis.** Three reviews yield perhaps five
dish mentions across an entire menu; a "most-loved dish" ranked on two mentions is a coin
flip. We therefore work with high-volume restaurants and enforce a **minimum of 5 mentions**
before any dish is ranked.

---

## 3. Noise and preprocessing

Covered in full in [noise_analysis.md](noise_analysis.md). Summary:

**89.1% of the corpus is duplicated** (1,317,782 → 143,789), and deduplication accounts for
**99.2% of all rows removed** by the entire nine-stage pipeline. Deduplicating on `url` fails
silently because Zomato appends a per-category query string; deduplicating on
`(name, address)` first discards 32,803 real reviews. The correct key is
`(restaurant, review_text)`, applied after exploding to review level.

Noise is **task-relative**: non-food reviews are noise for the dish panel and signal for the
restaurant panel, so they are routed rather than deleted. Relevance filtering therefore runs
*after* dish extraction, not before.

---

## 4. Dish extraction

**Off-the-shelf NER does not detect dishes.** spaCy's pretrained models recognise `PERSON`,
`ORG`, `GPE` and `DATE`; there is no `FOOD` entity type. Running NER over *"the chicken
biryani was dry"* returns nothing useful. Our original proposal said NER, and that was wrong.

Training a dish NER would require span-annotated data we do not have. We use **dictionary
matching plus noun-phrase discovery** instead:

1. A **2,774-term gazetteer** built from `dish_liked` across the full dataset.
2. spaCy `PhraseMatcher` with **longest-match preference**, so `chicken biryani` wins over
   `biryani`.
3. **Variant normalisation** — `Panneer`/`Panner` → `paneer`, `Biriyani` → `biryani` — so
   counts do not fragment across spellings.
4. **Bare ingredients excluded.** `chicken`, `rice`, `fish` and `paneer` alone are not
   orderable items; attributing sentiment to them is meaningless. They are blocked as single
   words only, so `chicken biryani` and `fried rice` survive.

`dish_liked` is **weak supervision, not ground truth**: it covers only 36.9% of restaurants,
attaches to the restaurant rather than the review, and its terms are coarse (`pasta`,
`burgers`, `cocktails` are categories, not menu items). We use it as a vocabulary source and
for recall estimation, not as labels.

---

## 5. Sentiment model

### Why we trained our own

The corpus carries **free per-review labels** — every review tuple has its own star rating —
so training cost nothing in annotation. Labels: positive ≥ 4.0, neutral 3.0–3.5, negative ≤ 2.5.

We chose **TF-IDF + logistic regression** primarily for explainability. TF-IDF converts each
review to a vector of word weights, where term frequency measures how often a word appears
here and inverse document frequency downweights words appearing everywhere. Logistic
regression learns one weight per word, sums them, and squashes the result to a probability.

**The learned weights are the explanation.** No deep model offers this as directly.

### Results

Trained on 91,535 reviews, tuned on 16,154, evaluated on a held-out 26,923.

| System | Accuracy | Macro F1 |
|---|---|---|
| Majority class (always positive) | 60.3% | 25.1% |
| VADER (lexicon, untrained) | 72.2% | 53.7% |
| **TF-IDF + logistic regression** | **82.1%** | **77.3%** |
| Same, default sklearn stopwords | 80.1% | 74.8% |
| Binary + uncertainty band | 77.4% | 71.6% |

Per class: negative F1 **0.847**, positive F1 **0.892**, neutral F1 **0.581**.

### What the model learned

| Class | Strongest features |
|---|---|
| Negative | `worst` +12.86, `pathetic` +9.75, `horrible` +8.37, `bad` +7.82, `not` +7.74, `not good` +6.45 |
| Neutral | `good` +5.77, `decent` +4.79, `average` +4.62, `ok` +4.01, `however` +3.95, `but` +3.67 |
| Positive | `amazing` +10.03, `best` +9.74, `awesome` +9.71, `delicious` +8.91, `not disappointed` +6.64 |

### The neutral class, and a negative result

Neutral is the weak point at F1 0.581. The confusion matrix shows why: the model **almost
never confuses positive with negative** — only 379 of 26,923 test reviews (**1.4%**) — while
1,280 neutral reviews are read as positive and 1,783 positive as neutral. All the error sits
on the neutral boundary.

**We tried to fix this and failed.** We trained a binary model on clearly positive versus
clearly negative reviews and derived neutral from model uncertainty, tuning the confidence
band on validation data. It scored **71.6% macro-F1, six points worse** than simply training
on three classes. We report the attempt because the negative result is informative: neutral is
not a modelling artefact that a reframing can remove.

What it did establish is more useful. On the **binary task the same model reaches 96.5%
accuracy and 95.5% macro-F1**. The three-class figure is held down almost entirely by a
class sitting on an arbitrary boundary — a 3-star review is not a distinct opinion, it is the
gap between two. For the dashboard's actual question, *is this dish liked or disliked*, the
model is highly accurate.

---

## 6. Clause-level attribution

Each review is split at sentence boundaries and again at `but`, `however`, `although`,
`though`, `whereas`, `yet`. Dish mentions are matched per clause; the clause is classified;
the result is attributed only to dishes inside that clause.

*"The biryani was great but the paratha was stale"* becomes two clauses with opposite labels
attributed to different dishes. A star rating cannot express this.

**Measured effect** on our three-restaurant sample (1,400 reviews → 1,069 after cleaning →
605 dish-bearing clauses):

- Clause prediction disagreed with the review's star rating on **25.8%** of dish clauses
- **65 reviews** contained dishes assigned genuinely opposite sentiment

Largest single correction: `egg biryani` moved from **+0.38 to −0.75** (shift −1.13). Its true
split is 1 positive to 7 negative; the star rating had been crediting it for praise directed at
other dishes in the same reviews.

---

## 7. Dashboard

Static HTML, CSS and vanilla JavaScript with Chart.js. No backend — the Python pipeline
exports static JSON. Served on localhost:

```bash
cd output_project/web && python -m http.server 8000
```

It must be served over HTTP, not opened as a file: the page loads its data via `fetch()`,
which browsers block over `file://`.

**Landing view** — restaurant cards with sentiment split and review counts, the cleaning
funnel, model comparison, and the learned-weights table.

**Detail view** — KPIs, overall sentiment split, a **menu action map** plotting mention volume
against positive share (dividing the menu into signature / hidden gem / fix-or-cut /
low-priority), a **"where the star rating was wrong"** panel showing which dishes moved under
clause-level attribution, a sortable dish table with star baseline, model score and shift, and
click-through to the actual review text behind every score.

Plotting volume against sentiment matters: ranking on sentiment alone puts a dish praised once
above the restaurant's best seller.

---

## 8. Results

For the three highest-volume restaurants:

| Restaurant | Reviews | Positive | Dishes ranked |
|---|---|---|---|
| Biriyani Nights | 391 | 40% | 5 |
| Night Food Joint | 347 | 26% | 8 |
| BOX8- Desi Meals | 331 | 61% | 22 |

The ordering matches the platform's own `rate` values (3.2 / 2.9 / 4.1) despite never using
them, which is an independent sanity check.

---

## 9. Limitations

- **Neutral-class F1 of 0.581.** Documented above, with a failed remediation attempt.
- **Sampling bias.** Text reviewers are ~6% of raters and skew toward strong opinions.
- **Dish coverage.** 677 of 1,069 cleaned reviews mention no dish; they feed the restaurant
  panel only. Our sample restaurants are delivery-led, so service complaints dominate.
- **Noun-phrase discovery is not usable yet.** It returns `food`, `they`, `order` and needs
  part-of-speech filtering.
- **No manual audit** of dropped rows, so filter precision is unmeasured.
- **The 15-character threshold is unvalidated** by ablation.
- **No timestamps**, so no temporal analysis.
- **Weak supervision only** for dish extraction; we report no precision/recall for it. A
  labelled evaluation set such as SemEval-2016 Task 5 would fix this.

---

## 10. Reproducing

```bash
py -3.10 -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python -m spacy download en_core_web_sm

cd src
../.venv/Scripts/python build_gazetteer.py   # dish dictionary
../.venv/Scripts/python build_corpus.py      # full cleaning (~10 min)
../.venv/Scripts/python train_sentiment.py   # train and evaluate
../.venv/Scripts/python make_subset.py       # pick which restaurants to show
../.venv/Scripts/python build_slice.py       # dashboard JSON

../.venv/Scripts/python app.py               # serve http://localhost:8000
```

Serve with `app.py`, not `python -m http.server`. Flask sends `Cache-Control: no-store`, so a
refresh after a rebuild shows the new numbers; a plain static server lets the browser reuse a
cached `dashboard.json` and silently display the previous run's results.

All generated artefacts are written under `output_project/`; nothing is written beside the
source code, and everything there is regenerable from the raw dataset.
