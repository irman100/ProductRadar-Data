#!/usr/bin/env python3
"""Prepare missing-image review queue. Never invent or download merchant photos."""
import argparse
from pathlib import Path
from audit_images import ROOT, read, write, now, suspicious

def build(catalog, index):
    items = []
    for p in catalog["products"]:
        pid = p["id"]
        i = index["items"].get(pid, {})
        image = i.get("image_url") or p.get("image_url")
        status = i.get("primary_image_audit", {}).get("status")
        fallback = i.get("fallback_image_url") or p.get("fallback_image_url")
        if image and not suspicious(image) and status not in ("broken_source", "needs_review", "access_unverified", "missing"):
            continue
        if fallback and i.get("fallback_image_audit", {}).get("status") == "ok":
            continue
        items.append({"product_id": pid, "name": p["name"], "sku": p.get("sku"),
            "merchant_url": p["url"], "primary_image_url": image,
            "reason": "missing" if not image else ("suspect_metadata" if suspicious(image) else status),
            "fallback_image_url": fallback,
            "suggested_asset_path": "assets/fallback-images/" + pid + ".webp",
            "allowed_types": ["official_backup", "licensed_copy", "synthetic_backup"],
            "next_action": "Find exact model photo and verify reuse permission; otherwise create clearly labeled illustrative backup.",
            "synthetic_label": "Иллюстрация, не оригинальное фото товара",
            "exact_photo_required_for_verified": True})
    return {"schema_version": "1.0", "generated_at": now(), "count": len(items), "items": items}
def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output", type=Path, default=ROOT / "data/quality/fallback_manifest.json")
    args = ap.parse_args()
    out = build(read(ROOT / "data/catalog/unified.json"), read(ROOT / "data/catalog/images.json"))
    write(args.output, out)
    print(f"Fallback review queue: {out['count']}")
if __name__ == "__main__":
    main()
