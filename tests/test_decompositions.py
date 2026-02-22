"""Tests for personal kanji decomposition feature (bd-8y4).

These tests define the API contract for the `kanji decompose` command.
They are expected to fail until the feature is implemented (TDD).
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
def decompositions_file(config_dir):
    """Create a decompositions.json file with sample data."""
    data = {
        "語": {
            "parts": ["言", "吾"],
            "phonetic": "吾",
            "semantic": "言",
        },
        "蝶": {
            "parts": ["虫", "木", "世"],
            "phonetic": None,
            "semantic": None,
        },
    }
    (config_dir / "decompositions.json").write_text(
        json.dumps(data, ensure_ascii=False), encoding="utf-8"
    )
    return config_dir / "decompositions.json"


@pytest.fixture
def sample_personal_decompositions():
    """Sample personal decompositions dict (as returned by load_personal_decompositions)."""
    return {
        "語": {
            "parts": ["言", "吾"],
            "phonetic": "吾",
            "semantic": "言",
        },
    }


# ---------------------------------------------------------------------------
# Tests: load_personal_decompositions()
# ---------------------------------------------------------------------------


class TestLoadPersonalDecompositions:
    """Tests for load_personal_decompositions() in data.py."""

    def test_loads_existing_file(self, config_dir, decompositions_file):
        from kanji_mnemonic.data import load_personal_decompositions

        result = load_personal_decompositions()
        assert "語" in result
        assert result["語"]["parts"] == ["言", "吾"]
        assert result["語"]["phonetic"] == "吾"
        assert result["語"]["semantic"] == "言"

    def test_returns_empty_dict_when_file_missing(self, config_dir):
        from kanji_mnemonic.data import load_personal_decompositions

        result = load_personal_decompositions()
        assert result == {}

    def test_returns_empty_dict_for_empty_json(self, config_dir):
        from kanji_mnemonic.data import load_personal_decompositions

        (config_dir / "decompositions.json").write_text("{}", encoding="utf-8")
        result = load_personal_decompositions()
        assert result == {}


# ---------------------------------------------------------------------------
# Tests: save_personal_decomposition()
# ---------------------------------------------------------------------------


class TestSavePersonalDecomposition:
    """Tests for save_personal_decomposition() in data.py."""

    def test_saves_new_entry(self, config_dir):
        from kanji_mnemonic.data import save_personal_decomposition

        save_personal_decomposition("語", ["言", "吾"], phonetic="吾", semantic="言")
        data = json.loads(
            (config_dir / "decompositions.json").read_text(encoding="utf-8")
        )
        assert data["語"]["parts"] == ["言", "吾"]
        assert data["語"]["phonetic"] == "吾"
        assert data["語"]["semantic"] == "言"

    def test_saves_without_phonetic_semantic(self, config_dir):
        from kanji_mnemonic.data import save_personal_decomposition

        save_personal_decomposition("蝶", ["虫", "木", "世"])
        data = json.loads(
            (config_dir / "decompositions.json").read_text(encoding="utf-8")
        )
        assert data["蝶"]["parts"] == ["虫", "木", "世"]
        assert data["蝶"]["phonetic"] is None
        assert data["蝶"]["semantic"] is None

    def test_overwrites_existing_entry(self, config_dir, decompositions_file):
        from kanji_mnemonic.data import save_personal_decomposition

        save_personal_decomposition("語", ["言", "五", "口"])
        data = json.loads(
            (config_dir / "decompositions.json").read_text(encoding="utf-8")
        )
        assert data["語"]["parts"] == ["言", "五", "口"]
        # Other entries untouched
        assert "蝶" in data

    def test_creates_directory_if_missing(self, tmp_path, monkeypatch):
        from kanji_mnemonic.data import save_personal_decomposition

        cfg = tmp_path / "nonexistent" / "config"
        monkeypatch.setattr("kanji_mnemonic.data.CONFIG_DIR", cfg)
        save_personal_decomposition("語", ["言", "吾"], phonetic="吾", semantic="言")
        assert (cfg / "decompositions.json").exists()


# ---------------------------------------------------------------------------
# Tests: remove_personal_decomposition()
# ---------------------------------------------------------------------------


class TestRemovePersonalDecomposition:
    """Tests for remove_personal_decomposition() in data.py."""

    def test_removes_existing_entry(self, config_dir, decompositions_file):
        from kanji_mnemonic.data import remove_personal_decomposition

        result = remove_personal_decomposition("語")
        assert result is True
        data = json.loads(
            (config_dir / "decompositions.json").read_text(encoding="utf-8")
        )
        assert "語" not in data
        # Other entries untouched
        assert "蝶" in data

    def test_returns_false_for_missing_entry(self, config_dir, decompositions_file):
        from kanji_mnemonic.data import remove_personal_decomposition

        result = remove_personal_decomposition("山")
        assert result is False

    def test_returns_false_when_file_missing(self, config_dir):
        from kanji_mnemonic.data import remove_personal_decomposition

        result = remove_personal_decomposition("語")
        assert result is False


# ---------------------------------------------------------------------------
# Tests: reverse_lookup_radical()
# ---------------------------------------------------------------------------


class TestReverseLookupRadical:
    """Tests for reverse_lookup_radical() in lookup.py."""

    def test_finds_wk_radical_by_name(self, sample_wk_radicals):
        from kanji_mnemonic.lookup import reverse_lookup_radical

        result = reverse_lookup_radical("Say", sample_wk_radicals, {})
        assert result == "言"

    def test_case_insensitive_match(self, sample_wk_radicals):
        from kanji_mnemonic.lookup import reverse_lookup_radical

        result = reverse_lookup_radical("say", sample_wk_radicals, {})
        assert result == "言"

    def test_finds_personal_radical_by_name(self, sample_wk_radicals):
        from kanji_mnemonic.lookup import reverse_lookup_radical

        personal_radicals = {"世": "World"}
        result = reverse_lookup_radical("World", sample_wk_radicals, personal_radicals)
        assert result == "世"

    def test_personal_radicals_take_priority(self, sample_wk_radicals):
        """If same name exists in both, personal dict wins."""
        from kanji_mnemonic.lookup import reverse_lookup_radical

        # "Mountain" exists in WK (山), but personal dict maps it differently
        personal_radicals = {"⛰": "Mountain"}
        result = reverse_lookup_radical(
            "Mountain", sample_wk_radicals, personal_radicals
        )
        assert result == "⛰"

    def test_returns_none_when_not_found(self, sample_wk_radicals):
        from kanji_mnemonic.lookup import reverse_lookup_radical

        result = reverse_lookup_radical("Nonexistent", sample_wk_radicals, {})
        assert result is None

    def test_finds_multi_word_name(self, sample_wk_radicals):
        from kanji_mnemonic.lookup import reverse_lookup_radical

        result = reverse_lookup_radical("Five Mouths", sample_wk_radicals, {})
        assert result == "吾"

    def test_case_insensitive_multi_word(self, sample_wk_radicals):
        from kanji_mnemonic.lookup import reverse_lookup_radical

        result = reverse_lookup_radical("five mouths", sample_wk_radicals, {})
        assert result == "吾"


# ---------------------------------------------------------------------------
# Tests: personal decomposition in lookup_kanji()
# ---------------------------------------------------------------------------


class TestPersonalDecompInLookup:
    """Tests for personal decomposition integration in lookup_kanji()."""

    def test_personal_decomp_overrides_auto(
        self,
        sample_kanji_db,
        sample_phonetic_db,
        sample_wk_kanji_db,
        sample_wk_radicals,
        sample_wk_kanji_subjects,
        sample_kradfile,
        sample_personal_decompositions,
    ):
        """Personal decomposition replaces auto-detected decomposition."""
        from kanji_mnemonic.lookup import lookup_kanji

        profile = lookup_kanji(
            "語",
            sample_kanji_db,
            sample_phonetic_db,
            sample_wk_kanji_db,
            sample_wk_radicals,
            sample_wk_kanji_subjects,
            sample_kradfile,
            personal_decompositions=sample_personal_decompositions,
        )
        assert profile.decomposition == ["言", "吾"]
        assert profile.semantic_component == "言"
        assert profile.phonetic_component == "吾"
        assert profile.personal_decomposition is not None

    def test_auto_values_stashed(
        self,
        sample_kanji_db,
        sample_phonetic_db,
        sample_wk_kanji_db,
        sample_wk_radicals,
        sample_wk_kanji_subjects,
        sample_kradfile,
        sample_personal_decompositions,
    ):
        """Auto-detected decomposition is preserved in auto_* fields."""
        from kanji_mnemonic.lookup import lookup_kanji

        profile = lookup_kanji(
            "語",
            sample_kanji_db,
            sample_phonetic_db,
            sample_wk_kanji_db,
            sample_wk_radicals,
            sample_wk_kanji_subjects,
            sample_kradfile,
            personal_decompositions=sample_personal_decompositions,
        )
        # Auto-detected values should be stashed
        assert profile.auto_decomposition is not None
        assert len(profile.auto_decomposition) > 0
        assert profile.auto_wk_components is not None
        assert len(profile.auto_wk_components) > 0

    def test_decomposition_source_set_to_personal(
        self,
        sample_kanji_db,
        sample_phonetic_db,
        sample_wk_kanji_db,
        sample_wk_radicals,
        sample_wk_kanji_subjects,
        sample_kradfile,
        sample_personal_decompositions,
    ):
        from kanji_mnemonic.lookup import lookup_kanji

        profile = lookup_kanji(
            "語",
            sample_kanji_db,
            sample_phonetic_db,
            sample_wk_kanji_db,
            sample_wk_radicals,
            sample_wk_kanji_subjects,
            sample_kradfile,
            personal_decompositions=sample_personal_decompositions,
        )
        assert profile.decomposition_source == "personal"

    def test_no_personal_decomp_unchanged(
        self,
        sample_kanji_db,
        sample_phonetic_db,
        sample_wk_kanji_db,
        sample_wk_radicals,
        sample_wk_kanji_subjects,
        sample_kradfile,
    ):
        """Without personal decomp, behavior is unchanged."""
        from kanji_mnemonic.lookup import lookup_kanji

        profile = lookup_kanji(
            "語",
            sample_kanji_db,
            sample_phonetic_db,
            sample_wk_kanji_db,
            sample_wk_radicals,
            sample_wk_kanji_subjects,
            sample_kradfile,
        )
        assert profile.personal_decomposition is None
        assert profile.decomposition_source != "personal"

    def test_personal_phonetic_triggers_family_lookup(
        self,
        sample_kanji_db,
        sample_phonetic_db,
        sample_wk_kanji_db,
        sample_wk_radicals,
        sample_wk_kanji_subjects,
        sample_kradfile,
    ):
        """Personal decomposition with phonetic set triggers phonetic family lookup."""
        from kanji_mnemonic.lookup import lookup_kanji

        personal_decompositions = {
            "語": {
                "parts": ["言", "吾"],
                "phonetic": "吾",
                "semantic": "言",
            },
        }
        profile = lookup_kanji(
            "語",
            sample_kanji_db,
            sample_phonetic_db,
            sample_wk_kanji_db,
            sample_wk_radicals,
            sample_wk_kanji_subjects,
            sample_kradfile,
            personal_decompositions=personal_decompositions,
        )
        assert profile.phonetic_family is not None
        assert profile.phonetic_family["phonetic_char"] == "吾"

    def test_wk_components_rebuilt_from_personal_parts(
        self,
        sample_kanji_db,
        sample_phonetic_db,
        sample_wk_kanji_db,
        sample_wk_radicals,
        sample_wk_kanji_subjects,
        sample_kradfile,
        sample_personal_decompositions,
    ):
        """wk_components are rebuilt from personal decomposition parts with names."""
        from kanji_mnemonic.lookup import lookup_kanji

        profile = lookup_kanji(
            "語",
            sample_kanji_db,
            sample_phonetic_db,
            sample_wk_kanji_db,
            sample_wk_radicals,
            sample_wk_kanji_subjects,
            sample_kradfile,
            personal_decompositions=sample_personal_decompositions,
        )
        chars = [c["char"] for c in profile.wk_components]
        assert "言" in chars
        assert "吾" in chars
        # Each should have a name resolved
        for comp in profile.wk_components:
            assert comp["name"] is not None

    def test_inherits_auto_ps_when_not_specified(
        self,
        sample_kanji_db,
        sample_phonetic_db,
        sample_wk_kanji_db,
        sample_wk_radicals,
        sample_wk_kanji_subjects,
        sample_kradfile,
    ):
        """Personal decomp without -p/-s inherits auto PS when components are in parts."""
        from kanji_mnemonic.lookup import lookup_kanji

        # 語 auto-detects as comp_phonetic with semantic=言, phonetic=吾
        # Personal decomp has same parts but no PS markers
        personal_decompositions = {
            "語": {
                "parts": ["言", "吾"],
                "phonetic": None,
                "semantic": None,
            },
        }
        profile = lookup_kanji(
            "語",
            sample_kanji_db,
            sample_phonetic_db,
            sample_wk_kanji_db,
            sample_wk_radicals,
            sample_wk_kanji_subjects,
            sample_kradfile,
            personal_decompositions=personal_decompositions,
        )
        # Should inherit auto-detected PS since both are in parts list
        assert profile.semantic_component == "言"
        assert profile.phonetic_component == "吾"
        assert profile.keisei_type == "comp_phonetic"
        assert profile.decomposition_source == "personal"

    def test_no_inherit_when_auto_component_not_in_parts(
        self,
        sample_kanji_db,
        sample_phonetic_db,
        sample_wk_kanji_db,
        sample_wk_radicals,
        sample_wk_kanji_subjects,
        sample_kradfile,
    ):
        """Auto PS components not inherited if they're not in the personal parts list."""
        from kanji_mnemonic.lookup import lookup_kanji

        # 語 auto-detects phonetic=吾, but personal decomp only has 言
        personal_decompositions = {
            "語": {
                "parts": ["言"],
                "phonetic": None,
                "semantic": None,
            },
        }
        profile = lookup_kanji(
            "語",
            sample_kanji_db,
            sample_phonetic_db,
            sample_wk_kanji_db,
            sample_wk_radicals,
            sample_wk_kanji_subjects,
            sample_kradfile,
            personal_decompositions=personal_decompositions,
        )
        # 言 (semantic) IS in parts, so it should inherit
        assert profile.semantic_component == "言"
        # 吾 (phonetic) is NOT in parts, so should NOT inherit
        assert profile.phonetic_component is None


# ---------------------------------------------------------------------------
# Tests: format_profile with personal decomposition
# ---------------------------------------------------------------------------


class TestFormatProfilePersonalDecomp:
    """Tests for format_profile() with personal decomposition."""

    def test_personal_annotation_on_components(
        self,
        sample_kanji_db,
        sample_phonetic_db,
        sample_wk_kanji_db,
        sample_wk_radicals,
        sample_wk_kanji_subjects,
        sample_kradfile,
        sample_personal_decompositions,
    ):
        """Components header shows [personal] when personal decomp active."""
        from kanji_mnemonic.lookup import format_profile, lookup_kanji

        profile = lookup_kanji(
            "語",
            sample_kanji_db,
            sample_phonetic_db,
            sample_wk_kanji_db,
            sample_wk_radicals,
            sample_wk_kanji_subjects,
            sample_kradfile,
            personal_decompositions=sample_personal_decompositions,
        )
        output = format_profile(profile)
        assert "[personal]" in output

    def test_no_annotation_without_personal_decomp(
        self,
        sample_kanji_db,
        sample_phonetic_db,
        sample_wk_kanji_db,
        sample_wk_radicals,
        sample_wk_kanji_subjects,
        sample_kradfile,
    ):
        """No [personal] annotation when using auto-detected decomposition."""
        from kanji_mnemonic.lookup import format_profile, lookup_kanji

        profile = lookup_kanji(
            "語",
            sample_kanji_db,
            sample_phonetic_db,
            sample_wk_kanji_db,
            sample_wk_radicals,
            sample_wk_kanji_subjects,
            sample_kradfile,
        )
        output = format_profile(profile)
        assert "[personal]" not in output

    def test_show_all_decomp_has_both_sections(
        self,
        sample_kanji_db,
        sample_phonetic_db,
        sample_wk_kanji_db,
        sample_wk_radicals,
        sample_wk_kanji_subjects,
        sample_kradfile,
        sample_personal_decompositions,
    ):
        """show_all_decomp=True shows both personal and auto-detected sections."""
        from kanji_mnemonic.lookup import format_profile, lookup_kanji

        profile = lookup_kanji(
            "語",
            sample_kanji_db,
            sample_phonetic_db,
            sample_wk_kanji_db,
            sample_wk_radicals,
            sample_wk_kanji_subjects,
            sample_kradfile,
            personal_decompositions=sample_personal_decompositions,
        )
        output = format_profile(profile, show_all_decomp=True)
        # Both sections should be present
        assert "[personal]" in output.lower() or "personal" in output.lower()
        assert "auto" in output.lower()

    def test_show_all_decomp_no_personal(
        self,
        sample_kanji_db,
        sample_phonetic_db,
        sample_wk_kanji_db,
        sample_wk_radicals,
        sample_wk_kanji_subjects,
        sample_kradfile,
    ):
        """show_all_decomp=True without personal decomp shows auto-detected only."""
        from kanji_mnemonic.lookup import format_profile, lookup_kanji

        profile = lookup_kanji(
            "語",
            sample_kanji_db,
            sample_phonetic_db,
            sample_wk_kanji_db,
            sample_wk_radicals,
            sample_wk_kanji_subjects,
            sample_kradfile,
        )
        output = format_profile(profile, show_all_decomp=True)
        assert "[personal]" not in output


# ---------------------------------------------------------------------------
# Tests: cmd_decompose()
# ---------------------------------------------------------------------------


class TestCmdDecompose:
    """Tests for cmd_decompose() CLI command."""

    def test_saves_decomposition_with_kanji_parts(
        self,
        config_dir,
        capsys,
        sample_kanji_db,
        sample_phonetic_db,
        sample_wk_kanji_db,
        sample_wk_radicals,
        sample_wk_kanji_subjects,
        sample_kradfile,
    ):
        """kanji decompose 語 言 吾 saves the decomposition."""
        from kanji_mnemonic.cli import cmd_decompose

        args = argparse.Namespace(
            kanji="語",
            parts=["言", "吾"],
            phonetic=None,
            semantic=None,
            remove=False,
        )
        cmd_decompose(
            args,
            sample_kanji_db,
            sample_phonetic_db,
            sample_wk_kanji_db,
            sample_wk_radicals,
            sample_wk_kanji_subjects,
            sample_kradfile,
            None,
            {},
            {},
        )
        data = json.loads(
            (config_dir / "decompositions.json").read_text(encoding="utf-8")
        )
        assert data["語"]["parts"] == ["言", "吾"]

    def test_saves_with_phonetic_semantic_flags(
        self,
        config_dir,
        capsys,
        sample_kanji_db,
        sample_phonetic_db,
        sample_wk_kanji_db,
        sample_wk_radicals,
        sample_wk_kanji_subjects,
        sample_kradfile,
    ):
        """kanji decompose 語 -s 言 -p 吾 saves phonetic and semantic."""
        from kanji_mnemonic.cli import cmd_decompose

        args = argparse.Namespace(
            kanji="語",
            parts=[],
            phonetic="吾",
            semantic="言",
            remove=False,
        )
        cmd_decompose(
            args,
            sample_kanji_db,
            sample_phonetic_db,
            sample_wk_kanji_db,
            sample_wk_radicals,
            sample_wk_kanji_subjects,
            sample_kradfile,
            None,
            {},
            {},
        )
        data = json.loads(
            (config_dir / "decompositions.json").read_text(encoding="utf-8")
        )
        assert data["語"]["phonetic"] == "吾"
        assert data["語"]["semantic"] == "言"
        # -p and -s values should be in parts list
        assert "言" in data["語"]["parts"]
        assert "吾" in data["語"]["parts"]

    def test_resolves_word_to_radical(
        self,
        config_dir,
        capsys,
        sample_kanji_db,
        sample_phonetic_db,
        sample_wk_kanji_db,
        sample_wk_radicals,
        sample_wk_kanji_subjects,
        sample_kradfile,
    ):
        """Words are reverse-looked-up to their radical characters."""
        from kanji_mnemonic.cli import cmd_decompose

        args = argparse.Namespace(
            kanji="語",
            parts=["Say"],
            phonetic="Five Mouths",
            semantic=None,
            remove=False,
        )
        cmd_decompose(
            args,
            sample_kanji_db,
            sample_phonetic_db,
            sample_wk_kanji_db,
            sample_wk_radicals,
            sample_wk_kanji_subjects,
            sample_kradfile,
            None,
            {},
            {},
        )
        data = json.loads(
            (config_dir / "decompositions.json").read_text(encoding="utf-8")
        )
        # "Say" should resolve to 言, "Five Mouths" to 吾
        assert "言" in data["語"]["parts"]
        assert data["語"]["phonetic"] == "吾"

    def test_errors_on_unknown_word(
        self,
        config_dir,
        capsys,
        sample_kanji_db,
        sample_phonetic_db,
        sample_wk_kanji_db,
        sample_wk_radicals,
        sample_wk_kanji_subjects,
        sample_kradfile,
    ):
        """Unknown radical word prints error with hint to use kanji name."""
        from kanji_mnemonic.cli import cmd_decompose

        args = argparse.Namespace(
            kanji="語",
            parts=["Nonexistent"],
            phonetic=None,
            semantic=None,
            remove=False,
        )
        with pytest.raises(SystemExit):
            cmd_decompose(
                args,
                sample_kanji_db,
                sample_phonetic_db,
                sample_wk_kanji_db,
                sample_wk_radicals,
                sample_wk_kanji_subjects,
                sample_kradfile,
                None,
                {},
                {},
            )
        output = capsys.readouterr().err
        assert "Nonexistent" in output
        assert "kanji name" in output

    def test_remove_flag(
        self,
        config_dir,
        decompositions_file,
        capsys,
        sample_kanji_db,
        sample_phonetic_db,
        sample_wk_kanji_db,
        sample_wk_radicals,
        sample_wk_kanji_subjects,
        sample_kradfile,
    ):
        """--remove deletes the personal decomposition."""
        from kanji_mnemonic.cli import cmd_decompose

        args = argparse.Namespace(
            kanji="語",
            parts=[],
            phonetic=None,
            semantic=None,
            remove=True,
        )
        cmd_decompose(
            args,
            sample_kanji_db,
            sample_phonetic_db,
            sample_wk_kanji_db,
            sample_wk_radicals,
            sample_wk_kanji_subjects,
            sample_kradfile,
            None,
            {},
            {},
        )
        data = json.loads(
            (config_dir / "decompositions.json").read_text(encoding="utf-8")
        )
        assert "語" not in data

    def test_show_saved_decomposition(
        self,
        config_dir,
        decompositions_file,
        capsys,
        sample_kanji_db,
        sample_phonetic_db,
        sample_wk_kanji_db,
        sample_wk_radicals,
        sample_wk_kanji_subjects,
        sample_kradfile,
    ):
        """No parts = show saved decomposition."""
        from kanji_mnemonic.cli import cmd_decompose
        from kanji_mnemonic.data import load_personal_decompositions

        personal_decompositions = load_personal_decompositions()
        args = argparse.Namespace(
            kanji="語",
            parts=[],
            phonetic=None,
            semantic=None,
            remove=False,
        )
        cmd_decompose(
            args,
            sample_kanji_db,
            sample_phonetic_db,
            sample_wk_kanji_db,
            sample_wk_radicals,
            sample_wk_kanji_subjects,
            sample_kradfile,
            None,
            {},
            personal_decompositions,
        )
        output = capsys.readouterr().out
        assert "語" in output
        assert "言" in output
        assert "吾" in output

    def test_show_no_saved_decomposition(
        self,
        config_dir,
        capsys,
        sample_kanji_db,
        sample_phonetic_db,
        sample_wk_kanji_db,
        sample_wk_radicals,
        sample_wk_kanji_subjects,
        sample_kradfile,
    ):
        """No parts and no saved decomposition prints helpful message."""
        from kanji_mnemonic.cli import cmd_decompose

        args = argparse.Namespace(
            kanji="語",
            parts=[],
            phonetic=None,
            semantic=None,
            remove=False,
        )
        cmd_decompose(
            args,
            sample_kanji_db,
            sample_phonetic_db,
            sample_wk_kanji_db,
            sample_wk_radicals,
            sample_wk_kanji_subjects,
            sample_kradfile,
            None,
            {},
            {},
        )
        output = capsys.readouterr().out
        assert "No personal decomposition" in output

    def test_semantic_inserted_first_phonetic_last(
        self,
        config_dir,
        capsys,
        sample_kanji_db,
        sample_phonetic_db,
        sample_wk_kanji_db,
        sample_wk_radicals,
        sample_wk_kanji_subjects,
        sample_kradfile,
    ):
        """Semantic component is first in parts, phonetic is last."""
        from kanji_mnemonic.cli import cmd_decompose

        args = argparse.Namespace(
            kanji="語",
            parts=["口"],
            phonetic="吾",
            semantic="言",
            remove=False,
        )
        cmd_decompose(
            args,
            sample_kanji_db,
            sample_phonetic_db,
            sample_wk_kanji_db,
            sample_wk_radicals,
            sample_wk_kanji_subjects,
            sample_kradfile,
            None,
            {},
            {},
        )
        data = json.loads(
            (config_dir / "decompositions.json").read_text(encoding="utf-8")
        )
        parts = data["語"]["parts"]
        assert parts[0] == "言"  # semantic first
        assert parts[-1] == "吾"  # phonetic last


# ---------------------------------------------------------------------------
# Tests: CLI dispatch for decompose command
# ---------------------------------------------------------------------------


class TestDecomposeCommandDispatch:
    """Tests for main() routing to decompose command."""

    def _setup_mocks(self, monkeypatch):
        mock_data = ({}, {}, {}, {}, {}, {}, {}, {}, {})
        monkeypatch.setattr("kanji_mnemonic.cli.get_wk_api_key", lambda: None)
        monkeypatch.setattr("kanji_mnemonic.cli.load_all_data", lambda key: mock_data)

    def test_decompose_command(self, monkeypatch, config_dir):
        from kanji_mnemonic.cli import main

        self._setup_mocks(monkeypatch)
        mock_cmd = MagicMock()
        monkeypatch.setattr("kanji_mnemonic.cli.cmd_decompose", mock_cmd)
        monkeypatch.setattr("sys.argv", ["kanji", "decompose", "語", "言", "吾"])
        main()
        mock_cmd.assert_called_once()
        args = mock_cmd.call_args[0][0]
        assert args.kanji == "語"
        assert args.parts == ["言", "吾"]

    def test_decompose_alias_d(self, monkeypatch, config_dir):
        from kanji_mnemonic.cli import main

        self._setup_mocks(monkeypatch)
        mock_cmd = MagicMock()
        monkeypatch.setattr("kanji_mnemonic.cli.cmd_decompose", mock_cmd)
        monkeypatch.setattr("sys.argv", ["kanji", "d", "語", "言", "吾"])
        main()
        mock_cmd.assert_called_once()

    def test_decompose_with_flags(self, monkeypatch, config_dir):
        from kanji_mnemonic.cli import main

        self._setup_mocks(monkeypatch)
        mock_cmd = MagicMock()
        monkeypatch.setattr("kanji_mnemonic.cli.cmd_decompose", mock_cmd)
        monkeypatch.setattr(
            "sys.argv", ["kanji", "decompose", "語", "-s", "言", "-p", "吾"]
        )
        main()
        mock_cmd.assert_called_once()
        args = mock_cmd.call_args[0][0]
        assert args.phonetic == "吾"
        assert args.semantic == "言"

    def test_decompose_with_remove(self, monkeypatch, config_dir):
        from kanji_mnemonic.cli import main

        self._setup_mocks(monkeypatch)
        mock_cmd = MagicMock()
        monkeypatch.setattr("kanji_mnemonic.cli.cmd_decompose", mock_cmd)
        monkeypatch.setattr("sys.argv", ["kanji", "decompose", "語", "--remove"])
        main()
        mock_cmd.assert_called_once()
        args = mock_cmd.call_args[0][0]
        assert args.remove is True


# ---------------------------------------------------------------------------
# Tests: --all-decomp flag on lookup
# ---------------------------------------------------------------------------


class TestAllDecompFlag:
    """Tests for --all-decomp flag on kanji lookup."""

    def _setup_mocks(self, monkeypatch):
        mock_data = ({}, {}, {}, {}, {}, {}, {}, {}, {})
        monkeypatch.setattr("kanji_mnemonic.cli.get_wk_api_key", lambda: None)
        monkeypatch.setattr("kanji_mnemonic.cli.load_all_data", lambda key: mock_data)

    def test_all_decomp_parsed(self, monkeypatch, config_dir):
        """--all-decomp flag is correctly parsed for lookup command."""
        from kanji_mnemonic.cli import main

        self._setup_mocks(monkeypatch)
        mock_cmd = MagicMock()
        monkeypatch.setattr("kanji_mnemonic.cli.cmd_lookup", mock_cmd)
        monkeypatch.setattr("sys.argv", ["kanji", "lookup", "語", "--all-decomp"])
        main()
        mock_cmd.assert_called_once()
        args = mock_cmd.call_args[0][0]
        assert args.all_decomp is True

    def test_no_all_decomp_defaults_false(self, monkeypatch, config_dir):
        """Without --all-decomp, all_decomp is False."""
        from kanji_mnemonic.cli import main

        self._setup_mocks(monkeypatch)
        mock_cmd = MagicMock()
        monkeypatch.setattr("kanji_mnemonic.cli.cmd_lookup", mock_cmd)
        monkeypatch.setattr("sys.argv", ["kanji", "lookup", "語"])
        main()
        args = mock_cmd.call_args[0][0]
        assert args.all_decomp is False
