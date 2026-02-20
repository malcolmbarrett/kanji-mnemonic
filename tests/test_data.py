"""Tests for kanji_mnemonic.data — download, cache, and load databases."""

import json

import pytest
import requests
import responses

from kanji_mnemonic.data import (
    DB_URLS,
    KRADFILE_URLS,
    WK_API_BASE,
    _download_json,
    _load_or_download,
    clear_cache,
    fetch_wk_kanji_subjects,
    fetch_wk_radicals,
    load_kanji_db,
    load_kradfile,
    load_phonetic_db,
    load_wk_kanji_db,
)


# ---------------------------------------------------------------------------
# TestDownloadJson
# ---------------------------------------------------------------------------


class TestDownloadJson:
    """Tests for the low-level _download_json helper."""

    @responses.activate
    def test_success(self):
        """A 200 response with JSON body returns the parsed dict."""
        url = "https://example.com/data.json"
        expected = {"key": "value"}
        responses.add(responses.GET, url, json=expected, status=200)

        result = _download_json(url)

        assert result == expected

    @responses.activate
    def test_http_error_raises(self):
        """A 404 response raises HTTPError."""
        url = "https://example.com/missing.json"
        responses.add(responses.GET, url, status=404)

        with pytest.raises(requests.exceptions.HTTPError):
            _download_json(url)

    @responses.activate
    def test_connection_error(self):
        """A connection error propagates as ConnectionError."""
        url = "https://example.com/unreachable.json"
        responses.add(responses.GET, url, body=ConnectionError())

        with pytest.raises(ConnectionError):
            _download_json(url)


# ---------------------------------------------------------------------------
# TestLoadOrDownload
# ---------------------------------------------------------------------------


class TestLoadOrDownload:
    """Tests for the cache-or-fetch helper _load_or_download."""

    @responses.activate
    def test_cache_miss_downloads(self, tmp_cache_dir):
        """When the cache file is absent, the data is downloaded, written to
        disk, and returned."""
        url = "https://example.com/db.json"
        expected = {"kanji": "語"}
        responses.add(responses.GET, url, json=expected, status=200)

        result = _load_or_download("test_db", url)

        assert result == expected
        cache_file = tmp_cache_dir / "test_db.json"
        assert cache_file.exists()
        assert json.loads(cache_file.read_text(encoding="utf-8")) == expected

    def test_cache_hit_no_download(self, tmp_cache_dir):
        """When the cache file already exists, data is loaded from disk with no
        HTTP request (no responses mock registered, so any request would fail)."""
        cached = {"cached": True}
        cache_file = tmp_cache_dir / "test_db.json"
        cache_file.write_text(json.dumps(cached), encoding="utf-8")

        result = _load_or_download("test_db", "https://example.com/should-not-be-called")

        assert result == cached

    @responses.activate
    def test_download_failure_propagates(self, tmp_cache_dir):
        """A 500 error propagates as HTTPError and no cache file is written."""
        url = "https://example.com/broken.json"
        responses.add(responses.GET, url, status=500)

        with pytest.raises(requests.exceptions.HTTPError):
            _load_or_download("broken_db", url)

        cache_file = tmp_cache_dir / "broken_db.json"
        assert not cache_file.exists()


# ---------------------------------------------------------------------------
# TestLoadWrappers
# ---------------------------------------------------------------------------


class TestLoadWrappers:
    """Tests for the thin load_kanji_db / load_phonetic_db / load_wk_kanji_db
    wrappers that delegate to _load_or_download."""

    @responses.activate
    def test_load_kanji_db(self, tmp_cache_dir):
        expected = {"語": {"type": "comp_phonetic"}}
        responses.add(responses.GET, DB_URLS["kanji_db"], json=expected, status=200)

        result = load_kanji_db()

        assert result == expected

    @responses.activate
    def test_load_phonetic_db(self, tmp_cache_dir):
        expected = {"吾": {"readings": ["ゴ"]}}
        responses.add(responses.GET, DB_URLS["phonetic_db"], json=expected, status=200)

        result = load_phonetic_db()

        assert result == expected

    @responses.activate
    def test_load_wk_kanji_db(self, tmp_cache_dir):
        expected = {"語": {"meaning": "Language"}}
        responses.add(responses.GET, DB_URLS["wk_kanji_db"], json=expected, status=200)

        result = load_wk_kanji_db()

        assert result == expected


# ---------------------------------------------------------------------------
# TestFetchWkRadicals
# ---------------------------------------------------------------------------


def _wk_radical_page(radicals, next_url=None):
    """Build a WK API radical response page."""
    return {
        "data": [
            {
                "id": rad["id"],
                "data": {
                    "characters": rad.get("characters"),
                    "level": rad.get("level", 1),
                    "slug": rad.get("slug", "slug"),
                    "meanings": rad.get(
                        "meanings",
                        [{"meaning": rad.get("name", "Unknown"), "primary": True}],
                    ),
                },
            }
            for rad in radicals
        ],
        "pages": {"next_url": next_url},
    }


class TestFetchWkRadicals:
    """Tests for fetch_wk_radicals — WK API radical fetching and caching."""

    def test_cache_hit(self, tmp_cache_dir):
        """When wk_radicals.json exists, returns cached data with no HTTP."""
        cached = {"言": {"name": "Say", "level": 2, "slug": "say"}}
        cache_file = tmp_cache_dir / "wk_radicals.json"
        cache_file.write_text(json.dumps(cached), encoding="utf-8")

        result = fetch_wk_radicals("fake-api-key")

        assert result == cached

    @responses.activate
    def test_paginated_fetch(self, tmp_cache_dir):
        """Follows next_url pagination across two pages and collects all
        radicals."""
        page2_url = f"{WK_API_BASE}/subjects?types=radical&page_after_id=100"

        page1 = _wk_radical_page(
            [{"id": 1, "characters": "言", "name": "Say", "level": 2, "slug": "say"}],
            next_url=page2_url,
        )
        page2 = _wk_radical_page(
            [{"id": 2, "characters": "山", "name": "Mountain", "level": 1, "slug": "mountain"}],
            next_url=None,
        )

        responses.add(
            responses.GET,
            f"{WK_API_BASE}/subjects?types=radical",
            json=page1,
            status=200,
        )
        responses.add(responses.GET, page2_url, json=page2, status=200)

        result = fetch_wk_radicals("fake-key")

        assert "言" in result
        assert result["言"]["name"] == "Say"
        assert "山" in result
        assert result["山"]["name"] == "Mountain"

    @responses.activate
    def test_skips_image_only(self, tmp_cache_dir):
        """Radicals with characters=null (image-only) are excluded."""
        page = _wk_radical_page(
            [
                {"id": 1, "characters": "言", "name": "Say"},
                {"id": 2, "characters": None, "name": "Barb"},
            ]
        )
        responses.add(
            responses.GET,
            f"{WK_API_BASE}/subjects?types=radical",
            json=page,
            status=200,
        )

        result = fetch_wk_radicals("fake-key")

        assert "言" in result
        assert len(result) == 1

    @responses.activate
    def test_primary_meaning(self, tmp_cache_dir):
        """When a radical has multiple meanings, the primary one is used."""
        page = _wk_radical_page(
            [
                {
                    "id": 1,
                    "characters": "言",
                    "level": 2,
                    "slug": "say",
                    "meanings": [
                        {"meaning": "Speech", "primary": False},
                        {"meaning": "Say", "primary": True},
                        {"meaning": "Words", "primary": False},
                    ],
                }
            ]
        )
        responses.add(
            responses.GET,
            f"{WK_API_BASE}/subjects?types=radical",
            json=page,
            status=200,
        )

        result = fetch_wk_radicals("fake-key")

        assert result["言"]["name"] == "Say"

    @responses.activate
    def test_writes_cache(self, tmp_cache_dir):
        """After a fresh fetch, wk_radicals.json is written with correct content."""
        page = _wk_radical_page(
            [{"id": 1, "characters": "口", "name": "Mouth", "level": 1, "slug": "mouth"}]
        )
        responses.add(
            responses.GET,
            f"{WK_API_BASE}/subjects?types=radical",
            json=page,
            status=200,
        )

        fetch_wk_radicals("fake-key")

        cache_file = tmp_cache_dir / "wk_radicals.json"
        assert cache_file.exists()
        written = json.loads(cache_file.read_text(encoding="utf-8"))
        assert written["口"]["name"] == "Mouth"
        assert written["口"]["level"] == 1
        assert written["口"]["slug"] == "mouth"


# ---------------------------------------------------------------------------
# TestFetchWkKanjiSubjects
# ---------------------------------------------------------------------------


def _wk_kanji_page(kanji_items, next_url=None):
    """Build a WK API kanji response page."""
    return {
        "data": [
            {
                "id": item["id"],
                "data": {
                    "characters": item.get("characters"),
                    "level": item.get("level", 1),
                    "meanings": item.get(
                        "meanings",
                        [{"meaning": "Unknown", "primary": True}],
                    ),
                    "readings": item.get("readings", []),
                    "component_subject_ids": item.get("component_subject_ids", []),
                },
            }
            for item in kanji_items
        ],
        "pages": {"next_url": next_url},
    }


class TestFetchWkKanjiSubjects:
    """Tests for fetch_wk_kanji_subjects — two-pass WK API fetching."""

    def test_cache_hit(self, tmp_cache_dir):
        """When wk_kanji_subjects.json exists, returns cached data, no HTTP."""
        cached = {
            "語": {
                "meanings": ["Language"],
                "readings": {"onyomi": ["ゴ"], "kunyomi": []},
                "component_radicals": ["言"],
                "level": 5,
            }
        }
        cache_file = tmp_cache_dir / "wk_kanji_subjects.json"
        cache_file.write_text(json.dumps(cached), encoding="utf-8")

        result = fetch_wk_kanji_subjects("fake-key")

        assert result == cached

    @responses.activate
    def test_two_pass_fetch(self, tmp_cache_dir):
        """Both radical (first pass) and kanji (second pass) endpoints are
        called, producing a complete kanji map."""
        radical_page = _wk_radical_page(
            [{"id": 42, "characters": "言", "name": "Say"}]
        )
        kanji_page = _wk_kanji_page(
            [
                {
                    "id": 100,
                    "characters": "語",
                    "level": 5,
                    "meanings": [{"meaning": "Language", "primary": True}],
                    "readings": [
                        {"reading": "ゴ", "type": "onyomi"},
                        {"reading": "かた.る", "type": "kunyomi"},
                    ],
                    "component_subject_ids": [42],
                }
            ]
        )

        responses.add(
            responses.GET,
            f"{WK_API_BASE}/subjects?types=radical",
            json=radical_page,
            status=200,
        )
        responses.add(
            responses.GET,
            f"{WK_API_BASE}/subjects?types=kanji",
            json=kanji_page,
            status=200,
        )

        result = fetch_wk_kanji_subjects("fake-key")

        assert "語" in result
        assert result["語"]["meanings"] == ["Language"]
        assert result["語"]["readings"]["onyomi"] == ["ゴ"]
        assert result["語"]["readings"]["kunyomi"] == ["かた.る"]
        assert result["語"]["component_radicals"] == ["言"]
        assert result["語"]["level"] == 5

    @responses.activate
    def test_component_id_resolution(self, tmp_cache_dir):
        """Radical subject IDs in component_subject_ids are resolved to their
        character strings via the radical_id_map built in the first pass."""
        radical_page = _wk_radical_page(
            [
                {"id": 42, "characters": "言", "name": "Say"},
                {"id": 43, "characters": "五", "name": "Five"},
            ]
        )
        kanji_page = _wk_kanji_page(
            [
                {
                    "id": 200,
                    "characters": "語",
                    "level": 5,
                    "meanings": [{"meaning": "Language", "primary": True}],
                    "readings": [{"reading": "ゴ", "type": "onyomi"}],
                    "component_subject_ids": [42, 43],
                }
            ]
        )

        responses.add(
            responses.GET,
            f"{WK_API_BASE}/subjects?types=radical",
            json=radical_page,
            status=200,
        )
        responses.add(
            responses.GET,
            f"{WK_API_BASE}/subjects?types=kanji",
            json=kanji_page,
            status=200,
        )

        result = fetch_wk_kanji_subjects("fake-key")

        assert result["語"]["component_radicals"] == ["言", "五"]

    @responses.activate
    def test_skips_image_only_radical_in_id_map(self, tmp_cache_dir):
        """Radicals with characters=null are not added to the ID map, so
        component IDs referencing them produce no entry in component_radicals."""
        radical_page = _wk_radical_page(
            [
                {"id": 42, "characters": "言", "name": "Say"},
                {"id": 99, "characters": None, "name": "Barb"},
            ]
        )
        kanji_page = _wk_kanji_page(
            [
                {
                    "id": 200,
                    "characters": "語",
                    "level": 5,
                    "meanings": [{"meaning": "Language", "primary": True}],
                    "readings": [{"reading": "ゴ", "type": "onyomi"}],
                    "component_subject_ids": [42, 99],
                }
            ]
        )

        responses.add(
            responses.GET,
            f"{WK_API_BASE}/subjects?types=radical",
            json=radical_page,
            status=200,
        )
        responses.add(
            responses.GET,
            f"{WK_API_BASE}/subjects?types=kanji",
            json=kanji_page,
            status=200,
        )

        result = fetch_wk_kanji_subjects("fake-key")

        # Only the radical with a character is resolved; the image-only one is skipped.
        assert result["語"]["component_radicals"] == ["言"]


# ---------------------------------------------------------------------------
# TestLoadKradfile
# ---------------------------------------------------------------------------


KRADFILE_SAMPLE_TEXT = """\
# KRADFILE-u
# This is a comment

語 : 言 五 口
山 : 山
"""

KRADFILE_WITH_JUNK = """\
# comment line
語 : 言 五 口

malformed_line_without_colon
山 : 山
"""


class TestLoadKradfile:
    """Tests for load_kradfile — KRADFILE-u download, parsing, and caching."""

    def test_cache_hit(self, tmp_cache_dir):
        """When kradfile.json exists, returns cached data with no HTTP."""
        cached = {"語": ["言", "五", "口"]}
        cache_file = tmp_cache_dir / "kradfile.json"
        cache_file.write_text(json.dumps(cached), encoding="utf-8")

        result = load_kradfile()

        assert result == cached

    @responses.activate
    def test_download_and_parse(self, tmp_cache_dir):
        """Downloads from the first URL and parses KRADFILE-u format correctly."""
        responses.add(
            responses.GET,
            KRADFILE_URLS[0],
            body=KRADFILE_SAMPLE_TEXT,
            status=200,
        )

        result = load_kradfile()

        assert result["語"] == ["言", "五", "口"]
        assert result["山"] == ["山"]
        assert len(result) == 2

    @responses.activate
    def test_mirror_fallback(self, tmp_cache_dir):
        """When the first mirror fails with 404, falls back to the second."""
        responses.add(responses.GET, KRADFILE_URLS[0], status=404)
        responses.add(
            responses.GET,
            KRADFILE_URLS[1],
            body=KRADFILE_SAMPLE_TEXT,
            status=200,
        )

        result = load_kradfile()

        assert "語" in result
        assert "山" in result

    @responses.activate
    def test_all_mirrors_fail(self, tmp_cache_dir):
        """When all mirrors fail, returns an empty dict."""
        responses.add(responses.GET, KRADFILE_URLS[0], status=500)
        responses.add(responses.GET, KRADFILE_URLS[1], status=500)

        result = load_kradfile()

        assert result == {}

    @responses.activate
    def test_skips_comments_and_blanks(self, tmp_cache_dir):
        """Comment lines, blank lines, and lines without ' : ' are skipped."""
        responses.add(
            responses.GET,
            KRADFILE_URLS[0],
            body=KRADFILE_WITH_JUNK,
            status=200,
        )

        result = load_kradfile()

        assert result == {"語": ["言", "五", "口"], "山": ["山"]}
        assert "malformed_line_without_colon" not in result


# ---------------------------------------------------------------------------
# TestClearCache
# ---------------------------------------------------------------------------


class TestClearCache:
    """Tests for clear_cache — removal of all cached files."""

    def test_removes_files(self, tmp_cache_dir):
        """All files inside the cache directory are removed."""
        (tmp_cache_dir / "kanji_db.json").write_text("{}")
        (tmp_cache_dir / "wk_radicals.json").write_text("{}")
        (tmp_cache_dir / "kradfile.json").write_text("{}")

        clear_cache()

        remaining = list(tmp_cache_dir.iterdir())
        assert remaining == []

    def test_no_cache_dir(self, tmp_cache_dir, monkeypatch, capsys):
        """When the cache directory does not exist, prints a message and does
        not raise."""
        nonexistent = tmp_cache_dir / "does_not_exist"
        monkeypatch.setattr("kanji_mnemonic.data.CACHE_DIR", nonexistent)

        clear_cache()

        captured = capsys.readouterr()
        assert "No cache to clear" in captured.out
