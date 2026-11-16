#!/usr/bin/env python3
"""Validate the publishable Product Radar catalogue.

Only representative merchant photos (not AI art) with an attributable merchant
page are permitted. This checks structure; remote image availability should
also be smoke-tested, as shops may block third-party loading.
"""
import json
import sys
from pathlib import Path
from urllib.parse import urlparse

REQUIRED = (
    "id", "name", "category", "reasoning", "risk", "chinese_query",
    "image_url", "image_source_url", "image_source_title", "image_checked_at"
)


def validate(path: Path) -> list[str]:
    errors = []
    try:
        root = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [f"{path}: invalid JSON: {exc}"]
    products = root.get("products")
    if not isinstance(products, list) or not products:
        return ["products must be a nonempty array"]
    seen_ids: set[str] = set()
    for index, product in enumerate(products, start=1):
        if not isinstance(product, dict):
            errors.append(f"product #{index} must be an object")
            continue
        identifier = product.get("id", f"#{index}")
        for key in REQUIRED:
            if not isinstance(product.get(key), str) or not product[key].strip():
                errors.append(f"{identifier}: missing or empty {key}")
        if identifier in seen_ids:
            errors.append(f"{identifier}: duplicate id")
        seen_ids.add(identifier)
        for key in ("image_url", "image_source_url"):
            value = product.get(key)
            if isinstance(value, str) and value:
                u = urlparse(value)
                if u.scheme != "https" or not u.netloc:
                    errors.append(f"{identifier}: {key} must be a full HTTPS URL")
        if product.get("image_kind") != "merchant_example":
            errors.append(f"{identifier}: expected image_kind=merchant_example")
        if not product.get("image_note"):
            errors.append(f"{identifier}: image provenance note required")
        if isinstance(product.get("image_url"), str) and product["image_url"].lower().endswith(".svg"):
            errors.append(f"{identifier}: SVG drawings are not allowed as product photos")
    return errors


if __name__ == "__main__":
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/research/products.json")
    issues = validate(path)
    if issues:
        print(f"CATALOG REJECTED: {len(issues)} errors")
        print("\n".join(issues))
        raise SystemExit(1)
    print(f"CATALOG OK: {len(json.loads(path.read_text(encoding='utf-8'))['products'])} products with image-source metadata")
