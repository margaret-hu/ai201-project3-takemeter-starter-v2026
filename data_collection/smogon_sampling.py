#!/usr/bin/env python3
"""
Wrapper to run the stratified sampling using smogon_scraper.collect_posts_with_playwright.

Usage:
  python smogon_sampling.py --config config.json
  python smogon_sampling.py --config config.json --seed 123 --dry-run

Place this file in the same directory as smogon_scraper.py.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from typing import Any, Dict

# Import functions/classes from smogon_scraper (must be in same directory or on PYTHONPATH)
try:
    import smogon_scraper as scraper
except Exception as e:
    raise SystemExit(f"Could not import smogon_scraper.py from this directory: {e}")

DEFAULT_CONFIG = {
    "home": "https://www.smogon.com/forums/",
    "keywords": scraper.DEFAULT_KEYWORDS,
    "target": 200,
    "target_threads": 28,
    "type_props": scraper.DEFAULT_TYPE_PROPS,
    "tier_props": scraper.DEFAULT_TIER_PROPS,
    "recent_share": 0.5,
    "raw_per_thread": 15,  # oversample; subsample.py applies the in-scope filter and the 10-post cap
    "min_thread_posts": 12,
    "forum_pages": 3,
    "anonymize": False,
    "output": "smogon_posts_v2.jsonl",
    "cache_dir": "cache_smogon_v2",
    "manifest": "sample_manifest_v2.json",
    "seed": 42,
    "force": False,
    "headless": True,
    "verbose": False,
    # politeness tunables
    "default_sleep": None,
    "default_jitter": None,
}


def load_config(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf8") as fh:
        cfg = json.load(fh)
    return cfg


def merge_config(file_cfg: Dict[str, Any], cli_args: argparse.Namespace) -> Dict[str, Any]:
    cfg = dict(DEFAULT_CONFIG)
    cfg.update(file_cfg or {})
    # CLI overrides
    if cli_args.seed is not None:
        cfg["seed"] = cli_args.seed
    if cli_args.target is not None:
        cfg["target"] = cli_args.target
    if cli_args.target_threads is not None:
        cfg["target_threads"] = cli_args.target_threads
    if cli_args.forum_pages is not None:
        cfg["forum_pages"] = cli_args.forum_pages
    if cli_args.output is not None:
        cfg["output"] = cli_args.output
    if cli_args.cache_dir is not None:
        cfg["cache_dir"] = cli_args.cache_dir
    if cli_args.manifest is not None:
        cfg["manifest"] = cli_args.manifest
    if cli_args.anonymize:
        cfg["anonymize"] = True
    if cli_args.force:
        cfg["force"] = True
    if cli_args.headless is not None:
        cfg["headless"] = cli_args.headless
    if cli_args.verbose:
        cfg["verbose"] = True
    return cfg


def run(cfg: Dict[str, Any], dry_run: bool = False):
    # Logging
    logging.basicConfig(level=logging.DEBUG if cfg.get("verbose") else logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.info("Starting sampling run with seed=%s target=%s threads=%s", cfg["seed"], cfg["target"], cfg["target_threads"])

    # Create cache/output dirs
    os.makedirs(os.path.dirname(cfg["output"]) or ".", exist_ok=True)
    os.makedirs(cfg["cache_dir"], exist_ok=True)

    if dry_run:
        logging.info("Dry-run mode: not launching browser. Showing planned config:")
        print(json.dumps(cfg, indent=2))
        return

    # Instantiate BrowserFetcher from smogon_scraper
    fetcher = None
    try:
        fetcher = scraper.BrowserFetcher(headless=cfg.get("headless", True), user_agent=scraper.BROWSER_UA)
        out_file, manifest_file = scraper.collect_posts_with_playwright(
            fetcher=fetcher,
            base_forum_home=cfg.get("home"),
            include_keywords=cfg.get("keywords"),
            target_posts=int(cfg.get("target")),
            target_threads=int(cfg.get("target_threads")),
            forum_pages=int(cfg.get("forum_pages")),
            anonymize=bool(cfg.get("anonymize")),
            output_file=cfg.get("output"),
            cache_dir=cfg.get("cache_dir"),
            manifest_file=cfg.get("manifest"),
            seed=int(cfg.get("seed")),
            force_robots=bool(cfg.get("force")),
            type_props=cfg.get("type_props"),
            tier_props=cfg.get("tier_props"),
            recent_share=float(cfg.get("recent_share")),
            raw_per_thread=int(cfg.get("raw_per_thread")),
            min_thread_posts=int(cfg.get("min_thread_posts")),
        )
        logging.info("Completed run. Output: %s, Manifest: %s", out_file, manifest_file)
    finally:
        if fetcher:
            fetcher.close()


def cli():
    parser = argparse.ArgumentParser(description="smogon_sampling.py — wrapper around smogon_scraper.collect_posts_with_playwright")
    parser.add_argument("--config", required=True, help="Path to JSON config file")
    parser.add_argument("--seed", type=int, help="Override RNG seed")
    parser.add_argument("--target", type=int, help="Override number of posts to collect")
    parser.add_argument("--target-threads", type=int, help="Override number of threads to sample")
    parser.add_argument("--forum-pages", type=int, help="Override listing pages per section to scan")
    parser.add_argument("--output", help="Override JSONL output file")
    parser.add_argument("--cache-dir", help="Override cache directory")
    parser.add_argument("--manifest", help="Override manifest path")
    parser.add_argument("--anonymize", action="store_true", help="Hash usernames in output")
    parser.add_argument("--force", action="store_true", help="Ignore robots.txt errors")
    parser.add_argument("--dry-run", action="store_true", help="Print resolved config and exit (no network)")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    parser.add_argument("--headless", type=lambda v: v.lower() in ("1", "true", "yes"), nargs="?", const=True, help="Set headless True/False (default True)")
    args = parser.parse_args()

    if not os.path.exists(args.config):
        raise SystemExit(f"Config file not found: {args.config}")
    file_cfg = load_config(args.config)
    cfg = merge_config(file_cfg, args)
    run(cfg, dry_run=args.dry_run)


if __name__ == "__main__":
    cli()