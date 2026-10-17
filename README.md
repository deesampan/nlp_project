# ResRec — Restaurant Recommendation From Reviews

NLP group project · Deesampan Vongsurit (6510766) · Wattanan Jiratriluk (6520214)

Reads 1,400 Zomato reviews of three Bangalore restaurants, finds the dishes each review talks
about, decides whether the reviewer liked each dish, and shows the result as a website: for
every dish, how many people liked it. Live copy: <https://resrec.vercel.app>

## Run it

| To… | Do this |
|---|---|
| see the website | double-click `output_project/web/index.html` (no install, no server) |
| rebuild its numbers | double-click `start.bat`, or `.venv\Scripts\python src\run_pipeline.py` then refresh the page |
| retrain the model (~1 min) | `.venv\Scripts\python src\train_model.py` |
| set up a new PC (once) | `py -3.10 -m venv .venv` then `.venv\Scripts\pip install -r requirements.txt` |

**Proof the website really uses NLP.** Open `output_project/data/site_reviews.csv` in a text editor
(not Excel — Excel cuts long cells). Change `gulab jamun is mouth watering and tasty af!` to
`gulab jamun is stale and tasteless!` and double-click `start.bat`. On Biriyani Nights, Gulab Jamun
drops from **8 of 11** to **7 of 11** liked. Undo with `git checkout output_project/data/site_reviews.csv`.

## Files

| File | What it is |
|---|---|
| `src/run_pipeline.py` | the 6 NLP stages: reviews in → `web/data.js` out |
| `src/train_model.py` | cleans the full Kaggle corpus, picks the 3 restaurants, trains and tests the model |
| `output_project/web/index.html` | the whole website: page, style and script in one file |
| `output_project/web/data.js` | the numbers the page shows (written by `run_pipeline.py`) |
| `output_project/web/img/` | 6 dish photos |
| `output_project/data/site_reviews.csv` | input: 1,400 reviews of the 3 restaurants |
| `output_project/data/site_restaurants.json` | input: their menus and details |
| `output_project/data/reviews_clean.csv` | 134,612 cleaned, star-labelled reviews the model learns from |
| `output_project/models/sentiment_tfidf_lr.pkl` | the trained model |
| `output_project/results/model_metrics.json` | accuracy, per-class scores, the words the model relies on |
| `output_project/results/cleaning_funnel.csv` | reviews left after each step of cleaning the corpus |
| `output_project/results/confusion_matrix.png` | which labels the model mixes up |
| `output_project/reports/` | `report.md`, `presentation.pptx`, `defense_guide_th.pdf` (+ its `.html` source) |

`data_raw/zomato.csv` (548 MB, [Kaggle](https://www.kaggle.com/datasets/himanshupoddar/zomato-bangalore-restaurants))
is only needed to redo steps 1–2 of `train_model.py`. It is not in git.

## How it works — `src/run_pipeline.py`

| Stage | What happens | Code |
|---|---|---|
| 1 Load | read the reviews and menus | `load()` line 42 |
| 2 Clean | fix the text (prefix, broken characters, emoji, links, "soooo"), then drop noise: **N1** empty, **N2** duplicate, **N3** under 2 words, **N4** under 70% Latin letters | `clean_text()` 59, rules at 90 |
| 3 Dishes | match the restaurant's menu against the words of each review; spellings unified, small typos allowed, longest name wins | `dish_list()` 135, `find_dishes()` 155 |
| 4 Opinion | split the review into clauses at `. ! ? ;` and before *but / however / although…*; hide the dish name and "ordered"; the model gives each clause a score from −1 to +1; ±0.4 or more takes a side | `clauses()` 229, `attribute()` 248 |
| 5 Count | one vote per review per dish; tags: ≥80% liked "Customers love it", ≤40% "Needs work", in between "Mixed opinions" | `count_dishes()` 286 |
| 6 Export | write `web/data.js` | `export()` 325 |

The model (`src/train_model.py`): TF-IDF turns each review into word weights, logistic
regression learns which words mean positive, neutral or negative from 90,704 star-rated reviews.
It gets **82.2%** right on 26,678 test reviews; the ready-made VADER gets 72.7%. The website's three
restaurants are held out of training.

## Tools we use

Python libraries (versions in `requirements.txt`):

| Tool | What it does here | Where |
|---|---|---|
| **scikit-learn** | `TfidfVectorizer` turns text into word weights; `LogisticRegression` is the sentiment model; `train_test_split`, `accuracy_score`, `f1_score`, `classification_report`, `ConfusionMatrixDisplay` test it | imported `train_model.py:29-32`; model built `:208-211`; split `:226-227`; tested `:231-232`, `:248`, `:253`. Used on reviews in `run_pipeline.py:220` (`transform`) and `:223` (`predict_proba`) |
| **RapidFuzz** | `fuzz.ratio` lets "biryanni" match "biryani" | imported `run_pipeline.py:23`, used `:152` |
| **vaderSentiment** | ready-made sentiment word list, used only as the baseline our model beats | imported `train_model.py:33`, used `:217-218` |
| **ftfy** | repairs broken text encoding in the corpus | imported `train_model.py:25`, used `:83` |
| **langdetect** | keeps English reviews only | imported `train_model.py:28`, seed `:44`, used `:96` |
| **matplotlib** | draws the confusion matrix | imported `train_model.py:26-27`, saved `:255` |
| numpy | installed with scikit-learn; not imported by our code | — |

Python's own modules: `re` (all cleaning and clause rules, e.g. `run_pipeline.py:59-70`, `:199-202`),
`unicodedata` (removes emoji/accents, `run_pipeline.py:62`), `pickle` (saves/loads the model,
`train_model.py:257`, `run_pipeline.py:210`), `csv` / `json` (files), `hashlib` (finds duplicate
reviews, `train_model.py:69`), `ast` (reads the Kaggle file's lists, `train_model.py:53`, `:165`),
`html` (decodes `&amp;`, `train_model.py:83`).

The website uses no library: plain HTML, CSS and JavaScript (Poppins font from Google Fonts).
