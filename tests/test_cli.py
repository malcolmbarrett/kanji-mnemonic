"""Tests for kanji_mnemonic.cli — CLI entry point and command dispatch."""

import argparse
import json

import pytest
from unittest.mock import MagicMock

from kanji_mnemonic.cli import (
    cmd_lookup,
    cmd_memorize,
    cmd_prompt,
    get_wk_api_key,
    load_all_data,
    main,
)


class TestGetWkApiKey:
    """Tests for get_wk_api_key()."""

    def test_returns_env_var(self, monkeypatch):
        monkeypatch.setenv("WK_API_KEY", "test-key")
        assert get_wk_api_key() == "test-key"

    def test_returns_none_when_unset(self, monkeypatch):
        monkeypatch.delenv("WK_API_KEY", raising=False)
        assert get_wk_api_key() is None


class TestLoadAllData:
    """Tests for load_all_data()."""

    def test_with_api_key(self, monkeypatch):
        """When an API key is provided, fetch_wk_radicals and fetch_wk_kanji_subjects are called."""
        mock_kanji_db = {"k": 1}
        mock_phonetic_db = {"p": 2}
        mock_wk_kanji_db = {"w": 3}
        mock_kradfile = {"r": 4}
        mock_wk_radicals = {"rad": 5}
        mock_wk_subjects = {"sub": 6}

        mock_kanjidic = {"kd": 7}

        monkeypatch.setattr("kanji_mnemonic.cli.load_kanji_db", lambda: mock_kanji_db)
        monkeypatch.setattr(
            "kanji_mnemonic.cli.load_phonetic_db", lambda: mock_phonetic_db
        )
        monkeypatch.setattr(
            "kanji_mnemonic.cli.load_wk_kanji_db", lambda: mock_wk_kanji_db
        )
        monkeypatch.setattr("kanji_mnemonic.cli.load_kradfile", lambda: mock_kradfile)
        monkeypatch.setattr("kanji_mnemonic.cli.load_kanjidic", lambda: mock_kanjidic)
        monkeypatch.setattr("kanji_mnemonic.cli.load_personal_radicals", lambda: {})

        fetch_rad = MagicMock(return_value=mock_wk_radicals)
        fetch_subj = MagicMock(return_value=mock_wk_subjects)
        monkeypatch.setattr("kanji_mnemonic.cli.fetch_wk_radicals", fetch_rad)
        monkeypatch.setattr("kanji_mnemonic.cli.fetch_wk_kanji_subjects", fetch_subj)

        result = load_all_data("fake-key")

        fetch_rad.assert_called_once_with("fake-key")
        fetch_subj.assert_called_once_with("fake-key")

        (
            kanji_db,
            phonetic_db,
            wk_kanji_db,
            wk_radicals,
            wk_kanji_subjects,
            kradfile,
            kanjidic,
            personal_radicals,
        ) = result
        assert kanji_db == mock_kanji_db
        assert phonetic_db == mock_phonetic_db
        assert wk_kanji_db == mock_wk_kanji_db
        assert wk_radicals == mock_wk_radicals
        assert wk_kanji_subjects == mock_wk_subjects
        assert kradfile == mock_kradfile
        assert kanjidic == mock_kanjidic
        assert personal_radicals == {}

    def test_without_key_loads_cache(self, tmp_cache_dir, monkeypatch):
        """Without an API key, cached wk_radicals.json and wk_kanji_subjects.json are loaded."""
        cached_radicals = {"言": {"name": "Say"}}
        cached_subjects = {"語": {"meanings": ["Language"]}}

        (tmp_cache_dir / "wk_radicals.json").write_text(
            json.dumps(cached_radicals), encoding="utf-8"
        )
        (tmp_cache_dir / "wk_kanji_subjects.json").write_text(
            json.dumps(cached_subjects), encoding="utf-8"
        )

        monkeypatch.setattr("kanji_mnemonic.cli.load_kanji_db", lambda: {})
        monkeypatch.setattr("kanji_mnemonic.cli.load_phonetic_db", lambda: {})
        monkeypatch.setattr("kanji_mnemonic.cli.load_wk_kanji_db", lambda: {})
        monkeypatch.setattr("kanji_mnemonic.cli.load_kradfile", lambda: {})
        monkeypatch.setattr("kanji_mnemonic.cli.load_kanjidic", lambda: {})
        monkeypatch.setattr("kanji_mnemonic.cli.load_personal_radicals", lambda: {})

        result = load_all_data(None)
        _, _, _, wk_radicals, wk_kanji_subjects, _, _, _ = result

        assert wk_radicals == cached_radicals
        assert wk_kanji_subjects == cached_subjects

    def test_without_key_no_cache_warns(self, tmp_cache_dir, monkeypatch, capsys):
        """Without an API key and no cache, a warning is printed and empty data returned."""
        monkeypatch.setattr("kanji_mnemonic.cli.load_kanji_db", lambda: {})
        monkeypatch.setattr("kanji_mnemonic.cli.load_phonetic_db", lambda: {})
        monkeypatch.setattr("kanji_mnemonic.cli.load_wk_kanji_db", lambda: {})
        monkeypatch.setattr("kanji_mnemonic.cli.load_kradfile", lambda: {})
        monkeypatch.setattr("kanji_mnemonic.cli.load_kanjidic", lambda: {})
        monkeypatch.setattr("kanji_mnemonic.cli.load_personal_radicals", lambda: {})

        result = load_all_data(None)
        _, _, _, wk_radicals, wk_kanji_subjects, _, _, _ = result

        assert wk_radicals == {}
        assert wk_kanji_subjects is None

        captured = capsys.readouterr()
        assert "No WK_API_KEY" in captured.err
        assert "WK_API_KEY" in captured.err


class TestArgumentParsing:
    """Tests for main() argument parsing and command dispatch."""

    def _setup_mocks(self, monkeypatch):
        """Set up common mocks for main() dispatch tests.

        Returns a dict of mock cmd functions keyed by name.
        """
        mock_data = ({}, {}, {}, {}, {}, {}, {}, {})
        monkeypatch.setattr("kanji_mnemonic.cli.get_wk_api_key", lambda: None)
        monkeypatch.setattr("kanji_mnemonic.cli.load_all_data", lambda key: mock_data)

        mocks = {
            "cmd_lookup": MagicMock(),
            "cmd_memorize": MagicMock(),
            "cmd_prompt": MagicMock(),
            "cmd_clear_cache": MagicMock(),
        }
        for name, mock in mocks.items():
            monkeypatch.setattr(f"kanji_mnemonic.cli.{name}", mock)

        return mocks

    def test_lookup_command(self, monkeypatch):
        mocks = self._setup_mocks(monkeypatch)
        monkeypatch.setattr("sys.argv", ["kanji", "lookup", "語"])
        main()
        mocks["cmd_lookup"].assert_called_once()
        args = mocks["cmd_lookup"].call_args[0][0]
        assert args.kanji == ["語"]

    def test_lookup_alias_l(self, monkeypatch):
        mocks = self._setup_mocks(monkeypatch)
        monkeypatch.setattr("sys.argv", ["kanji", "l", "語"])
        main()
        mocks["cmd_lookup"].assert_called_once()

    def test_memorize_command(self, monkeypatch):
        mocks = self._setup_mocks(monkeypatch)
        monkeypatch.setattr("sys.argv", ["kanji", "memorize", "語"])
        main()
        mocks["cmd_memorize"].assert_called_once()
        args = mocks["cmd_memorize"].call_args[0][0]
        assert args.kanji == ["語"]

    def test_memorize_alias_m(self, monkeypatch):
        mocks = self._setup_mocks(monkeypatch)
        monkeypatch.setattr("sys.argv", ["kanji", "m", "語"])
        main()
        mocks["cmd_memorize"].assert_called_once()

    def test_clear_cache_skips_data_loading(self, monkeypatch):
        """clear-cache should dispatch to cmd_clear_cache without calling load_all_data."""
        mock_load = MagicMock()
        monkeypatch.setattr("kanji_mnemonic.cli.load_all_data", mock_load)

        mock_clear = MagicMock()
        monkeypatch.setattr("kanji_mnemonic.cli.cmd_clear_cache", mock_clear)

        monkeypatch.setattr("sys.argv", ["kanji", "clear-cache"])
        main()

        mock_clear.assert_called_once()
        mock_load.assert_not_called()

    def test_no_command_exits(self, monkeypatch):
        monkeypatch.setattr("sys.argv", ["kanji"])
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1

    def test_context_flag(self, monkeypatch):
        mocks = self._setup_mocks(monkeypatch)
        monkeypatch.setattr(
            "sys.argv", ["kanji", "prompt", "語", "-c", "focus on onyomi"]
        )
        main()
        mocks["cmd_prompt"].assert_called_once()
        args = mocks["cmd_prompt"].call_args[0][0]
        assert args.context == "focus on onyomi"


class TestCmdLookup:
    """Tests for cmd_lookup()."""

    def test_prints_formatted_profile(
        self,
        capsys,
        sample_kanji_db,
        sample_phonetic_db,
        sample_wk_kanji_db,
        sample_wk_radicals,
        sample_wk_kanji_subjects,
        sample_kradfile,
    ):
        args = argparse.Namespace(kanji=["語"])
        cmd_lookup(
            args,
            sample_kanji_db,
            sample_phonetic_db,
            sample_wk_kanji_db,
            sample_wk_radicals,
            sample_wk_kanji_subjects,
            sample_kradfile,
            None,
            {},
        )
        output = capsys.readouterr().out
        assert "═══ 語 ═══" in output
        assert "Language" in output

    def test_multiple_kanji(
        self,
        capsys,
        sample_kanji_db,
        sample_phonetic_db,
        sample_wk_kanji_db,
        sample_wk_radicals,
        sample_wk_kanji_subjects,
        sample_kradfile,
    ):
        args = argparse.Namespace(kanji=["語", "山"])
        cmd_lookup(
            args,
            sample_kanji_db,
            sample_phonetic_db,
            sample_wk_kanji_db,
            sample_wk_radicals,
            sample_wk_kanji_subjects,
            sample_kradfile,
            None,
            {},
        )
        output = capsys.readouterr().out
        assert "═══ 語 ═══" in output
        assert "═══ 山 ═══" in output


class TestCmdPrompt:
    """Tests for cmd_prompt()."""

    def test_prints_system_and_user_prompt(
        self,
        capsys,
        sample_kanji_db,
        sample_phonetic_db,
        sample_wk_kanji_db,
        sample_wk_radicals,
        sample_wk_kanji_subjects,
        sample_kradfile,
    ):
        args = argparse.Namespace(kanji=["語"], context=None)
        cmd_prompt(
            args,
            sample_kanji_db,
            sample_phonetic_db,
            sample_wk_kanji_db,
            sample_wk_radicals,
            sample_wk_kanji_subjects,
            sample_kradfile,
            None,
            {},
        )
        output = capsys.readouterr().out
        assert "SYSTEM PROMPT" in output
        assert "USER MESSAGE" in output

    def test_with_context(
        self,
        capsys,
        sample_kanji_db,
        sample_phonetic_db,
        sample_wk_kanji_db,
        sample_wk_radicals,
        sample_wk_kanji_subjects,
        sample_kradfile,
    ):
        args = argparse.Namespace(kanji=["語"], context="test context")
        cmd_prompt(
            args,
            sample_kanji_db,
            sample_phonetic_db,
            sample_wk_kanji_db,
            sample_wk_radicals,
            sample_wk_kanji_subjects,
            sample_kradfile,
            None,
            {},
        )
        output = capsys.readouterr().out
        assert "test context" in output


class TestCmdMemorize:
    """Tests for cmd_memorize()."""

    def _make_mock_client(self, text_chunks):
        """Create a mock Anthropic client whose stream yields the given text chunks."""
        mock_client = MagicMock()
        mock_stream = MagicMock()
        mock_stream.__enter__ = MagicMock(return_value=mock_stream)
        mock_stream.__exit__ = MagicMock(return_value=False)
        mock_stream.text_stream = iter(text_chunks)
        mock_client.messages.stream.return_value = mock_stream
        return mock_client

    def test_streams_response(
        self,
        capsys,
        monkeypatch,
        tmp_cache_dir,
        sample_kanji_db,
        sample_phonetic_db,
        sample_wk_kanji_db,
        sample_wk_radicals,
        sample_wk_kanji_subjects,
        sample_kradfile,
    ):
        mock_client = self._make_mock_client(["Hello ", "world"])
        monkeypatch.setattr(
            "kanji_mnemonic.cli.get_anthropic_client", lambda: mock_client
        )
        monkeypatch.setattr("kanji_mnemonic.data.CONFIG_DIR", tmp_cache_dir)

        args = argparse.Namespace(
            kanji=["語"], context=None, model="test-model", no_interactive=True
        )
        cmd_memorize(
            args,
            sample_kanji_db,
            sample_phonetic_db,
            sample_wk_kanji_db,
            sample_wk_radicals,
            sample_wk_kanji_subjects,
            sample_kradfile,
            None,
            {},
        )
        output = capsys.readouterr().out
        assert "Hello world" in output

    def test_prints_profile_before_mnemonic(
        self,
        capsys,
        monkeypatch,
        tmp_cache_dir,
        sample_kanji_db,
        sample_phonetic_db,
        sample_wk_kanji_db,
        sample_wk_radicals,
        sample_wk_kanji_subjects,
        sample_kradfile,
    ):
        mock_client = self._make_mock_client(["mnemonic text"])
        monkeypatch.setattr(
            "kanji_mnemonic.cli.get_anthropic_client", lambda: mock_client
        )
        monkeypatch.setattr("kanji_mnemonic.data.CONFIG_DIR", tmp_cache_dir)

        args = argparse.Namespace(
            kanji=["語"], context=None, model="test-model", no_interactive=True
        )
        cmd_memorize(
            args,
            sample_kanji_db,
            sample_phonetic_db,
            sample_wk_kanji_db,
            sample_wk_radicals,
            sample_wk_kanji_subjects,
            sample_kradfile,
            None,
            {},
        )
        output = capsys.readouterr().out
        profile_pos = output.index("═══ 語 ═══")
        generating_pos = output.index("Generating mnemonic...")
        assert profile_pos < generating_pos
