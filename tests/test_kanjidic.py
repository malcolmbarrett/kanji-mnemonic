"""Tests for JMdict/Kanjidic2 integration (bd-19m).

Tests the not-yet-implemented load_kanjidic() in data.py and the kanjidic
fallback path in lookup.py. These tests define the expected API contract
for the feature described in bd-1ne.

The kanjidic2 JSON from jmdict-simplified has this structure per character:
{
  "literal": "亜",
  "readingMeaning": {
    "groups": [{
      "readings": [
        {"type": "ja_on", "value": "ア"},      # katakana
        {"type": "ja_kun", "value": "つ.ぐ"}    # hiragana w/ okurigana
      ],
      "meanings": [
        {"lang": "en", "value": "Asia"},
        {"lang": "fr", "value": "Asie"}
      ]
    }],
    "nanori": ["や"]
  }
}

The load_kanjidic() function should:
- Download a .tgz tarball from GitHub releases
- Extract the JSON inside
- Parse into {kanji_char: {meanings: [...], onyomi: [...], kunyomi: [...]}}
  where ja_on readings are converted katakana -> hiragana
- Cache the parsed dict as kanjidic.json
"""

import io
import json
import tarfile

import pytest
import responses


# ---------------------------------------------------------------------------
# Helpers — build realistic kanjidic2 JSON and tarballs for tests
# ---------------------------------------------------------------------------


def _kanjidic2_entry(literal, groups=None, nanori=None, misc=None):
    """Build a single kanjidic2 character entry."""
    rm = None
    if groups is not None:
        rm = {"groups": groups, "nanori": nanori or []}
    return {
        "literal": literal,
        "codepoints": [],
        "radicals": [],
        "misc": misc or {},
        "dictionaryReferences": [],
        "queryCodes": [],
        "readingMeaning": rm,
    }


def _reading(type_, value):
    return {"type": type_, "value": value}


def _meaning(value, lang="en"):
    return {"lang": lang, "value": value}


def _kanjidic2_json(characters):
    """Build a complete kanjidic2 JSON structure."""
    return {
        "version": "3.6.1",
        "languages": ["en"],
        "commonOnly": False,
        "characters": characters,
    }


def _make_tarball(json_data, inner_filename="kanjidic2-en-3.6.1.json"):
    """Create an in-memory .tgz containing a single JSON file."""
    json_bytes = json.dumps(json_data, ensure_ascii=False).encode("utf-8")
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        info = tarfile.TarInfo(name=inner_filename)
        info.size = len(json_bytes)
        tar.addfile(info, io.BytesIO(json_bytes))
    buf.seek(0)
    return buf.read()


# ---------------------------------------------------------------------------
# Sample kanjidic2 entries for test fixtures
# ---------------------------------------------------------------------------

# 亜 — has on'yomi ア (katakana), kun'yomi つ.ぐ, English meanings
ENTRY_A = _kanjidic2_entry(
    "亜",
    groups=[
        {
            "readings": [
                _reading("ja_on", "ア"),
                _reading("ja_kun", "つ.ぐ"),
            ],
            "meanings": [
                _meaning("Asia"),
                _meaning("rank next"),
                _meaning("Asie", "fr"),  # non-English, should be filtered
            ],
        }
    ],
    misc={
        "grade": 8,
        "strokeCounts": [7],
        "frequency": 1509,
        "variants": [],
        "radicalNames": [],
    },
)

# 圧 — has on'yomi アツ (katakana, multi-mora), English meaning
ENTRY_ATSU = _kanjidic2_entry(
    "圧",
    groups=[
        {
            "readings": [
                _reading("ja_on", "アツ"),
                _reading("ja_kun", "お.す"),
            ],
            "meanings": [
                _meaning("pressure"),
                _meaning("push"),
            ],
        }
    ],
    misc={
        "grade": 5,
        "strokeCounts": [5],
        "frequency": 640,
        "variants": [],
        "radicalNames": [],
    },
)

# 鬱 — complex kanji with multiple on readings, no kun; no grade or frequency
ENTRY_UTSU = _kanjidic2_entry(
    "鬱",
    groups=[
        {
            "readings": [
                _reading("ja_on", "ウツ"),
            ],
            "meanings": [
                _meaning("gloom"),
                _meaning("depression"),
            ],
        }
    ],
    misc={"strokeCounts": [29], "variants": [], "radicalNames": []},
)

# 々 — readingMeaning is null (no readings/meanings)
ENTRY_NOMA = _kanjidic2_entry("々", groups=None)

# 丑 — has multiple readingMeaning groups
ENTRY_USHI = _kanjidic2_entry(
    "丑",
    groups=[
        {
            "readings": [
                _reading("ja_on", "チュウ"),
                _reading("ja_kun", "うし"),
            ],
            "meanings": [
                _meaning("sign of the ox"),
            ],
        },
        {
            "readings": [
                _reading("ja_kun", "ひねる"),
            ],
            "meanings": [
                _meaning("twist"),
            ],
        },
    ],
)

SAMPLE_CHARACTERS = [ENTRY_A, ENTRY_ATSU, ENTRY_UTSU, ENTRY_NOMA, ENTRY_USHI]
SAMPLE_KANJIDIC2_JSON = _kanjidic2_json(SAMPLE_CHARACTERS)
SAMPLE_TARBALL = _make_tarball(SAMPLE_KANJIDIC2_JSON)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_cache_dir(tmp_path, monkeypatch):
    """Redirect CACHE_DIR to a temp directory."""
    monkeypatch.setattr("kanji_mnemonic.data.CACHE_DIR", tmp_path)
    return tmp_path


@pytest.fixture
def sample_kanjidic():
    """Pre-parsed kanjidic dict in the format load_kanjidic() should return."""
    return {
        "亜": {
            "meanings": ["Asia", "rank next"],
            "onyomi": ["あ"],
            "kunyomi": ["つ.ぐ"],
            "grade": 8,
            "frequency": 1509,
        },
        "圧": {
            "meanings": ["pressure", "push"],
            "onyomi": ["あつ"],
            "kunyomi": ["お.す"],
            "grade": 5,
            "frequency": 640,
        },
        "鬱": {
            "meanings": ["gloom", "depression"],
            "onyomi": ["うつ"],
            "kunyomi": [],
            "grade": None,
            "frequency": None,
        },
        "丑": {
            "meanings": ["sign of the ox", "twist"],
            "onyomi": ["ちゅう"],
            "kunyomi": ["うし", "ひねる"],
            "grade": None,
            "frequency": None,
        },
        # 々 has no readingMeaning, so it should be omitted or have empty lists
    }


# ---------------------------------------------------------------------------
# TestKatakanaToHiragana
# ---------------------------------------------------------------------------


class TestKatakanaToHiragana:
    """Tests for the katakana-to-hiragana conversion used on ja_on readings."""

    def test_single_mora(self):
        """ア -> あ"""
        from kanji_mnemonic.data import _katakana_to_hiragana

        assert _katakana_to_hiragana("ア") == "あ"

    def test_multi_mora(self):
        """アツ -> あつ"""
        from kanji_mnemonic.data import _katakana_to_hiragana

        assert _katakana_to_hiragana("アツ") == "あつ"

    def test_with_dakuten(self):
        """ゴ -> ご"""
        from kanji_mnemonic.data import _katakana_to_hiragana

        assert _katakana_to_hiragana("ゴ") == "ご"

    def test_with_handakuten(self):
        """パ -> ぱ"""
        from kanji_mnemonic.data import _katakana_to_hiragana

        assert _katakana_to_hiragana("パ") == "ぱ"

    def test_long_reading(self):
        """チュウ -> ちゅう"""
        from kanji_mnemonic.data import _katakana_to_hiragana

        assert _katakana_to_hiragana("チュウ") == "ちゅう"

    def test_already_hiragana(self):
        """Hiragana input passes through unchanged."""
        from kanji_mnemonic.data import _katakana_to_hiragana

        assert _katakana_to_hiragana("あつ") == "あつ"

    def test_mixed_katakana_hiragana(self):
        """Mixed input converts only katakana characters."""
        from kanji_mnemonic.data import _katakana_to_hiragana

        assert _katakana_to_hiragana("カた") == "かた"

    def test_empty_string(self):
        """Empty string returns empty string."""
        from kanji_mnemonic.data import _katakana_to_hiragana

        assert _katakana_to_hiragana("") == ""


# ---------------------------------------------------------------------------
# TestParseKanjidic
# ---------------------------------------------------------------------------


class TestParseKanjidic:
    """Tests for parsing the raw kanjidic2 JSON into the app's internal format.

    The parser should extract English meanings, convert ja_on katakana to
    hiragana, and keep ja_kun as-is.
    """

    def test_basic_entry(self):
        """亜: on'yomi ア -> あ, kun'yomi つ.ぐ, English meanings only."""
        from kanji_mnemonic.data import _parse_kanjidic

        raw = _kanjidic2_json([ENTRY_A])
        result = _parse_kanjidic(raw)

        assert "亜" in result
        assert result["亜"]["meanings"] == ["Asia", "rank next"]
        assert result["亜"]["onyomi"] == ["あ"]
        assert result["亜"]["kunyomi"] == ["つ.ぐ"]

    def test_filters_non_english_meanings(self):
        """Only meanings with lang='en' are included."""
        from kanji_mnemonic.data import _parse_kanjidic

        raw = _kanjidic2_json([ENTRY_A])
        result = _parse_kanjidic(raw)

        meanings = result["亜"]["meanings"]
        assert "Asie" not in meanings
        assert "Asia" in meanings

    def test_null_reading_meaning_skipped(self):
        """Characters with readingMeaning=null are excluded from the result."""
        from kanji_mnemonic.data import _parse_kanjidic

        raw = _kanjidic2_json([ENTRY_NOMA])
        result = _parse_kanjidic(raw)

        assert "々" not in result

    def test_multiple_groups_merged(self):
        """丑 has two readingMeaning groups; readings and meanings are merged."""
        from kanji_mnemonic.data import _parse_kanjidic

        raw = _kanjidic2_json([ENTRY_USHI])
        result = _parse_kanjidic(raw)

        assert "丑" in result
        entry = result["丑"]
        assert entry["onyomi"] == ["ちゅう"]
        assert "うし" in entry["kunyomi"]
        assert "ひねる" in entry["kunyomi"]
        assert "sign of the ox" in entry["meanings"]
        assert "twist" in entry["meanings"]

    def test_no_kun_readings(self):
        """鬱 has only on'yomi, kunyomi should be empty list."""
        from kanji_mnemonic.data import _parse_kanjidic

        raw = _kanjidic2_json([ENTRY_UTSU])
        result = _parse_kanjidic(raw)

        assert result["鬱"]["kunyomi"] == []
        assert result["鬱"]["onyomi"] == ["うつ"]

    def test_multiple_characters(self):
        """Parsing multiple characters produces correct number of entries."""
        from kanji_mnemonic.data import _parse_kanjidic

        raw = _kanjidic2_json([ENTRY_A, ENTRY_ATSU, ENTRY_UTSU])
        result = _parse_kanjidic(raw)

        assert len(result) == 3
        assert all(k in result for k in ["亜", "圧", "鬱"])

    def test_non_japanese_readings_excluded(self):
        """pinyin and other non-Japanese reading types are excluded."""
        from kanji_mnemonic.data import _parse_kanjidic

        entry = _kanjidic2_entry(
            "亜",
            groups=[
                {
                    "readings": [
                        _reading("ja_on", "ア"),
                        _reading("pinyin", "yà"),
                        _reading("korean_r", "a"),
                    ],
                    "meanings": [_meaning("Asia")],
                }
            ],
        )
        raw = _kanjidic2_json([entry])
        result = _parse_kanjidic(raw)

        assert result["亜"]["onyomi"] == ["あ"]
        assert result["亜"]["kunyomi"] == []

    def test_extracts_grade(self):
        """Parsed entry includes grade from misc section."""
        from kanji_mnemonic.data import _parse_kanjidic

        raw = _kanjidic2_json([ENTRY_A])
        result = _parse_kanjidic(raw)

        assert result["亜"]["grade"] == 8

    def test_extracts_frequency(self):
        """Parsed entry includes frequency from misc section."""
        from kanji_mnemonic.data import _parse_kanjidic

        raw = _kanjidic2_json([ENTRY_ATSU])
        result = _parse_kanjidic(raw)

        assert result["圧"]["frequency"] == 640

    def test_missing_grade_is_none(self):
        """Entries without grade in misc get grade=None."""
        from kanji_mnemonic.data import _parse_kanjidic

        raw = _kanjidic2_json([ENTRY_UTSU])
        result = _parse_kanjidic(raw)

        assert result["鬱"]["grade"] is None

    def test_missing_frequency_is_none(self):
        """Entries without frequency in misc get frequency=None."""
        from kanji_mnemonic.data import _parse_kanjidic

        raw = _kanjidic2_json([ENTRY_UTSU])
        result = _parse_kanjidic(raw)

        assert result["鬱"]["frequency"] is None


# ---------------------------------------------------------------------------
# TestLoadKanjidic
# ---------------------------------------------------------------------------


class TestLoadKanjidic:
    """Tests for load_kanjidic() — download tarball, extract, parse, cache."""

    def test_cache_hit(self, tmp_cache_dir):
        """When kanjidic.json exists, returns cached data with no HTTP."""
        from kanji_mnemonic.data import load_kanjidic

        cached = {"亜": {"meanings": ["Asia"], "onyomi": ["あ"], "kunyomi": ["つ.ぐ"]}}
        cache_file = tmp_cache_dir / "kanjidic.json"
        cache_file.write_text(json.dumps(cached), encoding="utf-8")

        result = load_kanjidic()

        assert result == cached

    @responses.activate
    def test_download_and_parse(self, tmp_cache_dir):
        """Downloads tarball, extracts JSON, parses into expected format, and caches."""
        from kanji_mnemonic.data import load_kanjidic

        # Mock the GitHub releases API to get the download URL
        responses.add(
            responses.GET,
            "https://api.github.com/repos/scriptin/jmdict-simplified/releases/latest",
            json={
                "assets": [
                    {
                        "name": "kanjidic2-en-3.6.1.json.tgz",
                        "browser_download_url": "https://github.com/scriptin/jmdict-simplified/releases/download/3.6.1/kanjidic2-en-3.6.1.json.tgz",
                    },
                    {
                        "name": "jmdict-en-3.6.1.json.tgz",
                        "browser_download_url": "https://example.com/other",
                    },
                ]
            },
            status=200,
        )
        responses.add(
            responses.GET,
            "https://github.com/scriptin/jmdict-simplified/releases/download/3.6.1/kanjidic2-en-3.6.1.json.tgz",
            body=SAMPLE_TARBALL,
            status=200,
            content_type="application/gzip",
        )

        result = load_kanjidic()

        # Basic structure checks
        assert "亜" in result
        assert result["亜"]["onyomi"] == ["あ"]  # katakana converted
        assert result["亜"]["kunyomi"] == ["つ.ぐ"]
        assert "Asia" in result["亜"]["meanings"]

        # Cache was written
        cache_file = tmp_cache_dir / "kanjidic.json"
        assert cache_file.exists()
        cached = json.loads(cache_file.read_text(encoding="utf-8"))
        assert cached == result

    @responses.activate
    def test_tarball_extraction(self, tmp_cache_dir):
        """The tarball is correctly extracted regardless of inner filename."""
        from kanji_mnemonic.data import load_kanjidic

        # Use a differently named inner file
        custom_tarball = _make_tarball(
            _kanjidic2_json([ENTRY_A]),
            inner_filename="some-other-name.json",
        )

        responses.add(
            responses.GET,
            "https://api.github.com/repos/scriptin/jmdict-simplified/releases/latest",
            json={
                "assets": [
                    {
                        "name": "kanjidic2-en-3.6.1.json.tgz",
                        "browser_download_url": "https://example.com/kanjidic.tgz",
                    }
                ]
            },
            status=200,
        )
        responses.add(
            responses.GET,
            "https://example.com/kanjidic.tgz",
            body=custom_tarball,
            status=200,
            content_type="application/gzip",
        )

        result = load_kanjidic()

        assert "亜" in result

    @responses.activate
    def test_download_failure_propagates(self, tmp_cache_dir):
        """When the tarball download fails, the error propagates."""
        from kanji_mnemonic.data import load_kanjidic

        responses.add(
            responses.GET,
            "https://api.github.com/repos/scriptin/jmdict-simplified/releases/latest",
            json={
                "assets": [
                    {
                        "name": "kanjidic2-en-3.6.1.json.tgz",
                        "browser_download_url": "https://example.com/kanjidic.tgz",
                    }
                ]
            },
            status=200,
        )
        responses.add(
            responses.GET,
            "https://example.com/kanjidic.tgz",
            status=500,
        )

        with pytest.raises(Exception):
            load_kanjidic()

        cache_file = tmp_cache_dir / "kanjidic.json"
        assert not cache_file.exists()

    @responses.activate
    def test_api_failure_propagates(self, tmp_cache_dir):
        """When the GitHub releases API fails, the error propagates."""
        from kanji_mnemonic.data import load_kanjidic

        responses.add(
            responses.GET,
            "https://api.github.com/repos/scriptin/jmdict-simplified/releases/latest",
            status=500,
        )

        with pytest.raises(Exception):
            load_kanjidic()


# ---------------------------------------------------------------------------
# TestLookupKanjiKanjidicFallback
# ---------------------------------------------------------------------------


class TestLookupKanjiKanjidicFallback:
    """Tests for lookup_kanji() using kanjidic to fill missing meaning/readings.

    When a kanji is not in wk_kanji_db or wk_kanji_subjects, lookup_kanji()
    should fall back to kanjidic for meaning, onyomi, and kunyomi.
    """

    def test_fills_missing_meaning(
        self,
        sample_kanjidic,
    ):
        """When a kanji has no WK data, wk_meaning is filled from kanjidic."""
        from kanji_mnemonic.lookup import lookup_kanji

        profile = lookup_kanji(
            "亜",
            {},  # empty kanji_db
            {},  # empty phonetic_db
            {},  # empty wk_kanji_db
            {},  # empty wk_radicals
            None,  # no wk_kanji_subjects
            None,  # no kradfile
            kanjidic=sample_kanjidic,
        )

        assert profile.wk_meaning == "Asia"

    def test_fills_missing_onyomi(
        self,
        sample_kanjidic,
    ):
        """When a kanji has no WK onyomi, onyomi comes from kanjidic."""
        from kanji_mnemonic.lookup import lookup_kanji

        profile = lookup_kanji(
            "亜",
            {},
            {},
            {},
            {},
            None,
            None,
            kanjidic=sample_kanjidic,
        )

        assert profile.onyomi == ["あ"]

    def test_fills_missing_kunyomi(
        self,
        sample_kanjidic,
    ):
        """When a kanji has no WK kunyomi, kunyomi comes from kanjidic."""
        from kanji_mnemonic.lookup import lookup_kanji

        profile = lookup_kanji(
            "亜",
            {},
            {},
            {},
            {},
            None,
            None,
            kanjidic=sample_kanjidic,
        )

        assert profile.kunyomi == ["つ.ぐ"]

    def test_wk_data_takes_priority(
        self,
        sample_kanjidic,
    ):
        """When WK data exists, kanjidic does NOT override it."""
        from kanji_mnemonic.lookup import lookup_kanji

        wk_kanji_db = {
            "亜": {
                "meaning": "Sub-",
                "level": 10,
                "onyomi": "ア",
                "kunyomi": "",
                "important_reading": "onyomi",
            }
        }

        profile = lookup_kanji(
            "亜",
            {},
            {},
            wk_kanji_db,
            {},
            None,
            None,
            kanjidic=sample_kanjidic,
        )

        # WK meaning wins
        assert profile.wk_meaning == "Sub-"
        # WK onyomi wins (note: WK format is comma-separated string)
        assert profile.onyomi == ["ア"]

    def test_partial_fill(
        self,
        sample_kanjidic,
    ):
        """Kanjidic fills only the missing fields; existing WK fields are kept."""
        from kanji_mnemonic.lookup import lookup_kanji

        # WK has meaning but not readings
        wk_kanji_db = {
            "亜": {
                "meaning": "Sub-",
                "level": 10,
                "onyomi": "",
                "kunyomi": "",
                "important_reading": "onyomi",
            }
        }

        profile = lookup_kanji(
            "亜",
            {},
            {},
            wk_kanji_db,
            {},
            None,
            None,
            kanjidic=sample_kanjidic,
        )

        assert profile.wk_meaning == "Sub-"  # from WK
        assert profile.onyomi == ["あ"]  # from kanjidic (WK had empty)
        assert profile.kunyomi == ["つ.ぐ"]  # from kanjidic (WK had empty)

    def test_kanji_not_in_kanjidic(self):
        """When a kanji is not in kanjidic either, fields stay empty."""
        from kanji_mnemonic.lookup import lookup_kanji

        profile = lookup_kanji(
            "X",
            {},
            {},
            {},
            {},
            None,
            None,
            kanjidic={"亜": {"meanings": ["Asia"], "onyomi": ["あ"], "kunyomi": []}},
        )

        assert profile.wk_meaning is None
        assert profile.onyomi == []
        assert profile.kunyomi == []

    def test_kanjidic_none_param(self):
        """When kanjidic=None (not loaded), lookup still works without error."""
        from kanji_mnemonic.lookup import lookup_kanji

        profile = lookup_kanji(
            "亜",
            {},
            {},
            {},
            {},
            None,
            None,
            kanjidic=None,
        )

        assert profile.wk_meaning is None
        assert profile.onyomi == []

    def test_fills_grade(self, sample_kanjidic):
        """lookup_kanji() populates joyo_grade from kanjidic."""
        from kanji_mnemonic.lookup import lookup_kanji

        profile = lookup_kanji(
            "圧",
            {},
            {},
            {},
            {},
            None,
            None,
            kanjidic=sample_kanjidic,
        )

        assert profile.joyo_grade == 5

    def test_fills_frequency(self, sample_kanjidic):
        """lookup_kanji() populates frequency_rank from kanjidic."""
        from kanji_mnemonic.lookup import lookup_kanji

        profile = lookup_kanji(
            "圧",
            {},
            {},
            {},
            {},
            None,
            None,
            kanjidic=sample_kanjidic,
        )

        assert profile.frequency_rank == 640

    def test_missing_grade_stays_none(self, sample_kanjidic):
        """When kanjidic entry has no grade, joyo_grade stays None."""
        from kanji_mnemonic.lookup import lookup_kanji

        profile = lookup_kanji(
            "鬱",
            {},
            {},
            {},
            {},
            None,
            None,
            kanjidic=sample_kanjidic,
        )

        assert profile.joyo_grade is None

    def test_missing_frequency_stays_none(self, sample_kanjidic):
        """When kanjidic entry has no frequency, frequency_rank stays None."""
        from kanji_mnemonic.lookup import lookup_kanji

        profile = lookup_kanji(
            "鬱",
            {},
            {},
            {},
            {},
            None,
            None,
            kanjidic=sample_kanjidic,
        )

        assert profile.frequency_rank is None

    def test_no_kanjidic_grade_stays_none(self):
        """When kanjidic=None, joyo_grade stays None."""
        from kanji_mnemonic.lookup import lookup_kanji

        profile = lookup_kanji(
            "亜",
            {},
            {},
            {},
            {},
            None,
            None,
            kanjidic=None,
        )

        assert profile.joyo_grade is None
        assert profile.frequency_rank is None


# ---------------------------------------------------------------------------
# TestInferPhoneticSemanticWithKanjidic
# ---------------------------------------------------------------------------


class TestInferPhoneticSemanticWithKanjidic:
    """Tests that kanjidic readings enable _infer_phonetic_semantic() for
    non-WK kanji that have no readings from WK sources.

    The key scenario: a non-WK kanji is in kradfile with a component that's
    in phonetic_db. Without kanjidic, the kanji has no onyomi so inference
    can't check reading overlap. With kanjidic providing the onyomi, the
    overlap check can succeed.
    """

    def test_inference_enabled_by_kanjidic_readings(self):
        """Non-WK kanji gets onyomi from kanjidic, enabling phonetic inference."""
        from kanji_mnemonic.lookup import lookup_kanji

        # 嗚 is not in WK. It contains 口 and 烏.
        # 烏 is a phonetic component with reading ウ.
        # 嗚 has on'yomi ウ (from kanjidic), which overlaps with 烏's family.
        phonetic_db = {
            "烏": {
                "readings": ["ウ"],
                "wk-radical": None,
                "compounds": ["鳴"],  # 嗚 not listed
                "non_compounds": [],
                "xrefs": [],
            },
        }
        kradfile = {
            "嗚": ["口", "烏"],
        }
        kanjidic = {
            "嗚": {
                "meanings": ["weep"],
                "onyomi": ["う"],
                "kunyomi": [],
            },
        }

        profile = lookup_kanji(
            "嗚",
            {},  # no kanji_db entry
            phonetic_db,
            {},  # no wk_kanji_db
            {},  # no wk_radicals
            None,
            kradfile,
            kanjidic=kanjidic,
        )

        # Kanjidic filled the onyomi
        assert profile.onyomi == ["う"]
        # This enabled inference: 烏's family readings ["ウ"] overlap with onyomi ["う"]
        # (after accounting for katakana/hiragana matching)
        assert profile.keisei_type in ("comp_phonetic", "comp_phonetic_inferred")
        assert profile.phonetic_component == "烏"
        assert profile.semantic_component == "口"

    def test_no_inference_without_kanjidic(self):
        """Without kanjidic, the same kanji gets no phonetic inference."""
        from kanji_mnemonic.lookup import lookup_kanji

        phonetic_db = {
            "烏": {
                "readings": ["ウ"],
                "wk-radical": None,
                "compounds": ["鳴"],
                "non_compounds": [],
                "xrefs": [],
            },
        }
        kradfile = {
            "嗚": ["口", "烏"],
        }

        profile = lookup_kanji(
            "嗚",
            {},
            phonetic_db,
            {},
            {},
            None,
            kradfile,
            kanjidic=None,
        )

        # Without readings, no inference possible
        assert profile.onyomi == []
        assert profile.keisei_type is None

    def test_kanjidic_meaning_in_profile(self):
        """Kanjidic meaning appears in the profile for non-WK kanji."""
        from kanji_mnemonic.lookup import lookup_kanji

        kanjidic = {
            "嗚": {
                "meanings": ["weep", "cry"],
                "onyomi": ["う"],
                "kunyomi": ["な.く"],
            },
        }

        profile = lookup_kanji(
            "嗚",
            {},
            {},
            {},
            {},
            None,
            None,
            kanjidic=kanjidic,
        )

        assert profile.wk_meaning == "weep"
        assert profile.kunyomi == ["な.く"]
