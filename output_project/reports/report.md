# Restaurant Recommendation From Reviews

**NLP Group Project**
Deesampan Vongsurit (6510766) · Wattanan Jiratriluk (6520214)

---

## Abstract

Restaurants receive hundreds of reviews monthly, but the useful information — which *dishes*
customers actually like — is buried in unstructured text. We trained a sentiment classifier on
133,389 labelled Zomato reviews, then used it to read the 1,321 reviews of three Bangalore
restaurants clause by clause, find the dishes in each clause, and rank every dish on a website.

The central technical claim is that **review-level sentiment is insufficient for dish-level
recommendation**. A star rating describes a whole review, so *"the biryani was great but the
paratha was stale"* credits both dishes identically. Splitting reviews into clauses and
classifying each separately gave a different answer from the review's own star rating on
**32.9% of dish opinions**, and found **19 reviews** that like one dish and dislike another.

Our classifier reaches **82.2% accuracy / 77.4% macro-F1** on three-class sentiment, and
**96.5% accuracy / 95.5% macro-F1** on the binary positive-versus-negative task that the
website actually depends on. The website's three restaurants are held out of training.

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
| Used for training (website's 3 restaurants held out) | **133,389** |
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
flip. We therefore work with high-volume restaurants, and a dish is ranked only once **at least 4
reviews take a side on it**. Dishes below that are listed separately as "too little to judge".

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

### The website's reviews

The three restaurants on the website go through a shorter, four-step filter
(`src/preprocess.py`). Every removed review is kept, with its reason, and listed at the bottom
of each restaurant page under "Reviews left out".

| Step | Removed | Left |
|---|---|---|
| Raw reviews | | 1,400 |
| N1 Empty after cleaning (only emoji, symbols or the `RATED` prefix) | 6 | 1,394 |
| N2 Duplicate review (same text, same restaurant) | 3 | 1,391 |
| N3 Too short (fewer than 2 words) | 70 | 1,321 |
| N4 Non-English (under 70% Latin characters) | 0 | 1,321 |

Cleaning before the filter removes the `RATED` prefix, broken characters and emoji, links, and
repeated letters and punctuation ("soooo good!!!" becomes "soo good!").

---

## 4. Dish extraction

**Off-the-shelf NER does not detect dishes.** spaCy's pretrained models recognise `PERSON`,
`ORG`, `GPE` and `DATE`; there is no `FOOD` entity type. Running NER over *"the chicken
biryani was dry"* returns nothing useful. Our original proposal said NER, and that was wrong.

Training a dish NER would require span-annotated data we do not have. We use **dictionary matching** instead (`src/dish_extract.py`). Each restaurant gets
its own dish list:

1. Its **Zomato menu** (`menu_item`) plus its `dish_liked` tags, plus 20 common dishes
   (biryani, kebab, naan, ...) that people mention without using the menu's exact name.
2. **Longest match wins**, so `chicken biryani` is found instead of `biryani`.
3. **Spelling variants are merged** — `Biriyani`/`Briyani` → `biryani`, `Panner` → `paneer` —
   and long words (6+ letters) also match small typos (RapidFuzz similarity of 88 or more).
4. **The restaurant's own name is not a dish**, so "Biriyani Nights" does not count as biryani.

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

**The website's restaurants are held out.** Their 1,223 reviews are removed before training,
so the model never scores a review it has already seen together with its star rating. The
remaining 133,389 reviews are split: trained on 90,704, tuned on 16,007, evaluated on a held-out
26,678.

| System | Accuracy | Macro F1 |
|---|---|---|
| Majority class (always positive) | 60.5% | 25.1% |
| VADER (lexicon, untrained) | 72.7% | 54.3% |
| **TF-IDF + logistic regression** | **82.2%** | **77.4%** |
| Same, default sklearn stopwords | 80.1% | 74.9% |
| Binary + uncertainty band | 77.2% | 71.7% |

Keeping negation words (`not`, `no`, `never`) out of the stopword list is worth **+2.1
accuracy points**. Per class: negative F1 **0.847**, positive F1 **0.893**, neutral F1
**0.582**.

### What the model learned

| Class | Strongest features |
|---|---|
| Negative | `worst` +12.99, `pathetic` +10.01, `not` +8.18, `bad` +8.10, `horrible` +7.68, `not good` +6.15 |
| Neutral | `good` +5.32, `decent` +4.86, `average` +4.85, `okay` +3.97, `ok` +3.86, `but` +3.78 |
| Positive | `awesome` +9.94, `best` +9.73, `amazing` +9.61, `delicious` +8.64, `loved` +8.49, `excellent` +7.40 |

### The neutral class, and a negative result

Neutral is the weak point at F1 0.582. The confusion matrix shows why: the model **almost
never confuses positive with negative** — only 351 of 26,678 test reviews (**1.3%**) — while
1,215 neutral reviews are read as positive and 1,809 positive as neutral. All the error sits
on the neutral boundary.

**We tried to fix this and failed.** We trained a binary model on clearly positive versus
clearly negative reviews and derived neutral from model uncertainty, tuning the confidence
band on validation data. It scored **71.7% macro-F1, six points worse** than simply training
on three classes. We report the attempt because the negative result is informative: neutral is
not a modelling artefact that a reframing can remove.

What it did establish is more useful. On the **binary task the same model reaches 96.5%
accuracy and 95.5% macro-F1**. The three-class figure is held down almost entirely by a
class sitting on an arbitrary boundary — a 3-star review is not a distinct opinion, it is the
gap between two. For the website's actual question, *is this dish liked or disliked*, the
model is highly accurate.

---

## 6. Clause-level attribution

Each review is split at sentence ends (`.` `!` `?` `;`) and again before `but`, `however`,
`although`, `though`, `whereas`, `except`, `while` (`src/sentiment.py`). The model labels each
clause positive, neutral or negative, and each dish takes the label of the clause it is in.

*"The salad was amazing, but the chicken breast was cold and greasy"* becomes two clauses with
opposite labels attributed to different dishes. A star rating cannot express this.

**What the model does not see.** The model was trained on whole reviews, where some words
mean something different from what they mean in one short clause. So before it reads a
clause, three things are hidden:

- **The dish names.** Otherwise a dish is judged by its reputation across all of Bangalore,
  not by what this reviewer said about it.
- **Words about ordering** (`ordered`, `order`, `tried`, `got`). Complaints often begin "I
  ordered ...", so the model learned `ordered` as a negative word (weight +4.1), and *"I
  ordered veg biryani."* would count as a complaint.
- **A leading `but`.** The model learned it as a sign of a mixed 3-star review (+3.78 for
  neutral), which would pull *"but the chicken was cold"* towards neutral.

**A clause takes a side only when the model is clearly on it.** The clause's score is
P(positive) − P(negative), from −1 to +1. At **+0.4 or more** the dish is liked, at **−0.4 or
less** it is not liked, and in between the clause takes no side. Whole reviews are labelled with
the model's answer as it is, because whole reviews are what it was trained and tested on.

If nothing the model knows is left after hiding, the clause says nothing. A dish in such a
clause takes the next clause's opinion, as long as that clause names no other dish and is about
the food, not the delivery: in *"We ordered biryani and kulcha. All good."*, both dishes are
liked. 21 of 915 dish mentions take their opinion this way.

When a review mentions the same dish more than once, the last mention that takes a side is
its vote, so each review counts once per dish.

**How we checked these rules.** There are no clause-level labels, so we used the star ratings
as a rough check: a dish marked liked inside a 1-star review, or not liked inside a 5-star
review, is very likely an error. Out of 747 dish opinions:

| Rules | Liked in a 1-star review | Not liked in a 5-star review | Total |
|---|---|---|---|
| VADER (the earlier version of the website) | 25 | 19 | 44 |
| Our model, no hiding, no 0.4 rule | 16 | 36 | 52 |
| **Our model, final rules** | **9** | **12** | **21** |

The cost is that fewer opinions take a side (554 of 747, against 649 with VADER), so 34
dishes are ranked instead of 40. The 0.4 cut-off was chosen with this same check, so these
numbers favour it; they show the rules remove obvious errors, not that clause accuracy is
measured.

**Measured effect** on the three website restaurants (1,400 reviews → 1,321 after cleaning →
416 reviews naming a dish → 747 dish opinions):

- On **246 of 747 dish opinions (32.9%)** the clause's label differs from what the review's
  star rating alone would say.
- **19 reviews** like one dish and dislike another.

---

## 7. Website

Plain HTML, CSS and JavaScript, no framework. `python run_pipeline.py` runs all six stages and
writes the results to `output_project/web/data.js`; the pages read that file. Start it with
`start.bat` (or `python src/app.py`), which serves the folder on <http://localhost:8000> with
browser caching turned off, so a refresh after a rebuild always shows the new numbers. A static
copy is also online on Vercel.

**Home page** (`index.html`) — one card per restaurant, with its share of positive reviews and
how many reviews were read.

**Restaurant page** (`restaurant.html`) — the restaurant's details and stats, then its menu
ranked from most liked to least liked. Each dish shows how many people liked it ("7 of 10
liked it") and a tag: **Customers love it** (8 in 10 or more liked it), **Mixed opinions**
(4–6 in 10) or **Needs work** (4 in 10 or fewer). Dishes with fewer than 4 opinions are listed
separately as too little to judge. Clicking a dish opens every review that mentions it, with
the dish highlighted green (liked) or red (not liked). At the bottom, "Reviews left out" lists
every review the cleaning step removed, with the reason.

The page answers one question — *which dishes are good?* — so model diagnostics stay in this
report, not on the website.

---

## 8. Results

| Restaurant | Reviews (after cleaning) | Positive reviews | Dishes ranked |
|---|---|---|---|
| Biriyani Nights | 501 | 36% | 8 |
| Night Food Joint | 422 | 26% | 9 |
| BOX8- Desi Meals | 398 | 57% | 17 |

The ordering matches the platform's own `rate` values (3.2 / 2.9 / 4.1) despite never using
them, which is an independent sanity check.

**A second check on unseen data.** On the website's reviews — held out of training — the
model's whole-review label agrees with the star rating on **90.1%** of 1,147 reviews (3-star
reviews excluded). When it says positive it is right 97.7% of the time; it finds 82.2% of the
positive reviews.

---

## 9. Limitations

- **Neutral-class F1 of 0.582.** Documented above, with a failed remediation attempt.
- **The model was trained on whole reviews but reads clauses.** Hiding dish names and
  ordering words and the 0.4 rule remove most obvious errors (section 6), but some remain,
  and about a quarter of dish opinions take no side. We have no clause-level labels, so clause
  accuracy is not measured directly; labelling a sample of clauses by hand would fix this.
- **Sampling bias.** Text reviewers are ~6% of raters and skew toward strong opinions.
- **Dish coverage.** 905 of 1,321 cleaned reviews mention no dish; they count towards the
  restaurant's positive-review share only. Our sample restaurants are delivery-led, so service
  complaints dominate.
- **No manual audit** of dropped rows, so filter precision is unmeasured.
- **The 15-character threshold** (training corpus) and the 2-word threshold (website) **are
  unvalidated** by ablation.
- **No timestamps**, so no temporal analysis.
- **Weak supervision only** for dish extraction; we report no precision/recall for it. A
  labelled evaluation set such as SemEval-2016 Task 5 would fix this.

---

## 10. Reproducing

```bash
py -3.10 -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt

cd src
../.venv/Scripts/python build_corpus.py      # clean the full Zomato file (~10 min)
../.venv/Scripts/python train_sentiment.py   # train and evaluate the model
cd ..
.venv/Scripts/python run_pipeline.py         # the three restaurants -> web/data.js

start.bat                                    # serve http://localhost:8000
```

`build_corpus.py` needs the Kaggle file at `data_raw/zomato.csv`; the cleaned corpus and the
trained model are already in `output_project/`, so the last two commands work without it.
The three restaurants' reviews are in `output_project/data/top3_restaurants_reviews.csv`.

All generated artefacts are written under `output_project/`; nothing is written beside the
source code, and everything there is regenerable from the raw dataset.
