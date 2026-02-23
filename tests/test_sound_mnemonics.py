"""Tests for WK sound mnemonics (bd-1xp) and personal sound overrides (bd-20u).

These tests define the API contract and validate the behavior of the sound mnemonic features.
"""

import argparse
import json

import pytest
from unittest.mock import MagicMock

from kanji_mnemonic.lookup import KanjiProfile


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
def sample_wk_sound_mnemonics():
    """Sample WK sound mnemonic database."""
    return {
        "こう": {"character": "Koichi", "description": "Koichi, the WaniKani founder"},
        "じょう": {
            "character": "Joe",
            "description": "Joe, a hard-working farmhand",
        },
        "しょう": {
            "character": "Shogun",
            "description": "A powerful military commander",
        },
        "ご": {"character": "Goku", "description": "Goku, a powerful warrior"},
    }


@pytest.fixture
def personal_sound_file(config_dir):
    """Create a personal sound_mnemonics.json file with sample data."""
    data = {
        "こう": {
            "character": "My Friend Kou",
            "description": "My friend named Kou from college",
        },
        "せい": {
            "character": "Say-sensei",
            "description": "My Japanese teacher",
        },
    }
    (config_dir / "sound_mnemonics.json").write_text(
        json.dumps(data, ensure_ascii=False), encoding="utf-8"
    )
    return config_dir / "sound_mnemonics.json"


# ===========================================================================
# Part 1: WK Sound Mnemonics (bd-1xp)
# ===========================================================================


# ---------------------------------------------------------------------------
# Tests: load_wk_sound_mnemonics()
# ---------------------------------------------------------------------------


class TestLoadWkSoundMnemonics:
    """Tests for load_wk_sound_mnemonics() in data.py."""

    def test_loads_bundled_json(self):
        from kanji_mnemonic.data import load_wk_sound_mnemonics

        result = load_wk_sound_mnemonics()
        assert isinstance(result, dict)
        # May be empty until populated from real WK data
        for reading, info in result.items():
            assert isinstance(reading, str)
            assert "character" in info
            assert "description" in info

    def test_structure_if_populated(self):
        """If bundled database has entries, they have correct structure."""
        from kanji_mnemonic.data import load_wk_sound_mnemonics

        result = load_wk_sound_mnemonics()
        for reading, info in result.items():
            assert "character" in info
            assert "description" in info


# ---------------------------------------------------------------------------
# Tests: merge_sound_mnemonics()
# ---------------------------------------------------------------------------


class TestMergeSoundMnemonics:
    """Tests for merge_sound_mnemonics() in data.py."""

    def test_wk_only(self, sample_wk_sound_mnemonics):
        from kanji_mnemonic.data import merge_sound_mnemonics

        result = merge_sound_mnemonics(sample_wk_sound_mnemonics, {})
        assert result == sample_wk_sound_mnemonics

    def test_personal_overrides_wk(self, sample_wk_sound_mnemonics):
        from kanji_mnemonic.data import merge_sound_mnemonics

        personal = {
            "こう": {
                "character": "My Kou",
                "description": "My custom character",
            }
        }
        result = merge_sound_mnemonics(sample_wk_sound_mnemonics, personal)
        assert result["こう"]["character"] == "My Kou"
        # Other WK entries still present
        assert result["じょう"]["character"] == "Joe"

    def test_personal_adds_new(self, sample_wk_sound_mnemonics):
        from kanji_mnemonic.data import merge_sound_mnemonics

        personal = {
            "せい": {
                "character": "Say-sensei",
                "description": "My teacher",
            }
        }
        result = merge_sound_mnemonics(sample_wk_sound_mnemonics, personal)
        assert "せい" in result
        assert result["せい"]["character"] == "Say-sensei"
        # WK entries still present
        assert "こう" in result

    def test_empty_both(self):
        from kanji_mnemonic.data import merge_sound_mnemonics

        result = merge_sound_mnemonics({}, {})
        assert result == {}


# ---------------------------------------------------------------------------
# Tests: get_relevant_sound_mnemonics()
# ---------------------------------------------------------------------------


class TestGetRelevantSoundMnemonics:
    """Tests for _get_relevant_sound_mnemonics() helper in prompt.py."""

    def test_matches_onyomi(self, sample_wk_sound_mnemonics):
        from kanji_mnemonic.prompt import _get_relevant_sound_mnemonics

        profile = KanjiProfile(
            character="語",
            onyomi=["ご"],
            kunyomi=["かた.る"],
        )
        result = _get_relevant_sound_mnemonics(profile, sample_wk_sound_mnemonics)
        assert "ご" in result
        assert result["ご"]["character"] == "Goku"

    def test_no_match(self, sample_wk_sound_mnemonics):
        from kanji_mnemonic.prompt import _get_relevant_sound_mnemonics

        profile = KanjiProfile(
            character="龍",
            onyomi=["りゅう"],
            kunyomi=[],
        )
        result = _get_relevant_sound_mnemonics(profile, sample_wk_sound_mnemonics)
        assert result == {}

    def test_empty_readings(self, sample_wk_sound_mnemonics):
        from kanji_mnemonic.prompt import _get_relevant_sound_mnemonics

        profile = KanjiProfile(character="龍")
        result = _get_relevant_sound_mnemonics(profile, sample_wk_sound_mnemonics)
        assert result == {}

    def test_empty_sound_mnemonics(self):
        from kanji_mnemonic.prompt import _get_relevant_sound_mnemonics

        profile = KanjiProfile(
            character="語",
            onyomi=["ご"],
        )
        result = _get_relevant_sound_mnemonics(profile, {})
        assert result == {}

    def test_multiple_readings_matched(self):
        from kanji_mnemonic.prompt import _get_relevant_sound_mnemonics

        sounds = {
            "ご": {"character": "Goku", "description": "Warrior"},
            "かた": {"character": "Katana", "description": "A sword"},
        }
        profile = KanjiProfile(
            character="語",
            onyomi=["ご"],
            kunyomi=["かた.る"],
        )
        result = _get_relevant_sound_mnemonics(profile, sounds)
        assert "ご" in result
        assert "かた" in result

    def test_important_reading_onyomi_filters_kunyomi(self):
        from kanji_mnemonic.prompt import _get_relevant_sound_mnemonics

        sounds = {
            "ご": {"character": "Goku", "description": "Warrior"},
            "かた": {"character": "Katana", "description": "A sword"},
        }
        profile = KanjiProfile(
            character="語",
            onyomi=["ご"],
            kunyomi=["かた.る"],
            important_reading="onyomi",
        )
        result = _get_relevant_sound_mnemonics(profile, sounds)
        assert "ご" in result
        assert "かた" not in result

    def test_important_reading_kunyomi_filters_onyomi(self):
        from kanji_mnemonic.prompt import _get_relevant_sound_mnemonics

        sounds = {
            "ご": {"character": "Goku", "description": "Warrior"},
            "かた": {"character": "Katana", "description": "A sword"},
        }
        profile = KanjiProfile(
            character="語",
            onyomi=["ご"],
            kunyomi=["かた.る"],
            important_reading="kunyomi",
        )
        result = _get_relevant_sound_mnemonics(profile, sounds)
        assert "ご" not in result
        assert "かた" in result

    def test_no_important_reading_includes_both(self):
        from kanji_mnemonic.prompt import _get_relevant_sound_mnemonics

        sounds = {
            "ご": {"character": "Goku", "description": "Warrior"},
            "かた": {"character": "Katana", "description": "A sword"},
        }
        profile = KanjiProfile(
            character="語",
            onyomi=["ご"],
            kunyomi=["かた.る"],
            important_reading=None,
        )
        result = _get_relevant_sound_mnemonics(profile, sounds)
        assert "ご" in result
        assert "かた" in result


# ---------------------------------------------------------------------------
# Tests: get_system_prompt() with sound mnemonics
# ---------------------------------------------------------------------------


class TestSystemPromptWithSounds:
    """Tests for get_system_prompt() sound mnemonic instruction."""

    def test_returns_non_empty_string(self):
        from kanji_mnemonic.prompt import get_system_prompt

        result = get_system_prompt()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_includes_sound_mnemonic_instruction(self):
        from kanji_mnemonic.prompt import get_system_prompt

        result = get_system_prompt()
        assert "Sound mnemonic characters" in result

    def test_does_not_dump_full_database(self):
        """System prompt should not contain all 184 entries."""
        from kanji_mnemonic.prompt import get_system_prompt

        result = get_system_prompt()
        # Should not contain specific reading entries
        assert "こう = " not in result
        assert "じょう = " not in result


# ---------------------------------------------------------------------------
# Tests: build_prompt() with sound mnemonics
# ---------------------------------------------------------------------------


class TestBuildPromptWithSounds:
    """Tests for build_prompt() with sound_mnemonics parameter."""

    def test_without_sounds_backward_compatible(self, sample_profile_phonetic):
        from kanji_mnemonic.prompt import build_prompt

        result = build_prompt(sample_profile_phonetic)
        assert "語" in result

    def test_with_relevant_sounds(self, sample_profile_phonetic):
        from kanji_mnemonic.prompt import build_prompt

        sounds = {"ご": {"character": "Goku", "description": "A powerful warrior"}}
        result = build_prompt(sample_profile_phonetic, sound_mnemonics=sounds)
        assert "Goku" in result
        assert "ご" in result

    def test_with_irrelevant_sounds(self, sample_profile_phonetic):
        from kanji_mnemonic.prompt import build_prompt

        sounds = {
            "りゅう": {
                "character": "Dragon",
                "description": "A mythical creature",
            }
        }
        result = build_prompt(sample_profile_phonetic, sound_mnemonics=sounds)
        # Irrelevant sound should not appear in the prompt
        assert "Dragon" not in result

    def test_with_none_sounds(self, sample_profile_phonetic):
        from kanji_mnemonic.prompt import build_prompt

        result = build_prompt(sample_profile_phonetic, sound_mnemonics=None)
        # Should not crash, same as no sounds
        assert "語" in result


# ---------------------------------------------------------------------------
# Tests: --sound flag on lookup command
# ---------------------------------------------------------------------------


class TestLookupSoundFlag:
    """Tests for --sound flag on the lookup command."""

    def _setup_mocks(self, monkeypatch):
        mock_data = ({}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {})
        monkeypatch.setattr("kanji_mnemonic.cli.get_wk_api_key", lambda: None)
        monkeypatch.setattr("kanji_mnemonic.cli.load_all_data", lambda key: mock_data)

    def test_sound_flag_parsed(self, monkeypatch, config_dir):
        from kanji_mnemonic.cli import main

        self._setup_mocks(monkeypatch)
        mock_cmd = MagicMock()
        monkeypatch.setattr("kanji_mnemonic.cli.cmd_lookup", mock_cmd)
        monkeypatch.setattr("sys.argv", ["kanji", "lookup", "語", "--sound"])
        main()
        mock_cmd.assert_called_once()
        args = mock_cmd.call_args[0][0]
        assert args.sound is True

    def test_no_sound_defaults_false(self, monkeypatch, config_dir):
        from kanji_mnemonic.cli import main

        self._setup_mocks(monkeypatch)
        mock_cmd = MagicMock()
        monkeypatch.setattr("kanji_mnemonic.cli.cmd_lookup", mock_cmd)
        monkeypatch.setattr("sys.argv", ["kanji", "lookup", "語"])
        main()
        args = mock_cmd.call_args[0][0]
        assert args.sound is False


# ---------------------------------------------------------------------------
# Tests: kanji sounds command
# ---------------------------------------------------------------------------


class TestCmdSounds:
    """Tests for 'kanji sounds' CLI command."""

    def _setup_mocks(self, monkeypatch):
        mock_data = ({}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {})
        monkeypatch.setattr("kanji_mnemonic.cli.get_wk_api_key", lambda: None)
        monkeypatch.setattr("kanji_mnemonic.cli.load_all_data", lambda key: mock_data)

    def test_sounds_command_dispatched(self, monkeypatch, config_dir):
        from kanji_mnemonic.cli import main

        self._setup_mocks(monkeypatch)
        mock_cmd = MagicMock()
        monkeypatch.setattr("kanji_mnemonic.cli.cmd_sounds", mock_cmd)
        monkeypatch.setattr("sys.argv", ["kanji", "sounds"])
        main()
        mock_cmd.assert_called_once()


# ===========================================================================
# Part 2: Personal Sound Mnemonic Overrides (bd-20u)
# ===========================================================================


# ---------------------------------------------------------------------------
# Tests: load_personal_sound_mnemonics()
# ---------------------------------------------------------------------------


class TestLoadPersonalSoundMnemonics:
    """Tests for load_personal_sound_mnemonics() in data.py."""

    def test_loads_existing_file(self, config_dir, personal_sound_file):
        from kanji_mnemonic.data import load_personal_sound_mnemonics

        result = load_personal_sound_mnemonics()
        assert "こう" in result
        assert result["こう"]["character"] == "My Friend Kou"
        assert "せい" in result

    def test_returns_empty_dict_when_file_missing(self, config_dir):
        from kanji_mnemonic.data import load_personal_sound_mnemonics

        result = load_personal_sound_mnemonics()
        assert result == {}

    def test_returns_empty_dict_for_empty_json(self, config_dir):
        from kanji_mnemonic.data import load_personal_sound_mnemonics

        (config_dir / "sound_mnemonics.json").write_text("{}", encoding="utf-8")
        result = load_personal_sound_mnemonics()
        assert result == {}


# ---------------------------------------------------------------------------
# Tests: save_personal_sound_mnemonic()
# ---------------------------------------------------------------------------


class TestSavePersonalSoundMnemonic:
    """Tests for save_personal_sound_mnemonic() in data.py."""

    def test_saves_new_entry(self, config_dir):
        from kanji_mnemonic.data import save_personal_sound_mnemonic

        save_personal_sound_mnemonic("りゅう", "Dragon", "A mythical creature")
        data = json.loads(
            (config_dir / "sound_mnemonics.json").read_text(encoding="utf-8")
        )
        assert data["りゅう"]["character"] == "Dragon"
        assert data["りゅう"]["description"] == "A mythical creature"

    def test_updates_existing_entry(self, config_dir, personal_sound_file):
        from kanji_mnemonic.data import save_personal_sound_mnemonic

        save_personal_sound_mnemonic("こう", "New Kou", "Updated description")
        data = json.loads(
            (config_dir / "sound_mnemonics.json").read_text(encoding="utf-8")
        )
        assert data["こう"]["character"] == "New Kou"
        # Other entries untouched
        assert "せい" in data

    def test_creates_directory_if_missing(self, tmp_path, monkeypatch):
        from kanji_mnemonic.data import save_personal_sound_mnemonic

        cfg = tmp_path / "nonexistent" / "config"
        monkeypatch.setattr("kanji_mnemonic.data.CONFIG_DIR", cfg)
        save_personal_sound_mnemonic("こう", "Kou", "A friend")
        assert (cfg / "sound_mnemonics.json").exists()


# ---------------------------------------------------------------------------
# Tests: remove_personal_sound_mnemonic()
# ---------------------------------------------------------------------------


class TestRemovePersonalSoundMnemonic:
    """Tests for remove_personal_sound_mnemonic() in data.py."""

    def test_removes_existing_entry(self, config_dir, personal_sound_file):
        from kanji_mnemonic.data import remove_personal_sound_mnemonic

        result = remove_personal_sound_mnemonic("こう")
        assert result is True
        data = json.loads(
            (config_dir / "sound_mnemonics.json").read_text(encoding="utf-8")
        )
        assert "こう" not in data
        assert "せい" in data

    def test_returns_false_for_missing_entry(self, config_dir, personal_sound_file):
        from kanji_mnemonic.data import remove_personal_sound_mnemonic

        result = remove_personal_sound_mnemonic("りゅう")
        assert result is False

    def test_returns_false_when_file_missing(self, config_dir):
        from kanji_mnemonic.data import remove_personal_sound_mnemonic

        result = remove_personal_sound_mnemonic("こう")
        assert result is False


# ---------------------------------------------------------------------------
# Tests: CLI commands for personal sound mnemonics
# ---------------------------------------------------------------------------


class TestCmdSound:
    """Tests for 'kanji sound' CLI command."""

    def test_saves_sound_mnemonic(self, config_dir, capsys):
        from kanji_mnemonic.cli import cmd_sound

        args = argparse.Namespace(
            reading="こう",
            character="My Kou",
            description="My friend",
            remove=False,
        )
        cmd_sound(args)
        data = json.loads(
            (config_dir / "sound_mnemonics.json").read_text(encoding="utf-8")
        )
        assert data["こう"]["character"] == "My Kou"

    def test_shows_current_sound(self, config_dir, personal_sound_file, capsys):
        from kanji_mnemonic.cli import cmd_sound

        args = argparse.Namespace(
            reading="こう", character=None, description=None, remove=False
        )
        cmd_sound(args)
        output = capsys.readouterr().out
        assert "こう" in output
        assert "My Friend Kou" in output

    def test_shows_no_sound_message(self, config_dir, capsys):
        from kanji_mnemonic.cli import cmd_sound

        args = argparse.Namespace(
            reading="りゅう", character=None, description=None, remove=False
        )
        cmd_sound(args)
        output = capsys.readouterr().out
        assert "No personal sound mnemonic" in output

    def test_removes_sound(self, config_dir, personal_sound_file, capsys):
        from kanji_mnemonic.cli import cmd_sound

        args = argparse.Namespace(
            reading="こう", character=None, description=None, remove=True
        )
        cmd_sound(args)
        data = json.loads(
            (config_dir / "sound_mnemonics.json").read_text(encoding="utf-8")
        )
        assert "こう" not in data

    def test_prints_confirmation_on_save(self, config_dir, capsys):
        from kanji_mnemonic.cli import cmd_sound

        args = argparse.Namespace(
            reading="こう",
            character="My Kou",
            description="My friend",
            remove=False,
        )
        cmd_sound(args)
        output = capsys.readouterr().out
        assert "こう" in output
        assert "My Kou" in output


class TestCmdSoundsOutput:
    """Tests for 'kanji sounds' listing output."""

    def test_lists_merged_sounds(self, config_dir, personal_sound_file, capsys):
        """sounds command should list merged WK + personal sound mnemonics."""
        from kanji_mnemonic.cli import cmd_sounds

        args = argparse.Namespace(personal=False)
        cmd_sounds(args)
        output = capsys.readouterr().out
        # Personal entries should show [personal] annotation
        assert "こう" in output
        assert "[personal]" in output

    def test_personal_flag(self, config_dir, personal_sound_file, capsys):
        """--personal flag shows only personal sound mnemonics."""
        from kanji_mnemonic.cli import cmd_sounds

        args = argparse.Namespace(personal=True)
        cmd_sounds(args)
        output = capsys.readouterr().out
        assert "こう" in output
        assert "My Friend Kou" in output

    def test_empty_sounds_message(self, config_dir, capsys):
        """With no sound mnemonics, prints helpful message."""
        from kanji_mnemonic.cli import cmd_sounds

        args = argparse.Namespace(personal=True)
        cmd_sounds(args)
        output = capsys.readouterr().out
        assert "kanji sound" in output


# ---------------------------------------------------------------------------
# Tests: CLI dispatch for sound/sounds commands
# ---------------------------------------------------------------------------


class TestSoundCommandDispatch:
    """Tests for main() routing to sound/sounds commands."""

    def _setup_mocks(self, monkeypatch):
        mock_data = ({}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {})
        monkeypatch.setattr("kanji_mnemonic.cli.get_wk_api_key", lambda: None)
        monkeypatch.setattr("kanji_mnemonic.cli.load_all_data", lambda key: mock_data)

    def test_sound_command_save(self, monkeypatch, config_dir):
        from kanji_mnemonic.cli import main

        self._setup_mocks(monkeypatch)
        mock_cmd = MagicMock()
        monkeypatch.setattr("kanji_mnemonic.cli.cmd_sound", mock_cmd)
        monkeypatch.setattr(
            "sys.argv", ["kanji", "sound", "こう", "My Kou", "My friend"]
        )
        main()
        mock_cmd.assert_called_once()
        args = mock_cmd.call_args[0][0]
        assert args.reading == "こう"
        assert args.character == "My Kou"
        assert args.description == "My friend"

    def test_sound_command_show(self, monkeypatch, config_dir):
        from kanji_mnemonic.cli import main

        self._setup_mocks(monkeypatch)
        mock_cmd = MagicMock()
        monkeypatch.setattr("kanji_mnemonic.cli.cmd_sound", mock_cmd)
        monkeypatch.setattr("sys.argv", ["kanji", "sound", "こう"])
        main()
        mock_cmd.assert_called_once()
        args = mock_cmd.call_args[0][0]
        assert args.reading == "こう"
        assert args.character is None

    def test_sounds_command(self, monkeypatch, config_dir):
        from kanji_mnemonic.cli import main

        self._setup_mocks(monkeypatch)
        mock_cmd = MagicMock()
        monkeypatch.setattr("kanji_mnemonic.cli.cmd_sounds", mock_cmd)
        monkeypatch.setattr("sys.argv", ["kanji", "sounds"])
        main()
        mock_cmd.assert_called_once()

    def test_sounds_personal_flag(self, monkeypatch, config_dir):
        from kanji_mnemonic.cli import main

        self._setup_mocks(monkeypatch)
        mock_cmd = MagicMock()
        monkeypatch.setattr("kanji_mnemonic.cli.cmd_sounds", mock_cmd)
        monkeypatch.setattr("sys.argv", ["kanji", "sounds", "--personal"])
        main()
        mock_cmd.assert_called_once()
        args = mock_cmd.call_args[0][0]
        assert args.personal is True
