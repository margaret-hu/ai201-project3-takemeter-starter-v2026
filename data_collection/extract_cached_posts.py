#!/usr/bin/env python3
"""Parse every post from the cached Smogon pages (no network) and keep the in-scope ones.

Usage:
  python extract_cached_posts.py --cache-dir cache_smogon --manifest sample_manifest.json --output pool_inscope.jsonl
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from inscope import classify
from data_collection.smogon_scraper import is_error_page, parse_post_element


def post_elements(soup):
    for sel in ("article.message", "div.message", ".post", ".postbit"):
        found = soup.select(sel)
        if found:
            return found
    return []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache-dir", default="cache_smogon")
    ap.add_argument("--manifest", default="sample_manifest.json")
    ap.add_argument("--output", default="pool_inscope.jsonl")
    args = ap.parse_args()

    manifest = json.load(open(args.manifest, encoding="utf-8"))
    rows, seen = [], set()
    for th in manifest["sampled_threads"]:
        for page, info in th.get("cached_pages", {}).items():
            path = info["path"].replace("\\", os.sep)
            if not os.path.exists(path):
                continue
            html = open(path, encoding="utf-8").read()
            if is_error_page(html):
                continue
            soup = BeautifulSoup(html, "lxml")
            for el in post_elements(soup):
                p = parse_post_element(el, th["thread_url"])
                text = (p.get("content_text") or "").strip()
                if not text or not p.get("post_id") or p["post_id"] in seen:
                    continue
                seen.add(p["post_id"])
                p["scraped_at"] = datetime.now(timezone.utc).isoformat()
                rows.append(p)
    kept, reasons = classify(rows)
    with open(args.output, "w", encoding="utf-8") as f:
        for r in kept:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"{len(rows)} cached posts -> {len(kept)} in scope -> {args.output}")


if __name__ == "__main__":
    main()
