"""Stage 2 - preprocess: noise removal, cleaning, tokenisation.

Input is the messiest column (review_text_raw, with the Zomato 'RATED\\n' prefix)
so every cleaning step does visible work. A noise funnel records how many rows
each filter removes.
"""
import re
import unicodedata
import nltk
import pandas as pd
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize

# pip installs NLTK without its data files; fetch them once on first run (needs internet).
for _res, _pkg in [("corpora/stopwords", "stopwords"), ("tokenizers/punkt_tab", "punkt_tab")]:
    try:
        nltk.data.find(_res)
    except LookupError:
        nltk.download(_pkg, quiet=True)

NEGATIONS = {"no", "not", "nor", "don't", "didn't", "wasn't", "isn't", "aren't", "weren't",
             "won't", "wouldn't", "couldn't", "shouldn't", "never", "hadn't", "hasn't", "haven't"}
STOP = set(stopwords.words("english")) - NEGATIONS - {"but", "very", "too", "more", "most", "only"}

CONTRACTIONS = {"n't": " not", "'re": " are", "'s": " is", "'ll": " will", "'ve": " have", "'m": " am", "'d": " would"}


# Runs of double/triple UTF-8 mis-decoding (Ã\x83Ã\x82...). Between two letters it was an apostrophe.
MOJIBAKE = re.compile(r"(?<=[A-Za-z])([ÃÂ\x80-\xff]+)(?=[a-z]\b)|[ÃÂ\x80-\xff]+")


def clean_text(raw: str) -> str:
    """Raw review -> readable cleaned sentence text (case kept for display)."""
    t = str(raw)
    t = re.sub(r"^\s*RATED\s*", "", t)                      # platform prefix
    t = MOJIBAKE.sub(lambda m: "'" if m.group(1) else " ", t)  # triple-encoded ' and emoji bytes
    t = unicodedata.normalize("NFKD", t)
    t = t.encode("ascii", "ignore").decode()                 # emoji / mojibake
    t = re.sub(r"https?://\S+|www\.\S+", " ", t)             # urls
    t = re.sub(r"([!?.])\1+", r"\1", t)                      # !!! -> !   .... -> .
    t = re.sub(r"(\w)\1{2,}", r"\1\1", t)                    # soooo -> soo
    t = re.sub(r"\s*\n+\s*", " ", t)                         # newlines
    t = re.sub(r"(?<=[a-z])([.,!?])(?=[A-Za-z])", r"\1 ", t)  # "food.even" -> "food. even"
    t = re.sub(r"\s+([.,!?])", r"\1", t)                     # "combo ," -> "combo,"
    t = re.sub(r"\s+", " ", t).strip()
    return t


def tokenize(clean: str) -> list[str]:
    t = clean.lower()
    t = re.sub(r"[^a-z0-9'\s.,!?]", " ", t)
    return [w for w in word_tokenize(t) if re.search(r"[a-z0-9]", w)]


def remove_stop(tokens: list[str]) -> list[str]:
    out = []
    for w in tokens:
        w = CONTRACTIONS.get(w, w).strip()
        if w and w not in STOP and len(w) > 1 or w in {"no", "not"}:
            out.append(w)
    return out


def ascii_ratio(raw: str) -> float:
    s = re.sub(r"\s", "", MOJIBAKE.sub("", str(raw)))
    return sum(c.isascii() for c in s) / max(len(s), 1)


def run(df: pd.DataFrame) -> tuple[pd.DataFrame, list[dict], pd.DataFrame]:
    """Returns the kept reviews, the noise funnel, and the removed reviews
    (each with a `reason` column naming the funnel step that dropped it)."""
    funnel = [{"step": "Raw reviews loaded", "removed": 0, "remaining": len(df)}]
    removed = []

    def keep(mask, step):
        nonlocal df
        removed.append(df[~mask].assign(reason=step))
        funnel.append({"step": step, "removed": int((~mask).sum()), "remaining": int(mask.sum())})
        df = df[mask]

    df = df.copy()
    df["clean_text"] = df["review_text_raw"].map(clean_text)

    keep(df["clean_text"].str.len() > 0, "N1 Empty after cleaning")
    keep(~df.duplicated(subset=["restaurant_name", "clean_text"]), "N2 Duplicate reviews")
    keep(df["clean_text"].str.split().str.len() >= 2, "N3 Too short (<2 words)")
    keep(df["review_text_raw"].map(ascii_ratio) >= 0.7, "N4 Non-English / non-Latin")

    df["tokens"] = df["clean_text"].map(tokenize)
    df["tokens_nostop"] = df["tokens"].map(remove_stop)
    return df.reset_index(drop=True), funnel, pd.concat(removed, ignore_index=True)
