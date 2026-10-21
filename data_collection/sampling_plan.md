# TakeMeter sampling plan (v2)

Supersedes the v1 plan (RMT-heavy, 30 threads / 200 posts). v1 was written before
`label_definitions.txt`; RMT OPs are teams/sets (out of scope) and RMT replies are team
advice, not opinions about the game, tiers, or tiering policy. v2 samples only places where
analysis / hot_take / chatter actually occur.

## Goal

200 labeled posts, in scope for analysis / hot_take / chatter, spread over many threads,
tiers, years, and lengths, with no single thread dominating.

## A. Strata

| Dimension | Buckets |
|---|---|
| Thread type | **Tiering/council** (tier updates, suspect/ban discussion, council threads) · **Viability/strategy** (viability rankings, metagame discussion, analysis threads) · **Community discussion** (tier talk, office hours, awards, general metagame chat) |
| Tier | OU · Doubles/VGC · UU/RU/NU/PU · Ubers/1v1/Monotype/Other |
| Time | Recent (last 24 months) · Older |
| Post role | Opening post (only in the threads in `KEEP_OPENING_POST`) · Reply |

**Excluded thread types:** RMT, tournament signups/rounds/standings, staff announcements,
site meta, mafia/anime/off-topic. `SKIP_THREADS` in `inscope.py` already covers most of these;
keep it as the single source of truth.

## B. Quotas (200 posts)

| Thread type | Threads | Posts | Share |
|---|---|---|---|
| Tiering/council | 10 | ~70 | 35% |
| Viability/strategy | 10 | ~70 | 35% |
| Community discussion | 8 | ~60 | 30% |
| **Total** | **28** (minimum 25) | **200** | |

| Tier | Share of posts |
|---|---|
| OU | 30% |
| Doubles/VGC | 20% |
| UU/RU/NU/PU | 25% |
| Ubers/1v1/Monotype/Other | 25% |

| Time | Share of posts |
|---|---|
| Recent (last 24 months) | 50% |
| Older | 50% |

The current pool is about 28% recent, mostly OU and 1v1, with 0 threads for VGC/UU/RU/PU
strategy, so recent and non-OU threads are the main gaps to fill.

## C. Per-thread rules

- **Cap:** at most 10 posts per thread, and no thread above 6% of the final 200.
- **Minimum:** at least 4 in-scope posts available, otherwise skip the thread.
- **Selection** (seeded RNG, seed stored in the manifest):
  1. Opening post only for threads in `KEEP_OPENING_POST`.
  2. First 2 in-scope replies in chronological order (immediate reactions).
  3. Fill the rest at random from the remaining in-scope replies.
- **Spread across pages:** fetch the page of each selected post, so long threads are not
  sampled only from their first page.
- **Prefer non-sticky** threads. Include stickies only when they are discussion threads.

## D. Post-level filter (applied before sampling)

Use `inscope.py` to drop:
- deleted or empty posts, and posts with no text of their own after removing quotes
- usage tables, staff/host rule or schedule text, teams/sets/spreads
- posts that are only a question or only a link
- hand-checked exclusions in `EXCLUDE_POST_IDS`

Sample **after** filtering so the quotas count only usable posts.

## E. Thread discovery

1. Crawl the forum index pages for: Tiering/council, OU, Doubles/VGC, UU/RU/NU/PU, Ubers,
   1v1, Monotype, and Metagame discussion boards.
2. Record thread title, tier, type, last-post date, and reply count.
3. Drop excluded types and threads under the minimum.
4. Sample threads uniformly within each (type × tier × time) cell until its quota is met.
   If a cell is empty, move its quota to the nearest cell by tier first, then by time, and
   log the move.
5. Save the thread list and RNG seed in `sample_manifest.json`. Cache fetched pages so
   parsing can be re-run without new requests.

## F. Label-balance check (after the first 50 labels)

Tier-update replies tend to be chatter or hot_take, so analysis may be scarce.
- Target: at least about 20% of each label in the final 200.
- If a label falls well short, add threads likely to hold it. For analysis, add viability and
  council discussions. For chatter, add reaction threads. Do not edit labels or definitions
  to fix the balance.
- Report the label counts in the README.

## G. Implementation (done)

Two stages, because the in-scope filter needs the scraped text:

1. **Scrape** (`python smogon_sampling.py --config config.json`): discovers threads, drops excluded types
   (`is_excluded_thread`: `inscope.SKIP_THREADS` plus title patterns), classifies type and tier group, picks
   28 threads to the quotas in `config.json` (`type_props`, `tier_props`, `recent_share`), and oversamples
   `raw_per_thread` = 15 posts per thread (OP, first 2 replies, random rest).
2. **Subsample** (`python subsample.py smogon_posts_v2.jsonl --manifest sample_manifest_v2.json`): runs
   `inscope.classify`, drops threads with fewer than 4 in-scope posts, keeps the first 2 in-scope replies plus a
   seeded shuffle of the rest, caps each thread at 10 posts (and 6% of the target), draws round-robin across threads
   up to 200, and prints the time, type and tier mix.

Outputs use new names (`smogon_posts_v2.jsonl`, `cache_smogon_v2`, `sample_manifest_v2.json`), so `smogon_posts.jsonl`
and the labeled data are not overwritten. The scraper writes its output with mode `w`.

Tier is taken from the section and title text with word-boundary matching; threads that name no tier land in
"Other". Time is the thread's opening-post date, not each post's date, so check the post-level recent share
in the `subsample.py` output.

## H. Deliverables

- `sample_manifest.json` with threads, seed, and per-cell quota fill.
- `sampling_plan.csv` regenerated with `plan_summary.py`.
- A short count table (type × tier × time, posts per thread, label counts), checked against
  the quotas above.
