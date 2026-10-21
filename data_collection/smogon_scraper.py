#!/usr/bin/env python3
"""
Smogon scraper (Playwright-based) with stratified sampling.

Requirements:
  pip install playwright requests beautifulsoup4 lxml python-dateutil
  python -m playwright install chromium

This script:
- Uses Playwright (Chromium) to fetch pages so Smogon's JS gate is satisfied.
- Implements the stratified sampling plan (thread type, tier, time buckets).
- Caches fetched thread pages (HTML) so re-parsing doesn't re-request.
- Writes sampled posts as JSONL and a manifest JSON describing the sample.

Run a fast dry-run first (target 10):
  python smogon_scraper.py --target 10 --target-threads 6 --cache-dir tmp_cache --output sample.jsonl --manifest sample_manifest.json --seed 123 --verbose

Run a full scrape (target 200):
  python smogon_scraper.py --home https://www.smogon.com/forums/ --target 200 --target-threads 30 --forum-pages 3 --cache-dir cache_smogon --output smogon_posts.jsonl --manifest sample_manifest.json --seed 123 --verbose
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import math
import os
import random
import re
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

# third-party
try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
except Exception as e:
    raise SystemExit(
        "Playwright is required but not importable. Install it with:\n"
        "  pip install playwright\n"
        "  python -m playwright install chromium\n\n"
        f"Import error: {e}"
    )

from bs4 import BeautifulSoup
from dateutil import parser as dtparser
import urllib.robotparser as robotparser

from inscope import SKIP_THREADS  # single source of truth for excluded thread URLs

# ---- Configuration defaults ----
BROWSER_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
DEFAULT_SLEEP = 1.5
DEFAULT_JITTER = 0.6
POST_ID_RE = re.compile(r"(?:post[_-]?|post-?)(\d+)", re.IGNORECASE)
THREAD_PATH_RE = re.compile(r"/threads/|/thread/|/topics/?", re.IGNORECASE)
RECENT_MONTHS = 24  # <= 24 months considered "recent"

# Sampling plan v2 (see sampling_plan.md). Overridable through config.json.
DEFAULT_TYPE_PROPS = {"Council": 0.35, "Viability": 0.35, "Community": 0.30}
DEFAULT_TIER_PROPS = {"OU": 0.30, "Doubles/VGC": 0.20, "Lower tiers": 0.25, "Other": 0.25}
DEFAULT_KEYWORDS = ["council", "viability", "metagame", "doubles", "vgc", "ou", "uu", "ru", "nu", "pu",
                    "monotype", "ubers", "1v1"]
# Thread types that hold no opinions about the game; extends inscope.SKIP_THREADS (matched on the URL).
EXCLUDED_TITLE_RE = re.compile(
    r"\brmt\b|rate my team|sign-?ups?\b|\bstandings\b|\bround \d+|\bweek (?:\d+|one|two|three|four|five|six)\b|"
    r"\bmafia\b|\banime\b|\bbadge|\bplayoffs?\b|\bsemifinals?\b|\bfinals?\b|\bdraft\b|\btournament\b",
    re.I,
)


# ---- Playwright fetcher (single browser instance, reused) ----
class BrowserFetcher:
    def __init__(self, headless: bool = True, user_agent: str = BROWSER_UA, slow_millis: int = 0):
        self.headless = headless
        self.user_agent = user_agent
        self.slow_millis = slow_millis
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
        self._start()

    def _start(self):
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=self.headless)
        self._context = self._browser.new_context(user_agent=self.user_agent)
        # create a reusable page
        self._page = self._context.new_page()

    def fetch_html(self, url: str, timeout_s: int = 60, wait_for_content: bool = True) -> Optional[str]:
        """Navigate to url and wait until the JS challenge clears or timeout.
        Returns HTML content or None if load failed.
        """
        try:
            logging.debug("Browser navigating to %s", url)
            # Use DOMContentLoaded to avoid waiting for heavy network; we'll poll body text
            self._page.goto(url, wait_until="domcontentloaded", timeout=timeout_s * 1000)
        except PlaywrightTimeoutError:
            logging.warning("Playwright timeout navigating to %s", url)
            # continue to try reading content
        except Exception as e:
            logging.warning("Playwright navigation error for %s: %s", url, e)
            return None

        # Wait for challenge to clear: poll body text for the "Checking your browser" marker.
        if wait_for_content:
            for i in range(timeout_s):
                try:
                    body_text = self._page.locator("body").inner_text(timeout=2000)
                except Exception:
                    body_text = ""
                # If the page still shows "Checking your browser" or "JavaScript and cookies are required", keep waiting.
                lower = body_text.lower()
                if "checking your browser" in lower or "javascript and cookies are required" in lower or "please wait" in lower:
                    time.sleep(1)
                    continue
                # otherwise assume the page content is ready
                break
        # Give a short pause so dynamic content can settle
        if self.slow_millis:
            time.sleep(self.slow_millis / 1000.0)
        try:
            html = self._page.content()
            return html
        except Exception as e:
            logging.warning("Playwright page.content() failed for %s: %s", url, e)
            return None

    def close(self):
        try:
            if self._page:
                self._page.close()
        except Exception:
            pass
        try:
            if self._context:
                self._context.close()
        except Exception:
            pass
        try:
            if self._browser:
                self._browser.close()
        except Exception:
            pass
        try:
            if self._playwright:
                self._playwright.stop()
        except Exception:
            pass


# ---- robots.txt ----
def check_robots(base_url: str, user_agent: str = BROWSER_UA) -> Tuple[Optional[robotparser.RobotFileParser], Optional[bool]]:
    parsed = urlparse(base_url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    robots_url = urljoin(base, "/robots.txt")
    rp = robotparser.RobotFileParser()
    try:
        rp.set_url(robots_url)
        rp.read()
        allowed_root = rp.can_fetch(user_agent, "/")
        allowed_forums = rp.can_fetch(user_agent, "/forums/")
        allowed_threads = rp.can_fetch(user_agent, "/threads/")
        allowed = allowed_root and allowed_forums and allowed_threads
        return rp, allowed
    except Exception as e:
        logging.warning("Could not fetch/parse robots.txt (%s): %s", robots_url, e)
        return None, None


# ---- parsing helpers (BeautifulSoup) ----
def find_pagination_next(soup: BeautifulSoup, base_url: str) -> Optional[str]:
    a = soup.find("a", rel="next")
    if a and a.get("href"):
        return urljoin(base_url, a["href"])
    selectors = ["a.next", "a.pageNext", "li.next a", "a[title='Next page']", "a[aria-label='Next']"]
    for sel in selectors:
        el = soup.select_one(sel)
        if el and el.get("href"):
            return urljoin(base_url, el["href"])
    for a in soup.find_all("a", href=True):
        href = a["href"]
        txt = (a.get_text(" ", strip=True) or "").lower()
        if "next" in txt or txt in ("›", "»"):
            return urljoin(base_url, href)
    return None


_THREAD_SUFFIX_RE = re.compile(r"(/threads/[^/]+)/(?:page-\d+|post-\d+|latest|unread)/?$", re.IGNORECASE)
ERROR_PAGE_MARKER = "the requested page could not be found"


def canonical_thread_url(url: str) -> str:
    """Strip /page-N, /post-N, /latest suffixes so page URLs can be built from the thread root."""
    return _THREAD_SUFFIX_RE.sub(r"\1/", url)


def is_error_page(html: str) -> bool:
    return ERROR_PAGE_MARKER in html.lower()


def parse_listing_for_threads(html: str, base_url: str) -> List[Tuple[str, str]]:
    soup = BeautifulSoup(html, "lxml")
    threads = []

    for a in soup.select("a.structItem-title, a.structItem-title--thread, a.thread-title, a.title"):
        href = a.get("href")
        if not href:
            continue
        title = a.get_text(" ", strip=True)
        if THREAD_PATH_RE.search(href) and title:
            threads.append((canonical_thread_url(urljoin(base_url, href.split("#")[0])), title))

    if not threads:
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if THREAD_PATH_RE.search(href):
                title = a.get_text(" ", strip=True) or ""
                threads.append((canonical_thread_url(urljoin(base_url, href.split("#")[0])), title))

    seen = set()
    unique = []
    for url, title in threads:
        if url not in seen:
            seen.add(url)
            unique.append((url, title))
    return unique


def extract_post_id_from_attrs(el: BeautifulSoup) -> Optional[str]:
    for attr in ("data-post-id", "data-message-id", "data-content", "data-postid", "data-id", "id"):
        if el.has_attr(attr):
            val = el.get(attr)
            if val:
                m = re.search(r"(\d+)", str(val))
                if m:
                    return m.group(1)
                return str(val)
    if el.has_attr("id"):
        mid = el.get("id", "")
        m = POST_ID_RE.search(mid)
        if m:
            return m.group(1)
        if mid.isdigit():
            return mid
    return None


def is_excluded_thread(thread_url: str, thread_title: str) -> bool:
    """True for thread types the labels do not cover (RMT, signups, tournament rounds, site meta, ...)."""
    u = (thread_url or "").lower()
    return any(s in u for s in SKIP_THREADS) or bool(EXCLUDED_TITLE_RE.search(thread_title or ""))


def detect_thread_type_and_tier(section_text: str, thread_title: str) -> Tuple[str, str]:
    """Return (thread_type, tier_group). Type is Council, Viability or Community; tier group is one of
    DEFAULT_TIER_PROPS' keys. Excluded threads are filtered out earlier by is_excluded_thread."""
    s = (section_text or "").lower()
    t = (thread_title or "").lower()
    both = f"{s} {t}"

    if re.search(r"council|suspect|tier update|tiering|survey|\bban(?:s|ned)?\b|usage[- ]based", both):
        thread_type = "Council"
    elif re.search(r"viability|strategy|analysis|guide|how to|metagame|rankings?", both):
        thread_type = "Viability"
    else:
        thread_type = "Community"

    # Doubles/VGC first so "doubles ou" and "dou" are not read as OU; 1v1/Monotype/Ubers fall under Other.
    if re.search(r"\bvgc\b|\bdoubles\b|\bdou\b", both):
        tier = "Doubles/VGC"
    elif re.search(r"\b1v1\b|\bmonotype\b|\bubers?\b|\blc\b|\bag\b|\bcap\b|\bhackmons\b|\bnatdex\b", both):
        tier = "Other"
    elif re.search(r"\b(?:uu|ru|nu|pu|zu)\b", both):
        tier = "Lower tiers"
    elif re.search(r"\bou\b", both):
        tier = "OU"
    else:
        tier = "Other"
    return thread_type, tier


def parse_post_element(post_el: BeautifulSoup, thread_url: str) -> dict:
    author = None
    for sel in (".username", ".message-userDetails .username", ".message-userBlock a", ".u-concealed", ".username--name"):
        a = post_el.select_one(sel)
        if a and a.get_text(strip=True):
            author = a.get_text(strip=True)
            break
    if not author:
        a = post_el.find("a", href=True)
        if a and "members" in (a.get("href") or "") and a.get_text(strip=True):
            author = a.get_text(strip=True)

    post_id = extract_post_id_from_attrs(post_el)

    timestamp_raw = None
    time_el = post_el.find("time")
    if time_el and time_el.has_attr("datetime"):
        timestamp_raw = time_el["datetime"]
    else:
        for sel in (".date", ".post-date", ".message-date", ".post_time", ".posted", ".u-dt"):
            el = post_el.select_one(sel)
            if el and el.get_text(strip=True):
                timestamp_raw = el.get_text(" ", strip=True)
                break

    content_el = None
    for sel in (".bbWrapper", ".message-content", ".messageText", ".message-body", ".postcontent", ".content"):
        content_el = post_el.select_one(sel)
        if content_el:
            break
    if not content_el:
        descendants = post_el.find_all(["div", "article", "section"], recursive=True)
        best = None
        best_len = 0
        for d in descendants:
            txt = d.get_text(strip=True) or ""
            if len(txt) > best_len:
                best_len = len(txt)
                best = d
        content_el = best or post_el

    content_html = content_el.decode_contents() if content_el else ""
    content_text = content_el.get_text("\n", strip=True) if content_el else post_el.get_text("\n", strip=True)

    permalink = None
    if post_id:
        if post_el.has_attr("id"):
            permalink = urljoin(thread_url, f"#{post_el.get('id')}")
        else:
            permalink = urljoin(thread_url, f"#post-{post_id}")

    return {
        "site": urlparse(thread_url).netloc,
        "thread_url": thread_url,
        "post_id": post_id,
        "author": author,
        "timestamp_raw": timestamp_raw,
        "content_html": content_html,
        "content_text": content_text,
        "permalink": permalink,
    }


# ---- discovery / thread metadata helpers ----
def parse_listing_page_html(html: str, base_url: str) -> List[Tuple[str, str]]:
    return parse_listing_for_threads(html, base_url)


def get_thread_first_page_info_from_html(thread_url: str, html: str) -> Dict:
    soup = BeautifulSoup(html, "lxml")
    title = None
    for sel in ("h1.p-title-value", "h1", ".structItem-title", ".thread-title", ".p-title"):
        el = soup.select_one(sel)
        if el:
            title = el.get_text(" ", strip=True)
            break

    post_elements = []
    for sel in ("article.message", "div.message", ".structItem--thread .structItem-row", ".post", ".postbit"):
        found = soup.select(sel)
        if found:
            post_elements = found
            break
    if not post_elements:
        found = soup.find_all(attrs={"class": re.compile(r".*message.*", re.I)})
        post_elements = found or []

    posts_on_first_page = len(post_elements)

    # Robust page-number detection
    page_nums = set()
    for a in soup.find_all("a", href=True):
        txt = (a.get_text(" ", strip=True) or "")
        if txt.isdigit():
            try:
                page_nums.add(int(txt))
            except ValueError:
                pass
        href = a["href"]
        m = re.search(r"(?:/page-|/page/|\bpage=)(\d+)", href)
        if m:
            try:
                page_nums.add(int(m.group(1)))
            except ValueError:
                pass

    for el in soup.find_all(attrs={"data-page": True}):
        try:
            page_nums.add(int(el.get("data-page")))
        except Exception:
            pass

    last_page = max(page_nums) if page_nums else 1

    return {
        "title": title,
        "posts_on_first_page": posts_on_first_page,
        "first_page_html": html,
        "last_page_num": last_page,
        "post_elements_count": posts_on_first_page,
        "soup": soup,
    }


# ---- caching helpers ----
def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


def cache_page_html(cache_dir: str, thread_url: str, page_num: int, html: str) -> str:
    h = hashlib.sha1(thread_url.encode("utf8")).hexdigest()[:12]
    fname = f"thread-{h}-page-{page_num}.html"
    path = os.path.join(cache_dir, fname)
    with open(path, "w", encoding="utf8") as fh:
        fh.write(html)
    return path


# ---- sampling and selection ----
def _apportion(props: Dict[str, float], n: int) -> Dict[str, int]:
    """Split n across keys by proportion (largest remainder) so the counts sum to n."""
    total = sum(props.values()) or 1.0
    raw = {k: v / total * n for k, v in props.items()}
    out = {k: int(r) for k, r in raw.items()}
    for k in sorted(raw, key=lambda k: raw[k] - out[k], reverse=True)[: n - sum(out.values())]:
        out[k] += 1
    return out


def stratified_thread_sampling(
    candidates: List[Dict],
    target_threads: int,
    seed: int,
    type_props: Optional[Dict[str, float]] = None,
    tier_props: Optional[Dict[str, float]] = None,
    recent_share: float = 0.5,
) -> List[Dict]:
    """Pick threads per (type x time) quota, steering the tier mix toward tier_props.

    Within each type, recent threads fill round(recent_share * quota) slots. Each slot takes a thread from the
    tier furthest below its target, so tiers stay balanced across types. Sticky threads are picked last.
    Quotas that cannot be filled are logged and topped up from whatever candidates remain."""
    rnd = random.Random(seed)
    pool = [c for c in candidates if c.get("thread_type") in (type_props or DEFAULT_TYPE_PROPS)]
    type_targets = _apportion(type_props or DEFAULT_TYPE_PROPS, target_threads)
    tier_targets = _apportion(tier_props or DEFAULT_TIER_PROPS, target_threads)
    tier_counts: Dict[str, int] = defaultdict(int)
    sampled: List[Dict] = []

    def take(ttype: str, recent: bool, need: int) -> int:
        avail = [c for c in pool if c["thread_type"] == ttype and bool(c.get("is_recent")) == recent and c not in sampled]
        rnd.shuffle(avail)
        avail.sort(key=lambda c: bool(c.get("sticky")))  # stable: non-sticky first
        got = 0
        while got < need and avail:
            tiers = {c.get("tier") or "Other" for c in avail}
            tier = max(tiers, key=lambda t: (tier_targets.get(t, 0) - tier_counts[t], rnd.random()))
            pick = next(c for c in avail if (c.get("tier") or "Other") == tier)
            avail.remove(pick)
            sampled.append(pick)
            tier_counts[tier] += 1
            got += 1
        return got

    for ttype, count in type_targets.items():
        recent_need = int(round(count * recent_share))
        for recent, need in ((True, recent_need), (False, count - recent_need)):
            got = take(ttype, recent, need)
            if got < need:
                logging.warning("Quota short: %s %s wanted %d threads, found %d", ttype, "recent" if recent else "older", need, got)

    if len(sampled) < target_threads:
        remaining = [c for c in pool if c not in sampled]
        rnd.shuffle(remaining)
        topup = remaining[: target_threads - len(sampled)]
        logging.warning("Topping up %d threads from outside the quota cells", len(topup))
        sampled.extend(topup)
    return sampled[:target_threads]


def select_posts_within_thread(thread_url: str, cached_pages: Dict[int, str], anonymize: bool, hash_salt: str, seed: int, raw_per_thread: int = 7) -> Tuple[List[dict], List[int]]:
    rnd = random.Random(seed + int(hashlib.sha256(thread_url.encode("utf8")).hexdigest()[:8], 16))
    page_nums = sorted(cached_pages.keys())
    global_posts = []
    for page_num in page_nums:
        path = cached_pages[page_num]
        with open(path, "r", encoding="utf8") as fh:
            html = fh.read()
        if is_error_page(html):
            logging.warning("Skipping cached error page %s", path)
            continue
        soup = BeautifulSoup(html, "lxml")
        post_elements = []
        for sel in ("article.message", "div.message", ".structItem--thread .structItem-row", ".post", ".postbit"):
            found = soup.select(sel)
            if found:
                post_elements = found
                break
        if not post_elements:
            found = soup.find_all(attrs={"class": re.compile(r".*message.*", re.I)})
            post_elements = found or []
        for el in post_elements:
            pdata = parse_post_element(el, thread_url)
            # mark deleted/empty
            content_text = (pdata.get("content_text") or "").strip()
            pdata["_is_deleted_or_empty"] = (not content_text)
            global_posts.append(pdata)

    # Helper: parse timestamp and return timezone-aware UTC datetime for consistent comparisons
    def _parse_ts_to_utc(p):
        ts = p.get("timestamp_raw")
        if not ts:
            return datetime.min.replace(tzinfo=timezone.utc)
        try:
            dt = dtparser.parse(ts)
            if dt.tzinfo is None:
                # assume UTC for naive timestamps
                dt = dt.replace(tzinfo=timezone.utc)
            else:
                dt = dt.astimezone(timezone.utc)
            return dt
        except Exception:
            return datetime.min.replace(tzinfo=timezone.utc)

    # stable sort: first by parsed time (UTC), then by original order (enumerate index)
    enumerated = list(enumerate(global_posts, start=1))
    enumerated.sort(key=lambda it: (_parse_ts_to_utc(it[1]), it[0]))
    chron_posts = [p for idx, p in enumerated]
    total_available = len(chron_posts)

    # Build desired indices (1-based) per plan: OP + first 2 replies + random replies up to raw_per_thread in all
    planned = []
    if total_available >= 1:
        planned.append(1)  # OP
    if total_available >= 2:
        planned.append(2)
    if total_available >= 3:
        planned.append(3)
    remaining = list(range(4, total_available + 1))
    if remaining:
        rnd.shuffle(remaining)
        extra = min(max(raw_per_thread - 3, 0), len(remaining))
        planned.extend(sorted(remaining[:extra]))

    # Filter out deleted/empty; if a planned index is excluded, choose the next available index (deterministic)
    final_indices = []
    for idx in planned:
        chosen = None
        for cand in range(idx, total_available + 1):
            p = chron_posts[cand - 1]
            if p.get("_is_deleted_or_empty"):
                continue
            chosen = cand
            break
        if chosen:
            final_indices.append(chosen)
    # dedupe & keep order
    final_indices = sorted(dict.fromkeys(final_indices).keys())

    selected_posts = []
    for idx in final_indices:
        p = chron_posts[idx - 1]
        post = dict(p)
        post["global_index"] = idx
        post["scraped_at"] = datetime.now(timezone.utc).isoformat()
        if anonymize and post.get("author"):
            post["author_hashed"] = hashlib.sha256((post["author"] + hash_salt).encode("utf8")).hexdigest()
            post.pop("author", None)
        selected_posts.append(post)

    return selected_posts, final_indices


# ---- orchestration ----
def collect_posts_with_playwright(
    fetcher: BrowserFetcher,
    base_forum_home: str,
    include_keywords: Optional[List[str]],
    target_posts: int = 200,
    target_threads: int = 30,
    forum_pages: int = 3,
    anonymize: bool = False,
    output_file: str = "smogon_posts.jsonl",
    cache_dir: str = "cache_smogon",
    manifest_file: str = "sample_manifest.json",
    seed: int = 42,
    force_robots: bool = False,
    type_props: Optional[Dict[str, float]] = None,
    tier_props: Optional[Dict[str, float]] = None,
    recent_share: float = 0.5,
    raw_per_thread: int = 7,
    min_thread_posts: int = 5,
) -> Tuple[str, str]:
    rp, can_fetch = check_robots(base_forum_home)
    if can_fetch is False:
        raise SystemExit("robots.txt explicitly disallows crawling these forum paths. Aborting.")
    if can_fetch is None and not force_robots:
        raise SystemExit("Could not read robots.txt. Aborting by default. Use --force to override.")
    if force_robots:
        logging.warning("Proceeding despite robots.txt unreadable or disallowing paths (user supplied --force).")

    ensure_dir(cache_dir)
    candidates = []
    sections = []
    # fetch forum home via browser
    logging.info("Fetching forum home: %s", base_forum_home)
    home_html = fetcher.fetch_html(base_forum_home, timeout_s=30)
    if not home_html:
        logging.warning("Could not fetch forum home HTML via browser; aborting discovery.")
        return output_file, manifest_file
    sections = parse_listing_for_threads(home_html, base_forum_home)
    # sections will contain many thread links; we want section links (forum sections).
    # fallback: discover section links by searching anchor hrefs that include '/forums/'
    if not sections:
        soup_home = BeautifulSoup(home_html, "lxml")
        sec_links = []
        for a in soup_home.find_all("a", href=True):
            href = a["href"]
            if "/forums/" in href and not THREAD_PATH_RE.search(href):
                sec_links.append((urljoin(base_forum_home, href), a.get_text(" ", strip=True)))
        # dedupe and limit
        seen = set()
        sections = []
        for u, t in sec_links:
            if u not in seen:
                seen.add(u)
                sections.append((u, t))
    # If still empty, log and abort
    if not sections:
        logging.warning("No forum sections found on home page; aborting.")
        return output_file, manifest_file

    # Prepare section list (we only need url and text)
    # If parse_listing_for_threads returned thread links rather than sections, convert to unique sections by path
    section_pairs = []
    for u, t in sections:
        # if this looks like a thread (contains /threads/), skip; we want '/forums/' section links
        if THREAD_PATH_RE.search(u):
            continue
        section_pairs.append((u, t))
    if not section_pairs:
        # fallback: take top-level forums by scanning all anchors again
        soup_home = BeautifulSoup(home_html, "lxml")
        sec_links = []
        for a in soup_home.find_all("a", href=True):
            href = a["href"]
            if "/forums/" in href and not THREAD_PATH_RE.search(href):
                sec_links.append((urljoin(base_forum_home, href), a.get_text(" ", strip=True)))
        seen = set()
        for u, t in sec_links:
            if u not in seen:
                seen.add(u)
                section_pairs.append((u, t))
    logging.info("Discovered %d forum sections", len(section_pairs))
    if include_keywords:
        kw_re = re.compile(r"(?:" + "|".join(re.escape(k) for k in include_keywords) + r")", re.I)
        matched = [(u, t) for u, t in section_pairs if kw_re.search(f"{t} {u}")]
        if matched:
            section_pairs = matched
            logging.info("Keyword filter kept %d sections", len(section_pairs))
        else:
            logging.warning("No section matched the keywords; scanning every section")

    # Candidate discovery: scan each section for threads
    for section_url, section_text in section_pairs:
        if len(candidates) >= target_threads * 8:
            break
        logging.info("Scanning section %s", section_url)
        for page in range(1, forum_pages + 1):
            page_url = section_url if page == 1 else (section_url.rstrip("/") + f"/page-{page}")
            logging.info("Fetching forum listing: %s", page_url)
            html = fetcher.fetch_html(page_url, timeout_s=30)
            if not html:
                logging.debug("Failed to fetch listing page %s", page_url)
                continue
            found_threads = parse_listing_for_threads(html, page_url)
            # convert to simple thread URL/title tuples
            for turl, title in found_threads:
                if is_excluded_thread(turl, title):
                    continue
                if turl not in [c.get("thread_url") for c in candidates]:
                    # get first page of thread to estimate pages/posts
                    thread_html = fetcher.fetch_html(turl, timeout_s=30)
                    if not thread_html:
                        continue
                    info = get_thread_first_page_info_from_html(turl, thread_html)
                    posts_per_page = max(1, info.get("posts_on_first_page", 1))
                    last_page = max(1, int(info.get("last_page_num", 1)))
                    total_estimated = max(1, posts_per_page * last_page)
                    # skip threads too short to hold enough in-scope replies
                    if total_estimated < min_thread_posts:
                        continue
                    # OP timestamp if present
                    op_time = None
                    soup = info.get("soup")
                    if soup:
                        post_hits = []
                        for sel in ("article.message", "div.message", ".post", ".postbit"):
                            post_hits = soup.select(sel)
                            if post_hits:
                                break
                        if not post_hits:
                            post_hits = soup.find_all(attrs={"class": re.compile(r".*message.*", re.I)})
                        if post_hits:
                            parsed_op = parse_post_element(post_hits[0], turl)
                            op_time = parsed_op.get("timestamp_raw")
                    is_recent = False
                    if op_time:
                        try:
                            dt = dtparser.parse(op_time)
                            # normalize to timezone-aware UTC
                            if dt.tzinfo is None:
                                dt = dt.replace(tzinfo=timezone.utc)
                            else:
                                dt = dt.astimezone(timezone.utc)
                            cutoff = datetime.now(timezone.utc) - timedelta(days=RECENT_MONTHS * 30)
                            is_recent = dt >= cutoff
                        except Exception:
                            is_recent = False
                    ttype, tier = detect_thread_type_and_tier(section_text or "", info.get("title") or "")
                    candidates.append({
                        "thread_url": turl,
                        "section_text": section_text,
                        "title": info.get("title"),
                        "posts_per_page": posts_per_page,
                        "last_page_num": last_page,
                        "total_posts_estimated": total_estimated,
                        "op_time": op_time,
                        "is_recent": is_recent,
                        "thread_type": ttype,
                        "tier": tier,
                        "first_page_html": info.get("first_page_html"),
                    })
                    # politeness
                    time.sleep(DEFAULT_SLEEP + random.random() * DEFAULT_JITTER)
            # polite pause between listing pages
            time.sleep(DEFAULT_SLEEP + random.random() * DEFAULT_JITTER)

    logging.info("Collected %d candidate threads", len(candidates))
    if not candidates:
        logging.warning("No candidate threads discovered; exiting.")
        return output_file, manifest_file

    sampled_threads = stratified_thread_sampling(candidates, target_threads, seed, type_props, tier_props, recent_share)
    logging.info("Sampled %d threads", len(sampled_threads))

    # Now fetch only pages needed for selected threads, cache, and pick posts within-thread
    ensure_dir(cache_dir)
    posts_written = 0
    # Stage 1 oversamples: every sampled thread gets its raw posts. subsample.py applies the final target.
    raw_limit = max(target_posts, len(sampled_threads) * raw_per_thread)
    manifest = {
        "seed": seed,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "target_posts": target_posts,
        "target_threads": target_threads,
        "sampling_plan": {
            "per_thread_type_proportions": type_props or DEFAULT_TYPE_PROPS,
            "tier_proportions": tier_props or DEFAULT_TIER_PROPS,
            "recent_share": recent_share,
            "raw_per_thread": raw_per_thread,
            "min_thread_posts": min_thread_posts,
        },
        "sampled_threads": [],
    }
    fh_out = open(output_file, "w", encoding="utf8")

    for th in sampled_threads:
        if posts_written >= raw_limit:
            break
        turl = th["thread_url"]
        total_est = int(th.get("total_posts_estimated", 1))
        posts_per_page = int(th.get("posts_per_page", 1))
        # plan indices: OP (1), first 2 replies (2,3) if present, plus random others up to raw_per_thread
        selected_indices = [1]
        if total_est >= 2:
            selected_indices.append(2)
        if total_est >= 3:
            selected_indices.append(3)
        possible = list(range(4, total_est + 1))
        if possible:
            rnd_thread = random.Random(seed + int(hashlib.sha256(turl.encode("utf8")).hexdigest()[:8], 16))
            rnd_thread.shuffle(possible)
            extra = min(max(raw_per_thread - 3, 0), len(possible))
            selected_indices.extend(sorted(possible[:extra]))

        pages_needed = sorted({math.ceil(idx / posts_per_page) for idx in selected_indices})
        # ensure page 1 fetched
        if 1 not in pages_needed:
            pages_needed.insert(0, 1)

        cached_pages = {}
        saved_page_paths = {}
        for pnum in pages_needed:
            if pnum == 1 and th.get("first_page_html"):
                html = th.get("first_page_html")
            else:
                page_url = turl if pnum == 1 else (turl.rstrip("/") + f"/page-{pnum}")
                html = fetcher.fetch_html(page_url, timeout_s=30)
                if not html:
                    logging.warning("Failed to fetch %s", page_url)
                    continue
                if is_error_page(html):
                    logging.warning("Got error page for %s; skipping", page_url)
                    continue
                time.sleep(DEFAULT_SLEEP + random.random() * DEFAULT_JITTER)
            path = cache_page_html(cache_dir, turl, pnum, html)
            # compute SHA1 of html for reproducibility
            sha = hashlib.sha1(html.encode("utf8")).hexdigest()
            cached_pages[pnum] = path
            saved_page_paths[str(pnum)] = {"path": path, "sha1": sha}

        # use improved selection that sorts chronologically and avoids empty/deleted posts
        selected_posts, resolved_indices = select_posts_within_thread(turl, cached_pages, anonymize, "", seed, raw_per_thread)
        wrote_indices = []
        for post in selected_posts:
            if posts_written >= raw_limit:
                break
            fh_out.write(json.dumps(post, ensure_ascii=False) + "\n")
            posts_written += 1
            wrote_indices.append(post.get("global_index"))
        manifest["sampled_threads"].append({
            "thread_url": turl,
            "thread_title": th.get("title"),
            "thread_type": th.get("thread_type"),
            "tier": th.get("tier"),
            "is_recent": th.get("is_recent"),
            "total_posts_estimated": total_est,
            "pages_fetched": pages_needed,
            "cached_pages": saved_page_paths,
            "selected_indices_planned": selected_indices,
            "selected_indices_written": wrote_indices,
            "thread_rng_seed": seed + int(hashlib.sha256(turl.encode("utf8")).hexdigest()[:8], 16),
        })
        time.sleep(DEFAULT_SLEEP * 1.5 + random.random() * DEFAULT_JITTER)

    fh_out.close()
    with open(manifest_file, "w", encoding="utf8") as mh:
        json.dump(manifest, mh, ensure_ascii=False, indent=2)

    logging.info("Finished collection: wrote %d posts to %s; manifest -> %s; cache_dir=%s", posts_written, output_file, manifest_file, cache_dir)
    return output_file, manifest_file


# ---- CLI ----
def main():
    parser = argparse.ArgumentParser(description="Smogon scraper (Playwright) with stratified sampling")
    parser.add_argument("--home", default="https://www.smogon.com/forums/", help="Smogon forum home URL")
    parser.add_argument("--keywords", nargs="+", default=DEFAULT_KEYWORDS, help="Forum keywords to include")
    parser.add_argument("--target", type=int, default=200, help="Number of posts to collect")
    parser.add_argument("--target-threads", type=int, default=28, help="Number of threads to sample")
    parser.add_argument("--forum-pages", type=int, default=3, help="Listing pages to scan per forum section")
    parser.add_argument("--anonymize", action="store_true", help="Hash usernames in output")
    parser.add_argument("--output", default="smogon_posts_v2.jsonl", help="JSONL output file")
    parser.add_argument("--cache-dir", default="cache_smogon_v2", help="Directory to cache HTML pages")
    parser.add_argument("--manifest", default="sample_manifest_v2.json", help="Manifest JSON describing sample")
    parser.add_argument("--seed", type=int, default=42, help="RNG seed for reproducible sampling")
    parser.add_argument("--force", action="store_true", help="Proceed even if robots.txt unreadable or disallows crawling")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    parser.add_argument("--headless", action="store_true", help="Run browser headless (default); omit to see browser window")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    fetcher = None
    try:
        fetcher = BrowserFetcher(headless=args.headless, user_agent=BROWSER_UA)
        collect_posts_with_playwright(
            fetcher=fetcher,
            base_forum_home=args.home,
            include_keywords=args.keywords,
            target_posts=args.target,
            target_threads=args.target_threads,
            forum_pages=args.forum_pages,
            anonymize=args.anonymize,
            output_file=args.output,
            cache_dir=args.cache_dir,
            manifest_file=args.manifest,
            seed=args.seed,
            force_robots=args.force,
        )
    except Exception as e:
        logging.exception("Unhandled error: %s", e)
    finally:
        if fetcher:
            fetcher.close()


if __name__ == "__main__":
    main()