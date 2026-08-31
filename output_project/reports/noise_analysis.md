# What is the noise in this data, and how do we remove it?

**Restaurant Recommendation From Reviews** — NLP Group Project
Deesampan Vongsurit (6510766), Wattanan Jiratriluk (6520214)

Dataset: Zomato Bangalore Restaurants (Kaggle), 51,717 rows × 17 columns, 548 MB.

---

## 1. Noise is defined by the task, not by the text

Before listing anything, one distinction decides everything else.

A review reading *"parking was impossible and the waiter was rude"* is a perfectly valid,
well-written, informative review. For **our** task — ranking dishes — it contains zero
signal. It is noise *for this task*, not noise in general.

Our system has two outputs: a **restaurant panel** (overall sentiment) and a **dish panel**
(per-dish sentiment). The same review is **signal for the first and noise for the second**.
So we never delete non-food reviews; we route them. Noise is relative to the question being
asked, and our own interface demonstrates why.

This is also why the relevance filter runs *after* dish extraction, not before. You cannot
decide whether a review is about food until you have looked for dish mentions in it.

---

## 2. What the noise actually is, measured

Every figure below is measured on our dataset, not quoted from a textbook.

| Type | Treatment | Measured in our data |
|---|---|---|
| Duplicate reviews | Delete | **1,317,782 → 143,789 (89.1% removed)** |
| Boilerplate / spam | Delete | 3,734 rows; one text posted at **496 different restaurants** |
| Empty or contentless | Delete | 2,765 rows under 15 characters or non-alphabetic |
| Non-English | Route out | 2,671 rows |
| Platform markers | Normalise | `RATED\n` prefix on **99.9%** of reviews |
| Embedded newlines | Normalise | **99.9%** of reviews |
| Mojibake (`â€™` for `'`) | Normalise | **6.0%** of reviews |
| Extreme length | Delete | longest single "review" is **39,312 characters** |
| Spelling variants | Normalise | `Panneer` / `Panner` / `Paneer`; `Biriyani` / `Biryani` |
| Non-food content | **Route, not delete** | 677 of 1,069 reviews in our sample mention no dish |

### The duplication trap

**89.1% of the corpus is duplicated.** This is by far the largest single source of noise,
and it is easy to miss in two separate ways.

**Trap 1 — the obvious key fails silently.** All 51,717 `url` values are unique, so
deduplicating on `url` removes nothing and reports success. The URLs differ because Zomato
appends a `?context=` query string that encodes the category listing. The same restaurant
appears under Buffet, Delivery, Dine-out and so on, each with a different URL.

**Trap 2 — the obvious fix loses data.** Deduplicating on `(name, address)` and keeping one
row per restaurant collapses 51,717 rows to 12,494 restaurants — but drops **32,803 unique
reviews**, because the different category listings hold *partially different* review sets,
not identical copies.

The correct order is: **explode every row to review level first, then deduplicate on
`(restaurant, review_text)`.** Restaurant-level deduplication must never happen first.

Consequence of getting this wrong: every dish mention count inflated roughly **9×**, with no
error ever surfacing. Because the inflation is not uniform across restaurants, it does not
cancel out — it reorders the rankings.

---

## 3. The two traps in standard cleaning advice

These are the cases where doing what the textbook says actively destroys the data.

### Stopword removal inverts sentiment

`not`, `no`, `never` and `nor` are all in scikit-learn's default English stopword list.
Strip them and *"the biryani was **not** good"* becomes *"biryani good"*. The label flips on
every negated sentence in the corpus.

**We measured this.** Training two otherwise identical models, one with a negation-preserving
stopword list and one with the default:

| Stopword list | Accuracy | Macro F1 |
|---|---|---|
| Negation-preserving | **82.1%** | **77.3%** |
| scikit-learn default | 80.1% | 74.8% |
| **Cost of stripping negations** | **−2.01 pts** | **−2.48 pts** |

The trained model confirms the mechanism independently. Among its strongest learned weights:

- `not` (+7.74) and `not good` (+6.45) → **negative**
- `not bad` (+3.67) → **neutral**
- `not disappointed` (+6.64) → **positive**

Three different sentiments, all carried by the same word. Delete `not` and all three collapse
into one.

### Emoji are signal, not decoration

In a short review the emoji is often the only polarity marker present. We map emoji to tokens
rather than stripping them.

---

## 4. The pipeline

Nine ordered stages. Order matters: deduplicate before cleaning so we do not pay to clean
rows we are about to drop, and filter language before any English-language model touches the
text.

| # | Stage | Action |
|---|---|---|
| 0 | Snapshot | `text_raw` preserved permanently; cleaning is additive |
| 1 | Parse and explode | `reviews_list` → one row per review |
| 2 | Deduplicate | on `(restaurant, review_text)` |
| 3 | Boilerplate removal | drop any text appearing at more than 5 restaurants |
| 4 | Structural clean | `ftfy`, HTML unescape, NFKC, strip markers/URLs/emails/phones |
| 5 | Language filter | `langdetect`, seeded for determinism, English only |
| 6 | Quality filter | drop under 15 or over 5,000 characters, drop non-alphabetic |
| 7 | Normalise | collapse elongations, expand contractions, lowercase |
| 8 | Label | derive sentiment from the review's own star rating |

Two design decisions worth defending:

**Cleaning is additive, never destructive.** `text_raw`, `text_clean` and `text_norm` are
stored side by side, so every filtering decision is reversible and auditable.

**Different models need different cleaning.** A TF-IDF model wants aggressive normalisation;
a transformer wants almost none, because it has its own tokeniser and loses accuracy on
over-cleaned input. Applying one cleaning level to both breaks one of them.

---

## 5. The funnel

| Stage | Rows | Dropped here |
|---|---|---|
| CSV rows | 51,717 | — |
| Review tuples extracted | 1,317,782 | — |
| After deduplication | 143,789 | **−1,173,993** |
| After boilerplate removal | 140,055 | −3,734 |
| After length / quality filter | 137,290 | −2,765 |
| After language filter | 134,619 | −2,671 |
| After labelling | **134,612** | −7 |

**Deduplication removes 99.2% of everything that gets removed.** Every other filter combined
accounts for 9,177 rows — less than 1% of what deduplication alone catches.

This is the most useful thing we learned. The boring stage matters enormously and the
sophisticated stages matter marginally. A team that skipped deduplication and spent its
effort on clever filtering would have produced confidently wrong results.

Final class balance: positive 81,213 (60.3%), negative 28,364 (21.1%), neutral 25,035 (18.6%).

---

## 6. How we know the cleaning worked

Four kinds of evidence, in ascending order of strength.

**1. Row funnel.** The table above — counts in, counts out, and a reason at every stage.

**2. Vocabulary reduction**, decomposed by stage over 143,789 reviews:

| Stage | Vocabulary | Change |
|---|---|---|
| Raw text, case sensitive | 76,914 | — |
| After lowercasing | 57,788 | **−24.9%** |
| After structural cleaning | 57,844 | +0.1% |
| After normalisation | 57,103 | −1.3% |
| **Total** | **57,103** | **−25.8%** |

Note the honest result: **lowercasing accounts for almost the entire reduction**, and
structural cleaning slightly *increases* vocabulary. That is not a failure — `ftfy` repairs
mojibake into real words about as fast as it removes garbage forms. It means vocabulary size
is simply the wrong metric for judging structural cleaning. Its value is making text
parseable, not making it smaller.

**3. Manual audit.** A random sample of dropped rows should be inspected by hand to confirm
they deserved removal. *Not yet performed — see limitations.*

**4. Ablation.** The negation experiment in section 3 is the strongest evidence we have,
because it measures *impact on the downstream task* rather than activity. It is the only
number here that proves a cleaning decision changed the result.

---

## 7. Limitations

- **No manual audit yet.** We have not hand-checked a sample of dropped rows, so we report
  the filters' behaviour but not their precision.
- **The 15-character threshold is unvalidated.** It removes 23% of reviews in our working
  sample. We have not run an ablation to confirm this is not discarding usable signal.
- **Language filtering is all-or-nothing.** Reviews mixing English with transliterated Kannada
  or Hindi are dropped entirely rather than partially recovered.
- **Spelling normalisation is a hand-written list**, not learned. It catches the variants we
  noticed; it will miss others.

---

## 8. Reproducing this

```bash
cd src
../.venv/Scripts/python build_corpus.py     # full cleaning pipeline + funnel
../.venv/Scripts/python vocab_analysis.py   # vocabulary decomposition
```

Outputs land in `output_project/results/`: `cleaning_funnel.csv`,
`vocab_before_after.txt`, and the cleaned corpus at
`output_project/data/reviews_clean.csv`.
