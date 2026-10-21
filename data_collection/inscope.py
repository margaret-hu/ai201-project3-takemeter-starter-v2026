#!/usr/bin/env python3
"""In-scope filter for TakeMeter: keeps posts that can take one of the labels in
label_definitions.txt (analysis / hot_take / chatter) and drops everything else.

Usage:
  python inscope.py smogon_posts.jsonl            # print pool size and drop reasons
"""
from __future__ import annotations

import collections
import json
import re
import sys

# Threads that are about tournament admin, site meta, or staff announcements, not the game itself.
SKIP_THREADS = (
    "badge-leaders", "introduction-to-smogon", "kickoff", "semifinals", "oupl-", "standings",
    "bazaar", "cap-38", "rmt-", "victim-of-the-week", "signups", "official-tournament-replays",
    "renaming-of-the-tier", "oufl-", "tlt-", "team-up", "smogon-festive",
    "reaction-lottery",
)
# Opening posts are skipped unless the thread exists to host the opener's own opinion.
KEEP_OPENING_POST = ("viability-rankings", "1v1-metagame-discussion")
# Hand-checked posts that look in scope but are data lists or staff notices.
EXCLUDE_POST_IDS = {
    "9526768": "list of Pokemon dropping tiers",
    "10097551": "notice about official drops, with link",
}
TEMPLATE_START_RE = re.compile(r"(OU|DOU) usage stats")
LIST_RE = re.compile(r"\b(?:moved|could move|dropped|rose) from\b", re.I)
QUESTION_START_RE = re.compile(
    r"\s*(what|why|how|do you|is |are |can |will |would |which|who|thoughts|should|did |does |has |have )", re.I
)
LINK_RE = re.compile(r"tiermaker|pastebin|pokepast|pokepaste|replay\.pokemonshowdown", re.I)
EXPAND = "Click to expand..."


def own_text(text: str) -> str:
    """The author's own words: drop every quoted block ("X said: ... Click to expand...")."""
    parts = text.split(EXPAND)
    kept = []
    for part in parts[:-1]:
        i = part.rfind("said:")
        # keep what came before the quote header, minus the author's name on that line
        kept.append(part[:i].rsplit("\n", 1)[0] if i >= 0 else "")
    kept.append(parts[-1])
    return "\n".join(kept).strip()


def clean(text: str) -> str:
    return re.sub(r"[ \t​]+", " ", text).strip().replace("’", "'")


def classify(rows):
    """Return (kept, reasons) where reasons maps post_id -> reason a post was dropped."""
    text_counts = collections.Counter(clean(r["content_text"]) for r in rows)
    opening = {}
    for r in rows:
        u = r["thread_url"]
        if u not in opening or int(r["post_id"]) < int(opening[u]):
            opening[u] = r["post_id"]
    kept, reasons = [], {}
    for r in rows:
        t = r["content_text"].strip()
        u, pid = r["thread_url"], r["post_id"]
        own = own_text(t)
        if pid in EXCLUDE_POST_IDS:
            why = "hand excluded"
        elif any(s in u for s in SKIP_THREADS):
            why = "skipped thread"
        elif pid == opening[u] and not any(s in u for s in KEEP_OPENING_POST):
            why = "opening post"
        elif "Combined usage" in t or "| Rank |" in t or TEMPLATE_START_RE.match(t):
            why = "usage table / template"
        elif text_counts[clean(t)] > 1:
            why = "duplicate text"
        elif len(own) < 10:
            why = "no own text"
        elif len(t) > 2500:
            why = "too long"
        elif LINK_RE.search(own) and len(own) < 500:
            why = "link post"
        elif len(LIST_RE.findall(own)) >= 2 or own.startswith(("Tier shifts", "Projected", "|")):
            why = "tier-change list"
        elif len(own) < 600 and (own.rstrip().endswith("?") or ("?" in own and QUESTION_START_RE.match(own))):
            why = "question"
        elif re.search(r"updated the op|update[d]? .*tiermaker", own, re.I):
            why = "op update"
        else:
            kept.append(r)
            continue
        reasons[pid] = why
    return kept, reasons


if __name__ == "__main__":
    rows = [json.loads(l) for l in open(sys.argv[1], encoding="utf-8")]
    kept, reasons = classify(rows)
    print(f"{len(rows)} posts -> {len(kept)} in scope")
    for why, n in collections.Counter(reasons.values()).most_common():
        print(f"  {n:4d} {why}")
