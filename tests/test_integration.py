"""Integration tests: lookup_kanji -> format_profile -> build_prompt pipeline."""

from kanji_mnemonic.lookup import lookup_kanji, format_profile
from kanji_mnemonic.prompt import build_prompt, get_system_prompt


class TestPhoneticSemanticPipeline:
    """Pipeline tests for phonetic-semantic compound kanji (語)."""

    def test_full_pipeline_comp_phonetic(
        self,
        sample_kanji_db,
        sample_phonetic_db,
        sample_wk_kanji_db,
        sample_wk_radicals,
        sample_wk_kanji_subjects,
        sample_kradfile,
    ):
        """lookup_kanji -> format_profile -> build_prompt for 語 produces a complete prompt."""
        profile = lookup_kanji(
            "語",
            sample_kanji_db,
            sample_phonetic_db,
            sample_wk_kanji_db,
            sample_wk_radicals,
            sample_wk_kanji_subjects,
            sample_kradfile,
        )
        formatted = format_profile(profile)
        prompt = build_prompt(profile)

        # Profile header is present
        assert "═══ 語 ═══" in prompt
        # Prompt requests both mnemonic types
        assert "Meaning mnemonic" in prompt
        assert "Reading mnemonic" in prompt
        # Phonetic-semantic compounds get a phonetic family note request
        assert "Phonetic family note" in prompt
        # The WK meaning appears in the formatted profile section
        assert "Language" in prompt

    def test_phonetic_family_in_prompt(
        self,
        sample_kanji_db,
        sample_phonetic_db,
        sample_wk_kanji_db,
        sample_wk_radicals,
        sample_wk_kanji_subjects,
        sample_kradfile,
    ):
        """Prompt for 語 includes family members 悟 (Enlightenment) and 誤 (Mistake)."""
        profile = lookup_kanji(
            "語",
            sample_kanji_db,
            sample_phonetic_db,
            sample_wk_kanji_db,
            sample_wk_radicals,
            sample_wk_kanji_subjects,
            sample_kradfile,
        )
        prompt = build_prompt(profile)

        # Family members and their meanings should appear
        assert "悟" in prompt
        assert "Enlightenment" in prompt
        assert "誤" in prompt
        assert "Mistake" in prompt


class TestKradfileFallbackPipeline:
    """Pipeline tests for kanji only present in KRADFILE (蝶)."""

    def test_kradfile_only_kanji(
        self,
        sample_kanji_db,
        sample_phonetic_db,
        sample_wk_kanji_db,
        sample_wk_radicals,
        sample_wk_kanji_subjects,
        sample_kradfile,
    ):
        """Lookup 蝶 (not in kanji_db) completes and has decomposition from kradfile."""
        profile = lookup_kanji(
            "蝶",
            sample_kanji_db,
            sample_phonetic_db,
            sample_wk_kanji_db,
            sample_wk_radicals,
            sample_wk_kanji_subjects,
            sample_kradfile,
        )
        formatted = format_profile(profile)
        prompt = build_prompt(profile)

        # Pipeline completes without error and produces output
        assert "蝶" in prompt
        # Decomposition from kradfile is present on the profile
        assert profile.decomposition == ["虫", "木", "世"]

    def test_component_names_in_prompt(
        self,
        sample_kanji_db,
        sample_phonetic_db,
        sample_wk_kanji_db,
        sample_wk_radicals,
        sample_wk_kanji_subjects,
        sample_kradfile,
    ):
        """Prompt for 蝶 contains WK radical names 'Insect' (虫) and 'Tree' (木)."""
        profile = lookup_kanji(
            "蝶",
            sample_kanji_db,
            sample_phonetic_db,
            sample_wk_kanji_db,
            sample_wk_radicals,
            sample_wk_kanji_subjects,
            sample_kradfile,
        )
        prompt = build_prompt(profile)

        assert "Insect" in prompt
        assert "Tree" in prompt


class TestUnknownKanjiPipeline:
    """Pipeline tests for a kanji absent from all databases (龘)."""

    def test_unknown_kanji(
        self,
        sample_kanji_db,
        sample_phonetic_db,
        sample_wk_kanji_db,
        sample_wk_radicals,
        sample_wk_kanji_subjects,
        sample_kradfile,
    ):
        """Lookup 龘 (not in any database) completes with minimal profile."""
        profile = lookup_kanji(
            "龘",
            sample_kanji_db,
            sample_phonetic_db,
            sample_wk_kanji_db,
            sample_wk_radicals,
            sample_wk_kanji_subjects,
            sample_kradfile,
        )
        formatted = format_profile(profile)
        prompt = build_prompt(profile)

        # Pipeline completes and the character is present
        assert profile.character == "龘"
        assert "龘" in prompt
        # Minimal profile: no meaning, no keisei type
        assert profile.wk_meaning is None
        assert profile.keisei_type is None

    def test_empty_profile_prompt_structure(
        self,
        sample_kanji_db,
        sample_phonetic_db,
        sample_wk_kanji_db,
        sample_wk_radicals,
        sample_wk_kanji_subjects,
        sample_kradfile,
    ):
        """Prompt for 龘 still contains the essential mnemonic generation instructions."""
        profile = lookup_kanji(
            "龘",
            sample_kanji_db,
            sample_phonetic_db,
            sample_wk_kanji_db,
            sample_wk_radicals,
            sample_wk_kanji_subjects,
            sample_kradfile,
        )
        prompt = build_prompt(profile)

        assert "Generate a mnemonic" in prompt
        assert "Meaning mnemonic" in prompt
        assert "Reading mnemonic" in prompt


class TestFormatProfileEmbedding:
    """Verify that the formatted profile is embedded verbatim in the prompt."""

    def test_format_profile_is_substring_of_prompt(self, sample_profile_phonetic):
        """For 語, format_profile(profile) appears as a substring of build_prompt(profile)."""
        formatted = format_profile(sample_profile_phonetic)
        prompt = build_prompt(sample_profile_phonetic)

        assert formatted in prompt
