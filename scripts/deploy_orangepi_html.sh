#!/usr/bin/env bash
# Product Radar: safe one-file HTML deployment on Orange Pi.
# Does not touch JSON catalog data in GitHub or restart Docker.
set -euo pipefail
ROOT="/home/dockeruser/product-radar-public"
DEST="$ROOT/index.html"
SOURCE="https://raw.githubusercontent.com/irman100/ProductRadar-Data/d4393283545df52fb21544c8f8d61749b76bbf12/docs/index.html"
[ -f "$DEST" ] || { echo "ERROR: not found: $DEST" >&2; exit 1; }
command -v curl >/dev/null || { echo "ERROR: curl is required" >&2; exit 1; }
TMP="$(mktemp "$ROOT/.index.html.new.XXXXXX")"
trap 'rm -f "$TMP"' EXIT
curl -fLSs --connect-timeout 12 --max-time 45 "$SOURCE" -o "$TMP"
python3 - "$TMP" <<'PY'
import sys
s=open(sys.argv[1],encoding='utf-8').read()
required=['<!doctype html>','const BASE=','data/verified/','id="products"','function draw()','load();fashionStats();loadOffers();','id="shop"','id="research-report"','loadReport();','marketplace_purchase_counter_observed']
assert all(x in s for x in required), "Downloaded HTML is incomplete"
assert 'id="candidates"' not in s, "Unverified research cards must not be public"
print("HTML verified: published research report, purchase observations and real merchant offers")
PY
BACKUP="$ROOT/index.html.backup.$(date -u +%Y%m%dT%H%M%SZ)"
cp -p "$DEST" "$BACKUP"
chmod --reference="$DEST" "$TMP"
mv -f "$TMP" "$DEST"
trap - EXIT
echo "Deployed $DEST"
echo "Backup: $BACKUP"
if docker ps --format '{{.Names}}' 2>/dev/null | grep -qx 'product-radar-web'; then
  echo "Container: product-radar-web running"
else
  echo "Warning: container not confirmed, check Docker separately"
fi
if curl -fLsS --connect-timeout 3 --max-time 8 http://10.77.0.2:8766/ | grep -q 'Одежда — конкретные товары для покупки'; then
  echo "Local HTTP check: OK"
else
  echo "Local HTTP check: not confirmed (verify proxy/container mount before claiming public deployment)"
fi
