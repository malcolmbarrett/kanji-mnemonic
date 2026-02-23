# Scripts

Dev-time utilities for maintaining the WK sound mnemonic database.
These scripts are **not installed** with the package and **not tested by CI**.

## Prerequisites

Both scripts require a WaniKani API key. Set `WK_API_KEY` in either:

- `.env` in the project root
- `~/.config/kanji/.env`

Get a key at: <https://www.wanikani.com/settings/personal_access_tokens>

## Scripts

### `extract_wk_sound_mnemonics.py`

Extracts character-name-to-reading associations from WK kanji reading mnemonics.

WK uses recurring characters in mnemonics to encode readings. For example,
**Koichi** (こういち) appears in mnemonics for kanji read as こう, and **Ken**
(けん) appears for kanji read as けん. This script finds those patterns.

It detects two formats WK uses in `<reading>` tags:

1. `<reading>EnglishName</reading> (hiragana)` — e.g., `<reading>Ken</reading> (けん)`
2. `<reading>hiragana</reading>suffix` — e.g., `<reading>こう</reading>いち`

```bash
uv run python scripts/extract_wk_sound_mnemonics.py
```

**Output**: `wk_sound_mnemonics_draft.json` (clean, for bundling) and
`wk_sound_mnemonics_detailed.json` (with counts, alternatives, and intro context).

### `verify_wk_sound_mnemonics.py`

Validates each entry in the bundled `wk_sound_mnemonics.json` against live WK API data.

For every entry, it:

- Counts how many kanji have that reading as primary
- Searches those kanji's reading mnemonics for the character name
- Reports mention counts and sample context
- Flags entries with zero mentions, mismatched readings, or low confidence

Also scans for **missed entries** — readings not in the database that have a
consistent character name (5+ occurrences) in mnemonics.

```bash
uv run python scripts/verify_wk_sound_mnemonics.py           # uses cached API data
uv run python scripts/verify_wk_sound_mnemonics.py --no-cache # re-fetch from API
```

API data is cached locally to `scripts/.wk_mnemonic_cache.json` (gitignored).

## Curation workflow

1. **Extract** — Run `extract_wk_sound_mnemonics.py` to get a draft
2. **Curate** — Review the draft, fix character names and descriptions manually
3. **Update** — Copy curated entries to `kanji_mnemonic/wk_sound_mnemonics.json`
4. **Verify** — Run `verify_wk_sound_mnemonics.py` to validate against API
5. **Test** — Run `uv run pytest tests/` to confirm nothing broke
