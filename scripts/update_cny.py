#!/usr/bin/env python3
"""Fetch the official Bank of Russia daily CNY/RUB rate; no API key required."""
from __future__ import annotations
import datetime as dt
import json
import pathlib
import urllib.request
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = "https://www.cbr.ru/scripts/XML_daily.asp"

def fetch_rate():
    request = urllib.request.Request(SOURCE, headers={"User-Agent": "ProductRadar-Data/1.0 (public market data)"})
    with urllib.request.urlopen(request, timeout=25) as response:
        payload = response.read(2_000_000)
    root = ET.fromstring(payload)
    date_str = root.attrib["Date"]
    effective_date = dt.datetime.strptime(date_str, "%d.%m.%Y").date().isoformat()
    for entry in root.findall("Valute"):
        if entry.findtext("CharCode") == "CNY":
            nominal = int(entry.findtext("Nominal", "1"))
            value = float(entry.findtext("Value", "").replace(",", "."))
            if nominal <= 0 or value <= 0:
                raise ValueError("Invalid CNY quote")
            return effective_date, nominal, value / nominal
    raise RuntimeError("CNY is missing from Bank of Russia response")

def main():
    effective_date, nominal, rate = fetch_rate()
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    data = {
        "schema_version": "1.0",
        "source": SOURCE,
        "source_name": "Bank of Russia",
        "currency": "CNY",
        "base_currency": "RUB",
        "effective_date": effective_date,
        "rate_rub_per_cny": round(rate, 6),
        "nominal": nominal,
        "fetched_at": now,
        "status": "ok",
    }
    destination = ROOT / "data/market/cny_rub.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    status_file = ROOT / "data/status.json"
    status = json.loads(status_file.read_text(encoding="utf-8"))
    status["currency"] = {"state": "ok", "updated_at": now, "effective_date": effective_date}
    status_file.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"CNY/RUB: {rate:.6f}, effective {effective_date}")

if __name__ == "__main__":
    main()
