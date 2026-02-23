#!/usr/bin/env python3
"""Verify the bundled WK sound mnemonic database against live API data.

This script validates each entry in wk_sound_mnemonics.json by checking
whether the character name actually appears in WK reading mnemonics for
kanji with that reading. It also scans for associations missing from
the database.

Usage:
    uv run python scripts/verify_wk_sound_mnemonics.py
    uv run python scripts/verify_wk_sound_mnemonics.py --no-cache

Output: a verification report printed to stdout.
"""

import argparse
import json
import os
import re
from collections import Counter, defaultdict
from pathlib import Path

import requests
from dotenv import load_dotenv

WK_API_BASE = "https://api.wanikani.com/v2"
SCRIPT_DIR = Path(__file__).parent
CACHE_PATH = SCRIPT_DIR / ".wk_mnemonic_cache.json"
DB_PATH = SCRIPT_DIR.parent / "kanji_mnemonic" / "wk_sound_mnemonics.json"

# Short/common English words that need word-boundary matching
COMMON_WORDS = {"Go", "No", "Ha", "Jo", "Bo", "Me", "Ra", "Ya", "Eh", "Ah", "Ok"}


def fetch_or_load_cached(api_key: str, *, no_cache: bool = False) -> list[dict]:
    """Fetch kanji subjects from WK API, with local caching."""
    if not no_cache and CACHE_PATH.exists():
        print(f"  Loading cached data from {CACHE_PATH.name}...")
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))

    headers = {"Authorization": f"Bearer {api_key}"}
    results = []
    url = f"{WK_API_BASE}/subjects?types=kanji"

    page = 0
    while url:
        page += 1
        print(f"  Fetching page {page}...", end="\r")
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        payload = resp.json()
        for item in payload["data"]:
            d = item["data"]
            rm = d.get("reading_mnemonic", "")
            if rm:
                results.append(
                    {
                        "characters": d.get("characters", ""),
                        "readings": {
                            r["reading"]: r["type"] for r in d.get("readings", [])
                        },
                        "primary": [
                            r["reading"] for r in d.get("readings", []) if r["primary"]
                        ],
                        "reading_mnemonic": rm,
                    }
                )
        url = payload["pages"].get("next_url")

    print(f"  Fetched {len(results)} kanji with reading mnemonics.    ")
    CACHE_PATH.write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"  Cached to {CACHE_PATH.name}")
    return results


def _katakana_to_hiragana(text: str) -> str:
    """Convert katakana to hiragana."""
    return "".join(chr(ord(c) - 0x60) if "\u30a1" <= c <= "\u30f6" else c for c in text)


def _strip_html(text: str) -> str:
    """Strip HTML tags from text."""
    return re.sub(r"<[^>]+>", "", text)


def _name_in_text(name: str, text: str) -> bool:
    """Check if a character name appears in text.

    Strips HTML tags first (WK wraps parts of names in <reading> tags,
    e.g., <reading>Jo</reading>-Anne). Uses word-boundary matching for
    short/common English words to avoid false positives.
    """
    clean = _strip_html(text)
    if name in COMMON_WORDS:
        return bool(re.search(rf"\b{re.escape(name)}\b", clean))
    return name in clean


def _extract_context(name: str, text: str, width: int = 80) -> str:
    """Extract context around a name match in text."""
    # Strip HTML tags for cleaner display
    clean = re.sub(r"<[^>]+>", "", text)
    if name in COMMON_WORDS:
        m = re.search(rf"\b{re.escape(name)}\b", clean)
        if not m:
            return ""
        idx = m.start()
    else:
        idx = clean.find(name)
        if idx == -1:
            return ""
    start = max(0, idx - width // 2)
    end = min(len(clean), idx + len(name) + width // 2)
    snippet = clean[start:end].replace("\n", " ").strip()
    return f"...{snippet}..."


def verify_entries(db: dict, items: list[dict]) -> tuple[list[dict], list[dict]]:
    """Verify each database entry against WK mnemonic data.

    Returns (verified, flagged) lists.
    """
    verified = []
    flagged = []

    for reading, info in sorted(db.items()):
        char_name = info["character"]
        # Strip parenthetical from character name for matching
        # e.g., "Koichi (こういち)" -> search for both "Koichi" and "こういち"
        search_names = [char_name]
        paren_match = re.search(r"\(([^)]+)\)", char_name)
        if paren_match:
            search_names.append(paren_match.group(1))
            search_names.append(char_name.split("(")[0].strip())

        # Find kanji with this primary reading
        kanji_with_reading = [item for item in items if reading in item["primary"]]

        # Count mentions in kanji with this reading
        mentions_for_reading = 0
        # Count mentions across ALL kanji
        mentions_total = 0
        sample_contexts = []

        for item in items:
            text = item["reading_mnemonic"]
            found = any(_name_in_text(n, text) for n in search_names)
            if found:
                mentions_total += 1
                if reading in item["primary"]:
                    mentions_for_reading += 1
                if len(sample_contexts) < 3:
                    for n in search_names:
                        ctx = _extract_context(n, text)
                        if ctx:
                            sample_contexts.append(f"{item['characters']}: {ctx}")
                            break

        entry = {
            "reading": reading,
            "character": char_name,
            "description": info["description"],
            "kanji_with_reading": len(kanji_with_reading),
            "mentions_for_reading": mentions_for_reading,
            "mentions_total": mentions_total,
            "sample_contexts": sample_contexts,
            "flag": None,
        }

        if mentions_total == 0:
            entry["flag"] = "NOT FOUND in any mnemonic"
        elif mentions_for_reading == 0:
            entry["flag"] = (
                f"Found {mentions_total}x total but NEVER for {reading} reading"
            )
        elif mentions_for_reading < 3:
            entry["flag"] = (
                f"LOW confidence ({mentions_for_reading} mentions for {reading})"
            )

        if entry["flag"]:
            flagged.append(entry)
        else:
            verified.append(entry)

    return verified, flagged


def find_missed(items: list[dict], existing_readings: set[str]) -> list[dict]:
    """Find consistent character→reading associations not in the database."""
    # Same regex patterns as extraction script
    p_english = re.compile(
        r"<reading>([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)</reading>"
        r"[^(]{0,30}\(([ぁ-ゖァ-ヶー]+)\)"
    )
    p_hiragana = re.compile(r"<reading>([ぁ-ゖ]+)</reading>([ぁ-ゖ]+)")

    associations: dict[str, Counter] = defaultdict(Counter)

    for item in items:
        text = item["reading_mnemonic"]
        for name, reading in p_english.findall(text):
            reading_h = _katakana_to_hiragana(reading)
            associations[reading_h][name] += 1
        for reading, suffix in p_hiragana.findall(text):
            full_name = reading + suffix
            if suffix and len(full_name) >= 2:
                associations[reading][full_name] += 1

    missed = []
    for reading in sorted(associations.keys()):
        if reading in existing_readings:
            continue
        counter = associations[reading]
        top = counter.most_common(1)
        if top and top[0][1] >= 5:
            missed.append(
                {
                    "reading": reading,
                    "character": top[0][0],
                    "count": top[0][1],
                }
            )

    return missed


def print_report(
    verified: list[dict],
    flagged: list[dict],
    missed: list[dict],
    total_kanji: int,
) -> None:
    """Print the verification report."""
    total = len(verified) + len(flagged)

    print(f"\n{'=' * 60}")
    print("WK Sound Mnemonic Verification Report")
    print(f"{'=' * 60}")
    print(f"\nVerified {total} entries against {total_kanji} WK kanji.\n")

    # Verified
    print(f"── Verified Entries ({len(verified)}/{total}) ──\n")
    for e in verified:
        pct = (
            f" ({e['mentions_for_reading']}/{e['kanji_with_reading']}"
            f" kanji with this reading)"
        )
        print(f"  {e['reading']} → {e['character']}: {e['mentions_total']}x total{pct}")

    # Flagged
    if flagged:
        print(f"\n── Flagged Entries ({len(flagged)}/{total}) ──\n")
        for e in flagged:
            print(f"  !! {e['reading']} → {e['character']}: {e['flag']}")
            for ctx in e["sample_contexts"][:2]:
                print(f"     {ctx}")

    # Missed
    if missed:
        print(f"\n── Potential Missed Entries ({len(missed)}) ──\n")
        for m in missed:
            print(f"  {m['reading']} → {m['character']} ({m['count']}x)")

    # Summary
    print("\n── Summary ──\n")
    print(f"  Verified: {len(verified)}/{total}")
    print(f"  Flagged:  {len(flagged)}/{total}")
    print(f"  Missed:   {len(missed)} potential additions")


def main():
    parser = argparse.ArgumentParser(description="Verify WK sound mnemonic database")
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Force re-fetch from WK API (ignore cache)",
    )
    args = parser.parse_args()

    load_dotenv()
    load_dotenv(os.path.expanduser("~/.config/kanji/.env"))
    api_key = os.environ.get("WK_API_KEY")
    if not api_key:
        print("Error: Set WK_API_KEY environment variable")
        return

    print("Loading WK kanji data...")
    items = fetch_or_load_cached(api_key, no_cache=args.no_cache)

    print("Loading bundled database...")
    db = json.loads(DB_PATH.read_text(encoding="utf-8"))
    print(f"  {len(db)} entries in {DB_PATH.name}")

    print("Verifying entries...")
    verified, flagged = verify_entries(db, items)

    print("Scanning for missed associations...")
    missed = find_missed(items, set(db.keys()))

    print_report(verified, flagged, missed, len(items))


if __name__ == "__main__":
    main()
