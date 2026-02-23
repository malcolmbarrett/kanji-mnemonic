"""Download, cache, and load the Keisei and WaniKani databases."""

import importlib.resources
import io
import json
import os
import tarfile
from pathlib import Path

import requests

CACHE_DIR = Path(
    os.environ.get("KANJI_MNEMONIC_CACHE", Path.home() / ".cache" / "kanji-mnemonic")
)
CONFIG_DIR = Path(
    os.environ.get("KANJI_MNEMONIC_CONFIG", Path.home() / ".config" / "kanji")
)

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
                        "onyomi": [
                            r["reading"] for r in d["readings"] if r["type"] == "onyomi"
                        ],
                        "kunyomi": [
                            r["reading"]
                            for r in d["readings"]
                            if r["type"] == "kunyomi"
                        ],
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


KANJIDIC_API_URL = (
    "https://api.github.com/repos/scriptin/jmdict-simplified/releases/latest"
)


def _katakana_to_hiragana(text: str) -> str:
    """Convert katakana characters to hiragana. Non-katakana passes through."""
    # Katakana block: U+30A1..U+30F6, offset from hiragana is 0x60
    return "".join(chr(ord(c) - 0x60) if "\u30a1" <= c <= "\u30f6" else c for c in text)


def _parse_kanjidic(raw: dict) -> dict:
    """Parse raw kanjidic2 JSON into {char: {meanings, onyomi, kunyomi, grade, frequency}}.

    - ja_on readings are converted from katakana to hiragana
    - Only English meanings are kept
    - Characters with no readingMeaning are skipped
    - Multiple readingMeaning groups are merged
    - grade and frequency are extracted from the misc section (None if absent)
    """
    result = {}
    for entry in raw.get("characters", []):
        literal = entry["literal"]
        rm = entry.get("readingMeaning")
        if rm is None:
            continue

        meanings = []
        onyomi = []
        kunyomi = []
        for group in rm.get("groups", []):
            for r in group.get("readings", []):
                if r["type"] == "ja_on":
                    onyomi.append(_katakana_to_hiragana(r["value"]))
                elif r["type"] == "ja_kun":
                    kunyomi.append(r["value"])
            for m in group.get("meanings", []):
                if m.get("lang", "en") == "en":
                    meanings.append(m["value"])

        misc = entry.get("misc", {})
        result[literal] = {
            "meanings": meanings,
            "onyomi": onyomi,
            "kunyomi": kunyomi,
            "grade": misc.get("grade"),
            "frequency": misc.get("frequency"),
        }
    return result


def load_kanjidic() -> dict:
    """Load Kanjidic2 data from jmdict-simplified. Cached after first download.

    Downloads a .tgz tarball from the latest GitHub release, extracts the JSON,
    parses it into {char: {meanings, onyomi, kunyomi}}, and caches as kanjidic.json.
    """
    ensure_cache_dir()
    cache_path = CACHE_DIR / "kanjidic.json"
    if cache_path.exists():
        return json.loads(cache_path.read_text(encoding="utf-8"))

    print("Downloading Kanjidic2 from jmdict-simplified...")

    # Find the kanjidic2-en tarball URL from the latest release
    resp = requests.get(KANJIDIC_API_URL, timeout=30)
    resp.raise_for_status()
    release = resp.json()

    tarball_url = None
    for asset in release.get("assets", []):
        if asset["name"].startswith("kanjidic2-en") and asset["name"].endswith(
            ".json.tgz"
        ):
            tarball_url = asset["browser_download_url"]
            break

    if tarball_url is None:
        raise RuntimeError(
            "Could not find kanjidic2-en tarball in latest jmdict-simplified release"
        )

    # Download and extract the tarball
    resp = requests.get(tarball_url, timeout=120)
    resp.raise_for_status()

    with tarfile.open(fileobj=io.BytesIO(resp.content), mode="r:gz") as tar:
        # The tarball contains a single JSON file
        members = tar.getmembers()
        json_member = next(m for m in members if m.name.endswith(".json"))
        f = tar.extractfile(json_member)
        if f is None:
            raise RuntimeError(f"Could not extract {json_member.name} from tarball")
        raw = json.loads(f.read().decode("utf-8"))

    result = _parse_kanjidic(raw)

    cache_path.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    print(f"  Cached {len(result)} Kanjidic2 entries.")
    return result


def load_personal_radicals() -> dict:
    """Load the user's personal radical name dictionary.

    Returns {char: name} dict, or empty dict if the file doesn't exist.
    """
    path = CONFIG_DIR / "radicals.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_personal_radical(char: str, name: str) -> None:
    """Save or update a personal radical name.

    Creates the config directory and file if they don't exist.
    """
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    path = CONFIG_DIR / "radicals.json"
    data = {}
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
    data[char] = name
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def load_personal_decompositions() -> dict:
    """Load the user's personal kanji decompositions.

    Returns {kanji: {"parts": [...], "phonetic": str|None, "semantic": str|None}},
    or empty dict if the file doesn't exist.
    """
    path = CONFIG_DIR / "decompositions.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_personal_decomposition(
    kanji: str,
    parts: list[str],
    phonetic: str | None = None,
    semantic: str | None = None,
) -> None:
    """Save or update a personal kanji decomposition.

    Creates the config directory and file if they don't exist.
    """
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    path = CONFIG_DIR / "decompositions.json"
    data = {}
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
    data[kanji] = {
        "parts": parts,
        "phonetic": phonetic,
        "semantic": semantic,
    }
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def remove_personal_decomposition(kanji: str) -> bool:
    """Remove a personal decomposition for a kanji.

    Returns True if an entry was removed, False if not found.
    """
    path = CONFIG_DIR / "decompositions.json"
    if not path.exists():
        return False
    data = json.loads(path.read_text(encoding="utf-8"))
    if kanji not in data:
        return False
    del data[kanji]
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return True


def load_wk_sound_mnemonics() -> dict:
    """Load the bundled WK sound mnemonic database.

    Returns {reading: {"character": str, "description": str}}.
    Loaded from kanji_mnemonic/wk_sound_mnemonics.json via importlib.resources.
    """
    ref = importlib.resources.files("kanji_mnemonic") / "wk_sound_mnemonics.json"
    return json.loads(ref.read_text(encoding="utf-8"))


def merge_sound_mnemonics(wk_sounds: dict, personal_sounds: dict) -> dict:
    """Merge WK and personal sound mnemonics. Personal overrides WK."""
    merged = dict(wk_sounds)
    merged.update(personal_sounds)
    return merged


def load_personal_sound_mnemonics() -> dict:
    """Load the user's personal sound mnemonic dictionary.

    Returns {reading: {"character": str, "description": str}}, or empty dict.
    """
    path = CONFIG_DIR / "sound_mnemonics.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_personal_sound_mnemonic(
    reading: str, character: str, description: str
) -> None:
    """Save or update a personal sound mnemonic for a reading."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    path = CONFIG_DIR / "sound_mnemonics.json"
    data = {}
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
    data[reading] = {"character": character, "description": description}
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def remove_personal_sound_mnemonic(reading: str) -> bool:
    """Remove a personal sound mnemonic. Returns True if removed, False if not found."""
    path = CONFIG_DIR / "sound_mnemonics.json"
    if not path.exists():
        return False
    data = json.loads(path.read_text(encoding="utf-8"))
    if reading not in data:
        return False
    del data[reading]
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return True


def load_reading_overrides() -> dict:
    """Load the user's reading override dictionary.

    Returns {kanji: "onyomi"|"kunyomi"} dict, or empty dict if the file doesn't exist.
    """
    path = CONFIG_DIR / "reading_overrides.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_reading_override(kanji: str, reading_type: str) -> None:
    """Save or update a reading override for a kanji.

    Creates the config directory and file if they don't exist.
    Raises ValueError if reading_type is not 'onyomi' or 'kunyomi'.
    """
    if reading_type not in ("onyomi", "kunyomi"):
        raise ValueError(
            f"reading_type must be 'onyomi' or 'kunyomi', got '{reading_type}'"
        )
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    path = CONFIG_DIR / "reading_overrides.json"
    data = {}
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
    data[kanji] = reading_type
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def remove_reading_override(kanji: str) -> bool:
    """Remove a reading override for a kanji.

    Returns True if an entry was removed, False if not found.
    """
    path = CONFIG_DIR / "reading_overrides.json"
    if not path.exists():
        return False
    data = json.loads(path.read_text(encoding="utf-8"))
    if kanji not in data:
        return False
    del data[kanji]
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return True


def load_mnemonics() -> dict:
    """Load the user's saved mnemonics dictionary.

    Returns {kanji: {"mnemonic": str, "model": str, "timestamp": str}},
    or empty dict if the file doesn't exist.
    """
    path = CONFIG_DIR / "mnemonics.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_mnemonic_for_kanji(kanji: str) -> dict | None:
    """Load a single saved mnemonic entry, or None if not found."""
    return load_mnemonics().get(kanji)


def save_mnemonic(kanji: str, mnemonic: str, model: str) -> None:
    """Save or update a mnemonic for a kanji character.

    Creates the config directory and file if they don't exist.
    Stores with an ISO-format timestamp.
    """
    from datetime import datetime

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    path = CONFIG_DIR / "mnemonics.json"
    data = {}
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
    data[kanji] = {
        "mnemonic": mnemonic,
        "model": model,
        "timestamp": datetime.now().isoformat(),
    }
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def clear_cache():
    """Remove all cached files."""
    if CACHE_DIR.exists():
        for f in CACHE_DIR.iterdir():
            f.unlink()
        print(f"Cache cleared: {CACHE_DIR}")
    else:
        print("No cache to clear.")
