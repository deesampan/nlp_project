"""Stage 1 - collect: load reviews + restaurant metadata/menus."""
import ast
import re
import pandas as pd
from .common import REVIEWS_CSV, RAW_CSV


def load_reviews() -> pd.DataFrame:
    df = pd.read_csv(REVIEWS_CSV)
    # Git on Windows (core.autocrlf) checks the CSV out with \r\n inside reviews; undo it
    # so data.js is byte-identical on every machine.
    df["review_text_raw"] = df["review_text_raw"].str.replace("\r\n", "\n", regex=False)
    df["review_id"] = range(len(df))
    return df


def load_restaurants() -> dict:
    raw = pd.read_csv(RAW_CSV)
    out = {}
    for name, g in raw.groupby("name"):
        menu = set()
        for m in g["menu_item"]:
            try:
                items = ast.literal_eval(m)
            except (ValueError, SyntaxError):
                items = []
            menu |= {re.sub(r"\s*\[.*?\]", "", x).strip() for x in items}
        first = g.iloc[0]
        out[name] = {
            "name": name,
            "location": first["location"],
            "address": first["address"],
            "rest_type": first["rest_type"],
            "cuisines": first["cuisines"],
            "cost_for_two": str(first["approx_cost(for two people)"]),
            "zomato_rate": str(first["rate"]).replace(" ", ""),
            "votes": int(g["votes"].max()),
            "online_order": first["online_order"],
            "book_table": first["book_table"],
            "dish_liked": [d.strip() for d in str(first["dish_liked"]).split(",") if d.strip() and d != "nan"],
            "menu": sorted(menu),
        }
    return out
