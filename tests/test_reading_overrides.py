"""Tests for primary reading override feature (bd-3gt).

These tests define the API contract for the reading override feature
and verify its behavior.
"""

import argparse
import json

import pytest
from unittest.mock import MagicMock


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def config_dir(tmp_path, monkeypatch):
    """Redirect CONFIG_DIR to a temp directory."""
    cfg = tmp_path / "config" / "kanji"
    cfg.mkdir(parents=True)
    monkeypatch.setattr("kanji_mnemonic.data.CONFIG_DIR", cfg)
    return cfg


@pytest.fixture
def reading_overrides_file(config_dir):
    """Create a reading_overrides.json file with sample data."""
    data = {"山": "kunyomi", "語": "onyomi"}
    (config_dir / "reading_overrides.json").write_text(
        json.dumps(data, ensure_ascii=False), encoding="utf-8"
    )
    return config_dir / "reading_overrides.json"


# ---------------------------------------------------------------------------
# Tests: load_reading_overrides()
# ---------------------------------------------------------------------------


class TestLoadReadingOverrides:
    """Tests for load_reading_overrides() in data.py."""

    def test_loads_existing_file(self, config_dir, reading_overrides_file):
        from kanji_mnemonic.data import load_reading_overrides

        result = load_reading_overrides()
        assert result == {"山": "kunyomi", "語": "onyomi"}

    def test_returns_empty_dict_when_file_missing(self, config_dir):
        from kanji_mnemonic.data import load_reading_overrides

        result = load_reading_overrides()
        assert result == {}

    def test_returns_empty_dict_for_empty_json(self, config_dir):
        from kanji_mnemonic.data import load_reading_overrides

        (config_dir / "reading_overrides.json").write_text("{}", encoding="utf-8")
        result = load_reading_overrides()
        assert result == {}


# ---------------------------------------------------------------------------
# Tests: save_reading_override()
# ---------------------------------------------------------------------------


class TestSaveReadingOverride:
    """Tests for save_reading_override() in data.py."""

    def test_saves_new_override(self, config_dir):
        from kanji_mnemonic.data import save_reading_override

        save_reading_override("詠", "kunyomi")
        data = json.loads(
            (config_dir / "reading_overrides.json").read_text(encoding="utf-8")
        )
        assert data == {"詠": "kunyomi"}

    def test_updates_existing_override(self, config_dir, reading_overrides_file):
        from kanji_mnemonic.data import save_reading_override

        save_reading_override("山", "onyomi")
        data = json.loads(
            (config_dir / "reading_overrides.json").read_text(encoding="utf-8")
        )
        assert data["山"] == "onyomi"
        # Other entries untouched
        assert data["語"] == "onyomi"

    def test_creates_directory_if_missing(self, tmp_path, monkeypatch):
        from kanji_mnemonic.data import save_reading_override

        cfg = tmp_path / "nonexistent" / "config"
        monkeypatch.setattr("kanji_mnemonic.data.CONFIG_DIR", cfg)
        save_reading_override("詠", "kunyomi")
        assert (cfg / "reading_overrides.json").exists()

    def test_validates_reading_type(self, config_dir):
        from kanji_mnemonic.data import save_reading_override

        with pytest.raises(ValueError, match="onyomi.*kunyomi"):
            save_reading_override("詠", "invalid")

    def test_accepts_onyomi(self, config_dir):
        from kanji_mnemonic.data import save_reading_override

        save_reading_override("詠", "onyomi")
        data = json.loads(
            (config_dir / "reading_overrides.json").read_text(encoding="utf-8")
        )
        assert data["詠"] == "onyomi"

    def test_accepts_kunyomi(self, config_dir):
        from kanji_mnemonic.data import save_reading_override

        save_reading_override("詠", "kunyomi")
        data = json.loads(
            (config_dir / "reading_overrides.json").read_text(encoding="utf-8")
        )
        assert data["詠"] == "kunyomi"


# ---------------------------------------------------------------------------
# Tests: remove_reading_override()
# ---------------------------------------------------------------------------


class TestRemoveReadingOverride:
    """Tests for remove_reading_override() in data.py."""

    def test_removes_existing_override(self, config_dir, reading_overrides_file):
        from kanji_mnemonic.data import remove_reading_override

        result = remove_reading_override("山")
        assert result is True
        data = json.loads(
            (config_dir / "reading_overrides.json").read_text(encoding="utf-8")
        )
        assert "山" not in data
        assert "語" in data

    def test_returns_false_for_missing_entry(self, config_dir, reading_overrides_file):
        from kanji_mnemonic.data import remove_reading_override

        result = remove_reading_override("蝶")
        assert result is False

    def test_returns_false_when_file_missing(self, config_dir):
        from kanji_mnemonic.data import remove_reading_override

        result = remove_reading_override("山")
        assert result is False


# ---------------------------------------------------------------------------
# Tests: reading override in lookup_kanji()
# ---------------------------------------------------------------------------


class TestReadingOverrideInLookup:
    """Tests for reading_overrides parameter in lookup_kanji()."""

    def test_override_takes_precedence(
        self,
        sample_kanji_db,
        sample_phonetic_db,
        sample_wk_kanji_db,
        sample_wk_radicals,
        sample_wk_kanji_subjects,
        sample_kradfile,
    ):
        """Personal reading override takes precedence over Keisei data."""
        from kanji_mnemonic.lookup import lookup_kanji

        # 語 has important_reading="onyomi" from wk_kanji_db
        profile = lookup_kanji(
            "語",
            sample_kanji_db,
            sample_phonetic_db,
            sample_wk_kanji_db,
            sample_wk_radicals,
            sample_wk_kanji_subjects,
            sample_kradfile,
            reading_overrides={"語": "kunyomi"},
        )
        assert profile.important_reading == "kunyomi"

    def test_no_override_uses_default(
        self,
        sample_kanji_db,
        sample_phonetic_db,
        sample_wk_kanji_db,
        sample_wk_radicals,
        sample_wk_kanji_subjects,
        sample_kradfile,
    ):
        """Without override, Keisei data is used as before."""
        from kanji_mnemonic.lookup import lookup_kanji

        profile = lookup_kanji(
            "語",
            sample_kanji_db,
            sample_phonetic_db,
            sample_wk_kanji_db,
            sample_wk_radicals,
            sample_wk_kanji_subjects,
            sample_kradfile,
            reading_overrides={},
        )
        assert profile.important_reading == "onyomi"

    def test_none_overrides_ignored(
        self,
        sample_kanji_db,
        sample_phonetic_db,
        sample_wk_kanji_db,
        sample_wk_radicals,
        sample_wk_kanji_subjects,
        sample_kradfile,
    ):
        """reading_overrides=None works like no overrides."""
        from kanji_mnemonic.lookup import lookup_kanji

        profile = lookup_kanji(
            "語",
            sample_kanji_db,
            sample_phonetic_db,
            sample_wk_kanji_db,
            sample_wk_radicals,
            sample_wk_kanji_subjects,
            sample_kradfile,
            reading_overrides=None,
        )
        assert profile.important_reading == "onyomi"

    def test_override_for_different_kanji_ignored(
        self,
        sample_kanji_db,
        sample_phonetic_db,
        sample_wk_kanji_db,
        sample_wk_radicals,
        sample_wk_kanji_subjects,
        sample_kradfile,
    ):
        """Override for a different kanji does not affect this one."""
        from kanji_mnemonic.lookup import lookup_kanji

        profile = lookup_kanji(
            "語",
            sample_kanji_db,
            sample_phonetic_db,
            sample_wk_kanji_db,
            sample_wk_radicals,
            sample_wk_kanji_subjects,
            sample_kradfile,
            reading_overrides={"山": "onyomi"},
        )
        assert profile.important_reading == "onyomi"


# ---------------------------------------------------------------------------
# Tests: CLI commands for reading overrides
# ---------------------------------------------------------------------------


class TestCmdReading:
    """Tests for 'kanji reading' CLI command."""

    def test_saves_reading_override(self, config_dir, capsys):
        from kanji_mnemonic.cli import cmd_reading

        args = argparse.Namespace(kanji="詠", reading_type="kunyomi", remove=False)
        cmd_reading(args)
        data = json.loads(
            (config_dir / "reading_overrides.json").read_text(encoding="utf-8")
        )
        assert data["詠"] == "kunyomi"

    def test_shows_current_reading(self, config_dir, reading_overrides_file, capsys):
        from kanji_mnemonic.cli import cmd_reading

        args = argparse.Namespace(kanji="山", reading_type=None, remove=False)
        cmd_reading(args)
        output = capsys.readouterr().out
        assert "山" in output
        assert "kunyomi" in output

    def test_shows_no_override_message(self, config_dir, capsys):
        from kanji_mnemonic.cli import cmd_reading

        args = argparse.Namespace(kanji="詠", reading_type=None, remove=False)
        cmd_reading(args)
        output = capsys.readouterr().out
        assert "No reading override" in output

    def test_removes_override(self, config_dir, reading_overrides_file, capsys):
        from kanji_mnemonic.cli import cmd_reading

        args = argparse.Namespace(kanji="山", reading_type=None, remove=True)
        cmd_reading(args)
        data = json.loads(
            (config_dir / "reading_overrides.json").read_text(encoding="utf-8")
        )
        assert "山" not in data

    def test_prints_confirmation_on_save(self, config_dir, capsys):
        from kanji_mnemonic.cli import cmd_reading

        args = argparse.Namespace(kanji="詠", reading_type="kunyomi", remove=False)
        cmd_reading(args)
        output = capsys.readouterr().out
        assert "詠" in output
        assert "kunyomi" in output


class TestCmdReadings:
    """Tests for 'kanji readings' CLI command."""

    def test_lists_all_overrides(self, config_dir, reading_overrides_file, capsys):
        from kanji_mnemonic.cli import cmd_readings

        args = argparse.Namespace()
        cmd_readings(args)
        output = capsys.readouterr().out
        assert "山" in output
        assert "kunyomi" in output
        assert "語" in output
        assert "onyomi" in output

    def test_empty_overrides_message(self, config_dir, capsys):
        from kanji_mnemonic.cli import cmd_readings

        args = argparse.Namespace()
        cmd_readings(args)
        output = capsys.readouterr().out
        assert "kanji reading" in output


# ---------------------------------------------------------------------------
# Tests: --primary flag on memorize command
# ---------------------------------------------------------------------------


class TestMemorizePrimaryFlag:
    """Tests for --primary flag on the memorize command."""

    def _setup_mocks(self, monkeypatch):
        mock_data = ({}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {})
        monkeypatch.setattr("kanji_mnemonic.cli.get_wk_api_key", lambda: None)
        monkeypatch.setattr("kanji_mnemonic.cli.load_all_data", lambda key: mock_data)

    def test_primary_flag_parsed(self, monkeypatch, config_dir):
        """--primary flag is correctly parsed for memorize command."""
        from kanji_mnemonic.cli import main

        self._setup_mocks(monkeypatch)
        mock_cmd = MagicMock()
        monkeypatch.setattr("kanji_mnemonic.cli.cmd_memorize", mock_cmd)
        monkeypatch.setattr(
            "sys.argv", ["kanji", "memorize", "詠", "--primary", "kunyomi"]
        )
        main()
        mock_cmd.assert_called_once()
        args = mock_cmd.call_args[0][0]
        assert args.primary == "kunyomi"

    def test_primary_flag_choices(self, monkeypatch, config_dir):
        """--primary only accepts onyomi or kunyomi."""
        from kanji_mnemonic.cli import main

        self._setup_mocks(monkeypatch)
        monkeypatch.setattr(
            "sys.argv", ["kanji", "memorize", "詠", "--primary", "invalid"]
        )
        with pytest.raises(SystemExit):
            main()

    def test_no_primary_defaults_none(self, monkeypatch, config_dir):
        """Without --primary, the arg defaults to None."""
        from kanji_mnemonic.cli import main

        self._setup_mocks(monkeypatch)
        mock_cmd = MagicMock()
        monkeypatch.setattr("kanji_mnemonic.cli.cmd_memorize", mock_cmd)
        monkeypatch.setattr("sys.argv", ["kanji", "memorize", "詠"])
        main()
        args = mock_cmd.call_args[0][0]
        assert args.primary is None


# ---------------------------------------------------------------------------
# Tests: CLI dispatch for reading/readings commands
# ---------------------------------------------------------------------------


class TestReadingCommandDispatch:
    """Tests for main() routing to reading/readings commands."""

    def _setup_mocks(self, monkeypatch):
        mock_data = ({}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {})
        monkeypatch.setattr("kanji_mnemonic.cli.get_wk_api_key", lambda: None)
        monkeypatch.setattr("kanji_mnemonic.cli.load_all_data", lambda key: mock_data)

    def test_reading_command_save(self, monkeypatch, config_dir):
        from kanji_mnemonic.cli import main

        self._setup_mocks(monkeypatch)
        mock_cmd = MagicMock()
        monkeypatch.setattr("kanji_mnemonic.cli.cmd_reading", mock_cmd)
        monkeypatch.setattr("sys.argv", ["kanji", "reading", "詠", "kunyomi"])
        main()
        mock_cmd.assert_called_once()
        args = mock_cmd.call_args[0][0]
        assert args.kanji == "詠"
        assert args.reading_type == "kunyomi"

    def test_reading_command_show(self, monkeypatch, config_dir):
        from kanji_mnemonic.cli import main

        self._setup_mocks(monkeypatch)
        mock_cmd = MagicMock()
        monkeypatch.setattr("kanji_mnemonic.cli.cmd_reading", mock_cmd)
        monkeypatch.setattr("sys.argv", ["kanji", "reading", "詠"])
        main()
        mock_cmd.assert_called_once()
        args = mock_cmd.call_args[0][0]
        assert args.kanji == "詠"
        assert args.reading_type is None

    def test_readings_command(self, monkeypatch, config_dir):
        from kanji_mnemonic.cli import main

        self._setup_mocks(monkeypatch)
        mock_cmd = MagicMock()
        monkeypatch.setattr("kanji_mnemonic.cli.cmd_readings", mock_cmd)
        monkeypatch.setattr("sys.argv", ["kanji", "readings"])
        main()
        mock_cmd.assert_called_once()
