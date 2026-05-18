#!/usr/bin/env python3
"""Quartiles JSON çıktısını CSV'ye dönüştürür.

Kullanım:
    python3 convert_to_csv.py input.json output.csv
"""
import argparse
import csv
import json
import sys
from pathlib import Path


def normalize_query(q: str) -> str:
    if not q:
        return ""
    words = str(q).replace("&", " and ").split()
    return " ".join(
        "and" if w.lower() == "and" else w.capitalize()
        for w in words
    )


def main():
    parser = argparse.ArgumentParser(description="Convert quartiles JSON to CSV")
    parser.add_argument("input", help="Input JSON file")
    parser.add_argument("output", help="Output CSV file")
    args = parser.parse_args()

    in_path = Path(args.input)
    out_path = Path(args.output)

    if not in_path.exists():
        print(f"Input not found: {in_path}", file=sys.stderr)
        sys.exit(1)

    data = json.loads(in_path.read_text(encoding="utf-8"))

    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_ALL)
        writer.writerow(["query", "sid", "category", "year", "quartile", "timestamp"])
        for item in data:
            if not item.get("ok"):
                continue
            for row in item.get("rows", []):
                writer.writerow([
                    normalize_query(item.get("query", "")),
                    item.get("sid", ""),
                    row.get("category", ""),
                    row.get("year", ""),
                    row.get("quartile", ""),
                    item.get("timestamp", ""),
                ])

    print(f"CSV written: {out_path}")


if __name__ == "__main__":
    main()
