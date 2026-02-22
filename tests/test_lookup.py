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
        assert profile.joyo_grade is None
        assert profile.frequency_rank is None


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
# TestUnprocessedKeiseiType
# ---------------------------------------------------------------------------


class TestUnprocessedKeiseiType:
    """Tests for kanji with 'unprocessed' Keisei type (bd-2vf).

    Kanji like 辻 have type='unprocessed' in the Keisei DB. This should
    be treated as if no Keisei entry exists, falling through to KRADFILE-u
    for decomposition and component resolution.
    """

    def test_unprocessed_falls_through_to_kradfile(
        self,
        sample_phonetic_db,
        sample_wk_radicals,
    ):
        """Kanji with 'unprocessed' Keisei type gets decomposition from KRADFILE-u."""
        kanji_db = {
            "辻": {
                "type": "unprocessed",
                "semantic": None,
                "phonetic": None,
                "decomposition": [],
                "readings": [],
            },
        }
        kradfile = {"辻": ["辶", "十"]}
        profile = lookup_kanji(
            "辻",
            kanji_db,
            sample_phonetic_db,
            {},
            sample_wk_radicals,
            kradfile=kradfile,
        )
        assert profile.decomposition == ["辶", "十"]

    def test_unprocessed_does_not_set_keisei_type(
        self,
        sample_phonetic_db,
        sample_wk_radicals,
    ):
        """Kanji with 'unprocessed' Keisei type should not have keisei_type set."""
        kanji_db = {
            "辻": {
                "type": "unprocessed",
                "semantic": None,
                "phonetic": None,
                "decomposition": [],
                "readings": [],
            },
        }
        kradfile = {"辻": ["辶", "十"]}
        profile = lookup_kanji(
            "辻",
            kanji_db,
            sample_phonetic_db,
            {},
            sample_wk_radicals,
            kradfile=kradfile,
        )
        assert profile.keisei_type is None

    def test_unprocessed_does_not_display_raw_type(
        self,
        sample_phonetic_db,
        sample_wk_radicals,
    ):
        """format_profile() should not show 'Type: unprocessed' for unprocessed kanji."""
        kanji_db = {
            "辻": {
                "type": "unprocessed",
                "semantic": None,
                "phonetic": None,
                "decomposition": [],
                "readings": [],
            },
        }
        kradfile = {"辻": ["辶", "十"]}
        profile = lookup_kanji(
            "辻",
            kanji_db,
            sample_phonetic_db,
            {},
            sample_wk_radicals,
            kradfile=kradfile,
        )
        output = format_profile(profile)
        assert "unprocessed" not in output.lower()

    def test_unprocessed_resolves_kradfile_component_names(
        self,
        sample_phonetic_db,
    ):
        """Components from KRADFILE-u are resolved to WK radical names."""
        kanji_db = {
            "辻": {
                "type": "unprocessed",
                "semantic": None,
                "phonetic": None,
                "decomposition": [],
                "readings": [],
            },
        }
        wk_radicals = {
            "辶": {"name": "Scooter", "level": 3, "slug": "scooter"},
            "十": {"name": "Cross", "level": 1, "slug": "cross"},
        }
        kradfile = {"辻": ["辶", "十"]}
        profile = lookup_kanji(
            "辻",
            kanji_db,
            sample_phonetic_db,
            {},
            wk_radicals,
            kradfile=kradfile,
        )
        component_map = {c["char"]: c["name"] for c in profile.wk_components}
        assert component_map["辶"] == "Scooter"
        assert component_map["十"] == "Cross"

    def test_unprocessed_shows_decomposition_in_output(
        self,
        sample_phonetic_db,
        sample_wk_radicals,
    ):
        """format_profile() shows the KRADFILE decomposition for 'unprocessed' kanji."""
        kanji_db = {
            "辻": {
                "type": "unprocessed",
                "semantic": None,
                "phonetic": None,
                "decomposition": [],
                "readings": [],
            },
        }
        kradfile = {"辻": ["辶", "十"]}
        profile = lookup_kanji(
            "辻",
            kanji_db,
            sample_phonetic_db,
            {},
            sample_wk_radicals,
            kradfile=kradfile,
        )
        output = format_profile(profile)
        assert "Decomposition:" in output
        assert "辶" in output
        assert "十" in output


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
        assert len(chars) == len(set(chars)), (
            f"Duplicate chars in wk_components: {chars}"
        )


# ---------------------------------------------------------------------------
# TestKradfileSubsetInference
# ---------------------------------------------------------------------------


class TestKradfileSubsetInference:
    """Tests for KRADFILE subset-based phonetic inference.

    When a kanji's KRADFILE decomposition contains another kanji's
    decomposition as a proper subset AND they share an on'yomi reading,
    the subset kanji is likely the phonetic component.
    """

    def test_detects_phonetic_from_kradfile_subset(self):
        """槌 [｜,口,辶,木] contains 追 [｜,口,辶] with shared reading つい."""
        profile = lookup_kanji(
            "槌",
            {},  # empty kanji_db
            {},  # empty phonetic_db
            {},  # empty wk_kanji_db
            {},  # empty wk_radicals
            None,  # no wk_kanji_subjects
            kradfile={
                "槌": ["｜", "口", "辶", "木"],
                "追": ["｜", "口", "辶"],
            },
            kanjidic={
                "槌": {"meanings": ["hammer"], "onyomi": ["つい"], "kunyomi": []},
                "追": {"meanings": ["chase"], "onyomi": ["つい"], "kunyomi": []},
            },
        )
        assert profile.keisei_type == "comp_phonetic_inferred"
        assert profile.phonetic_component == "追"
        assert profile.semantic_component == "木"

    def test_no_inference_without_reading_overlap(self):
        """Subset exists but readings don't overlap — no inference."""
        profile = lookup_kanji(
            "槌",
            {},
            {},
            {},
            {},
            None,
            kradfile={
                "槌": ["｜", "口", "辶", "木"],
                "追": ["｜", "口", "辶"],
            },
            kanjidic={
                "槌": {"meanings": ["hammer"], "onyomi": ["つい"], "kunyomi": []},
                "追": {"meanings": ["chase"], "onyomi": ["たい"], "kunyomi": []},
            },
        )
        assert profile.keisei_type is None
        assert profile.phonetic_component is None

    def test_prefers_largest_subset(self):
        """When multiple candidates match, pick the one with most components."""
        profile = lookup_kanji(
            "X",
            {},
            {},
            {},
            {},
            None,
            kradfile={
                "X": ["a", "b", "c", "d"],
                "Y": ["a", "b", "c"],  # 3 components — should win
                "Z": ["a", "b"],  # 2 components
            },
            kanjidic={
                "X": {"meanings": ["target"], "onyomi": ["か"], "kunyomi": []},
                "Y": {"meanings": ["bigger"], "onyomi": ["か"], "kunyomi": []},
                "Z": {"meanings": ["smaller"], "onyomi": ["か"], "kunyomi": []},
            },
        )
        assert profile.phonetic_component == "Y"

    def test_single_atom_subset_ignored(self):
        """Single-atom subsets should not trigger inference."""
        profile = lookup_kanji(
            "X",
            {},
            {},
            {},
            {},
            None,
            kradfile={
                "X": ["a", "b"],
                "Y": ["a"],  # single atom — should be ignored
            },
            kanjidic={
                "X": {"meanings": ["target"], "onyomi": ["か"], "kunyomi": []},
                "Y": {"meanings": ["single"], "onyomi": ["か"], "kunyomi": []},
            },
        )
        assert profile.keisei_type is None

    def test_no_inference_without_onyomi(self):
        """Target kanji has no onyomi — no inference possible."""
        profile = lookup_kanji(
            "X",
            {},
            {},
            {},
            {},
            None,
            kradfile={
                "X": ["a", "b", "c"],
                "Y": ["a", "b"],
            },
            kanjidic={
                "X": {"meanings": ["target"], "onyomi": [], "kunyomi": ["くん"]},
                "Y": {"meanings": ["cand"], "onyomi": ["か"], "kunyomi": []},
            },
        )
        assert profile.keisei_type is None

    def test_replaces_atoms_with_wk_subject_radicals(self):
        """After inference, KRADFILE atoms are replaced with WK subject radicals."""
        profile = lookup_kanji(
            "槌",
            {},
            {},
            {},
            {
                "⻌": {"name": "Scooter", "level": 5, "slug": "scooter"},
                "㠯": {"name": "Bear", "level": 11, "slug": "bear"},
                "丶": {"name": "Drop", "level": 1, "slug": "drop"},
                "木": {"name": "Tree", "level": 2, "slug": "tree"},
            },
            wk_kanji_subjects={
                "追": {
                    "meanings": ["Chase"],
                    "readings": {"onyomi": ["つい"], "kunyomi": []},
                    "component_radicals": ["⻌", "㠯", "丶"],
                    "level": 11,
                },
            },
            kradfile={
                "槌": ["｜", "口", "辶", "木"],
                "追": ["｜", "口", "辶"],
            },
            kanjidic={
                "槌": {"meanings": ["hammer"], "onyomi": ["つい"], "kunyomi": []},
                "追": {"meanings": ["chase"], "onyomi": ["つい"], "kunyomi": []},
            },
        )
        component_map = {c["char"]: c["name"] for c in profile.wk_components}
        assert "木" in component_map
        assert component_map["木"] == "Tree"
        assert "⻌" in component_map
        assert component_map["⻌"] == "Scooter"
        assert "㠯" in component_map
        assert component_map["㠯"] == "Bear"
        # Raw KRADFILE atoms should be gone
        assert "｜" not in component_map
        assert "辶" not in component_map

    def test_no_wk_subject_uses_kanji_meaning(self):
        """When phonetic component has no WK subject, use its meaning as name."""
        profile = lookup_kanji(
            "X",
            {},
            {},
            {},
            {},
            None,  # no wk_kanji_subjects
            kradfile={
                "X": ["a", "b", "c"],
                "Y": ["a", "b"],
            },
            kanjidic={
                "X": {"meanings": ["target"], "onyomi": ["か"], "kunyomi": []},
                "Y": {"meanings": ["source"], "onyomi": ["か"], "kunyomi": []},
            },
        )
        component_map = {c["char"]: c["name"] for c in profile.wk_components}
        # Y should appear with its kanjidic meaning
        assert "Y" in component_map
        assert component_map["Y"] == "source"

    def test_builds_synthetic_phonetic_family(self):
        """Synthetic family includes other kanji sharing the phonetic subset."""
        profile = lookup_kanji(
            "槌",
            {},
            {},
            {},
            {},
            None,
            kradfile={
                "槌": ["｜", "口", "辶", "木"],
                "追": ["｜", "口", "辶"],
                "椎": ["｜", "口", "辶", "木"],  # also contains 追's components
            },
            kanjidic={
                "槌": {"meanings": ["hammer"], "onyomi": ["つい"], "kunyomi": []},
                "追": {"meanings": ["chase"], "onyomi": ["つい"], "kunyomi": []},
                "椎": {
                    "meanings": ["chinquapin"],
                    "onyomi": ["つい"],
                    "kunyomi": [],
                },
            },
        )
        assert profile.phonetic_family is not None
        assert profile.phonetic_family["phonetic_char"] == "追"
        # 椎 should be in the synthetic family
        family_chars = [e["char"] for e in profile.phonetic_family_kanji_details]
        assert "椎" in family_chars

    def test_phonetic_db_inference_takes_priority(self, sample_phonetic_db):
        """When a KRADFILE atom is directly in phonetic_db, it wins over subset."""
        # 吾 is in phonetic_db AND is a direct KRADFILE atom of 語
        profile = lookup_kanji(
            "語",
            {},
            sample_phonetic_db,
            {},
            {},
            None,
            kradfile={
                "語": ["言", "吾"],  # 吾 is a direct atom AND in phonetic_db
            },
            kanjidic={
                "語": {"meanings": ["language"], "onyomi": ["ご"], "kunyomi": []},
            },
        )
        # Should use phonetic_db direct match (comp_phonetic)
        assert profile.keisei_type == "comp_phonetic"
        assert profile.phonetic_component == "吾"

    def test_detects_phonetic_from_kunyomi(self):
        """褄 [｜,ヨ,一,衤,女] contains 妻 [｜,ヨ,一,女] with shared kun'yomi つま."""
        profile = lookup_kanji(
            "褄",
            {},
            {},
            {},
            {},
            None,
            kradfile={
                "褄": ["｜", "ヨ", "一", "衤", "女"],
                "妻": ["｜", "ヨ", "一", "女"],
            },
            kanjidic={
                "褄": {
                    "meanings": ["skirt"],
                    "onyomi": [],
                    "kunyomi": ["つま"],
                },
                "妻": {
                    "meanings": ["wife"],
                    "onyomi": ["さい"],
                    "kunyomi": ["つま"],
                },
            },
        )
        assert profile.keisei_type == "comp_phonetic_inferred"
        assert profile.phonetic_component == "妻"
        assert profile.semantic_component == "衤"

    def test_phonetic_name_in_format_profile(self):
        """format_profile shows the phonetic component's meaning in breakdown."""
        profile = lookup_kanji(
            "槌",
            {},
            {},
            {},
            {"木": {"name": "Tree", "level": 2, "slug": "tree"}},
            None,
            kradfile={
                "槌": ["｜", "口", "辶", "木"],
                "追": ["｜", "口", "辶"],
            },
            kanjidic={
                "槌": {"meanings": ["hammer"], "onyomi": ["つい"], "kunyomi": []},
                "追": {"meanings": ["chase"], "onyomi": ["つい"], "kunyomi": []},
            },
        )
        output = format_profile(profile)
        assert "Phonetic (reading hint):  追 (chase)" in output
        assert "Semantic (meaning hint): 木 (Tree)" in output


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

    def test_joyo_grade_displayed(self):
        """Joyo grade appears in output when set."""
        profile = KanjiProfile(character="圧", joyo_grade=5)
        output = format_profile(profile)
        assert "Joyo Grade: 5" in output

    def test_frequency_rank_displayed(self):
        """Frequency rank appears in output when set."""
        profile = KanjiProfile(character="圧", frequency_rank=640)
        output = format_profile(profile)
        assert "Frequency Rank: 640" in output

    def test_no_grade_no_line(self):
        """No Joyo Grade line when joyo_grade is None."""
        profile = KanjiProfile(character="鬱")
        output = format_profile(profile)
        assert "Joyo Grade" not in output

    def test_no_frequency_no_line(self):
        """No Frequency Rank line when frequency_rank is None."""
        profile = KanjiProfile(character="鬱")
        output = format_profile(profile)
        assert "Frequency Rank" not in output


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
        assert (
            _find_name("X", components)
            == "(no name — use kanji name X <name> to add one)"
        )

    def test_none_name(self):
        """Returns hint message when component has name=None."""
        components = [{"char": "世", "name": None}]
        assert (
            _find_name("世", components)
            == "(no name — use kanji name 世 <name> to add one)"
        )


# ---------------------------------------------------------------------------
# TestTypeOnlyKeiseiWithKradfileFallback
# ---------------------------------------------------------------------------


class TestTypeOnlyKeiseiWithKradfileFallback:
    """Tests for kanji with a keisei type but no decomposition (bd-2jq).

    Kanji like 瓦 (hieroglyph) and 蓋 (unknown) have a keisei entry with a
    type classification but empty decomposition/components. KRADFILE should
    still be used for component breakdown in these cases.
    """

    def test_hieroglyph_preserves_keisei_type(
        self,
        sample_phonetic_db,
        sample_wk_radicals,
    ):
        """A hieroglyph with empty decomposition preserves its keisei_type."""
        kanji_db = {
            "瓦": {
                "type": "hieroglyph",
                "semantic": None,
                "phonetic": None,
                "decomposition": [],
                "readings": ["ガ"],
            },
        }
        kradfile = {"瓦": ["一", "瓦"]}
        profile = lookup_kanji(
            "瓦",
            kanji_db,
            sample_phonetic_db,
            {},
            sample_wk_radicals,
            kradfile=kradfile,
        )
        assert profile.keisei_type == "hieroglyph"

    def test_hieroglyph_gets_kradfile_decomposition(
        self,
        sample_phonetic_db,
        sample_wk_radicals,
    ):
        """A hieroglyph with empty keisei decomposition gets components from KRADFILE."""
        kanji_db = {
            "瓦": {
                "type": "hieroglyph",
                "semantic": None,
                "phonetic": None,
                "decomposition": [],
                "readings": ["ガ"],
            },
        }
        kradfile = {"瓦": ["一", "瓦"]}
        profile = lookup_kanji(
            "瓦",
            kanji_db,
            sample_phonetic_db,
            {},
            sample_wk_radicals,
            kradfile=kradfile,
        )
        assert profile.decomposition == ["一", "瓦"]

    def test_hieroglyph_resolves_component_names(
        self,
        sample_phonetic_db,
    ):
        """KRADFILE components for a type-only entry get WK radical names."""
        kanji_db = {
            "瓦": {
                "type": "hieroglyph",
                "semantic": None,
                "phonetic": None,
                "decomposition": [],
                "readings": ["ガ"],
            },
        }
        wk_radicals = {
            "一": {"name": "Ground", "level": 1, "slug": "ground"},
        }
        kradfile = {"瓦": ["一", "瓦"]}
        profile = lookup_kanji(
            "瓦",
            kanji_db,
            sample_phonetic_db,
            {},
            wk_radicals,
            kradfile=kradfile,
        )
        component_map = {c["char"]: c["name"] for c in profile.wk_components}
        assert component_map["一"] == "Ground"
        assert component_map["瓦"] is None  # not a WK radical

    def test_unknown_type_gets_kradfile_decomposition(
        self,
        sample_phonetic_db,
        sample_wk_radicals,
    ):
        """A kanji with type=unknown and empty decomposition gets KRADFILE components."""
        kanji_db = {
            "蓋": {
                "type": "unknown",
                "semantic": None,
                "phonetic": None,
                "decomposition": [],
                "readings": ["ガイ"],
            },
        }
        kradfile = {"蓋": ["艹", "去", "皿"]}
        profile = lookup_kanji(
            "蓋",
            kanji_db,
            sample_phonetic_db,
            {},
            sample_wk_radicals,
            kradfile=kradfile,
        )
        assert profile.keisei_type == "unknown"
        assert profile.decomposition == ["艹", "去", "皿"]

    def test_keisei_with_decomposition_not_overridden(
        self,
        sample_kanji_db,
        sample_phonetic_db,
        sample_wk_kanji_db,
        sample_wk_radicals,
        sample_wk_kanji_subjects,
        sample_kradfile,
    ):
        """When keisei provides both type AND decomposition, KRADFILE does not override."""
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

    def test_format_profile_shows_type_and_decomposition(
        self,
        sample_phonetic_db,
        sample_wk_radicals,
    ):
        """format_profile() shows both the keisei type and KRADFILE decomposition."""
        kanji_db = {
            "瓦": {
                "type": "hieroglyph",
                "semantic": None,
                "phonetic": None,
                "decomposition": [],
                "readings": ["ガ"],
            },
        }
        kradfile = {"瓦": ["一", "瓦"]}
        profile = lookup_kanji(
            "瓦",
            kanji_db,
            sample_phonetic_db,
            {},
            sample_wk_radicals,
            kradfile=kradfile,
        )
        output = format_profile(profile)
        assert "Hieroglyph" in output
        assert "Decomposition:" in output
        assert "一" in output
