#!/usr/bin/env python3
"""
Produce a human-friendly CSV and console summary from the sampling manifest JSON.

Usage:
  python plan_summary.py --manifest sample_manifest.json --out-csv sampling_plan.csv
"""
import argparse, json, csv, os
from collections import Counter, defaultdict

def load_manifest(path):
    with open(path, "r", encoding="utf8") as f:
        return json.load(f)

def write_csv(manifest, out_path):
    rows = []
    for t in manifest.get("sampled_threads", []):
        rows.append({
            "thread_url": t.get("thread_url"),
            "thread_title": t.get("thread_title") or "",
            "thread_type": t.get("thread_type") or "",
            "tier": t.get("tier") or "",
            "is_recent": bool(t.get("is_recent")),
            "total_posts_estimated": t.get("total_posts_estimated"),
            "pages_fetched": ",".join(map(str, t.get("pages_fetched", []))),
            "selected_indices_planned": ",".join(map(str, t.get("selected_indices_planned", []))),
            "selected_indices_written": ",".join(map(str, t.get("selected_indices_written", []))),
            "thread_rng_seed": t.get("thread_rng_seed"),
        })
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", newline='', encoding="utf8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()) if rows else [
            "thread_url","thread_title","thread_type","tier","is_recent","total_posts_estimated",
            "pages_fetched","selected_indices_planned","selected_indices_written","thread_rng_seed"
        ])
        writer.writeheader()
        for r in rows:
            writer.writerow(r)
    return rows

def summarize(manifest, rows):
    seed = manifest.get("seed")
    target_posts = manifest.get("target_posts")
    target_threads = manifest.get("target_threads")
    created_at = manifest.get("created_at")
    print(f"Sampling manifest (seed={seed}) created_at={created_at}")
    print(f"Target threads={target_threads}, Target posts={target_posts}\n")

    by_type = Counter()
    by_tier = Counter()
    by_time = Counter()
    planned_posts = 0
    written_posts = 0
    for t in manifest.get("sampled_threads", []):
        by_type[t.get("thread_type") or "Unknown"] += 1
        by_tier[t.get("tier") or "Other"] += 1
        by_time["recent" if t.get("is_recent") else "older"] += 1
        planned = len(t.get("selected_indices_planned") or [])
        written = len(t.get("selected_indices_written") or [])
        planned_posts += planned
        written_posts += written

    print("Counts by thread_type:")
    for k, v in by_type.most_common():
        print(f"  {k}: {v}")
    print("Counts by tier:")
    for k, v in by_tier.most_common():
        print(f"  {k}: {v}")
    print("Counts by time bucket:")
    for k, v in by_time.most_common():
        print(f"  {k}: {v}")

    print(f"\nPlanned post picks (sum of planned indices): {planned_posts}")
    print(f"Actual posts written (sum of selected_indices_written): {written_posts}")
    print("\nIf planned_posts < target_posts, increase per-thread extras or sample more threads.")
    print("If actual written < planned (due to deletions etc.), check manifest.sampled_threads[*].selected_indices_planned vs _written for replacements.\n")

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--manifest", "-m", required=True)
    p.add_argument("--out-csv", "-o", default="sampling_plan.csv")
    args = p.parse_args()
    manifest = load_manifest(args.manifest)
    rows = write_csv(manifest, args.out_csv)
    summarize(manifest, rows)
    print(f"\nWrote per-thread plan CSV to {args.out_csv}")

if __name__ == "__main__":
    main()