"""Tests for kanji_mnemonic.prompt — system prompt and user message assembly."""

from kanji_mnemonic.lookup import KanjiProfile
from kanji_mnemonic.prompt import build_prompt, get_system_prompt


class TestGetSystemPrompt:
    """Tests for get_system_prompt()."""

    def test_returns_non_empty_string(self):
        result = get_system_prompt()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_contains_key_sections(self):
        result = get_system_prompt()
        lower = result.lower()
        assert "meaning mnemonics" in lower
        assert "reading mnemonics" in lower
        assert "phonetic-semantic compounds" in lower

    def test_stable_output(self):
        first = get_system_prompt()
        second = get_system_prompt()
        assert first == second


class TestBuildPrompt:
    """Tests for build_prompt()."""

    def test_includes_formatted_profile(self, sample_profile_phonetic):
        result = build_prompt(sample_profile_phonetic)
        assert "\u2550\u2550\u2550 \u8a9e \u2550\u2550\u2550" in result

    def test_includes_generation_instructions(self, sample_profile_phonetic):
        result = build_prompt(sample_profile_phonetic)
        assert "Meaning mnemonic" in result
        assert "Reading mnemonic" in result

    def test_without_user_context(self, sample_profile_phonetic):
        result = build_prompt(sample_profile_phonetic, user_context=None)
        assert "Additional context" not in result

    def test_with_user_context(self, sample_profile_phonetic):
        context_text = "I confuse this with \u8a71"
        result = build_prompt(sample_profile_phonetic, user_context=context_text)
        assert "Additional context from user" in result
        assert context_text in result

    def test_comp_phonetic_includes_phonetic_note(self, sample_profile_phonetic):
        # sample_profile_phonetic has keisei_type="comp_phonetic" and a phonetic_family
        assert sample_profile_phonetic.keisei_type == "comp_phonetic"
        assert sample_profile_phonetic.phonetic_family is not None
        result = build_prompt(sample_profile_phonetic)
        assert "Phonetic family note" in result

    def test_comp_phonetic_inferred_includes_note(self):
        profile = KanjiProfile(
            character="\u8776",
            keisei_type="comp_phonetic_inferred",
            phonetic_component="\u4e16",
            semantic_component="\u866b",
            phonetic_family={
                "phonetic_char": "\u4e16",
                "readings": ["\u30bb\u30a4"],
                "wk_radical_name": None,
                "compounds": ["\u8776"],
                "non_compounds": [],
                "xrefs": [],
            },
        )
        result = build_prompt(profile)
        assert "Phonetic family note" in result

    def test_hieroglyph_skips_phonetic_note(self, sample_profile_hieroglyph):
        # sample_profile_hieroglyph has keisei_type="hieroglyph" and no phonetic_family
        assert sample_profile_hieroglyph.keisei_type == "hieroglyph"
        result = build_prompt(sample_profile_hieroglyph)
        assert "Phonetic family note" not in result

    def test_no_keisei_type_skips_note(self):
        profile = KanjiProfile(
            character="\u9f8d",
            keisei_type=None,
        )
        result = build_prompt(profile)
        assert "Phonetic family note" not in result

    def test_comp_phonetic_without_family_skips_note(self):
        profile = KanjiProfile(
            character="\u8a9e",
            keisei_type="comp_phonetic",
            phonetic_family=None,
        )
        result = build_prompt(profile)
        assert "Phonetic family note" not in result
