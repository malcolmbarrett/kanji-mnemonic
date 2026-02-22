"""Shared fixtures for kanji-mnemonic test suite."""

import pytest


@pytest.fixture
def tmp_cache_dir(tmp_path, monkeypatch):
    """Redirect CACHE_DIR to a temp directory for all data.py operations."""
    monkeypatch.setattr("kanji_mnemonic.data.CACHE_DIR", tmp_path)
    return tmp_path


@pytest.fixture
def sample_kanji_db():
    """Minimal Keisei kanji_db with comp_phonetic and hieroglyph entries."""
    return {
        "語": {
            "type": "comp_phonetic",
            "semantic": "言",
            "phonetic": "吾",
            "decomposition": ["言", "吾"],
            "readings": ["ゴ"],
        },
        "山": {
            "type": "hieroglyph",
            "semantic": None,
            "phonetic": None,
            "decomposition": ["山"],
            "readings": ["サン"],
        },
        "話": {
            "type": "comp_phonetic",
            "semantic": "言",
            "phonetic": "舌",
            "decomposition": ["言", "舌"],
            "readings": ["ワ"],
        },
    }


@pytest.fixture
def sample_phonetic_db():
    """Phonetic families matching sample_kanji_db entries."""
    return {
        "吾": {
            "readings": ["ゴ"],
            "wk-radical": "five-mouths",
            "compounds": ["語", "悟", "誤"],
            "non_compounds": ["唔"],
            "xrefs": [],
        },
        "舌": {
            "readings": ["ワ"],
            "wk-radical": None,
            "compounds": ["話", "活"],
            "non_compounds": [],
            "xrefs": [],
        },
    }


@pytest.fixture
def sample_wk_kanji_db():
    """WK kanji DB entries with meanings and readings (Keisei format)."""
    return {
        "語": {
            "meaning": "Language",
            "level": 5,
            "onyomi": "ゴ",
            "kunyomi": "かた.る",
            "important_reading": "onyomi",
        },
        "山": {
            "meaning": "Mountain",
            "level": 1,
            "onyomi": "サン",
            "kunyomi": "やま",
            "important_reading": "kunyomi",
        },
        "悟": {
            "meaning": "Enlightenment",
            "level": 30,
            "onyomi": "ゴ",
            "kunyomi": "さと.る",
            "important_reading": "onyomi",
        },
        "誤": {
            "meaning": "Mistake",
            "level": 32,
            "onyomi": "ゴ",
            "kunyomi": "",
            "important_reading": "onyomi",
        },
        "話": {
            "meaning": "Talk",
            "level": 5,
            "onyomi": "ワ",
            "kunyomi": "はな.す",
            "important_reading": "kunyomi",
        },
    }


@pytest.fixture
def sample_wk_radicals():
    """WK radical char -> name mapping."""
    return {
        "言": {"name": "Say", "level": 2, "slug": "say"},
        "吾": {"name": "Five Mouths", "level": 10, "slug": "five-mouths"},
        "山": {"name": "Mountain", "level": 1, "slug": "mountain"},
        "口": {"name": "Mouth", "level": 1, "slug": "mouth"},
        "虫": {"name": "Insect", "level": 5, "slug": "insect"},
        "木": {"name": "Tree", "level": 2, "slug": "tree"},
        "舌": {"name": "Tongue", "level": 7, "slug": "tongue"},
    }


@pytest.fixture
def sample_wk_kanji_subjects():
    """WK kanji subjects with component_radicals resolved to characters."""
    return {
        "語": {
            "meanings": ["Language", "Word"],
            "readings": {"onyomi": ["ゴ"], "kunyomi": ["かた.る"]},
            "component_radicals": ["言", "吾"],
            "level": 5,
        },
        "山": {
            "meanings": ["Mountain"],
            "readings": {"onyomi": ["サン"], "kunyomi": ["やま"]},
            "component_radicals": ["山"],
            "level": 1,
        },
        "話": {
            "meanings": ["Talk", "Speak"],
            "readings": {"onyomi": ["ワ"], "kunyomi": ["はな.す"]},
            "component_radicals": ["言", "舌"],
            "level": 5,
        },
    }


@pytest.fixture
def sample_kradfile():
    """KRADFILE-u decomposition data. Includes entries not in keisei DB."""
    return {
        "語": ["言", "五", "口"],
        "山": ["山"],
        "蝶": ["虫", "木", "世"],
        "話": ["言", "舌"],
    }


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


@pytest.fixture
def sample_profile_phonetic(
    sample_kanji_db,
    sample_phonetic_db,
    sample_wk_kanji_db,
    sample_wk_radicals,
    sample_wk_kanji_subjects,
    sample_kradfile,
):
    """Pre-built KanjiProfile for 語 (phonetic-semantic compound)."""
    from kanji_mnemonic.lookup import lookup_kanji

    return lookup_kanji(
        "語",
        sample_kanji_db,
        sample_phonetic_db,
        sample_wk_kanji_db,
        sample_wk_radicals,
        sample_wk_kanji_subjects,
        sample_kradfile,
    )


@pytest.fixture
def sample_profile_hieroglyph(
    sample_kanji_db,
    sample_phonetic_db,
    sample_wk_kanji_db,
    sample_wk_radicals,
    sample_wk_kanji_subjects,
    sample_kradfile,
):
    """Pre-built KanjiProfile for 山 (hieroglyph)."""
    from kanji_mnemonic.lookup import lookup_kanji

    return lookup_kanji(
        "山",
        sample_kanji_db,
        sample_phonetic_db,
        sample_wk_kanji_db,
        sample_wk_radicals,
        sample_wk_kanji_subjects,
        sample_kradfile,
    )
