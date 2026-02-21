"""Tests for personal radical dictionary feature (bd-3ds).

These tests define the API contract for bd-29p (personal radical dictionary).
They are expected to fail until the feature is implemented.
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
    """Redirect personal radicals config dir to a temp directory."""
    cfg = tmp_path / "config" / "kanji"
    cfg.mkdir(parents=True)
    monkeypatch.setattr("kanji_mnemonic.data.CONFIG_DIR", cfg)
    return cfg


@pytest.fixture
def personal_radicals_file(config_dir):
    """Create a personal radicals JSON file with sample data."""
    data = {"世": "World", "丶": "Drop"}
    (config_dir / "radicals.json").write_text(
        json.dumps(data, ensure_ascii=False), encoding="utf-8"
    )
    return config_dir / "radicals.json"


# ---------------------------------------------------------------------------
# Tests: load_personal_radicals()
# ---------------------------------------------------------------------------


class TestLoadPersonalRadicals:
    """Tests for load_personal_radicals() in data.py."""

    def test_loads_existing_file(self, config_dir, personal_radicals_file):
        from kanji_mnemonic.data import load_personal_radicals

        result = load_personal_radicals()
        assert result == {"世": "World", "丶": "Drop"}

    def test_returns_empty_dict_when_file_missing(self, config_dir):
        """No radicals.json file -> empty dict, no error."""
        from kanji_mnemonic.data import load_personal_radicals

        result = load_personal_radicals()
        assert result == {}

    def test_returns_empty_dict_for_empty_json(self, config_dir):
        """radicals.json exists but contains empty object."""
        from kanji_mnemonic.data import load_personal_radicals

        (config_dir / "radicals.json").write_text("{}", encoding="utf-8")
        result = load_personal_radicals()
        assert result == {}


# ---------------------------------------------------------------------------
# Tests: save_personal_radical()
# ---------------------------------------------------------------------------


class TestSavePersonalRadical:
    """Tests for save_personal_radical() in data.py."""

    def test_adds_new_radical(self, config_dir):
        """Saving to an empty/nonexistent file creates it with the entry."""
        from kanji_mnemonic.data import save_personal_radical

        save_personal_radical("世", "World")
        data = json.loads((config_dir / "radicals.json").read_text(encoding="utf-8"))
        assert data == {"世": "World"}

    def test_updates_existing_radical(self, config_dir, personal_radicals_file):
        """Saving an existing char overwrites its name."""
        from kanji_mnemonic.data import save_personal_radical

        save_personal_radical("世", "Generation")
        data = json.loads((config_dir / "radicals.json").read_text(encoding="utf-8"))
        assert data["世"] == "Generation"
        # Other entries untouched
        assert data["丶"] == "Drop"

    def test_creates_directory_if_missing(self, tmp_path, monkeypatch):
        """Config directory is created if it doesn't exist yet."""
        from kanji_mnemonic.data import save_personal_radical

        cfg = tmp_path / "nonexistent" / "config"
        monkeypatch.setattr("kanji_mnemonic.data.CONFIG_DIR", cfg)
        save_personal_radical("世", "World")
        assert (cfg / "radicals.json").exists()
        data = json.loads((cfg / "radicals.json").read_text(encoding="utf-8"))
        assert data == {"世": "World"}


# ---------------------------------------------------------------------------
# Tests: personal radicals override WK names in lookup
# ---------------------------------------------------------------------------


class TestPersonalRadicalsInLookup:
    """Tests for personal radical name integration in lookup_kanji()."""

    def test_personal_name_overrides_wk_name(
        self,
        sample_kanji_db,
        sample_phonetic_db,
        sample_wk_kanji_db,
        sample_wk_radicals,
        sample_wk_kanji_subjects,
        sample_kradfile,
    ):
        """Personal radical names take precedence over WK radical names."""
        from kanji_mnemonic.lookup import lookup_kanji

        personal_radicals = {"言": "My Say"}
        profile = lookup_kanji(
            "語",
            sample_kanji_db,
            sample_phonetic_db,
            sample_wk_kanji_db,
            sample_wk_radicals,
            sample_wk_kanji_subjects,
            sample_kradfile,
            personal_radicals=personal_radicals,
        )
        say_comp = next(c for c in profile.wk_components if c["char"] == "言")
        assert say_comp["name"] == "My Say"

    def test_personal_name_fills_missing_wk_name(
        self,
        sample_kanji_db,
        sample_phonetic_db,
        sample_wk_kanji_db,
        sample_wk_radicals,
        sample_wk_kanji_subjects,
        sample_kradfile,
    ):
        """Personal name is used for components with no WK radical entry."""
        from kanji_mnemonic.lookup import lookup_kanji

        # 蝶 uses KRADFILE fallback; "世" has no WK radical name
        personal_radicals = {"世": "World"}
        profile = lookup_kanji(
            "蝶",
            sample_kanji_db,
            sample_phonetic_db,
            sample_wk_kanji_db,
            sample_wk_radicals,
            sample_wk_kanji_subjects,
            sample_kradfile,
            personal_radicals=personal_radicals,
        )
        world_comp = next(c for c in profile.wk_components if c["char"] == "世")
        assert world_comp["name"] == "World"

    def test_no_personal_radical_falls_through(
        self,
        sample_kanji_db,
        sample_phonetic_db,
        sample_wk_kanji_db,
        sample_wk_radicals,
        sample_wk_kanji_subjects,
        sample_kradfile,
    ):
        """Without a personal radical entry, WK name is still used.

        See also TestPersonalRadicalsInPhoneticFamily for phonetic family tests.
        """
        from kanji_mnemonic.lookup import lookup_kanji

        profile = lookup_kanji(
            "語",
            sample_kanji_db,
            sample_phonetic_db,
            sample_wk_kanji_db,
            sample_wk_radicals,
            sample_wk_kanji_subjects,
            sample_kradfile,
            personal_radicals={},
        )
        say_comp = next(c for c in profile.wk_components if c["char"] == "言")
        assert say_comp["name"] == "Say"


# ---------------------------------------------------------------------------
# Tests: personal radicals in phonetic family display
# ---------------------------------------------------------------------------


class TestPersonalRadicalsInPhoneticFamily:
    """Tests for personal radical names appearing in phonetic family section (bd-3h0).

    The phonetic_family dict has its own wk_radical_name field that is
    set independently from wk_components. Personal radical overrides
    must also update this field.
    """

    def test_phonetic_family_uses_personal_radical_name(
        self,
        sample_kanji_db,
        sample_phonetic_db,
        sample_wk_kanji_db,
        sample_wk_radicals,
        sample_wk_kanji_subjects,
        sample_kradfile,
    ):
        """Phonetic family wk_radical_name reflects personal radical override."""
        from kanji_mnemonic.lookup import lookup_kanji

        # 話 has phonetic component 舌, which has wk-radical: None in phonetic_db
        personal_radicals = {"舌": "Tongue Radical"}
        profile = lookup_kanji(
            "話",
            sample_kanji_db,
            sample_phonetic_db,
            sample_wk_kanji_db,
            sample_wk_radicals,
            sample_wk_kanji_subjects,
            sample_kradfile,
            personal_radicals=personal_radicals,
        )
        assert profile.phonetic_family is not None
        assert profile.phonetic_family["wk_radical_name"] == "Tongue Radical"

    def test_phonetic_family_format_uses_personal_radical_name(
        self,
        sample_kanji_db,
        sample_phonetic_db,
        sample_wk_kanji_db,
        sample_wk_radicals,
        sample_wk_kanji_subjects,
        sample_kradfile,
    ):
        """format_profile() shows the personal radical name in Phonetic Family section."""
        from kanji_mnemonic.lookup import format_profile, lookup_kanji

        personal_radicals = {"舌": "Tongue Radical"}
        profile = lookup_kanji(
            "話",
            sample_kanji_db,
            sample_phonetic_db,
            sample_wk_kanji_db,
            sample_wk_radicals,
            sample_wk_kanji_subjects,
            sample_kradfile,
            personal_radicals=personal_radicals,
        )
        output = format_profile(profile)
        assert "Tongue Radical" in output
        assert "(WK:" not in output

    def test_phonetic_family_without_personal_radical_still_shows_no_name(
        self,
        sample_kanji_db,
        sample_phonetic_db,
        sample_wk_kanji_db,
        sample_wk_radicals,
        sample_wk_kanji_subjects,
        sample_kradfile,
    ):
        """Without a personal radical for the phonetic component, '(no name)' is shown."""
        from kanji_mnemonic.lookup import format_profile, lookup_kanji

        profile = lookup_kanji(
            "話",
            sample_kanji_db,
            sample_phonetic_db,
            sample_wk_kanji_db,
            sample_wk_radicals,
            sample_wk_kanji_subjects,
            sample_kradfile,
            personal_radicals={},
        )
        output = format_profile(profile)
        assert "(no name)" in output

    def test_phonetic_family_personal_overrides_existing_wk_name(
        self,
        sample_kanji_db,
        sample_phonetic_db,
        sample_wk_kanji_db,
        sample_wk_radicals,
        sample_wk_kanji_subjects,
        sample_kradfile,
    ):
        """Personal radical name overrides even an existing wk-radical name from phonetic_db."""
        from kanji_mnemonic.lookup import lookup_kanji

        # 語 has phonetic 吾, which has wk-radical: "five-mouths" in phonetic_db
        personal_radicals = {"吾": "My Custom Name"}
        profile = lookup_kanji(
            "語",
            sample_kanji_db,
            sample_phonetic_db,
            sample_wk_kanji_db,
            sample_wk_radicals,
            sample_wk_kanji_subjects,
            sample_kradfile,
            personal_radicals=personal_radicals,
        )
        assert profile.phonetic_family is not None
        assert profile.phonetic_family["wk_radical_name"] == "My Custom Name"


# ---------------------------------------------------------------------------
# Tests: hint message when no name from any source
# ---------------------------------------------------------------------------


class TestNoNameHint:
    """Tests for the hint message in format_profile() when no name exists."""

    def test_hint_message_for_unnamed_component(
        self,
        sample_kanji_db,
        sample_phonetic_db,
        sample_wk_kanji_db,
        sample_kradfile,
    ):
        """Component with no WK name and no personal name shows CLI hint."""
        from kanji_mnemonic.lookup import format_profile, lookup_kanji

        # 蝶 has "世" which has no WK radical name
        wk_radicals_without_world = {
            "虫": {"name": "Insect", "level": 5, "slug": "insect"},
            "木": {"name": "Tree", "level": 2, "slug": "tree"},
            # "世" deliberately absent
        }
        profile = lookup_kanji(
            "蝶",
            sample_kanji_db,
            sample_phonetic_db,
            sample_wk_kanji_db,
            wk_radicals_without_world,
            None,
            sample_kradfile,
            personal_radicals={},
        )
        output = format_profile(profile)
        assert "kanji name 世" in output

    def test_hint_not_shown_when_name_exists(
        self,
        sample_kanji_db,
        sample_phonetic_db,
        sample_wk_kanji_db,
        sample_wk_radicals,
        sample_wk_kanji_subjects,
        sample_kradfile,
    ):
        """Components with names do not show the hint."""
        from kanji_mnemonic.lookup import format_profile, lookup_kanji

        profile = lookup_kanji(
            "語",
            sample_kanji_db,
            sample_phonetic_db,
            sample_wk_kanji_db,
            sample_wk_radicals,
            sample_wk_kanji_subjects,
            sample_kradfile,
            personal_radicals={},
        )
        output = format_profile(profile)
        assert "kanji name" not in output
        assert "(no WK name)" not in output


# ---------------------------------------------------------------------------
# Tests: CLI commands for personal radical dictionary
# ---------------------------------------------------------------------------


class TestCmdName:
    """Tests for 'kanji name' CLI command."""

    def test_adds_radical_name(self, config_dir, capsys):
        """'kanji name 世 World' saves the radical name."""
        from kanji_mnemonic.cli import cmd_name

        args = argparse.Namespace(radical="世", name="World")
        cmd_name(args)
        data = json.loads((config_dir / "radicals.json").read_text(encoding="utf-8"))
        assert data["世"] == "World"

    def test_updates_existing_name(self, config_dir, personal_radicals_file, capsys):
        """'kanji name 世 Generation' overwrites the existing name."""
        from kanji_mnemonic.cli import cmd_name

        args = argparse.Namespace(radical="世", name="Generation")
        cmd_name(args)
        data = json.loads((config_dir / "radicals.json").read_text(encoding="utf-8"))
        assert data["世"] == "Generation"

    def test_prints_confirmation(self, config_dir, capsys):
        """Command prints a confirmation message."""
        from kanji_mnemonic.cli import cmd_name

        args = argparse.Namespace(radical="世", name="World")
        cmd_name(args)
        output = capsys.readouterr().out
        assert "世" in output
        assert "World" in output


# ---------------------------------------------------------------------------
# Tests: CLI 'kanji names' command
# ---------------------------------------------------------------------------


class TestCmdNames:
    """Tests for 'kanji names' CLI command."""

    def test_lists_all_personal_radicals(
        self, config_dir, personal_radicals_file, capsys
    ):
        """'kanji names' prints all personal radical entries."""
        from kanji_mnemonic.cli import cmd_names

        args = argparse.Namespace()
        cmd_names(args)
        output = capsys.readouterr().out
        assert "世" in output
        assert "World" in output
        assert "丶" in output
        assert "Drop" in output

    def test_empty_dictionary_message(self, config_dir, capsys):
        """'kanji names' with no entries prints a helpful message."""
        from kanji_mnemonic.cli import cmd_names

        args = argparse.Namespace()
        cmd_names(args)
        output = capsys.readouterr().out
        # Should mention how to add radicals
        assert "kanji name" in output


# ---------------------------------------------------------------------------
# Tests: CLI dispatch for name/names commands
# ---------------------------------------------------------------------------


class TestNameCommandDispatch:
    """Tests for main() routing to name/names commands."""

    def _setup_mocks(self, monkeypatch):
        """Set up common mocks so main() doesn't load real data."""
        mock_data = ({}, {}, {}, {}, {}, {}, {})
        monkeypatch.setattr("kanji_mnemonic.cli.get_wk_api_key", lambda: None)
        monkeypatch.setattr("kanji_mnemonic.cli.load_all_data", lambda key: mock_data)

    def test_name_command(self, monkeypatch, config_dir):
        """'kanji name 世 World' dispatches to cmd_name with correct args."""
        from kanji_mnemonic.cli import main

        self._setup_mocks(monkeypatch)
        mock_cmd = MagicMock()
        monkeypatch.setattr("kanji_mnemonic.cli.cmd_name", mock_cmd)
        monkeypatch.setattr("sys.argv", ["kanji", "name", "世", "World"])
        main()
        mock_cmd.assert_called_once()
        args = mock_cmd.call_args[0][0]
        assert args.radical == "世"
        assert args.name == "World"

    def test_names_command(self, monkeypatch, config_dir):
        """'kanji names' dispatches to cmd_names."""
        from kanji_mnemonic.cli import main

        self._setup_mocks(monkeypatch)
        mock_cmd = MagicMock()
        monkeypatch.setattr("kanji_mnemonic.cli.cmd_names", mock_cmd)
        monkeypatch.setattr("sys.argv", ["kanji", "names"])
        main()
        mock_cmd.assert_called_once()


# ---------------------------------------------------------------------------
# Tests: WK: prefix removed from Phonetic Family section (bd-1qt)
# ---------------------------------------------------------------------------


class TestWkPrefixRemoved:
    """Verify format_profile() does not add 'WK:' prefix to phonetic component names.

    The Phonetic Family section should show just '(Name)' regardless of
    whether the name came from WK, personal radicals, or is missing.
    """

    def test_wk_sourced_name_has_no_wk_prefix(
        self,
        sample_kanji_db,
        sample_phonetic_db,
        sample_wk_kanji_db,
        sample_wk_radicals,
        sample_wk_kanji_subjects,
        sample_kradfile,
    ):
        """WK-sourced phonetic name shows (Name) not (WK: Name)."""
        from kanji_mnemonic.lookup import format_profile, lookup_kanji

        # 語 has phonetic 吾 with wk-radical: "five-mouths" from Keisei
        profile = lookup_kanji(
            "語",
            sample_kanji_db,
            sample_phonetic_db,
            sample_wk_kanji_db,
            sample_wk_radicals,
            sample_wk_kanji_subjects,
            sample_kradfile,
            personal_radicals={},
        )
        output = format_profile(profile)
        assert "(five-mouths)" in output
        assert "(WK:" not in output

    def test_personal_radical_name_has_no_wk_prefix(
        self,
        sample_kanji_db,
        sample_phonetic_db,
        sample_wk_kanji_db,
        sample_wk_radicals,
        sample_wk_kanji_subjects,
        sample_kradfile,
    ):
        """Personal radical name shows (Name) not (WK: Name)."""
        from kanji_mnemonic.lookup import format_profile, lookup_kanji

        # 話 has phonetic 舌 with no keisei wk-radical; personal name overrides
        personal_radicals = {"舌": "Tongue"}
        profile = lookup_kanji(
            "話",
            sample_kanji_db,
            sample_phonetic_db,
            sample_wk_kanji_db,
            sample_wk_radicals,
            sample_wk_kanji_subjects,
            sample_kradfile,
            personal_radicals=personal_radicals,
        )
        output = format_profile(profile)
        assert "(Tongue)" in output
        assert "(WK:" not in output

    def test_missing_name_shows_no_name_fallback(
        self,
        sample_kanji_db,
        sample_phonetic_db,
        sample_wk_kanji_db,
        sample_wk_kanji_subjects,
        sample_kradfile,
    ):
        """Missing name shows '(no name)' not '(no WK name)'."""
        from kanji_mnemonic.lookup import format_profile, lookup_kanji

        # 話 has phonetic 舌; remove 舌 from wk_radicals so no name source exists
        wk_radicals_no_tongue = {
            "言": {"name": "Say", "level": 2, "slug": "say"},
        }
        profile = lookup_kanji(
            "話",
            sample_kanji_db,
            sample_phonetic_db,
            sample_wk_kanji_db,
            wk_radicals_no_tongue,
            sample_wk_kanji_subjects,
            sample_kradfile,
            personal_radicals={},
        )
        output = format_profile(profile)
        assert "(no name)" in output
        assert "(no WK name)" not in output
        assert "(WK:" not in output
