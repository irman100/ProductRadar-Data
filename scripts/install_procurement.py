#!/usr/bin/env python3
"""Install the GitHub-hosted static procurement dashboard; preserve the old catalog."""
import argparse
import hashlib
import os
import re
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen

PAGE_URL = "https://raw.githubusercontent.com/irman100/ProductRadar-Data/e401e113cfc2389d6866c4e4754f2c1a57cb78a1/web/procurement/index.html"
PAGE_BLOB = "ce4d17cc9dbbadde4e30b7283d7ac93a4e7042e7"
MARKER = b"radar-procurement-v1"

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", type=Path, default=Path("/home/dockeruser/product-radar-public/index.html"))
    parser.add_argument("--check", action="store_true", help="Download and validate without modifying any site files")
    args = parser.parse_args()
    p = args.path.resolve(strict=True)
    old = p.read_bytes()
    archive = p.with_name("catalog-archive.html")
    if not old or b"<html" not in old.lower():
        raise SystemExit("ERROR: unexpected existing index; no changes")
    with urlopen(Request(PAGE_URL, headers={"User-Agent": "ProductRadarInstaller/1.0"}), timeout=30) as response:
        new = response.read(500001)
    sha = hashlib.sha1(("blob %d\0" % len(new)).encode("ascii") + new).hexdigest()
    if sha != PAGE_BLOB or len(new) > 500000 or MARKER not in new:
        raise SystemExit("ERROR: pinned HTML integrity check failed; no changes")
    new_text = new.decode("utf-8")
    if shutil.which("node"):
        for code in re.findall(r"<script\b[^>]*>(.*?)</script\s*>", new_text, re.I | re.S):
            with tempfile.NamedTemporaryFile(mode="w", suffix=".js", encoding="utf-8") as temp:
                temp.write(code); temp.flush()
                subprocess.run(["node", "--check", temp.name], check=True)
    else:
        print("Node.js not installed on server; syntax test skipped here")
    if MARKER in old and (not archive.is_file() or MARKER in archive.read_bytes()):
        raise SystemExit("ERROR: old catalog archive not found; no changes")
    if MARKER not in old and archive.exists():
        raise SystemExit("ERROR: catalog-archive.html already exists; refusing to overwrite it")
    if old == new:
        print("ALREADY INSTALLED; archive:", archive)
        return
    if args.check:
        print("CHECK OK; no site files modified")
        return
    backup = p.with_name(p.name + ".bak-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f"))
    shutil.copy2(p, backup)
    created_archive = False
    try:
        if MARKER not in old:
            # Keep original page with its existing research features. Add a return link,
            # and prevent the archived page from registering the old service worker again.
            archive_text = old.decode("utf-8")
            anchor = '<div style="padding:12px 16px;text-align:center;background:#e8eef5;color:#173f64"><a href="./?view=procurement" style="color:inherit;font-weight:600">← Закупочная витрина Product Radar</a></div>'
            archive_text, count = re.subn(r"(<body\b[^>]*>)", lambda m: m.group(1) + anchor, archive_text, count=1, flags=re.I)
            if count != 1:
                raise RuntimeError("Missing archive body")
            registration = "if('serviceWorker' in navigator)window.addEventListener('load',()=>navigator.serviceWorker.register('./sw.js').catch(()=>{}));"
            archive_text = archive_text.replace(registration, "")
            with archive.open("x", encoding="utf-8") as out:
                created_archive = True
                out.write(archive_text); out.flush(); os.fsync(out.fileno())
            os.chmod(archive, p.stat().st_mode & 0o777)
        # In-place update keeps the existing inode for single-file Docker bind mounts.
        with p.open("wb") as out:
            out.write(new); out.flush(); os.fsync(out.fileno())
        if p.read_bytes() != new or not archive.is_file():
            raise RuntimeError("Local readback failed")
    except BaseException:
        shutil.copyfile(backup, p)
        if created_archive:
            archive.unlink(missing_ok=True)
        raise
    print("PRODUCT RADAR PROCUREMENT INSTALLED")
    print("HTML:", p)
    print("ARCHIVE:", archive)
    print("BACKUP:", backup)
    print("No container restart, backend or database modifications performed.")

if __name__ == "__main__":
    main()
