"""ResRec - run the full 6-stage review -> dashboard pipeline.

    .venv/bin/python run_pipeline.py
"""
import csv
from src import load_data, preprocess, dish_extract, sentiment, aggregate, export_web, export_removed
from src.common import RESULTS


def main():
    # 1. collect
    df = load_data.load_reviews()
    rests = load_data.load_restaurants()
    # 2. preprocess
    df, funnel, removed = preprocess.run(df)
    # 3 + 4. dish extraction and dish-level sentiment
    gaz = {name: dish_extract.build_gazetteer(r) for name, r in rests.items()}
    reviews = []
    for row in df.itertuples():
        text = row.clean_text
        cls = sentiment.clauses(text)
        mentions = sentiment.attribute(dish_extract.extract(text, gaz[row.restaurant_name], row.restaurant_name), cls)
        c = sentiment.review_score(text)
        reviews.append({
            "id": int(row.review_id), "restaurant": row.restaurant_name, "rating": float(row.review_rating),
            "raw": row.review_text_raw, "clean": text, "tokens": row.tokens, "tokens_nostop": row.tokens_nostop,
            "compound": round(c, 3), "sentiment": sentiment.label(c), "clauses": cls, "dishes": mentions,
        })
    # 5. aggregate
    dishes = aggregate.dishes(reviews)
    stats = aggregate.restaurant_stats(reviews)
    evaluation = aggregate.weak_label_eval(reviews)
    for name, r in rests.items():
        r["rank"] = int(df.loc[df.restaurant_name == name, "restaurant_rank"].iloc[0])
        r.update(stats.get(name, {}))
    # 6. export
    RESULTS.mkdir(parents=True, exist_ok=True)
    with open(RESULTS / "dish_scores.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=[k for k in dishes[0] if k != "review_ids"])
        w.writeheader()
        w.writerows({k: v for k, v in d.items() if k != "review_ids"} for d in dishes)
    export_web.write({
        "restaurants": sorted(rests.values(), key=lambda r: r["rank"]),
        "dishes": dishes, "reviews": reviews, "funnel": funnel, "evaluation": evaluation,
        "thresholds": {"min_opinions": aggregate.MIN_OPINIONS, "love_it": aggregate.LOVE_IT,
                       "mixed_low": aggregate.MIXED_LOW, "mixed_high": aggregate.MIXED_HIGH},
    })
    export_removed.write(removed)
    for f in funnel:
        print(f"{f['step']:<30} -{f['removed']:<4} -> {f['remaining']}")
    print("reviews naming a dish:", sum(bool(r["dishes"]) for r in reviews), "/", len(reviews))
    print("eval:", evaluation)
    for d in dishes[:25]:
        print(f"{d['restaurant'][:16]:<16} {d['dish']:<28} liked {d['positive']}/{d['opinions']} (+{d['neutral']} no opinion) {d['category']}")


if __name__ == "__main__":
    main()
