"""Look up a kanji across all databases and assemble a complete profile."""

from dataclasses import dataclass, field

from .data import _katakana_to_hiragana


@dataclass
class KanjiProfile:
    character: str
    # From wk_kanji_db / wk subjects
    wk_meaning: str | None = None
    wk_level: int | None = None
    onyomi: list[str] = field(default_factory=list)
    kunyomi: list[str] = field(default_factory=list)
    important_reading: str | None = None  # "onyomi" or "kunyomi"
    # From kanji_db (Keisei)
    keisei_type: str | None = None  # comp_phonetic, hieroglyph, comp_indicative, indicative, unknown
    semantic_component: str | None = None
    phonetic_component: str | None = None
    decomposition: list[str] = field(default_factory=list)
    # Component radical names (from WK)
    wk_components: list[dict] = field(default_factory=list)  # [{"char": "x", "name": "Name"}, ...]
    # Phonetic family info
    phonetic_family: dict | None = None  # from phonetic_db
    phonetic_family_kanji_details: list[dict] = field(default_factory=list)


def lookup_kanji(
    char: str,
    kanji_db: dict,
    phonetic_db: dict,
    wk_kanji_db: dict,
    wk_radicals: dict,
    wk_kanji_subjects: dict | None = None,
    kradfile: dict | None = None,
    kanjidic: dict | None = None,
    personal_radicals: dict | None = None,
) -> KanjiProfile:
    profile = KanjiProfile(character=char)

    # --- WK Keisei kanji DB ---
    wk_info = wk_kanji_db.get(char)
    if wk_info:
        profile.wk_meaning = wk_info.get("meaning")
        profile.wk_level = wk_info.get("level")
        profile.onyomi = [r.strip() for r in wk_info.get("onyomi", "").split(",") if r.strip()] if wk_info.get("onyomi") else []
        profile.kunyomi = [r.strip() for r in wk_info.get("kunyomi", "").split(",") if r.strip()] if wk_info.get("kunyomi") else []
        profile.important_reading = wk_info.get("important_reading")

    # --- Supplement/override from WK API subjects if available ---
    if wk_kanji_subjects:
        subj = wk_kanji_subjects.get(char)
        if subj:
            if not profile.wk_meaning:
                profile.wk_meaning = subj["meanings"][0] if subj["meanings"] else None
            if not profile.onyomi:
                profile.onyomi = subj["readings"].get("onyomi", [])
            if not profile.kunyomi:
                profile.kunyomi = subj["readings"].get("kunyomi", [])
            if subj.get("level"):
                profile.wk_level = subj["level"]
            # Map component radicals to names
            for rc in subj.get("component_radicals", []):
                rad_info = wk_radicals.get(rc)
                if rad_info:
                    profile.wk_components.append({"char": rc, "name": rad_info["name"]})
                else:
                    profile.wk_components.append({"char": rc, "name": None})

    # --- Kanjidic fallback for meaning/readings (non-WK kanji) ---
    if kanjidic:
        kd = kanjidic.get(char)
        if kd:
            if not profile.wk_meaning and kd.get("meanings"):
                profile.wk_meaning = kd["meanings"][0]
            if not profile.onyomi and kd.get("onyomi"):
                profile.onyomi = kd["onyomi"]
            if not profile.kunyomi and kd.get("kunyomi"):
                profile.kunyomi = kd["kunyomi"]

    # Track which component chars we've already added to wk_components
    existing_chars = {c["char"] for c in profile.wk_components}

    # --- Keisei kanji DB ---
    keisei = kanji_db.get(char)
    if keisei:
        keisei_type = keisei.get("type")
        if keisei_type == "unprocessed":
            keisei = None  # fall through to KRADFILE
        else:
            profile.keisei_type = keisei_type
            profile.semantic_component = keisei.get("semantic")
            profile.phonetic_component = keisei.get("phonetic")
            profile.decomposition = keisei.get("decomposition", [])

            # If readings weren't found in WK data, use Keisei readings
            if not profile.onyomi and keisei.get("readings"):
                profile.onyomi = keisei["readings"]

    # --- KRADFILE-u fallback (non-WK kanji) ---
    if not keisei and kradfile:
        krad_components = kradfile.get(char, [])
        if krad_components:
            profile.decomposition = krad_components
            # Resolve component names from WK radicals
            for comp_char in krad_components:
                if comp_char not in existing_chars:
                    rad_info = wk_radicals.get(comp_char)
                    name = rad_info["name"] if rad_info else None
                    profile.wk_components.append({"char": comp_char, "name": name})
                    existing_chars.add(comp_char)
            # Try to infer phonetic-semantic relationship
            _infer_phonetic_semantic(profile, krad_components, phonetic_db)

    # --- Phonetic family lookup ---
    phonetic_char = profile.phonetic_component
    if phonetic_char and phonetic_char in phonetic_db:
        ph = phonetic_db[phonetic_char]
        profile.phonetic_family = {
            "phonetic_char": phonetic_char,
            "readings": ph.get("readings", []),
            "wk_radical_name": ph.get("wk-radical"),
            "compounds": ph.get("compounds", []),
            "non_compounds": ph.get("non_compounds", []),
            "xrefs": ph.get("xrefs", []),
        }
        # Enrich compounds with their meanings from wk_kanji_db
        for compound_char in ph.get("compounds", []):
            entry = {"char": compound_char}
            wk_c = wk_kanji_db.get(compound_char)
            if wk_c:
                entry["meaning"] = wk_c.get("meaning")
                entry["onyomi"] = wk_c.get("onyomi")
            profile.phonetic_family_kanji_details.append(entry)
    elif phonetic_char:
        # Phonetic component exists but isn't in phonetic_db — still note it
        # Check if the phonetic component itself is a known WK radical
        rad_info = wk_radicals.get(phonetic_char)
        profile.phonetic_family = {
            "phonetic_char": phonetic_char,
            "readings": keisei.get("readings", []) if keisei else [],
            "wk_radical_name": rad_info["name"] if rad_info else None,
            "compounds": [],
            "non_compounds": [],
            "xrefs": [],
        }

    # --- Resolve component radical names from all available sources ---
    # (existing_chars was initialized earlier, before Keisei/KRADFILE blocks)

    # Add semantic component if not already present
    if profile.semantic_component and profile.semantic_component not in existing_chars:
        rad_info = wk_radicals.get(profile.semantic_component)
        name = rad_info["name"] if rad_info else None
        profile.wk_components.insert(0, {"char": profile.semantic_component, "name": name})
        existing_chars.add(profile.semantic_component)

    # Add phonetic component if not already present
    if profile.phonetic_component and profile.phonetic_component not in existing_chars:
        rad_info = wk_radicals.get(profile.phonetic_component)
        # Also check phonetic_db for wk-radical name
        ph_entry = phonetic_db.get(profile.phonetic_component, {})
        name = None
        if rad_info:
            name = rad_info["name"]
        elif ph_entry.get("wk-radical"):
            name = ph_entry["wk-radical"]
        profile.wk_components.append({"char": profile.phonetic_component, "name": name})
        existing_chars.add(profile.phonetic_component)

    # Add decomposition components if not already present
    for comp_char in profile.decomposition:
        if comp_char not in existing_chars:
            rad_info = wk_radicals.get(comp_char)
            name = rad_info["name"] if rad_info else None
            profile.wk_components.append({"char": comp_char, "name": name})
            existing_chars.add(comp_char)

    # Apply personal radical name overrides
    if personal_radicals:
        for comp in profile.wk_components:
            if comp["char"] in personal_radicals:
                comp["name"] = personal_radicals[comp["char"]]
        # Also update phonetic_family's wk_radical_name if applicable
        if profile.phonetic_family:
            ph_char = profile.phonetic_family.get("phonetic_char")
            if ph_char and ph_char in personal_radicals:
                profile.phonetic_family["wk_radical_name"] = personal_radicals[ph_char]

    return profile


def _infer_phonetic_semantic(
    profile: KanjiProfile,
    components: list[str],
    phonetic_db: dict,
) -> None:
    """Try to infer a phonetic-semantic relationship from KRADFILE components.

    Only infers when there is actual evidence: the component is a known phonetic
    AND either the kanji is in its compounds list or readings overlap.
    """
    for comp in components:
        if comp not in phonetic_db:
            continue
        ph = phonetic_db[comp]
        compounds = ph.get("compounds", [])

        if profile.character in compounds:
            profile.keisei_type = "comp_phonetic"
        elif profile.onyomi:
            family_readings = {_katakana_to_hiragana(r) for r in ph.get("readings", [])}
            kanji_readings = {_katakana_to_hiragana(r) for r in profile.onyomi}
            if family_readings & kanji_readings:
                profile.keisei_type = "comp_phonetic_inferred"
            else:
                continue
        else:
            continue

        profile.phonetic_component = comp
        remaining = [c for c in components if c != comp]
        profile.semantic_component = remaining[0] if remaining else None
        return


def format_profile(profile: KanjiProfile) -> str:
    """Format the profile as a human-readable summary (also used as LLM context)."""
    lines = []
    lines.append(f"═══ {profile.character} ═══")
    if profile.wk_meaning:
        lines.append(f"Meaning: {profile.wk_meaning}")
    if profile.wk_level:
        lines.append(f"WaniKani Level: {profile.wk_level}")
    if profile.onyomi:
        lines.append(f"On'yomi: {', '.join(profile.onyomi)}")
    if profile.kunyomi:
        lines.append(f"Kun'yomi: {', '.join(profile.kunyomi)}")
    if profile.important_reading:
        lines.append(f"Important reading: {profile.important_reading}")

    lines.append("")

    if profile.keisei_type:
        type_labels = {
            "comp_phonetic": "Phonetic-Semantic Compound (形声)",
            "comp_phonetic_inferred": "Phonetic-Semantic Compound (形声) [inferred from KRADFILE]",
            "comp_indicative": "Compound Indicative (会意)",
            "hieroglyph": "Hieroglyph / Pictograph (象形)",
            "indicative": "Simple Indicative (指事)",
            "unknown": "Unknown origin",
        }
        lines.append(f"Type: {type_labels.get(profile.keisei_type, profile.keisei_type)}")

    if profile.wk_components:
        lines.append("WaniKani Components:")
        for c in profile.wk_components:
            if c["name"]:
                lines.append(f"  {c['char']} → {c['name']}")
            else:
                lines.append(f"  {c['char']} → (no name — use kanji name {c['char']} <name> to add one)")

    if profile.keisei_type in ("comp_phonetic", "comp_phonetic_inferred"):
        lines.append("")
        lines.append("── Phonetic-Semantic Breakdown ──")
        sem = profile.semantic_component or "?"
        ph = profile.phonetic_component or "?"
        sem_name = _find_name(sem, profile.wk_components)
        ph_name = _find_name(ph, profile.wk_components)
        lines.append(f"  Semantic (meaning hint): {sem} ({sem_name})")
        lines.append(f"  Phonetic (reading hint):  {ph} ({ph_name})")

    if profile.phonetic_family:
        pf = profile.phonetic_family
        lines.append("")
        lines.append("── Phonetic Family ──")
        ph_name = pf.get("wk_radical_name") or "(no WK name)"
        lines.append(f"  Phonetic component: {pf['phonetic_char']} (WK: {ph_name})")
        lines.append(f"  Family readings: {', '.join(pf['readings'])}")
        if profile.phonetic_family_kanji_details:
            lines.append("  Other kanji in this family:")
            for entry in profile.phonetic_family_kanji_details:
                if entry["char"] == profile.character:
                    continue
                meaning = entry.get("meaning", "?")
                reading = entry.get("onyomi", "?")
                lines.append(f"    {entry['char']} — {meaning} ({reading})")
        if pf.get("non_compounds"):
            lines.append(f"  ⚠ Looks similar but different reading: {', '.join(pf['non_compounds'])}")

    if profile.decomposition and profile.keisei_type not in ("comp_phonetic", "comp_phonetic_inferred"):
        lines.append("")
        lines.append("Decomposition: " + " + ".join(profile.decomposition))

    return "\n".join(lines)


def _find_name(char: str, components: list[dict]) -> str:
    for c in components:
        if c["char"] == char:
            return c["name"] or f"(no name — use kanji name {char} <name> to add one)"
    return f"(no name — use kanji name {char} <name> to add one)"
