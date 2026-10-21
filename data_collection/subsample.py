#!/usr/bin/env python3
"""Stage 2 of sampling plan: filter scraped posts to in-scope, cap per thread, draw the final sample.

Usage:
  python subsample.py smogon_posts.jsonl --manifest sample_manifest.json --out sample_200.jsonl
"""
from __future__ import annotations

import argparse
import collections
import json
import random
from datetime import datetime, timedelta, timezone

from inscope import classify

RECENT_MONTHS = 24


def post_time(row):
    try:
        dt = datetime.fromisoformat(row["timestamp_raw"])  # e.g. 2026-04-01T08:38:05-0400
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return datetime.min.replace(tzinfo=timezone.utc)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("posts", help="JSONL from the scraper")
    ap.add_argument("--manifest", help="manifest JSON, used only for the summary tables")
    ap.add_argument("--out", default="sample_200.jsonl")
    ap.add_argument("--target", type=int, default=200)
    ap.add_argument("--thread-cap", type=int, default=10, help="max posts per thread")
    ap.add_argument("--max-thread-share", type=float, default=0.06, help="max share of the target from one thread")
    ap.add_argument("--min-thread-posts", type=int, default=4, help="skip threads with fewer in-scope posts")
    ap.add_argument("--seed", type=int, default=123)
    args = ap.parse_args()

    rows = [json.loads(l) for l in open(args.posts, encoding="utf-8")]
    kept, _ = classify(rows)
    cap = min(args.thread_cap, int(args.max_thread_share * args.target))

    by_thread = collections.defaultdict(list)
    for r in kept:
        by_thread[r["thread_url"]].append(r)
    by_thread = {u: sorted(rs, key=lambda r: (post_time(r), int(r["post_id"]))) for u, rs in by_thread.items()
                 if len(rs) >= args.min_thread_posts}

    # Per thread: first 2 in-scope replies in order, then the rest shuffled (seeded per run).
    rnd = random.Random(args.seed)
    queues = {}
    for u in sorted(by_thread):
        rs = by_thread[u]
        rest = rs[2:]
        rnd.shuffle(rest)
        queues[u] = (rs[:2] + rest)[:cap]

    # Round-robin over threads so no thread dominates when the pool exceeds the target.
    order = sorted(queues)
    rnd.shuffle(order)
    chosen = []
    for i in range(cap):
        for u in order:
            if len(chosen) < args.target and i < len(queues[u]):
                chosen.append(queues[u][i])

    with open(args.out, "w", encoding="utf-8") as fh:
        for r in chosen:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    meta = {}
    if args.manifest:
        meta = {t["thread_url"]: t for t in json.load(open(args.manifest, encoding="utf-8")).get("sampled_threads", [])}
    cutoff = datetime.now(timezone.utc) - timedelta(days=RECENT_MONTHS * 30)
    per_thread = collections.Counter(r["thread_url"] for r in chosen)
    print(f"{len(rows)} scraped -> {len(kept)} in scope -> {len(chosen)} chosen from {len(per_thread)} threads "
          f"(cap {cap}, target {args.target})")
    if len(chosen) < args.target:
        print(f"WARNING: short by {args.target - len(chosen)}; scrape more threads.")
    recent = sum(post_time(r) >= cutoff for r in chosen)
    print(f"time: {recent} recent / {len(chosen) - recent} older ({recent / max(len(chosen), 1):.0%} recent)")
    for key in ("thread_type", "tier"):
        if meta:
            c = collections.Counter(meta.get(r["thread_url"], {}).get(key) or "?" for r in chosen)
            print(f"{key}: " + ", ".join(f"{k} {v} ({v / len(chosen):.0%})" for k, v in c.most_common()))
    print("posts per thread: max", max(per_thread.values(), default=0), "| min", min(per_thread.values(), default=0))


if __name__ == "__main__":
    main()
