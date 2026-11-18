#!/usr/bin/env python3
"""Find merchant-hosted primary product images without downloading or copying images.

Only public HTML metadata (og:image, twitter:image, Product JSON-LD) is read.
No third-party images are stored. Blocked sites remain unresolved.
"""
from __future__ import annotations
import argparse
import datetime as dt
import html
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import time
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "data/catalog/unified.json"
OUT = ROOT / "data/catalog/images.json"
MAX_BYTES = 1_500_000
UA = "ProductRadarResearchBot/1.0 (public product image metadata; no image downloads)"
ALLOWED_META = {"og:image", "og:image:url", "twitter:image", "twitter:image:src"}

def valid_url(value):
    if not isinstance(value, str):
        return False
    try:
        u = urlsplit(value)
        return u.scheme == "https" and bool(u.hostname) and not u.username and not u.password
    except ValueError:
        return False

class MetaParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.meta = []
        self.jsonld = []
        self.in_jsonld = False
        self.parts = []
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "meta":
            key = (a.get("property") or a.get("name") or "").lower()
            if key in ALLOWED_META and a.get("content"):
                self.meta.append((key, a["content"]))
        if tag == "script" and "ld+json" in (a.get("type") or "").lower():
            self.in_jsonld = True
            self.parts = []
    def handle_data(self, data):
        if self.in_jsonld:
            self.parts.append(data)
    def handle_endtag(self, tag):
        if tag == "script" and self.in_jsonld:
            self.jsonld.append("".join(self.parts))
            self.in_jsonld = False

def ld_images(data):
    if isinstance(data, list):
        for v in data:
            yield from ld_images(v)
    elif isinstance(data, dict):
        kind = data.get("@type", "")
        if kind == "Product" or isinstance(kind, list) and "Product" in kind:
            images = data.get("image", [])
            for x in images if isinstance(images, list) else [images]:
                if isinstance(x, str):
                    yield x
                elif isinstance(x, dict) and isinstance(x.get("url"), str):
                    yield x["url"]
        for k in ("@graph", "mainEntity"):
            if k in data:
                yield from ld_images(data[k])

def discover(url):
    if not valid_url(url):
        return None, "invalid_url"
    try:
        req = Request(url, headers={"User-Agent": UA, "Accept": "text/html,application/xhtml+xml"})
        with urlopen(req, timeout=12) as response:
            if not valid_url(response.url):
                return None, "invalid_redirect"
            ctype = response.headers.get("Content-Type", "").lower()
            if "text/html" not in ctype:
                return None, "not_html"
            raw = response.read(MAX_BYTES + 1)
            # Metadata is normally in the document head. Parse the first MAX_BYTES
            # even if a marketplace sends a very large HTML document.
            content = raw[:MAX_BYTES].decode(response.headers.get_content_charset() or "utf-8", "replace")
        parser = MetaParser()
        parser.feed(content)
        offers = [v for _, v in parser.meta]
        for script in parser.jsonld:
            try:
                offers += list(ld_images(json.loads(script)))
            except (ValueError, TypeError):
                pass
        for candidate in offers:
            image = urljoin(url, html.unescape(candidate).strip())
            if valid_url(image) and not re.search(r"\.(svg)(\?|$)", image, re.I):
                return image, "public_metadata"
        return None, "no_public_image_metadata"
    except Exception as ex:
        # Do not add sensitive page contents or a large traceback to public JSON.
        return None, type(ex).__name__

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=40)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))["products"]
    previous = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {"items": {}}
    old = previous.get("items", {})
    out = {}
    checks = 0
    date = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    for p in catalog:
        id_, page, known_image = p["id"], p["url"], p.get("image_url")
        earlier = old.get(id_, {})
        if valid_url(known_image):
            out[id_] = {"image_url": known_image, "image_source_url": p.get("image_source_url") or page,
                        "status": "catalog_image_url", "checked_at": date}
        elif earlier.get("image_url") and valid_url(earlier.get("image_url")) and not args.force:
            out[id_] = earlier
        elif checks < args.limit:
            image, status = discover(page)
            checks += 1
            out[id_] = {"image_url": image, "image_source_url": page, "status": status, "checked_at": date}
            print(f"{id_}: {status} {'image URL found' if image else 'unresolved'}")
            time.sleep(0.4)
        else:
            out[id_] = earlier if earlier else {"image_url": None, "image_source_url": page,
                                                 "status": "not_checked", "checked_at": date}
    # Preserve metadata and chronology but don't touch the checked-in images when they are available.
    result = {"schema_version": "1.0", "updated_at": date,
              "description": "Remote primary image URLs from public merchant product metadata. Not a guarantee that hotlinking works or is licensed.",
              "items": out}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Completed: {len(out)} items; queried {checks}; image URLs: {sum(bool(x.get('image_url')) for x in out.values())}")

if __name__ == "__main__":
    main()
