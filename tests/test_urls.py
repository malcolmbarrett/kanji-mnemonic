"""Integration tests: verify all data source URLs in data.py still resolve.

Marked with @pytest.mark.integration — these hit the network and are skipped
by default. Run explicitly with: uv run pytest -m integration
"""

import pytest
import requests

from kanji_mnemonic.data import DB_URLS, KANJIDIC_API_URL, KRADFILE_URLS, WK_API_BASE

pytestmark = pytest.mark.integration


def _head(url: str, *, allow_status: set[int] | None = None, timeout: int = 15):
    """Send a HEAD request; fall back to GET if HEAD is not allowed."""
    allow_status = allow_status or {200}
    try:
        resp = requests.head(url, timeout=timeout, allow_redirects=True)
    except requests.RequestException:
        resp = requests.get(url, timeout=timeout, stream=True, allow_redirects=True)
    assert resp.status_code in allow_status, (
        f"{url} returned {resp.status_code}, expected one of {allow_status}"
    )


class TestKeiseiUrls:
    """The three Keisei JSON files hosted on GitHub."""

    @pytest.mark.parametrize("name,url", list(DB_URLS.items()))
    def test_keisei_db_accessible(self, name, url):
        _head(url)


class TestKradfileUrls:
    """KRADFILE-u mirrors — at least one should be accessible."""

    def test_at_least_one_mirror_accessible(self):
        statuses = []
        for url in KRADFILE_URLS:
            try:
                resp = requests.head(url, timeout=15, allow_redirects=True)
                statuses.append(resp.status_code)
                if resp.status_code == 200:
                    return  # success — at least one mirror works
            except requests.RequestException as exc:
                statuses.append(str(exc))
        pytest.fail(f"No KRADFILE-u mirror accessible. Statuses: {statuses}")


class TestWanikaniApiUrl:
    """WK API base endpoint — should return 401 without a valid key."""

    def test_wk_api_reachable(self):
        _head(f"{WK_API_BASE}/subjects", allow_status={401})


class TestKanjidicUrl:
    """GitHub releases API for jmdict-simplified."""

    def test_kanjidic_releases_api_accessible(self):
        _head(KANJIDIC_API_URL)
