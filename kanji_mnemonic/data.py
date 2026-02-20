"""Download, cache, and load the Keisei and WaniKani databases."""

import json
import os
from pathlib import Path

import requests

CACHE_DIR = Path(os.environ.get("KANJI_MNEMONIC_CACHE", Path.home() / ".cache" / "kanji-mnemonic"))

KEISEI_BASE = "https://raw.githubusercontent.com/mwil/wanikani-userscripts/8ee517737d604f1df0ff103a33b69f1f07218815/wanikani-phonetic-compounds/db"
DB_URLS = {
    "kanji_db": f"{KEISEI_BASE}/kanji_esc.json",
    "phonetic_db": f"{KEISEI_BASE}/phonetic_esc.json",
    "wk_kanji_db": f"{KEISEI_BASE}/wk_kanji_esc.json",
}

KRADFILE_URLS = [
    "https://raw.githubusercontent.com/jmettraux/kensaku/master/data/kradfile-u",
    "https://raw.githubusercontent.com/fasiha/kanjipath/master/resources/data/kradfile-u",
]

WK_API_BASE = "https://api.wanikani.com/v2"


def ensure_cache_dir():
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _download_json(url: str) -> dict:
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _load_or_download(name: str, url: str) -> dict:
    ensure_cache_dir()
    cache_path = CACHE_DIR / f"{name}.json"
    if cache_path.exists():
        return json.loads(cache_path.read_text(encoding="utf-8"))
    print(f"Downloading {name}...")
    data = _download_json(url)
    cache_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return data


def load_kanji_db() -> dict:
    return _load_or_download("kanji_db", DB_URLS["kanji_db"])


def load_phonetic_db() -> dict:
    return _load_or_download("phonetic_db", DB_URLS["phonetic_db"])


def load_wk_kanji_db() -> dict:
    return _load_or_download("wk_kanji_db", DB_URLS["wk_kanji_db"])


def fetch_wk_radicals(api_key: str) -> dict:
    """Fetch all WK radicals and build a char->name mapping. Cached after first call."""
    ensure_cache_dir()
    cache_path = CACHE_DIR / "wk_radicals.json"
    if cache_path.exists():
        return json.loads(cache_path.read_text(encoding="utf-8"))

    print("Fetching WaniKani radicals (one-time)...")
    radicals = {}  # character -> {"name": str, "level": int}
    url = f"{WK_API_BASE}/subjects?types=radical"
    headers = {"Authorization": f"Bearer {api_key}"}

    while url:
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        payload = resp.json()
        for item in payload["data"]:
            d = item["data"]
            char = d.get("characters")
            if char:  # some radicals are image-only
                primary = next(
                    (m["meaning"] for m in d["meanings"] if m["primary"]),
                    d["meanings"][0]["meaning"] if d["meanings"] else None,
                )
                radicals[char] = {
                    "name": primary,
                    "level": d["level"],
                    "slug": d["slug"],
                }
        url = payload["pages"].get("next_url")

    cache_path.write_text(json.dumps(radicals, ensure_ascii=False), encoding="utf-8")
    print(f"  Cached {len(radicals)} radicals.")
    return radicals


def fetch_wk_kanji_subjects(api_key: str) -> dict:
    """Fetch all WK kanji subjects for component/amalgamation info. Cached."""
    ensure_cache_dir()
    cache_path = CACHE_DIR / "wk_kanji_subjects.json"
    if cache_path.exists():
        return json.loads(cache_path.read_text(encoding="utf-8"))

    print("Fetching WaniKani kanji subjects (one-time)...")
    kanji_map = {}  # character -> subject data
    # Also need radical subjects for ID->char mapping
    radical_id_map = {}  # subject_id -> character
    
    # First pass: get radicals to build ID map
    url = f"{WK_API_BASE}/subjects?types=radical"
    headers = {"Authorization": f"Bearer {api_key}"}
    while url:
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        payload = resp.json()
        for item in payload["data"]:
            char = item["data"].get("characters")
            if char:
                radical_id_map[item["id"]] = char
        url = payload["pages"].get("next_url")

    # Second pass: get kanji
    url = f"{WK_API_BASE}/subjects?types=kanji"
    while url:
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        payload = resp.json()
        for item in payload["data"]:
            d = item["data"]
            char = d.get("characters")
            if char:
                # Resolve component radical IDs to characters
                component_chars = []
                for rid in d.get("component_subject_ids", []):
                    if rid in radical_id_map:
                        component_chars.append(radical_id_map[rid])
                kanji_map[char] = {
                    "meanings": [m["meaning"] for m in d["meanings"]],
                    "readings": {
                        "onyomi": [r["reading"] for r in d["readings"] if r["type"] == "onyomi"],
                        "kunyomi": [r["reading"] for r in d["readings"] if r["type"] == "kunyomi"],
                    },
                    "component_radicals": component_chars,
                    "level": d["level"],
                }
        url = payload["pages"].get("next_url")

    cache_path.write_text(json.dumps(kanji_map, ensure_ascii=False), encoding="utf-8")
    print(f"  Cached {len(kanji_map)} kanji subjects.")
    return kanji_map


def load_kradfile() -> dict:
    """Load KRADFILE-u radical decomposition data. Cached after first download."""
    ensure_cache_dir()
    cache_path = CACHE_DIR / "kradfile.json"
    if cache_path.exists():
        return json.loads(cache_path.read_text(encoding="utf-8"))

    print("Downloading KRADFILE-u...")
    text = None
    for url in KRADFILE_URLS:
        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            text = resp.text
            break
        except requests.RequestException:
            continue

    if text is None:
        print("Warning: Could not download KRADFILE-u from any mirror.")
        return {}

    # Parse: each line is "kanji : radical1 radical2 ..."
    kradfile = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if " : " not in line:
            continue
        kanji, radicals = line.split(" : ", 1)
        kradfile[kanji.strip()] = radicals.strip().split()

    cache_path.write_text(json.dumps(kradfile, ensure_ascii=False), encoding="utf-8")
    print(f"  Cached {len(kradfile)} KRADFILE-u entries.")
    return kradfile


def clear_cache():
    """Remove all cached files."""
    if CACHE_DIR.exists():
        for f in CACHE_DIR.iterdir():
            f.unlink()
        print(f"Cache cleared: {CACHE_DIR}")
    else:
        print("No cache to clear.")
