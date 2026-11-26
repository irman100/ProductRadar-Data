#!/usr/bin/env python3
"""Compute observed mean retail offer prices, NEVER realized transaction prices."""
import argparse
import datetime as dt
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from pathlib import Path
from urllib.parse import urlsplit
from audit_images import read, write

ROOT = Path(__file__).resolve().parents[1]
def summarize(observations, as_of, max_age=7):
    latest = {}
    for item in observations:
        try:
            if (item.get("match_confidence") != "exact_sku" or item.get("currency") != "RUB"
                or item.get("price_type") != "public_unconditional_retail_offer"
                or item.get("in_stock") is not True):
                continue
            url = urlsplit(item["url"])
            platform = item["platform"].strip().casefold()
            date = dt.date.fromisoformat(item["observed_at"][:10])
            price = Decimal(str(item["price_rub"]))
            if (not platform or url.scheme != "https" or not url.hostname or url.username or url.password
                or not price.is_finite() or price <= 0 or not 0 <= (as_of-date).days <= max_age):
                continue
            # One dated observation per independent marketplace; never sum variants.
            prev = latest.get(platform)
            if prev is None or item["observed_at"] > prev["observed_at"]:
                latest[platform] = item
        except (KeyError, ValueError, TypeError, AttributeError, InvalidOperation):
            continue
    chosen = [latest[k] for k in sorted(latest)]
    prices = [Decimal(str(x["price_rub"])) for x in chosen]
    mean = int((sum(prices)/len(prices)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)) if len(prices) >= 2 else None
    return {"average_sale_price_rub": mean, "average_sale_price_currency": "RUB",
            "average_sale_price_method": "mean_of_exact_sku_observed_retail_offers" if mean is not None else None,
            "average_sale_price_sample_size": len(prices), "average_sale_price_observed_at": as_of.isoformat(),
            "average_sale_price_note": ("Средняя наблюдаемая розничная цена предложений, не фактическая цена сделок."
                 if mean is not None else "Недостаточно свежих сопоставимых цен точного SKU с независимых площадок."),
            "price_observations_used": chosen,
            "retail_offer_price_min_rub": float(min(prices)) if prices else None,
            "retail_offer_price_max_rub": float(max(prices)) if prices else None,
            "realized_sale_price_verified": False}
def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--observations", type=Path, help="JSON object keyed by product id, each value a list of verified observations")
    ap.add_argument("--as-of", type=dt.date.fromisoformat, default=dt.datetime.now(dt.timezone.utc).date())
    ap.add_argument("--max-age", type=int, default=7)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    path = ROOT / "data/catalog/unified.json"
    catalog = read(path)
    extra = read(args.observations) if args.observations else {}
    ids = {p["id"] for p in catalog["products"]}
    if not isinstance(extra, dict) or set(extra) - ids or any(not isinstance(v, list) or any(not isinstance(x, dict) for x in v) for v in extra.values()):
        ap.error("observations must map existing product ids to lists of objects")
    if args.max_age < 0:
        ap.error("max-age must not be negative")
    count = 0
    for p in catalog["products"]:
        old = p.get("price_observations") or []
        merged = { (x.get("platform"), x.get("url"), x.get("observed_at"), x.get("price_rub")): x
                  for x in old + extra.get(p["id"], []) }
        p["price_observations"] = list(merged.values())
        p.update(summarize(p["price_observations"], args.as_of, args.max_age))
        count += p["average_sale_price_rub"] is not None
    if args.apply:
        write(path, catalog)
    print(f"Average offer prices available: {count}/{len(ids)}; applied={args.apply}")
if __name__ == "__main__":
    main()
