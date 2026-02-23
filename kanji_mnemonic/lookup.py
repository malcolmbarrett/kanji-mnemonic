"""Look up a kanji across all databases and assemble a complete profile."""

from dataclasses import dataclass, field

from .data import _katakana_to_hiragana


def reverse_lookup_radical(
    name: str,
    wk_radicals: dict,
    personal_radicals: dict,
) -> str | None:
    """Look up a radical character by its name (case-insensitive).

    Checks personal radicals first, then WK radicals.
    Returns the character, or None if not found.
    """
    name_lower = name.lower()

    # Personal radicals first (higher priority)
    for char, rad_name in personal_radicals.items():
        if rad_name.lower() == name_lower:
            return char

    # WK radicals
    for char, info in wk_radicals.items():
        if info["name"].lower() == name_lower:
            return char

    return None


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
    keisei_type: str | None = (
        None  # comp_phonetic, hieroglyph, comp_indicative, indicative, unknown
    )
    semantic_component: str | None = None
    phonetic_component: str | None = None
    decomposition: list[str] = field(default_factory=list)
    # Component radical names (from WK)
    wk_components: list[dict] = field(
        default_factory=list
    )  # [{"char": "x", "name": "Name"}, ...]
    # Phonetic family info
    phonetic_family: dict | None = None  # from phonetic_db
    phonetic_family_kanji_details: list[dict] = field(default_factory=list)
    # From kanjidic2 (jmdict-simplified)
    joyo_grade: int | None = None
    frequency_rank: int | None = None
    # Personal decomposition
    personal_decomposition: dict | None = None  # raw stored dict
    decomposition_source: str | None = None  # "personal", "keisei", or "kradfile"
    auto_decomposition: list[str] = field(default_factory=list)
    auto_wk_components: list[dict] = field(default_factory=list)
    auto_keisei_type: str | None = None
    auto_semantic_component: str | None = None
    auto_phonetic_component: str | None = None


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
    infer_phonetic: bool = True,
    personal_decompositions: dict | None = None,
    reading_overrides: dict | None = None,
) -> KanjiProfile:
    profile = KanjiProfile(character=char)

    # --- WK Keisei kanji DB ---
    wk_info = wk_kanji_db.get(char)
    if wk_info:
        profile.wk_meaning = wk_info.get("meaning")
        profile.wk_level = wk_info.get("level")
        profile.onyomi = (
            [r.strip() for r in wk_info.get("onyomi", "").split(",") if r.strip()]
            if wk_info.get("onyomi")
            else []
        )
        profile.kunyomi = (
            [r.strip() for r in wk_info.get("kunyomi", "").split(",") if r.strip()]
            if wk_info.get("kunyomi")
            else []
        )
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
            if kd.get("grade") is not None:
                profile.joyo_grade = kd["grade"]
            if kd.get("frequency") is not None:
                profile.frequency_rank = kd["frequency"]

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
            profile.decomposition_source = "keisei"

            # If readings weren't found in WK data, use Keisei readings
            if not profile.onyomi and keisei.get("readings"):
                profile.onyomi = keisei["readings"]

    # --- KRADFILE-u fallback (non-WK kanji or type-only keisei entries) ---
    if kradfile and (not keisei or not profile.decomposition):
        krad_components = kradfile.get(char, [])
        if krad_components:
            profile.decomposition = krad_components
            if not profile.decomposition_source:
                profile.decomposition_source = "kradfile"
            # Resolve component names from WK radicals
            for comp_char in krad_components:
                if comp_char not in existing_chars:
                    rad_info = wk_radicals.get(comp_char)
                    name = rad_info["name"] if rad_info else None
                    profile.wk_components.append({"char": comp_char, "name": name})
                    existing_chars.add(comp_char)
            # Try to infer phonetic-semantic relationship
            _infer_phonetic_semantic(profile, krad_components, phonetic_db)

            # Fallback: KRADFILE subset matching when phonetic_db has no match
            if infer_phonetic and not profile.phonetic_component:
                detected = _infer_phonetic_from_kradfile_subsets(
                    profile, krad_components, kradfile, kanjidic, wk_kanji_db
                )
                if detected:
                    phonetic_krad = kradfile.get(detected, [])
                    _replace_atoms_with_phonetic_components(
                        profile,
                        detected,
                        phonetic_krad,
                        wk_kanji_subjects,
                        wk_radicals,
                        wk_kanji_db,
                        kanjidic,
                    )
                    existing_chars = {c["char"] for c in profile.wk_components}
                    # Mark phonetic component as "present" so it won't be
                    # re-added by the later component resolution block
                    # (its sub-radicals are already in wk_components).
                    existing_chars.add(detected)

    # --- Phonetic family lookup ---
    phonetic_char = profile.phonetic_component
    if phonetic_char and phonetic_char in phonetic_db:
        ph = phonetic_db[phonetic_char]
        # Resolve display name: phonetic_db wk-radical > wk_radicals > meaning
        ph_display_name = ph.get("wk-radical")
        if not ph_display_name:
            rad_info = wk_radicals.get(phonetic_char)
            if rad_info:
                ph_display_name = rad_info["name"]
        if not ph_display_name:
            wk_entry = wk_kanji_db.get(phonetic_char)
            if wk_entry:
                ph_display_name = wk_entry.get("meaning")
        profile.phonetic_family = {
            "phonetic_char": phonetic_char,
            "readings": ph.get("readings", []),
            "wk_radical_name": ph_display_name,
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
        # Phonetic component exists but isn't in phonetic_db — build synthetic
        # family by scanning KRADFILE for kanji sharing this phonetic subset.
        rad_info = wk_radicals.get(phonetic_char)

        # Get the phonetic component's readings (on'yomi + kun'yomi stems)
        phonetic_readings: list[str] = []
        if keisei and keisei.get("readings"):
            phonetic_readings = keisei["readings"]
        else:
            wk_entry = wk_kanji_db.get(phonetic_char)
            if wk_entry:
                if wk_entry.get("onyomi"):
                    phonetic_readings.extend(
                        _katakana_to_hiragana(r.strip())
                        for r in wk_entry["onyomi"].split(",")
                        if r.strip()
                    )
                if wk_entry.get("kunyomi"):
                    phonetic_readings.extend(
                        _kun_stem(r.strip())
                        for r in wk_entry["kunyomi"].split(",")
                        if r.strip()
                    )
            if not phonetic_readings and kanjidic:
                kd = kanjidic.get(phonetic_char, {})
                if kd.get("onyomi"):
                    phonetic_readings.extend(kd["onyomi"])
                if kd.get("kunyomi"):
                    phonetic_readings.extend(_kun_stem(r) for r in kd["kunyomi"])

        # Get the phonetic component's meaning for display
        phonetic_name = rad_info["name"] if rad_info else None
        if not phonetic_name:
            wk_entry = wk_kanji_db.get(phonetic_char)
            if wk_entry:
                phonetic_name = wk_entry.get("meaning")
            elif kanjidic:
                kd = kanjidic.get(phonetic_char, {})
                if kd.get("meanings"):
                    phonetic_name = kd["meanings"][0]

        # Scan KRADFILE for other kanji sharing this phonetic component
        synthetic_compounds: list[str] = []
        if kradfile and phonetic_readings:
            ph_krad = kradfile.get(phonetic_char, [])
            ph_set = set(ph_krad) if ph_krad else {phonetic_char}
            ph_reading_set = {_katakana_to_hiragana(r) for r in phonetic_readings}

            for k_char, k_components in kradfile.items():
                if k_char == profile.character or k_char == phonetic_char:
                    continue
                if not ph_set.issubset(set(k_components)):
                    continue
                # Check reading overlap (on'yomi + kun'yomi)
                k_readings: set[str] = set()
                wk_c = wk_kanji_db.get(k_char)
                if wk_c:
                    if wk_c.get("onyomi"):
                        k_readings.update(
                            _katakana_to_hiragana(r.strip())
                            for r in wk_c["onyomi"].split(",")
                            if r.strip()
                        )
                    if wk_c.get("kunyomi"):
                        k_readings.update(
                            _kun_stem(r.strip())
                            for r in wk_c["kunyomi"].split(",")
                            if r.strip()
                        )
                if kanjidic:
                    kd_c = kanjidic.get(k_char, {})
                    if kd_c.get("onyomi"):
                        k_readings.update(kd_c["onyomi"])
                    if kd_c.get("kunyomi"):
                        k_readings.update(_kun_stem(r) for r in kd_c["kunyomi"])
                if ph_reading_set & k_readings:
                    synthetic_compounds.append(k_char)

        profile.phonetic_family = {
            "phonetic_char": phonetic_char,
            "readings": phonetic_readings,
            "wk_radical_name": phonetic_name,
            "compounds": synthetic_compounds,
            "non_compounds": [],
            "xrefs": [],
        }

        # Enrich synthetic compounds with meanings
        for compound_char in synthetic_compounds:
            entry: dict = {"char": compound_char}
            wk_c = wk_kanji_db.get(compound_char)
            if wk_c:
                entry["meaning"] = wk_c.get("meaning")
                entry["onyomi"] = wk_c.get("onyomi")
            elif kanjidic:
                kd_c = kanjidic.get(compound_char, {})
                if kd_c.get("meanings"):
                    entry["meaning"] = kd_c["meanings"][0]
                if kd_c.get("onyomi"):
                    entry["onyomi"] = ", ".join(kd_c["onyomi"])
            profile.phonetic_family_kanji_details.append(entry)

    # --- Resolve component radical names from all available sources ---
    # (existing_chars was initialized earlier, before Keisei/KRADFILE blocks)

    # Add semantic component if not already present
    if profile.semantic_component and profile.semantic_component not in existing_chars:
        rad_info = wk_radicals.get(profile.semantic_component)
        name = rad_info["name"] if rad_info else None
        profile.wk_components.insert(
            0, {"char": profile.semantic_component, "name": name}
        )
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

    # --- Apply personal decomposition override ---
    if personal_decompositions and char in personal_decompositions:
        pd = personal_decompositions[char]
        # Stash auto-detected values
        profile.auto_decomposition = list(profile.decomposition)
        profile.auto_wk_components = list(profile.wk_components)
        profile.auto_keisei_type = profile.keisei_type
        profile.auto_semantic_component = profile.semantic_component
        profile.auto_phonetic_component = profile.phonetic_component

        # Store raw personal decomposition and update source
        profile.personal_decomposition = pd
        profile.decomposition_source = "personal"

        # Override decomposition
        profile.decomposition = pd["parts"]
        parts_set = set(pd["parts"])

        # Inherit auto-detected PS components if not explicitly set
        # and if the auto component is in the personal parts list
        personal_semantic = pd.get("semantic")
        personal_phonetic = pd.get("phonetic")

        if personal_semantic is None and profile.auto_semantic_component in parts_set:
            personal_semantic = profile.auto_semantic_component
        if personal_phonetic is None and profile.auto_phonetic_component in parts_set:
            personal_phonetic = profile.auto_phonetic_component

        profile.semantic_component = personal_semantic
        profile.phonetic_component = personal_phonetic

        # Set keisei_type based on resolved PS components
        if personal_phonetic and personal_semantic:
            profile.keisei_type = "comp_phonetic"
        elif personal_phonetic or personal_semantic:
            # Partial — keep whatever was auto-detected
            pass
        else:
            profile.keisei_type = profile.auto_keisei_type

        # Rebuild wk_components from personal parts
        profile.wk_components = []
        for part_char in pd["parts"]:
            rad_info = wk_radicals.get(part_char)
            name = rad_info["name"] if rad_info else None
            if not name:
                ph_entry = phonetic_db.get(part_char, {})
                if ph_entry.get("wk-radical"):
                    name = ph_entry["wk-radical"]
            if not name:
                wk_entry = wk_kanji_db.get(part_char)
                if wk_entry:
                    name = wk_entry.get("meaning")
            if not name and kanjidic:
                kd = kanjidic.get(part_char, {})
                if kd.get("meanings"):
                    name = kd["meanings"][0]
            profile.wk_components.append({"char": part_char, "name": name})

        # Rebuild phonetic family if phonetic component changed
        new_phonetic = personal_phonetic
        if new_phonetic and new_phonetic != profile.auto_phonetic_component:
            if new_phonetic in phonetic_db:
                ph = phonetic_db[new_phonetic]
                ph_display_name = ph.get("wk-radical")
                if not ph_display_name:
                    ri = wk_radicals.get(new_phonetic)
                    if ri:
                        ph_display_name = ri["name"]
                if not ph_display_name:
                    wk_entry = wk_kanji_db.get(new_phonetic)
                    if wk_entry:
                        ph_display_name = wk_entry.get("meaning")
                profile.phonetic_family = {
                    "phonetic_char": new_phonetic,
                    "readings": ph.get("readings", []),
                    "wk_radical_name": ph_display_name,
                    "compounds": ph.get("compounds", []),
                    "non_compounds": ph.get("non_compounds", []),
                    "xrefs": ph.get("xrefs", []),
                }
                # Enrich compounds
                profile.phonetic_family_kanji_details = []
                for compound_char in ph.get("compounds", []):
                    entry = {"char": compound_char}
                    wk_c = wk_kanji_db.get(compound_char)
                    if wk_c:
                        entry["meaning"] = wk_c.get("meaning")
                        entry["onyomi"] = wk_c.get("onyomi")
                    profile.phonetic_family_kanji_details.append(entry)

    # Apply personal reading override
    if reading_overrides and char in reading_overrides:
        profile.important_reading = reading_overrides[char]

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


def _kun_stem(reading: str) -> str:
    """Strip okurigana from a kun'yomi reading (e.g. 'つ.ぐ' -> 'つ')."""
    return reading.split(".")[0]


def _infer_phonetic_from_kradfile_subsets(
    profile: KanjiProfile,
    target_components: list[str],
    kradfile: dict,
    kanjidic: dict | None,
    wk_kanji_db: dict,
) -> str | None:
    """Fallback: find kanji whose KRADFILE components are a subset with shared reading.

    Scans all KRADFILE entries to find kanji whose decomposition is a proper
    subset of ``target_components`` AND shares an on'yomi or kun'yomi reading
    with the target. Returns the detected phonetic component character, or
    ``None``.
    """
    target_set = set(target_components)
    if len(target_set) < 2:
        return None

    # Collect all target readings (on'yomi + kun'yomi stems)
    target_readings: set[str] = set()
    for r in profile.onyomi:
        target_readings.add(_katakana_to_hiragana(r))
    for r in profile.kunyomi:
        target_readings.add(_kun_stem(r))

    if not target_readings:
        return None

    best_char: str | None = None
    best_size = 0

    for cand_char, cand_components in kradfile.items():
        if cand_char == profile.character:
            continue
        cand_set = set(cand_components)
        if len(cand_set) < 2:
            continue
        if not (cand_set < target_set):  # must be proper subset
            continue

        # Get candidate's readings (on'yomi + kun'yomi)
        cand_readings: set[str] = set()
        wk_entry = wk_kanji_db.get(cand_char)
        if wk_entry:
            if wk_entry.get("onyomi"):
                cand_readings.update(
                    _katakana_to_hiragana(r.strip())
                    for r in wk_entry["onyomi"].split(",")
                    if r.strip()
                )
            if wk_entry.get("kunyomi"):
                cand_readings.update(
                    _kun_stem(r.strip())
                    for r in wk_entry["kunyomi"].split(",")
                    if r.strip()
                )
        if kanjidic:
            kd = kanjidic.get(cand_char, {})
            if kd.get("onyomi"):
                cand_readings.update(kd["onyomi"])  # already hiragana
            if kd.get("kunyomi"):
                cand_readings.update(_kun_stem(r) for r in kd["kunyomi"])

        if not (target_readings & cand_readings):
            continue

        # Prefer candidate with most components (largest phonetic unit)
        if len(cand_set) > best_size:
            best_size = len(cand_set)
            best_char = cand_char

    if best_char is None:
        return None

    profile.keisei_type = "comp_phonetic_inferred"
    profile.phonetic_component = best_char

    best_set = set(kradfile[best_char])
    remaining = [c for c in target_components if c not in best_set]
    profile.semantic_component = remaining[0] if remaining else None

    return best_char


def _replace_atoms_with_phonetic_components(
    profile: KanjiProfile,
    phonetic_char: str,
    phonetic_krad_components: list[str],
    wk_kanji_subjects: dict | None,
    wk_radicals: dict,
    wk_kanji_db: dict,
    kanjidic: dict | None,
) -> None:
    """Replace KRADFILE atoms in wk_components with the phonetic component's WK radicals.

    When we discover that e.g. 追 is the phonetic component of 槌, the
    wk_components list has raw KRADFILE atoms [｜, 口, 辶].  This function
    replaces those atoms with 追's WK subject radicals [⻌, 㠯, 丶] (Scooter,
    Bear, Drop) so the user sees familiar WK radical names.
    """
    phonetic_atoms = set(phonetic_krad_components)

    # Find the index of the first atom belonging to the phonetic component
    insert_idx = None
    for i, comp in enumerate(profile.wk_components):
        if comp["char"] in phonetic_atoms:
            if insert_idx is None:
                insert_idx = i

    # Remove the phonetic component's atoms
    profile.wk_components = [
        c for c in profile.wk_components if c["char"] not in phonetic_atoms
    ]

    if insert_idx is None:
        insert_idx = len(profile.wk_components)
    else:
        # Adjust index for removals before insert_idx
        insert_idx = min(insert_idx, len(profile.wk_components))

    # Get replacement components from WK kanji subject if available
    new_components: list[dict] = []
    subj = wk_kanji_subjects.get(phonetic_char) if wk_kanji_subjects else None
    if subj and subj.get("component_radicals"):
        for rc in subj["component_radicals"]:
            rad_info = wk_radicals.get(rc)
            name = rad_info["name"] if rad_info else None
            new_components.append({"char": rc, "name": name})
    else:
        # No WK subject — insert the phonetic component itself with its meaning
        name = None
        wk_entry = wk_kanji_db.get(phonetic_char)
        if wk_entry:
            name = wk_entry.get("meaning")
        elif kanjidic:
            kd = kanjidic.get(phonetic_char, {})
            if kd.get("meanings"):
                name = kd["meanings"][0]
        new_components.append({"char": phonetic_char, "name": name})

    # Insert at the position where the first atom was
    for i, comp in enumerate(new_components):
        profile.wk_components.insert(insert_idx + i, comp)

    # Update decomposition to use the new radical chars instead of atoms
    new_decomp = [c for c in profile.decomposition if c not in phonetic_atoms]
    for comp in new_components:
        if comp["char"] not in new_decomp:
            new_decomp.append(comp["char"])
    profile.decomposition = new_decomp


def format_profile(profile: KanjiProfile, *, show_all_decomp: bool = False) -> str:
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
    if profile.joyo_grade is not None:
        lines.append(f"Joyo Grade: {profile.joyo_grade}")
    if profile.frequency_rank is not None:
        lines.append(f"Frequency Rank: {profile.frequency_rank}")

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
        lines.append(
            f"Type: {type_labels.get(profile.keisei_type, profile.keisei_type)}"
        )

    is_personal = profile.personal_decomposition is not None

    if profile.wk_components:
        header = "WaniKani Components"
        if is_personal:
            header += " [personal]"
        lines.append(f"{header}:")
        for c in profile.wk_components:
            if c["name"]:
                lines.append(f"  {c['char']} → {c['name']}")
            else:
                lines.append(
                    f"  {c['char']} → (no name — use kanji name {c['char']} <name> to add one)"
                )

    if profile.keisei_type in ("comp_phonetic", "comp_phonetic_inferred"):
        lines.append("")
        header = "── Phonetic-Semantic Breakdown"
        if is_personal:
            header += " [personal]"
        header += " ──"
        lines.append(header)
        sem = profile.semantic_component or "?"
        ph = profile.phonetic_component or "?"
        sem_name = _find_name(sem, profile.wk_components)
        # For phonetic component, fall back to phonetic_family name (covers
        # cases where the phonetic is a kanji whose sub-radicals replaced it
        # in wk_components, e.g. 追 replaced by Bear + Scooter).
        ph_name = _find_name(ph, profile.wk_components, allow_missing=True)
        if ph_name is None and profile.phonetic_family:
            ph_name = profile.phonetic_family.get("wk_radical_name")
        if ph_name is None:
            ph_name = f"(no name — use kanji name {ph} <name> to add one)"
        lines.append(f"  Semantic (meaning hint): {sem} ({sem_name})")
        lines.append(f"  Phonetic (reading hint):  {ph} ({ph_name})")

    if profile.phonetic_family:
        pf = profile.phonetic_family
        lines.append("")
        lines.append("── Phonetic Family ──")
        ph_name = pf.get("wk_radical_name") or "(no name)"
        lines.append(f"  Phonetic component: {pf['phonetic_char']} ({ph_name})")
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
            lines.append(
                f"  ⚠ Looks similar but different reading: {', '.join(pf['non_compounds'])}"
            )

    if profile.decomposition and profile.keisei_type not in (
        "comp_phonetic",
        "comp_phonetic_inferred",
    ):
        lines.append("")
        lines.append("Decomposition: " + " + ".join(profile.decomposition))

    # --- All-decomp mode: show auto-detected decomposition as separate section ---
    if show_all_decomp and is_personal and profile.auto_wk_components:
        lines.append("")
        lines.append("── Auto-detected Decomposition ──")
        if profile.auto_keisei_type:
            auto_type_labels = {
                "comp_phonetic": "Phonetic-Semantic Compound (形声)",
                "comp_phonetic_inferred": "Phonetic-Semantic Compound (形声) [inferred]",
                "comp_indicative": "Compound Indicative (会意)",
                "hieroglyph": "Hieroglyph / Pictograph (象形)",
                "indicative": "Simple Indicative (指事)",
                "unknown": "Unknown origin",
            }
            lines.append(
                f"  Type: {auto_type_labels.get(profile.auto_keisei_type, profile.auto_keisei_type)}"
            )
        lines.append("  Components:")
        for c in profile.auto_wk_components:
            name = c["name"] or "(no name)"
            lines.append(f"    {c['char']} → {name}")
        if profile.auto_semantic_component or profile.auto_phonetic_component:
            if profile.auto_semantic_component:
                lines.append(f"  Semantic: {profile.auto_semantic_component}")
            if profile.auto_phonetic_component:
                lines.append(f"  Phonetic: {profile.auto_phonetic_component}")
        if profile.auto_decomposition:
            lines.append("  Decomposition: " + " + ".join(profile.auto_decomposition))

    return "\n".join(lines)


def _find_name(
    char: str, components: list[dict], *, allow_missing: bool = False
) -> str | None:
    for c in components:
        if c["char"] == char:
            return c["name"] or f"(no name — use kanji name {char} <name> to add one)"
    if allow_missing:
        return None
    return f"(no name — use kanji name {char} <name> to add one)"
