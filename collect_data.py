"""
collect_data.py
===============
Data collection for the campus survival guide RAG pipeline.

Usage
-----
# 1. Scrape Bucket B sources (static HTML sites):
    python collect_data.py --scrape

# 2. After manually saving Bucket A .txt files into ./docs/raw/:
    python collect_data.py --validate

# 3. Do both in one go:
    python collect_data.py --scrape --validate

Output
------
  docs/raw/          one .txt file per source
  docs/sources.json  metadata for every collected file

Requirements
------------
    pip install requests beautifulsoup4
"""

import argparse
import json
import os
import re
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    sys.exit(
        "Missing dependencies. Run:\n"
        "    pip install requests beautifulsoup4"
    )

# ── Paths ─────────────────────────────────────────────────────────────────────

RAW_DIR = Path("docs/raw")
META_FILE = Path("docs/sources.json")

RAW_DIR.mkdir(parents=True, exist_ok=True)
META_FILE.parent.mkdir(parents=True, exist_ok=True)

# ── Source definitions ─────────────────────────────────────────────────────────

@dataclass
class Source:
    filename: str
    source_type: str
    subtopic: list
    url: str
    published_date: str
    bucket: str          # "A" = manual copy  |  "B" = scriptable
    css_selector: Optional[str] = None   # Bucket B only


SOURCES: list[Source] = [

    # ── Bucket A: copy manually ──────────────────────────────────────────────

    Source(
        filename="reddit_college_tips.txt",
        source_type="reddit",
        subtopic=["housing", "classes", "mental_health", "campus_jobs"],
        url="https://www.reddit.com/r/college/",
        published_date="2024",
        bucket="A",
    ),
    Source(
        filename="ratemyprofessors_sample.txt",
        source_type="review_site",
        subtopic=["classes", "academics"],
        url="https://www.ratemyprofessors.com",
        published_date="2024",
        bucket="A",
    ),
    Source(
        filename="niche_reviews_sample.txt",
        source_type="review_site",
        subtopic=["housing", "food", "safety", "social_life"],
        url="https://www.niche.com/colleges/search/best-student-life/",
        published_date="2024",
        bucket="A",
    ),
    Source(
        filename="quora_college_advice.txt",
        source_type="qa_forum",
        subtopic=["hidden_resources", "finances", "classes", "campus_jobs"],
        url="https://www.quora.com/What-are-some-of-the-most-valuable-experiences-a-college-student-should-not-miss-out-on",
        published_date="2024",
        bucket="A",
    ),
    Source(
        filename="youtube_survival_guide_transcript.txt",
        source_type="youtube",
        subtopic=["study_spaces", "social_life", "mental_health", "classes"],
        url="https://www.youtube.com/watch?v=c58yVp_j55Q",
        published_date="2024",
        bucket="A",
    ),

    # ── Bucket B: scriptable ─────────────────────────────────────────────────

    Source(
        filename="advancetitan_survival_guide.txt",
        source_type="campus_newspaper",
        subtopic=["safety", "transportation", "housing"],
        url="https://advancetitan.com/opinion/2024/09/03/freshman-survival-guide",
        published_date="2024-09-03",
        bucket="B",
        css_selector="article p",
    ),
    Source(
        filename="thedp_dorm_tips.txt",
        source_type="campus_newspaper",
        subtopic=["housing", "social_life"],
        url="https://www.thedp.com/article/2016/06/new-student-issue-tips-dorm-living",
        published_date="2016-06-01",
        bucket="B",
        css_selector="article p",
    ),
    Source(
        filename="umass_sbs_pathways_blog.txt",
        source_type="student_blog",
        subtopic=["classes", "campus_jobs", "mental_health", "hidden_resources"],
        url="https://sbspathways.umass.edu/blog/2022/08/31/what-i-wish-id-known-advice-from-juniors-seniors-and-new-grads/",
        published_date="2022-08-31",
        bucket="B",
        css_selector=".entry-content p",
    ),
    Source(
        filename="hercampus_lmu_hidden_perks.txt",
        source_type="student_blog",
        subtopic=["food", "mental_health", "social_life", "hidden_resources"],
        url="https://www.hercampus.com/school/lmu/hidden-perks-being-college-student/",
        published_date="2023",
        bucket="B",
        css_selector=".article-content p, .hc-content p, article p",
    ),
    Source(
        filename="nbc_news_13_things.txt",
        source_type="news_article",
        subtopic=["food", "finances", "social_life", "classes"],
        url="https://www.nbcnews.com/feature/freshman-year/keep-calm-study-13-things-i-wish-i-knew-freshman-n399641",
        published_date="2015-08-25",
        bucket="B",
        css_selector="article p, .article-body p",
    ),
    Source(
        filename="familyaware_alexs_guide.txt",
        source_type="student_blog",
        subtopic=["mental_health", "housing", "hidden_resources", "classes"],
        url="https://www.familyaware.org/alexs-declassified-college-survival-guide/",
        published_date="2022",
        bucket="B",
        css_selector=".entry-content p, .post-content p, article p",
    ),
    Source(
        filename="unigo_reviews_sample.txt",
        source_type="review_site",
        subtopic=["housing", "food", "social_life", "classes"],
        url="https://www.unigo.com/colleges",
        published_date="2024",
        bucket="B",
        css_selector=".review-text p, .review p, p",
    ),
]


# ── Scraping helpers ──────────────────────────────────────────────────────────

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

# CSS selector fallback chain used when a source's own selector returns nothing
FALLBACK_SELECTORS = [
    "article p",
    ".post-content p",
    ".entry-content p",
    ".article-body p",
    "main p",
    "p",
]


def _clean_text(raw: str) -> str:
    """Remove HTML entities, excessive whitespace, and boilerplate fragments."""
    # Decode common HTML entities that BeautifulSoup may leave behind
    replacements = {
        "&amp;": "&", "&nbsp;": " ", "&lt;": "<", "&gt;": ">",
        "&quot;": '"', "&#39;": "'", "\xa0": " ",
    }
    for entity, char in replacements.items():
        raw = raw.replace(entity, char)

    # Collapse runs of whitespace / blank lines
    raw = re.sub(r"\n{3,}", "\n\n", raw)
    raw = re.sub(r"[ \t]+", " ", raw)

    # Drop very short lines that are almost certainly nav/UI fragments
    lines = [ln.strip() for ln in raw.splitlines()]
    lines = [ln for ln in lines if len(ln) > 30 or ln == ""]
    return "\n".join(lines).strip()


def scrape(source: Source) -> Optional[str]:
    """
    Fetch a Bucket B URL and extract paragraph text.
    Returns cleaned text string, or None on failure.
    """
    print(f"  Fetching {source.url} ...")
    try:
        resp = requests.get(source.url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as exc:
        print(f"    ✗ Request failed: {exc}")
        return None

    soup = BeautifulSoup(resp.text, "html.parser")

    # Remove clutter elements before extracting text
    for tag in soup.select("nav, header, footer, script, style, "
                           ".cookie-banner, .ad, .advertisement, "
                           ".sidebar, .related-posts, .share-buttons"):
        tag.decompose()

    # Try the source-specific selector first, then fall back
    selectors = [source.css_selector] + FALLBACK_SELECTORS if source.css_selector \
        else FALLBACK_SELECTORS

    paragraphs: list[str] = []
    for sel in selectors:
        nodes = soup.select(sel)
        paragraphs = [n.get_text(separator=" ", strip=True) for n in nodes]
        paragraphs = [p for p in paragraphs if len(p) > 40]
        if len(paragraphs) >= 3:
            break

    if not paragraphs:
        print(f"    ✗ No usable paragraphs found (tried {len(selectors)} selectors)")
        return None

    text = _clean_text("\n\n".join(paragraphs))
    word_count = len(text.split())
    print(f"    ✓ {len(paragraphs)} paragraphs · {word_count} words")
    return text


# ── Collection runners ────────────────────────────────────────────────────────

def run_scrape() -> dict[str, bool]:
    """Scrape all Bucket B sources. Returns {filename: success} map."""
    bucket_b = [s for s in SOURCES if s.bucket == "B"]
    print(f"\n── Scraping {len(bucket_b)} Bucket B sources ──")
    results: dict[str, bool] = {}

    for i, source in enumerate(bucket_b):
        print(f"\n[{i+1}/{len(bucket_b)}] {source.filename}")
        text = scrape(source)
        if text:
            path = RAW_DIR / source.filename
            path.write_text(text, encoding="utf-8")
            print(f"    Saved → {path}")
            results[source.filename] = True
        else:
            print(f"    ! Skipped — save text manually to {RAW_DIR / source.filename}")
            results[source.filename] = False

        # Be polite — don't hammer servers
        if i < len(bucket_b) - 1:
            time.sleep(1.5)

    return results


def run_validate() -> None:
    """
    Check every source in SOURCES:
    - Confirm the .txt file exists in docs/raw/
    - Report word count and a 200-character preview
    - Flag files that are suspiciously short
    """
    print(f"\n── Validating {len(SOURCES)} sources ──\n")
    missing: list[str] = []
    short: list[str] = []

    for source in SOURCES:
        path = RAW_DIR / source.filename
        mark = "B" if source.bucket == "B" else "A (manual)"

        if not path.exists():
            print(f"  ✗ MISSING  [{mark}]  {source.filename}")
            if source.bucket == "A":
                print(f"           → Copy text manually and save to {path}")
            missing.append(source.filename)
            continue

        text = path.read_text(encoding="utf-8").strip()
        words = len(text.split())
        preview = text[:200].replace("\n", " ")

        status = "✓" if words >= 100 else "⚠"
        print(f"  {status} {source.filename}")
        print(f"    {words} words  |  {mark}")
        print(f"    Preview: {preview}…\n")

        if words < 100:
            short.append(source.filename)

    # Summary
    present = [s for s in SOURCES if (RAW_DIR / s.filename).exists()]
    print("─" * 60)
    print(f"  Files present : {len(present)} / {len(SOURCES)}")
    if missing:
        print(f"  Missing       : {len(missing)} — add these before chunking")
        for f in missing:
            print(f"    · {f}")
    if short:
        print(f"  Too short (<100 words) : {len(short)}")
        for f in short:
            print(f"    · {f}")
    if not missing and not short:
        print("  All sources look good. Ready for Milestone 3.")


def write_metadata() -> None:
    """Write / overwrite docs/sources.json from the SOURCES list."""
    data = []
    for s in SOURCES:
        entry = asdict(s)
        entry.pop("bucket")
        entry.pop("css_selector")
        data.append(entry)

    META_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"\n  Metadata written → {META_FILE}  ({len(data)} entries)")


# ── Bucket A reminder ─────────────────────────────────────────────────────────

def print_manual_instructions() -> None:
    bucket_a = [s for s in SOURCES if s.bucket == "A"]
    print("\n── Bucket A: manual collection needed ──\n")
    for s in bucket_a:
        path = RAW_DIR / s.filename
        exists = "✓ already saved" if path.exists() else "✗ not yet saved"
        print(f"  {exists}  {s.filename}")
        print(f"    URL  : {s.url}")
        if "reddit" in s.source_type:
            print("    Tip  : Copy 8-12 individual comments, one blank line between each")
        elif "youtube" in s.source_type:
            print("    Tip  : Click ··· under the video → Show transcript, copy all text")
        elif "quora" in s.source_type:
            print("    Tip  : Copy 6-10 top answers; skip the question text itself")
        else:
            print("    Tip  : Copy the main review text only; skip nav/footer/ads")
        print()


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Collect campus survival guide data for the RAG pipeline."
    )
    parser.add_argument(
        "--scrape", action="store_true",
        help="Fetch and save all Bucket B (scriptable) sources"
    )
    parser.add_argument(
        "--validate", action="store_true",
        help="Check all source files and report status"
    )
    parser.add_argument(
        "--instructions", action="store_true",
        help="Print manual collection instructions for Bucket A sources"
    )
    args = parser.parse_args()

    # Default: show help if no flags given
    if not any(vars(args).values()):
        parser.print_help()
        print("\nQuick start:")
        print("  python collect_data.py --instructions   # see what to copy manually")
        print("  python collect_data.py --scrape         # auto-fetch static sites")
        print("  python collect_data.py --validate       # check everything collected")
        return

    # Always write metadata so sources.json stays in sync
    write_metadata()

    if args.instructions:
        print_manual_instructions()

    if args.scrape:
        run_scrape()

    if args.validate:
        run_validate()


if __name__ == "__main__":
    main()