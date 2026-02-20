"""Comprehensive tests for kanji_mnemonic.lookup module."""

from kanji_mnemonic.lookup import (
    KanjiProfile,
    _find_name,
    _infer_phonetic_semantic,
    format_profile,
    lookup_kanji,
)


# ---------------------------------------------------------------------------
# TestKanjiProfileDefaults
# ---------------------------------------------------------------------------


class TestKanjiProfileDefaults:
    def test_required_character(self):
        """KanjiProfile can be created with only the required 'character' field."""
        profile = KanjiProfile(character="語")
        assert profile.character == "語"

    def test_default_values(self):
        """All optional fields have their expected default values."""
        profile = KanjiProfile(character="X")
        assert profile.wk_meaning is None
        assert profile.wk_level is None
        assert profile.onyomi == []
        assert profile.kunyomi == []
        assert profile.important_reading is None
        assert profile.keisei_type is None
        assert profile.semantic_component is None
        assert profile.phonetic_component is None
        assert profile.decomposition == []
        assert profile.wk_components == []
        assert profile.phonetic_family is None
        assert profile.phonetic_family_kanji_details == []


# ---------------------------------------------------------------------------
# TestLookupKanjiWkData
# ---------------------------------------------------------------------------


class TestLookupKanjiWkData:
    def test_wk_kanji_db_fills_meaning_readings(
        self,
        sample_kanji_db,
        sample_phonetic_db,
        sample_wk_kanji_db,
        sample_wk_radicals,
        sample_wk_kanji_subjects,
        sample_kradfile,
    ):
        """Lookup of 語 populates meaning, onyomi, kunyomi, and important_reading from wk_kanji_db."""
        profile = lookup_kanji(
            "語",
            sample_kanji_db,
            sample_phonetic_db,
            sample_wk_kanji_db,
            sample_wk_radicals,
            sample_wk_kanji_subjects,
            sample_kradfile,
        )
        assert profile.wk_meaning == "Language"
        assert profile.onyomi == ["ゴ"]
        assert profile.kunyomi == ["かた.る"]
        assert profile.important_reading == "onyomi"

    def test_wk_subjects_supplements_missing(
        self,
        sample_kanji_db,
        sample_phonetic_db,
        sample_wk_radicals,
        sample_wk_kanji_subjects,
    ):
        """When wk_kanji_db is empty, meaning and readings come from wk_kanji_subjects."""
        profile = lookup_kanji(
            "語",
            sample_kanji_db,
            sample_phonetic_db,
            {},  # empty wk_kanji_db
            sample_wk_radicals,
            sample_wk_kanji_subjects,
        )
        assert profile.wk_meaning == "Language"
        assert profile.onyomi == ["ゴ"]
        assert profile.kunyomi == ["かた.る"]

    def test_wk_subjects_component_radicals_resolved(
        self,
        sample_kanji_db,
        sample_phonetic_db,
        sample_wk_kanji_db,
        sample_wk_radicals,
        sample_wk_kanji_subjects,
    ):
        """Component radicals for 語 are resolved to char/name dicts from wk_radicals."""
        profile = lookup_kanji(
            "語",
            sample_kanji_db,
            sample_phonetic_db,
            sample_wk_kanji_db,
            sample_wk_radicals,
            sample_wk_kanji_subjects,
        )
        component_map = {c["char"]: c["name"] for c in profile.wk_components}
        assert component_map["言"] == "Say"
        assert component_map["吾"] == "Five Mouths"

    def test_wk_subjects_unknown_radical(
        self,
        sample_kanji_db,
        sample_phonetic_db,
        sample_wk_kanji_db,
        sample_wk_radicals,
    ):
        """A component radical char not in wk_radicals appears with name=None."""
        wk_subjects = {
            "語": {
                "meanings": ["Language"],
                "readings": {"onyomi": ["ゴ"], "kunyomi": []},
                "component_radicals": ["言", "???"],
                "level": 5,
            },
        }
        profile = lookup_kanji(
            "語",
            sample_kanji_db,
            sample_phonetic_db,
            sample_wk_kanji_db,
            sample_wk_radicals,
            wk_subjects,
        )
        unknown_entries = [c for c in profile.wk_components if c["char"] == "???"]
        assert len(unknown_entries) == 1
        assert unknown_entries[0]["name"] is None


# ---------------------------------------------------------------------------
# TestLookupKanjiKeisei
# ---------------------------------------------------------------------------


class TestLookupKanjiKeisei:
    def test_keisei_type_set(
        self,
        sample_kanji_db,
        sample_phonetic_db,
        sample_wk_kanji_db,
        sample_wk_radicals,
        sample_wk_kanji_subjects,
    ):
        """語 gets keisei_type='comp_phonetic' from kanji_db."""
        profile = lookup_kanji(
            "語",
            sample_kanji_db,
            sample_phonetic_db,
            sample_wk_kanji_db,
            sample_wk_radicals,
            sample_wk_kanji_subjects,
        )
        assert profile.keisei_type == "comp_phonetic"

    def test_semantic_phonetic_set(
        self,
        sample_kanji_db,
        sample_phonetic_db,
        sample_wk_kanji_db,
        sample_wk_radicals,
        sample_wk_kanji_subjects,
    ):
        """語 gets semantic_component='言' and phonetic_component='吾'."""
        profile = lookup_kanji(
            "語",
            sample_kanji_db,
            sample_phonetic_db,
            sample_wk_kanji_db,
            sample_wk_radicals,
            sample_wk_kanji_subjects,
        )
        assert profile.semantic_component == "言"
        assert profile.phonetic_component == "吾"

    def test_hieroglyph_type(
        self,
        sample_kanji_db,
        sample_phonetic_db,
        sample_wk_kanji_db,
        sample_wk_radicals,
        sample_wk_kanji_subjects,
    ):
        """山 is classified as hieroglyph with no semantic or phonetic component."""
        profile = lookup_kanji(
            "山",
            sample_kanji_db,
            sample_phonetic_db,
            sample_wk_kanji_db,
            sample_wk_radicals,
            sample_wk_kanji_subjects,
        )
        assert profile.keisei_type == "hieroglyph"
        assert profile.semantic_component is None
        assert profile.phonetic_component is None

    def test_keisei_readings_fallback(
        self,
        sample_phonetic_db,
        sample_wk_radicals,
    ):
        """When a kanji is in kanji_db with readings but not in wk_kanji_db, onyomi comes from keisei readings."""
        kanji_db = {
            "偽": {
                "type": "comp_phonetic",
                "semantic": "亻",
                "phonetic": "為",
                "decomposition": ["亻", "為"],
                "readings": ["ギ"],
            },
        }
        profile = lookup_kanji(
            "偽",
            kanji_db,
            sample_phonetic_db,
            {},  # empty wk_kanji_db
            sample_wk_radicals,
        )
        assert profile.onyomi == ["ギ"]


# ---------------------------------------------------------------------------
# TestLookupKanjiPhoneticFamily
# ---------------------------------------------------------------------------


class TestLookupKanjiPhoneticFamily:
    def test_phonetic_family_populated(
        self,
        sample_kanji_db,
        sample_phonetic_db,
        sample_wk_kanji_db,
        sample_wk_radicals,
        sample_wk_kanji_subjects,
    ):
        """語's phonetic_family has correct phonetic_char, readings, wk_radical_name, and compounds."""
        profile = lookup_kanji(
            "語",
            sample_kanji_db,
            sample_phonetic_db,
            sample_wk_kanji_db,
            sample_wk_radicals,
            sample_wk_kanji_subjects,
        )
        pf = profile.phonetic_family
        assert pf is not None
        assert pf["phonetic_char"] == "吾"
        assert pf["readings"] == ["ゴ"]
        assert pf["wk_radical_name"] == "five-mouths"
        assert pf["compounds"] == ["語", "悟", "誤"]

    def test_phonetic_family_compounds_enriched(
        self,
        sample_kanji_db,
        sample_phonetic_db,
        sample_wk_kanji_db,
        sample_wk_radicals,
        sample_wk_kanji_subjects,
    ):
        """phonetic_family_kanji_details has enriched entries for 悟 and 誤 from wk_kanji_db."""
        profile = lookup_kanji(
            "語",
            sample_kanji_db,
            sample_phonetic_db,
            sample_wk_kanji_db,
            sample_wk_radicals,
            sample_wk_kanji_subjects,
        )
        details_map = {e["char"]: e for e in profile.phonetic_family_kanji_details}
        assert "悟" in details_map
        assert details_map["悟"]["meaning"] == "Enlightenment"
        assert details_map["悟"]["onyomi"] == "ゴ"
        assert "誤" in details_map
        assert details_map["誤"]["meaning"] == "Mistake"

    def test_phonetic_not_in_phonetic_db(
        self,
        sample_phonetic_db,
        sample_wk_radicals,
    ):
        """When the phonetic component exists but is not in phonetic_db, a minimal phonetic_family is created."""
        kanji_db = {
            "鋼": {
                "type": "comp_phonetic",
                "semantic": "金",
                "phonetic": "岡",
                "decomposition": ["金", "岡"],
                "readings": ["コウ"],
            },
        }
        profile = lookup_kanji(
            "鋼",
            kanji_db,
            sample_phonetic_db,  # does not contain "岡"
            {},
            sample_wk_radicals,
        )
        pf = profile.phonetic_family
        assert pf is not None
        assert pf["phonetic_char"] == "岡"
        assert pf["compounds"] == []
        assert pf["readings"] == ["コウ"]

    def test_no_phonetic_component(self, sample_profile_hieroglyph):
        """山 (hieroglyph) has no phonetic_family."""
        assert sample_profile_hieroglyph.phonetic_family is None


# ---------------------------------------------------------------------------
# TestLookupKanjiKradfileFallback
# ---------------------------------------------------------------------------


class TestLookupKanjiKradfileFallback:
    def test_kradfile_used_when_no_keisei(
        self,
        sample_phonetic_db,
        sample_wk_radicals,
        sample_kradfile,
    ):
        """蝶 is not in kanji_db; decomposition comes from kradfile."""
        profile = lookup_kanji(
            "蝶",
            {},  # empty kanji_db
            sample_phonetic_db,
            {},
            sample_wk_radicals,
            kradfile=sample_kradfile,
        )
        assert profile.decomposition == ["虫", "木", "世"]

    def test_kradfile_component_names_resolved(
        self,
        sample_phonetic_db,
        sample_wk_radicals,
        sample_kradfile,
    ):
        """蝶's kradfile components get WK names: 虫->Insect, 木->Tree, 世->None."""
        profile = lookup_kanji(
            "蝶",
            {},
            sample_phonetic_db,
            {},
            sample_wk_radicals,
            kradfile=sample_kradfile,
        )
        component_map = {c["char"]: c["name"] for c in profile.wk_components}
        assert component_map["虫"] == "Insect"
        assert component_map["木"] == "Tree"
        assert component_map["世"] is None

    def test_kradfile_not_used_when_keisei_exists(
        self,
        sample_kanji_db,
        sample_phonetic_db,
        sample_wk_kanji_db,
        sample_wk_radicals,
        sample_wk_kanji_subjects,
        sample_kradfile,
    ):
        """語 is in both kanji_db and kradfile; decomposition comes from kanji_db, not kradfile."""
        profile = lookup_kanji(
            "語",
            sample_kanji_db,
            sample_phonetic_db,
            sample_wk_kanji_db,
            sample_wk_radicals,
            sample_wk_kanji_subjects,
            sample_kradfile,
        )
        # kanji_db has ["言", "吾"], kradfile has ["言", "五", "口"]
        assert profile.decomposition == ["言", "吾"]


# ---------------------------------------------------------------------------
# TestInferPhoneticSemantic
# ---------------------------------------------------------------------------


class TestInferPhoneticSemantic:
    def test_compound_match(self, sample_phonetic_db):
        """Character found in phonetic_db compounds -> keisei_type='comp_phonetic'."""
        profile = KanjiProfile(character="語", onyomi=["ゴ"])
        components = ["言", "吾"]
        _infer_phonetic_semantic(profile, components, sample_phonetic_db)
        assert profile.keisei_type == "comp_phonetic"
        assert profile.phonetic_component == "吾"

    def test_reading_overlap(self, sample_phonetic_db):
        """Character NOT in compounds but onyomi overlaps family readings -> 'comp_phonetic_inferred'."""
        # Create a phonetic_db entry where our target is NOT in compounds
        phonetic_db = {
            "吾": {
                "readings": ["ゴ"],
                "compounds": ["悟", "誤"],  # 語 intentionally omitted
                "non_compounds": [],
            },
        }
        profile = KanjiProfile(character="語", onyomi=["ゴ"])
        components = ["言", "吾"]
        _infer_phonetic_semantic(profile, components, phonetic_db)
        assert profile.keisei_type == "comp_phonetic_inferred"
        assert profile.phonetic_component == "吾"

    def test_no_evidence(self):
        """Not in compounds and readings don't overlap -> keisei_type stays None."""
        phonetic_db = {
            "吾": {
                "readings": ["ゴ"],
                "compounds": ["悟"],
                "non_compounds": [],
            },
        }
        profile = KanjiProfile(character="X", onyomi=["カ"])
        components = ["言", "吾"]
        _infer_phonetic_semantic(profile, components, phonetic_db)
        assert profile.keisei_type is None
        assert profile.phonetic_component is None

    def test_no_onyomi_no_inference(self):
        """Profile has no onyomi and is not in compounds -> no inference made."""
        phonetic_db = {
            "吾": {
                "readings": ["ゴ"],
                "compounds": ["悟"],
                "non_compounds": [],
            },
        }
        profile = KanjiProfile(character="X")  # no onyomi
        components = ["言", "吾"]
        _infer_phonetic_semantic(profile, components, phonetic_db)
        assert profile.keisei_type is None
        assert profile.phonetic_component is None
        assert profile.semantic_component is None

    def test_semantic_from_remaining(self, sample_phonetic_db):
        """After inference, remaining components[0] becomes the semantic_component."""
        profile = KanjiProfile(character="語", onyomi=["ゴ"])
        components = ["言", "吾"]
        _infer_phonetic_semantic(profile, components, sample_phonetic_db)
        # 吾 is phonetic, so remaining is ["言"] -> semantic = "言"
        assert profile.semantic_component == "言"


# ---------------------------------------------------------------------------
# TestComponentDeduplication
# ---------------------------------------------------------------------------


class TestComponentDeduplication:
    def test_no_duplicate_wk_components(
        self,
        sample_kanji_db,
        sample_phonetic_db,
        sample_wk_kanji_db,
        sample_wk_radicals,
        sample_wk_kanji_subjects,
        sample_kradfile,
    ):
        """For 語, no character appears more than once in wk_components despite multiple sources."""
        profile = lookup_kanji(
            "語",
            sample_kanji_db,
            sample_phonetic_db,
            sample_wk_kanji_db,
            sample_wk_radicals,
            sample_wk_kanji_subjects,
            sample_kradfile,
        )
        chars = [c["char"] for c in profile.wk_components]
        assert len(chars) == len(set(chars)), f"Duplicate chars in wk_components: {chars}"


# ---------------------------------------------------------------------------
# TestFormatProfile
# ---------------------------------------------------------------------------


class TestFormatProfile:
    def test_minimal_profile(self):
        """A profile with only character set outputs the header line."""
        profile = KanjiProfile(character="X")
        output = format_profile(profile)
        assert output.startswith("═══ X ═══")

    def test_full_wk_info(self):
        """All WK fields set produce corresponding lines in the output."""
        profile = KanjiProfile(
            character="語",
            wk_meaning="Language",
            wk_level=5,
            onyomi=["ゴ"],
            kunyomi=["かた.る"],
            important_reading="onyomi",
        )
        output = format_profile(profile)
        assert "Meaning: Language" in output
        assert "WaniKani Level: 5" in output
        assert "On'yomi: ゴ" in output
        assert "Kun'yomi: かた.る" in output
        assert "Important reading: onyomi" in output

    def test_comp_phonetic_shows_breakdown(self, sample_profile_phonetic):
        """Phonetic-semantic profile output contains the breakdown section."""
        output = format_profile(sample_profile_phonetic)
        assert "Phonetic-Semantic Breakdown" in output
        assert "Semantic (meaning hint)" in output
        assert "Phonetic (reading hint)" in output

    def test_inferred_label(self):
        """keisei_type='comp_phonetic_inferred' shows '[inferred from KRADFILE]' in the output."""
        profile = KanjiProfile(
            character="X",
            keisei_type="comp_phonetic_inferred",
            semantic_component="A",
            phonetic_component="B",
            wk_components=[
                {"char": "A", "name": "Alpha"},
                {"char": "B", "name": "Beta"},
            ],
        )
        output = format_profile(profile)
        assert "[inferred from KRADFILE]" in output

    def test_non_phonetic_shows_decomposition(self, sample_profile_hieroglyph):
        """Hieroglyph profile shows Decomposition but not Phonetic-Semantic Breakdown."""
        output = format_profile(sample_profile_hieroglyph)
        assert "Decomposition:" in output
        assert "Phonetic-Semantic Breakdown" not in output

    def test_phonetic_family_section(self, sample_profile_phonetic):
        """Profile with phonetic_family shows the Phonetic Family section."""
        output = format_profile(sample_profile_phonetic)
        assert "Phonetic Family" in output
        assert "Family readings:" in output
        # Should show other compounds (悟 and 誤), but not 語 itself
        assert "悟" in output
        assert "誤" in output

    def test_non_compounds_warning(self):
        """phonetic_family with non_compounds shows the warning character."""
        profile = KanjiProfile(
            character="語",
            phonetic_family={
                "phonetic_char": "吾",
                "readings": ["ゴ"],
                "wk_radical_name": "five-mouths",
                "compounds": [],
                "non_compounds": ["唔"],
                "xrefs": [],
            },
        )
        output = format_profile(profile)
        assert "\u26a0" in output  # ⚠ character
        assert "唔" in output

    def test_no_wk_name_placeholder(self):
        """A component with name=None renders as '(no WK name)' in the output."""
        profile = KanjiProfile(
            character="X",
            wk_components=[{"char": "世", "name": None}],
        )
        output = format_profile(profile)
        assert "kanji name 世" in output
        assert "世" in output


# ---------------------------------------------------------------------------
# TestFindName
# ---------------------------------------------------------------------------


class TestFindName:
    def test_found(self):
        """Returns the component name when char is present."""
        components = [{"char": "言", "name": "Say"}]
        assert _find_name("言", components) == "Say"

    def test_not_found(self):
        """Returns hint message when char is not in components."""
        components = [{"char": "言", "name": "Say"}]
        assert _find_name("X", components) == "(no name — use kanji name X <name> to add one)"

    def test_none_name(self):
        """Returns hint message when component has name=None."""
        components = [{"char": "世", "name": None}]
        assert _find_name("世", components) == "(no name — use kanji name 世 <name> to add one)"
