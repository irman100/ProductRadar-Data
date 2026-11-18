#!/usr/bin/env python3
"""Validate cross-market Product Radar candidates without network access."""
import json
import sys
from pathlib import Path
from urllib.parse import urlparse

def https(value):
    if not isinstance(value, str):
        return False
    u = urlparse(value)
    return u.scheme == "https" and bool(u.netloc)

def validate(path):
    root = json.loads(Path(path).read_text(encoding="utf-8"))
    if root.get("market") != "RU":
        raise ValueError("market must be RU")
    items = root.get("items")
    if not isinstance(items, list) or not items:
        raise ValueError("items must be nonempty")
    seen = set()
    for i, p in enumerate(items, 1):
        label = p.get("id", "#" + str(i))
        if label in seen:
            raise ValueError(f"duplicate id {label}")
        seen.add(label)
        for key in ("name", "category", "ru_platform", "ru_sku", "why", "risks", "checked_at"):
            if not isinstance(p.get(key), str) or not p[key].strip():
                raise ValueError(f"{label}: missing {key}")
        for key in ("ru_product_url", "china_offer_url"):
            if not https(p.get(key)):
                raise ValueError(f"{label}: invalid {key}")
        if p.get("ready_to_buy") is True and not (p.get("landed_cost_verified") and p.get("supplier_quote_verified")):
            raise ValueError(f"{label}: cannot be ready to buy without verified quote and landed cost")
        for signal in p.get("signals", []):
            if not https(signal.get("url")) or not signal.get("source") or not signal.get("type") or not signal.get("note"):
                raise ValueError(f"{label}: incomplete signal")
        if not p.get("signals"):
            raise ValueError(f"{label}: no evidence signals")
        if p.get("china_offer_type") not in ("comparable_unbranded_products", "category_analogs_not_same_sku", "comparable_product_not_identical", "exact_sku_verified"):
            raise ValueError(f"{label}: sourcing relationship unknown")
        if p.get("china_offer_type") != "exact_sku_verified" and p.get("china_supplier_verified"):
            raise ValueError(f"{label}: cannot verify original SKU supplier with analog-only link")
    print(f"OK: {len(items)} validated candidate records (structure only, not live checks)")

if __name__ == "__main__":
    validate(sys.argv[1] if len(sys.argv) > 1 else "data/research/multimarket_opportunities_20261118.json")
