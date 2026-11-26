#!/usr/bin/env python3
"""Audit remote image URLs and flag suspicious metadata. Does not store remote images."""
import argparse
import datetime as dt
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

ROOT = Path(__file__).resolve().parents[1]
def read(path):
    return json.loads(path.read_text(encoding="utf-8"))
def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)
def now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
def suspicious(url):
    return bool(url and ("yastatic.net/s3/home-static/" in url.lower() or
        any(x in url.lower().split("?")[0] for x in ("/placeholder.", "/no-image.", "/noimage.", "/logo."))))
def raster_signature(data):
    return (data.startswith(b"\xff\xd8\xff") or data.startswith(b"\x89PNG\r\n\x1a\n")
            or data.startswith((b"GIF87a", b"GIF89a")) or
            (data[:4] == b"RIFF" and data[8:12] == b"WEBP") or
            (data[4:8] == b"ftyp" and data[8:12] in (b"avif", b"avis")))
def probe(url, timeout=12):
    if not url:
        return {"status": "missing"}
    if suspicious(url):
        return {"status": "needs_review", "reason": "generic_or_placeholder_url"}
    try:
        u = urlsplit(url)
        if u.scheme != "https" or not u.hostname or u.username or u.password:
            return {"status": "needs_review", "reason": "invalid_https_url"}
        req = Request(url, headers={"User-Agent": "ProductRadarImageAudit/1.0", "Accept": "image/*"})
        with urlopen(req, timeout=timeout) as response:
            mime = response.headers.get("Content-Type", "").split(";")[0].lower()
            data = response.read(64)
            if not mime.startswith("image/") or not raster_signature(data):
                return {"status": "needs_review", "reason": "not_supported_raster", "mime": mime}
            return {"status": "ok", "mime": mime, "http_status": response.status,
                    "note": "Transport check only; exact SKU, licensing and browser hotlinking not verified"}
    except HTTPError as e:
        return {"status": "broken_source" if e.code in (404, 410) else "access_unverified",
                "http_status": e.code}
    except (URLError, TimeoutError, OSError, ValueError) as e:
        return {"status": "access_unverified", "reason": type(e).__name__}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Update image index audit fields; otherwise report only")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    catalog = read(ROOT / "data/catalog/unified.json")
    path = ROOT / "data/catalog/images.json"
    index = read(path)
    stamp = now()
    records = []
    for p in catalog["products"]:
        i = index["items"].get(p["id"], {})
        records.append((p["id"], i.get("image_url") or p.get("image_url"), i.get("fallback_image_url") or p.get("fallback_image_url")))
    def check(row):
        pid, primary, fallback = row
        return {"product_id": pid, "primary_image_url": primary, "primary": probe(primary),
                "fallback_image_url": fallback, "fallback": probe(fallback) if fallback else {"status": "missing"},
                "checked_at": stamp}
    with ThreadPoolExecutor(max_workers=4) as pool:
        items = list(pool.map(check, records))
    summary = {}
    for item in items:
        status = item["primary"]["status"]
        summary[status] = summary.get(status, 0) + 1
        if args.apply:
            i = index["items"].setdefault(item["product_id"], {})
            i["primary_image_audit"] = item["primary"]
            i["primary_image_last_checked_at"] = stamp
            i["fallback_image_audit"] = item["fallback"]
            i["image_status"] = ("fallback_only" if status != "ok" and item["fallback"]["status"] == "ok" else status)
    output = args.output or ROOT / ("data/quality/image_fallback_audit_" + stamp[:10] + ".json")
    write(output, {"schema_version": "1.0", "generated_at": stamp, "scope": "HTTP and raster signature only",
                   "summary": {"checked": len(items), **summary}, "items": items})
    if args.apply:
        write(path, index)
    print(json.dumps({"checked": len(items), **summary}, ensure_ascii=False))
if __name__ == "__main__":
    main()
