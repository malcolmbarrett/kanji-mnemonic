#!/usr/bin/env python3
"""Extract sound mnemonic character→reading mappings from WaniKani API.

This is a one-time helper script (not installed, not tested by CI).
It fetches reading_mnemonic text from kanji subjects and extracts
the recurring character names WK associates with specific readings.

WK uses two patterns in reading mnemonics:
  1. <reading>EnglishName</reading> (hiragana) — e.g., <reading>Ken</reading> (けん)
  2. <reading>hiragana</reading>suffix — e.g., <reading>こう</reading>いち

Usage:
    uv run python scripts/extract_wk_sound_mnemonics.py

Output: wk_sound_mnemonics_draft.json for manual curation, plus a
        detailed report of all associations with context.
"""

import json
import os
import re
from collections import Counter, defaultdict

import requests
from dotenv import load_dotenv

WK_API_BASE = "https://api.wanikani.com/v2"


def fetch_kanji_reading_mnemonics(api_key: str) -> list[dict]:
    """Fetch all kanji subjects with reading_mnemonic fields."""
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
    return results


def extract_associations(items: list[dict]) -> dict[str, Counter]:
    """Extract reading → character name associations from mnemonic text.

    Looks for two WK patterns:
      1. <reading>EnglishName</reading>...(hiragana)
      2. <reading>hiragana</reading>trailing_hiragana (forms a name)
    """
    # Pattern 1: English name in <reading> tag, hiragana reading in parens
    p_english = re.compile(
        r"<reading>([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)</reading>"
        r"[^(]{0,30}\(([ぁ-ゖァ-ヶー]+)\)"
    )

    # Pattern 2: Hiragana in <reading> tag, followed by more hiragana
    p_hiragana = re.compile(r"<reading>([ぁ-ゖ]+)</reading>([ぁ-ゖ]+)")

    # reading (hiragana) -> {character_name: count}
    associations: dict[str, Counter] = defaultdict(Counter)

    for item in items:
        text = item["reading_mnemonic"]

        # Pattern 1: English name
        for name, reading in p_english.findall(text):
            reading_h = _katakana_to_hiragana(reading)
            associations[reading_h][name] += 1

        # Pattern 2: Hiragana reading + suffix = name
        for reading, suffix in p_hiragana.findall(text):
            full_name = reading + suffix
            if suffix and len(full_name) >= 2:
                associations[reading][full_name] += 1

    return associations


def find_character_intros(
    items: list[dict], character_names: set[str]
) -> dict[str, str]:
    """Find character introduction text in mnemonics for descriptions."""
    intros: dict[str, str] = {}

    for item in items:
        text = item["reading_mnemonic"]
        for name in character_names:
            if name not in text:
                continue
            idx = text.find(name)
            start = max(0, idx - 80)
            end = min(len(text), idx + len(name) + 150)
            context = text[start:end].replace("\n", " ").strip()
            # Prefer introductions
            intro_keywords = [
                "character",
                "use",
                "meet",
                "every time",
                "introduce",
                "he's",
                "she's",
                "who is",
                "will be",
                "remember",
            ]
            if any(kw in context.lower() for kw in intro_keywords):
                if name not in intros or len(context) > len(intros[name]):
                    intros[name] = context
    return intros


def _katakana_to_hiragana(text: str) -> str:
    """Convert katakana to hiragana."""
    return "".join(chr(ord(c) - 0x60) if "\u30a1" <= c <= "\u30f6" else c for c in text)


def main():
    load_dotenv()
    load_dotenv(os.path.expanduser("~/.config/kanji/.env"))
    api_key = os.environ.get("WK_API_KEY")
    if not api_key:
        print("Error: Set WK_API_KEY environment variable")
        print(
            "  Get your key at:"
            " https://www.wanikani.com/settings/personal_access_tokens"
        )
        return

    print("Fetching WK kanji reading mnemonics...")
    items = fetch_kanji_reading_mnemonics(api_key)

    print("\nExtracting character→reading associations...")
    associations = extract_associations(items)

    # Collect all character names for intro search
    all_names: set[str] = set()
    for counter in associations.values():
        all_names.update(counter.keys())

    print("Searching for character introductions...")
    intros = find_character_intros(items, all_names)

    # Build result
    print("\n=== Character→reading associations (≥2 occurrences) ===\n")
    result = {}
    for reading in sorted(associations.keys()):
        counter = associations[reading]
        top = counter.most_common(3)
        if top and top[0][1] >= 2:
            char_name = top[0][0]
            count = top[0][1]
            names_str = ", ".join(f"{n} (×{c})" for n, c in top)
            print(f"  {reading} → {names_str}")
            result[reading] = {
                "character": char_name,
                "count": count,
                "alternatives": [
                    {"character": name, "count": c} for name, c in top[1:]
                ],
                "intro": intros.get(char_name, ""),
            }

    # Write detailed draft (with counts and context)
    detail_path = "wk_sound_mnemonics_detailed.json"
    with open(detail_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\nDetailed draft saved to {detail_path}")

    # Write clean version (for bundling after curation)
    clean = {}
    for reading, info in result.items():
        clean[reading] = {
            "character": info["character"],
            "description": f"{info['character']} (from WK mnemonics, {info['count']} occurrences)",
        }

    output_path = "wk_sound_mnemonics_draft.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(clean, f, ensure_ascii=False, indent=2)
    print(f"Clean draft saved to {output_path}")
    print("Review and curate before copying to kanji_mnemonic/wk_sound_mnemonics.json")


if __name__ == "__main__":
    main()
