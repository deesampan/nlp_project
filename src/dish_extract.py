"""Stage 3 - dish extraction via a per-restaurant gazetteer + fuzzy keyword matching.

Gazetteer = the restaurant's Zomato menu_item list + its dish_liked tags + a small
curated list of generic dishes. Matching is strict: contiguous token sequence,
per-token fuzzy (RapidFuzz ratio) only for tokens of 6+ chars, exact otherwise,
longest match wins.
"""
import re
from rapidfuzz import fuzz
from .common import simple_words, norm_token

SUFFIXES = {"meal", "box", "rice box", "combo"}
GENERIC = ["Biryani", "Chicken Biryani", "Kebab", "Fried Rice", "Noodles", "Paratha",
           "Brownie", "Salad", "Gulab Jamun", "Naan", "Roti", "Paneer", "Wrap", "Sandwich",
           "Raita", "Dal", "Rajma", "Tandoori Chicken", "Chicken Kebab", "Butter Chicken"]
FUZZ_MIN = 88


def _canon(name: str) -> str:
    name = re.sub(r"\s+", " ", name).strip()
    words = name.split()
    while len(words) > 1 and words[-1].lower() in {"meal", "box"}:
        words = words[:-1]
    return " ".join(w.capitalize() if w.islower() else w for w in words)


def build_gazetteer(rest: dict) -> dict[tuple, str]:
    """alias token-tuple -> canonical display name."""
    gaz = {}
    for src in (rest["menu"], rest["dish_liked"], GENERIC):
        for item in src:
            if re.search(r"combo|water|coke|sprite|pepsi", item, re.I):
                continue
            canon = _canon(item)
            key = tuple(simple_words(canon))
            if key and key not in gaz:
                gaz[key] = canon
    # merge canonical names that normalise identically (e.g. Kabab/Kebab)
    seen = {}
    for key, name in gaz.items():
        seen.setdefault(key, name)
        gaz[key] = seen[key]
    return gaz


def _tok_match(a: str, b: str) -> bool:
    if a == b:
        return True
    if len(a) >= 6 and len(b) >= 6:
        return fuzz.ratio(a, b) >= FUZZ_MIN
    return False


def extract(text: str, gaz: dict[tuple, str], restaurant: str = "") -> list[dict]:
    """Return dish mentions with char spans in `text`."""
    spans = [(m.start(), m.end(), norm_token(m.group())) for m in re.finditer(r"[A-Za-z0-9]+(?:'[a-z]+)?", text)]
    toks = [s[2] for s in spans]
    keys = sorted(gaz, key=len, reverse=True)
    used = [False] * len(toks)
    # the restaurant's own name ("Biriyani Nights") is not a dish mention
    name = tuple(simple_words(re.sub(r"[-\d]+", " ", restaurant)))
    for i in range(len(toks) - len(name) + 1 if len(name) > 1 else 0):
        if all(_tok_match(toks[i + j], name[j]) for j in range(len(name))):
            used[i:i + len(name)] = [True] * len(name)
    found = []
    for i in range(len(toks)):
        if used[i]:
            continue
        for key in keys:
            L = len(key)
            if i + L > len(toks) or any(used[i:i + L]):
                continue
            if all(_tok_match(toks[i + j], key[j]) for j in range(L)):
                for j in range(i, i + L):
                    used[j] = True
                found.append({"dish": gaz[key], "start": spans[i][0], "end": spans[i + L - 1][1]})
                break
    return found
