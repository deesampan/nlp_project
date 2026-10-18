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

Our classifier reaches **82.2% accuracy / 77.4% macro-F1** on three-class sentiment, against
72.7% for the ready-made VADER. It almost never mistakes a positive review for a negative one
(1.3% of test reviews). The website's three restaurants are held out of training.

The whole project is two Python files and one web page: `src/train_model.py` makes the model,
`src/run_pipeline.py` runs the six NLP stages, and `output_project/web/index.html` shows the result.

---

## 1. Problem

Feedback is unstructured and does not scale to manual reading. Menu decisions get made on
intuition: weak dishes stay on the menu, strong dishes go unpromoted.

A single sentence can praise one dish and condemn another, so the unit of opinion is not the
review — it is the dish mention inside it. That is what makes this an NLP problem rather than
a spreadsheet problem.

**Objective.** Convert a corpus of restaurant reviews into a per-dish recommendation: which
dishes customers love, which get mixed opinions, and which need work.

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

**Zomato Bangalore Restaurants** (Kaggle), 51,717 rows × 17 columns, 548 MB. Source, licence
and every tool we downloaded are listed in Appendix A.

| Property | Value |
|---|---|
| Unique restaurants (`name` + `address`) | 12,494 |
| Review tuples in `reviews_list` | 1,317,782 |
| Unique reviews after deduplication | 143,789 |
| Clean, labelled corpus (`output_project/data/reviews_clean.csv`) | **134,612** |
| Used for training (website's 3 restaurants held out) | **133,389** |
| Website input (`output_project/data/site_reviews.csv`) | 1,400 reviews of the 3 restaurants with the most reviews |
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
flip. We therefore work with the three restaurants with the most reviews, and a dish is ranked
only once **at least 4 reviews take a side on it**. Dishes below that are listed separately as
"too little to judge".

---

## 3. Noise and how we remove it

### Noise depends on the task

A review reading *"parking was impossible and the waiter was rude"* is a perfectly good review.
For **our** task — rating dishes — it says nothing. It is noise *for this task*, not noise in
general. So we never delete non-food reviews: they are kept and counted as read, but they give
no vote: the restaurant's score and every dish's score come only from opinions about dishes.
Whether a review is about food is decided *after* looking for dishes in it, not before.

### What the noise is, measured on our data

| Type | Treatment | Measured |
|---|---|---|
| Duplicate reviews | delete | **1,317,782 → 143,789 (89.1% removed)** |
| Boilerplate / spam | delete | 3,734 rows; one text posted at **496 different restaurants** |
| Too short, too long or no letters | delete | 2,765 rows outside 15–5,000 characters |
| Non-English | delete | 2,671 rows |
| Zomato's `RATED` prefix | strip | on **99.9%** of reviews |
| Line breaks inside reviews | strip | on **99.9%** of reviews |
| Broken characters (`â€™` for `'`) | repair | **6.0%** of reviews |
| Extreme length | delete | longest single "review" is **39,312 characters** |
| Spelling variants | unify | `Panneer` / `Panner` / `Paneer`; `Biriyani` / `Biryani` |
| Non-food content | **keep, no dish vote** | 905 of the 1,321 website reviews mention no dish |

### The duplication trap

**89.1% of the corpus is duplicated** — by far the largest source of noise, and easy to miss
in two ways.

**Trap 1 — the obvious key fails silently.** All 51,717 `url` values are unique, so
deduplicating on `url` removes nothing and reports success. Zomato appends a `?context=` query
string for each category listing, so the same restaurant appears under Buffet, Delivery,
Dine-out and so on, each with a different URL.

**Trap 2 — the obvious fix loses data.** Keeping one row per `(name, address)` collapses 51,717
rows to 12,494 restaurants but drops **32,803 unique reviews**, because the category listings
hold *partly different* review sets.

The correct order: **split every row into single reviews first, then remove repeats of the
same `(restaurant, review text)`.** Getting it wrong inflates every dish count roughly 9×, and
unevenly, so it reorders the rankings without any error appearing.

### Stopword removal can flip sentiment

`not`, `no`, `never` and `nor` are in scikit-learn's default stopword list. Strip them and
*"the biryani was **not** good"* becomes *"biryani good"*. We keep 23 such words
(`KEEP_WORDS`, `src/train_model.py` line 190) and measured the difference with two otherwise
identical models:

| Stopword list | Accuracy | Macro F1 |
|---|---|---|
| Keeping `not`, `no`, `never` … | **82.2%** | **77.4%** |
| scikit-learn default | 80.0% | 74.9% |
| **Cost of stripping them** | **−2.1 pts** | **−2.5 pts** |

The trained model shows why: `not` (+8.18) and `not good` (+6.15) push towards **negative**,
while `not bad` (+4.12) and `not disappointed` (+6.17) push towards **positive**. Delete `not`
and these collapse into the same words.

Emoji are a smaller case of the same problem: in a short review an emoji can be the only sign
of opinion, but TF-IDF only reads words, so our model cannot use them. The website's cleaning
removes them; this is a known limitation.

### Cleaning the training corpus — `src/train_model.py`, step 1

| # | Step | Rows left | Removed |
|---|---|---|---|
| 1 | Rows in the Kaggle file → split into single reviews | 1,317,782 | — |
| 2 | Remove repeats of the same review at the same restaurant | 143,789 | **−1,173,993** |
| 3 | Remove boilerplate (same text at more than 5 restaurants) | 140,055 | −3,734 |
| 4 | Repair text (`ftfy`, `&amp;`, `RATED`, links, e-mails, phone numbers), then keep 15–5,000 characters with letters | 137,290 | −2,765 |
| 5 | Keep English only (`langdetect`, fixed seed) | 134,619 | −2,671 |
| 6 | Label from the review's own stars, drop reviews without stars | **134,612** | −7 |

Then each review is normalised for the model: lower-case, "soooo" → "soo", "wasn't" → "was
not" (`normalise()`, `src/run_pipeline.py` line 193; the website uses the same function).
Counts are saved in `output_project/results/cleaning_funnel.csv`.

**Removing repeats is 99.2% of everything removed.** All other filters together remove 9,177
rows. The boring step matters most. Final labels: positive 81,213 (60.3%), negative 28,364
(21.1%), neutral 25,035 (18.6%).

### Cleaning the website's reviews — `src/run_pipeline.py`, stage 2

The three restaurants on the website go through a shorter filter. The text is first repaired
(`clean_text()`, line 59): the `RATED` prefix, broken characters, emoji, links, repeated
letters and punctuation ("soooo good!!!" → "soo good!"). Then four rules decide what is noise
(line 90):

| Rule | Removed | Left |
|---|---|---|
| Raw reviews | | 1,400 |
| N1 Empty after cleaning (only emoji, symbols or the `RATED` prefix) | 6 | 1,394 |
| N2 Duplicate review (same text, same restaurant) | 3 | 1,391 |
| N3 Too short (fewer than 2 words) | 70 | 1,321 |
| N4 Not English (under 70% Latin characters) | 0 | 1,321 |

Every removed review is kept with its reason and listed at the bottom of each restaurant's page
under "Reviews left out", so the cleaning can be checked by eye.

### How we know the cleaning worked

1. **Counts at every step** — the two tables above, each with a reason.
2. **Effect on the result** — the stopword experiment measures a cleaning decision by how much
   the model's accuracy changes. It is the strongest evidence we have.
3. **Manual audit** — not done yet; see Limitations.

---

## 4. Dish extraction

**Off-the-shelf NER does not detect dishes.** spaCy's pretrained models recognise `PERSON`,
`ORG`, `GPE` and `DATE`; there is no `FOOD` entity type. Running NER over *"the chicken
biryani was dry"* returns nothing useful. Our original proposal said NER, and that was wrong.

Training a dish NER would require span-annotated data we do not have. We use **dictionary
matching** instead (`src/run_pipeline.py`, stage 3). Each restaurant gets its own dish list:

1. Its **Zomato menu** plus its `dish_liked` tags, plus 20 common dishes (biryani, kebab,
   naan, …) that people mention without using the menu's exact name (`dish_list()`, line 135).
2. **Longest match wins**, so `chicken biryani` is found instead of `biryani` (`find_dishes()`,
   line 155).
3. **Spelling variants are merged** — `Biriyani`/`Briyani` → `biryani`, `Panner` → `paneer` —
   and long words (6+ letters) also match small typos (RapidFuzz similarity of 88 or more,
   line 152).
4. **The restaurant's own name is not a dish**, so "Biriyani Nights" does not count as biryani.

`dish_liked` is **weak supervision, not ground truth**: it covers only 36.9% of restaurants,
attaches to the restaurant rather than the review, and its terms are coarse (`pasta`,
`burgers`, `cocktails` are categories, not menu items). We use it only as extra dish names.

---

## 5. Sentiment model

### Why we trained our own

The corpus carries **free per-review labels** — every review has its own star rating — so
training cost nothing in annotation. Labels: positive ≥ 4.0, neutral 3.0–3.5, negative ≤ 2.5.

We chose **TF-IDF + logistic regression** for explainability (`src/train_model.py`, step 3).
TF-IDF turns each review into word weights: a word counts more the more often it appears in this
review, and less the more reviews it appears in overall. Single words and pairs of words
("not good") are both used. Logistic regression learns one weight per word for each label,
adds them up, and turns the sums into probabilities.

**The learned weights are the explanation.** No deep model offers this as directly.

### Results

**The website's restaurants are held out.** Their 1,223 reviews are removed before training, so
the model never scores a review it has already seen together with its star rating. The other
133,389 reviews are split: 90,704 to learn from, 26,678 to test on, and 16,007 kept aside as a
validation set so that trying ideas never touches the test set.

| System | Accuracy | Macro F1 |
|---|---|---|
| Always say the most common label (positive) | 60.5% | 25.1% |
| VADER (ready-made word list, no training) | 72.7% | 54.3% |
| **Our model: TF-IDF + logistic regression** | **82.2%** | **77.4%** |
| Same, but with scikit-learn's default stopwords | 80.0% | 74.9% |

Per class: negative F1 **0.847**, positive F1 **0.893**, neutral F1 **0.582**. All numbers are
in `output_project/results/model_metrics.json`.

### What the model learned

| Label | Strongest words |
|---|---|
| Negative | `worst` +12.99, `pathetic` +10.01, `not` +8.18, `bad` +8.10, `horrible` +7.68, `not good` +6.15 |
| Neutral | `good` +5.32, `decent` +4.86, `average` +4.85, `okay` +3.97, `ok` +3.86, `okayish` +3.81 |
| Positive | `awesome` +9.94, `best` +9.73, `amazing` +9.61, `delicious` +8.64, `loved` +8.49, `excellent` +7.40 |

### The weak point: neutral

Neutral is the weak class at F1 0.582. The confusion matrix
(`output_project/results/confusion_matrix.png`) shows why: the model **almost never confuses
positive with negative** — only 351 of 26,678 test reviews (**1.3%**) — while 1,215 neutral
reviews are read as positive and 1,809 positive as neutral. All the error sits on the neutral
boundary: a 3-star review is often not a distinct opinion but something in between. For the
website's question — *liked or not liked* — this matters less, because the two sides are
almost never swapped.

---

## 6. Clause-level attribution

Each review is split at sentence ends (`.` `!` `?` `;`) and again before `but`, `however`,
`although`, `though`, `whereas`, `except`, `while` (`clauses()`, `src/run_pipeline.py` line 229).
The model labels each clause, and each dish takes the label of the clause it is in
(`attribute()`, line 248).

*"The salad was amazing, but the chicken breast was cold and greasy"* becomes two clauses with
opposite labels attributed to different dishes. A star rating cannot express this.

**What the model does not see.** The model was trained on whole reviews, where some words
mean something different from what they mean in one short clause. So before it reads a
clause, three things are hidden (lines 199–202):

- **The dish names.** Otherwise a dish is judged by its reputation across all of Bangalore,
  not by what this reviewer said about it.
- **Words about ordering** (`ordered`, `order`, `tried`, `got`). Complaints often begin "I
  ordered …", so the model learned `ordered` as a negative word (weight +4.1), and *"I
  ordered veg biryani."* would count as a complaint.
- **A leading `but`.** The model learned it as a sign of a mixed 3-star review (+3.78 for
  neutral), which would pull *"but the chicken was cold"* towards neutral.

**A clause takes a side only when the model is clearly on it.** The clause's score is
P(positive) − P(negative), from −1 to +1. At **+0.4 or more** the dish is liked, at **−0.4 or
less** it is not liked, and in between the clause takes no side (`CLAUSE_MARGIN`, line 34).
Whole reviews are labelled with the model's answer as it is, because whole reviews are what it
was trained and tested on.

If nothing the model knows is left after hiding, the clause says nothing. A dish in such a
clause takes the next clause's opinion, as long as that clause names no other dish and is about
the food, not the delivery: in *"We ordered biryani and kulcha. All good."*, both dishes are
liked. 21 of 915 dish mentions take their opinion this way.

When a review mentions the same dish more than once, the last mention that takes a side is
its vote, so each review counts once per dish (`vote()`, line 270).

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

One file, `output_project/web/index.html`: page, style and script together, plain HTML, CSS and
JavaScript with no framework. Its numbers come from `output_project/web/data.js`, which
`src/run_pipeline.py` writes. It opens by double-click, with no server; `start.bat` rebuilds
`data.js` and opens the page. A static copy is online at <https://resrec.vercel.app>.

**Home view** (`index.html`) — one card per restaurant: how many of the opinions on its dishes
liked the food ("52% liked the food"). Service complaints do not count.

**Restaurant view** (`index.html#biriyani-nights`) — the restaurant's details and stats, then its
menu ranked from most liked to least liked. Each dish shows how many people liked it ("7 of 10
liked it") and a tag: **Customers love it** (8 in 10 or more liked it), **Mixed opinions**
(4–6 in 10) or **Needs work** (4 in 10 or fewer). Dishes with fewer than 4 opinions are listed
separately as too little to judge. Clicking a dish opens every review that mentions it, with
the dish highlighted blue (liked) or red (not liked). At the bottom, "Reviews left out" lists
every review the cleaning step removed, with the reason.

The page answers one question — *which dishes are good?* — so model diagnostics stay in this
report, not on the website.

---

## 8. Results

| Restaurant | Reviews (after cleaning) | Liked the food (opinions on dishes) | Dishes ranked |
|---|---|---|---|
| Biriyani Nights | 501 | 52% (106 of 202) | 8 |
| Night Food Joint | 422 | 38% (42 of 111) | 9 |
| BOX8- Desi Meals | 398 | 81% (196 of 241) | 17 |

The ordering matches the platform's own `rate` values (3.2 / 2.9 / 4.1) despite never using them.
Counting whole reviews instead, service complaints pulled these down to 36% / 26% / 57%.

**A second check on unseen data.** On the website's reviews — held out of training — the
model's whole-review label agrees with the star rating on **90.1%** of 1,147 reviews (3-star
reviews excluded; `star_check()`, `src/run_pipeline.py` line 307). When it says positive it is
right 97.7% of the time; it finds 82.2% of the positive reviews.

---

## 9. Limitations

- **Neutral-class F1 of 0.582.** The model separates liked from not liked well, but not
  "in between".
- **The model was trained on whole reviews but reads clauses.** Hiding dish names and
  ordering words and the 0.4 rule remove most obvious errors (section 6), but some remain,
  and about a quarter of dish opinions take no side. We have no clause-level labels, so clause
  accuracy is not measured directly; labelling a sample of clauses by hand would fix this.
- **Emoji are ignored.** TF-IDF only reads words.
- **Sampling bias.** Text reviewers are ~6% of raters and skew toward strong opinions.
- **Dish coverage.** 905 of 1,321 cleaned reviews mention no dish, so they give no vote to any
  dish or to the restaurant's score. Our sample restaurants are delivery-led, so service
  complaints dominate.
- **No manual audit** of removed reviews, so the filters' precision is unmeasured.
- **The 15-character threshold** (training corpus) and the 2-word threshold (website) **are
  unvalidated** by ablation.
- **Language filtering is all-or-nothing.** Reviews mixing English with Kannada or Hindi
  written in Latin letters may be dropped from the training corpus.
- **Spelling variants are a hand-written list** (`SPELLING`, `src/run_pipeline.py`); it will
  miss variants we did not notice.
- **No timestamps**, so no temporal analysis.
- **Weak supervision only** for dish extraction; we report no precision/recall for it. A
  labelled evaluation set such as SemEval-2016 Task 5 would fix this.

---

## 10. Reproducing

```bash
py -3.10 -m venv .venv
.venv\Scripts\pip install -r requirements.txt

.venv\Scripts\python src\train_model.py     # model, metrics, confusion matrix (~1 min)
.venv\Scripts\python src\run_pipeline.py    # the six stages -> output_project\web\data.js
```

Then double-click `output_project/web/index.html`. `train_model.py` re-cleans the corpus and
re-picks the three restaurants only when the Kaggle file is at `data_raw/zomato.csv`; otherwise
it trains from the committed `reviews_clean.csv`. Training is seeded, so it reproduces the same
model and the same numbers. Everything generated is written under `output_project/`.

---

## 11. Use of AI tools

We used an AI coding assistant, **Claude Code** (Anthropic's Claude), throughout this project.
It wrote most of the code in `src/`, built the website, ran the experiments, and drafted parts
of this report and the Thai defence guide (`defense_guide_th.pdf`). The instructions we gave it
are in `CLAUDE.md` in the repository. We set the problem, chose the dataset and made the scope
decisions — dropping ABSA, no scraping, one trained model, holding the website's restaurants
out of training — and we reviewed the results. No AI service runs inside the pipeline or the
website: every sentiment label comes from the TF-IDF + logistic regression model we trained,
and every number in this report comes from running the code in the repository. We are
responsible for all of it and can explain each part.

---

## Appendix A. Sources and licences

### Dataset

| | |
|---|---|
| Title | **Zomato Bangalore Restaurants** ("Restaurants of Bengaluru") |
| Author | Himanshu Poddar (`himanshupoddar`), Kaggle, version 1, updated 2019-03-31 |
| URL | https://www.kaggle.com/datasets/himanshupoddar/zomato-bangalore-restaurants |
| Size | 574,072,999 bytes (548 MB), one file `zomato.csv`, 51,717 rows × 17 columns |
| Licence | **"Data files © Original Authors"** — not an open licence |

Our local `data_raw/zomato.csv` is exactly 574,072,999 bytes, the size Kaggle's API reports, so
we used the unmodified file. The data was scraped from Zomato around March 2019 by the Kaggle
author; we did not scrape anything. Reviews are Indian-English reviews from one city in 2019.

**The licence and our repository.** The raw `zomato.csv` is never committed. The repository is
public, and it does contain derived files with review text — `reviews_clean.csv` (134,612
reviews), `site_reviews.csv` and the website's `data.js`. Publishing these goes beyond what the
licence clearly allows; the team made the repository public knowingly and accepts that risk.

### Tools we downloaded

No pre-trained sentiment model, transformer or external API is used; the sentiment model is
trained by us. Versions are pinned in `requirements.txt`.

| Package | Version | Licence | Used for | Where |
|---|---|---|---|---|
| scikit-learn | 1.5.2 | BSD-3-Clause | TF-IDF + logistic regression, train/test split, metrics, confusion matrix | `train_model.py` 29–32, 208–211, 226–255; `run_pipeline.py` 220, 223 |
| RapidFuzz | 3.14.5 | MIT | matching misspelt dish names | `run_pipeline.py` 23, 152 |
| vaderSentiment | 3.3.2 | MIT | the baseline our model is compared with | `train_model.py` 33, 217–218 |
| ftfy | 6.3.0 | Apache-2.0 | repairing broken text encoding | `train_model.py` 25, 83 |
| langdetect | 1.0.9 | MIT / Apache-2.0 (its metadata says both) | keeping English reviews only | `train_model.py` 28, 44, 96 |
| matplotlib | 3.9.2 | PSF-based | drawing the confusion matrix | `train_model.py` 26–27, 255 |
| numpy | 1.26.4 | BSD-3-Clause | installed with scikit-learn | — |

The website loads the Poppins font from Google Fonts (SIL Open Font Licence) and no code library.

### Citations

> Poddar, H. (2019). *Zomato Bangalore Restaurants* [Data set]. Kaggle.
> https://www.kaggle.com/datasets/himanshupoddar/zomato-bangalore-restaurants
> (Data files © Original Authors. Accessed 2026-08-28.)

> Pedregosa, F., Varoquaux, G., Gramfort, A., et al. (2011). Scikit-learn: Machine Learning in
> Python. *Journal of Machine Learning Research*, 12, 2825–2830.

> Hutto, C. J., & Gilbert, E. (2014). VADER: A Parsimonious Rule-based Model for Sentiment
> Analysis of Social Media Text. *Proceedings of the Eighth International AAAI Conference on
> Weblogs and Social Media (ICWSM-14)*, Ann Arbor, MI.
