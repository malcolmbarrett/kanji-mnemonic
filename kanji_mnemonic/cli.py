"""CLI for kanji mnemonic generation."""

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import anthropic
from dotenv import load_dotenv

from .data import (
    clear_cache,
    fetch_wk_kanji_subjects,
    fetch_wk_radicals,
    load_kanji_db,
    load_kanjidic,
    load_kradfile,
    load_mnemonic_for_kanji,
    load_personal_decompositions,
    load_personal_radicals,
    load_personal_sound_mnemonics,
    load_phonetic_db,
    load_reading_overrides,
    load_wk_kanji_db,
    load_wk_sound_mnemonics,
    merge_sound_mnemonics,
    remove_personal_decomposition,
    remove_personal_sound_mnemonic,
    remove_reading_override,
    save_mnemonic,
    save_personal_decomposition,
    save_personal_radical,
    save_personal_sound_mnemonic,
    save_reading_override,
)
from .lookup import format_profile, lookup_kanji, reverse_lookup_radical
from .prompt import build_prompt, get_system_prompt

# Load .env — checks cwd first, then home directory
load_dotenv()
load_dotenv(Path.home() / ".config" / "kanji" / ".env")


def get_wk_api_key() -> str | None:
    return os.environ.get("WK_API_KEY")


def get_anthropic_client() -> anthropic.Anthropic:
    # anthropic lib reads ANTHROPIC_API_KEY from env by default
    return anthropic.Anthropic()


def load_all_data(wk_api_key: str | None):
    """Load all databases, fetching WK data if API key is available."""
    kanji_db = load_kanji_db()
    phonetic_db = load_phonetic_db()
    wk_kanji_db = load_wk_kanji_db()

    kradfile = load_kradfile()
    kanjidic = load_kanjidic()

    wk_radicals = {}
    wk_kanji_subjects = None
    if wk_api_key:
        wk_radicals = fetch_wk_radicals(wk_api_key)
        wk_kanji_subjects = fetch_wk_kanji_subjects(wk_api_key)
    else:
        # Try to load from cache even without key
        from .data import CACHE_DIR
        import json

        rad_cache = CACHE_DIR / "wk_radicals.json"
        subj_cache = CACHE_DIR / "wk_kanji_subjects.json"
        if rad_cache.exists():
            wk_radicals = json.loads(rad_cache.read_text(encoding="utf-8"))
        if subj_cache.exists():
            wk_kanji_subjects = json.loads(subj_cache.read_text(encoding="utf-8"))
        if not wk_radicals:
            print(
                "Warning: No WK_API_KEY set and no cached radical data.",
                file=sys.stderr,
            )
            print("  Set WK_API_KEY for full radical name resolution.", file=sys.stderr)
            print(
                "  Get your key at: https://www.wanikani.com/settings/personal_access_tokens",
                file=sys.stderr,
            )

    personal_radicals = load_personal_radicals()
    personal_decompositions = load_personal_decompositions()
    reading_overrides = load_reading_overrides()
    personal_sounds = load_personal_sound_mnemonics()
    sound_mnemonics = merge_sound_mnemonics(load_wk_sound_mnemonics(), personal_sounds)

    return (
        kanji_db,
        phonetic_db,
        wk_kanji_db,
        wk_radicals,
        wk_kanji_subjects,
        kradfile,
        kanjidic,
        personal_radicals,
        personal_decompositions,
        reading_overrides,
        sound_mnemonics,
    )


def cmd_lookup(
    args,
    kanji_db,
    phonetic_db,
    wk_kanji_db,
    wk_radicals,
    wk_kanji_subjects,
    kradfile,
    kanjidic,
    personal_radicals,
    personal_decompositions,
    reading_overrides,
    sound_mnemonics,
):
    """Just show the kanji profile without generating a mnemonic."""
    from .prompt import _get_relevant_sound_mnemonics

    for char in args.kanji:
        profile = lookup_kanji(
            char,
            kanji_db,
            phonetic_db,
            wk_kanji_db,
            wk_radicals,
            wk_kanji_subjects,
            kradfile,
            kanjidic,
            personal_radicals=personal_radicals,
            infer_phonetic=not getattr(args, "no_infer", False),
            personal_decompositions=personal_decompositions,
            reading_overrides=reading_overrides,
        )
        print(
            format_profile(
                profile,
                show_all_decomp=getattr(args, "all_decomp", False),
            )
        )
        if getattr(args, "sound", False) and sound_mnemonics:
            relevant = _get_relevant_sound_mnemonics(profile, sound_mnemonics)
            if relevant:
                print("Sound mnemonics:")
                for reading, info in relevant.items():
                    print(f"  {reading} → {info['character']} ({info['description']})")
        print()


def _stream_mnemonic(client, model, user_msg):
    """Stream a mnemonic from the LLM, printing chunks and returning the full text."""
    chunks = []
    with client.messages.stream(
        model=model,
        max_tokens=1024,
        system=get_system_prompt(),
        messages=[{"role": "user", "content": user_msg}],
    ) as stream:
        for text in stream.text_stream:
            print(text, end="", flush=True)
            chunks.append(text)
    print()  # Final newline
    return "".join(chunks)


def _edit_mnemonic(current_text):
    """Open the user's editor with the current mnemonic text. Returns edited text."""
    editor = os.environ.get("EDITOR") or os.environ.get("VISUAL") or "vi"
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", delete=False, encoding="utf-8"
    ) as f:
        f.write(current_text)
        tmppath = f.name
    try:
        subprocess.call([editor, tmppath])
        edited = Path(tmppath).read_text(encoding="utf-8").strip()
        return edited if edited else None
    finally:
        Path(tmppath).unlink(missing_ok=True)


def cmd_memorize(
    args,
    kanji_db,
    phonetic_db,
    wk_kanji_db,
    wk_radicals,
    wk_kanji_subjects,
    kradfile,
    kanjidic,
    personal_radicals,
    personal_decompositions,
    reading_overrides,
    sound_mnemonics,
):
    """Generate a mnemonic for the given kanji."""
    client = get_anthropic_client()

    for char in args.kanji:
        profile = lookup_kanji(
            char,
            kanji_db,
            phonetic_db,
            wk_kanji_db,
            wk_radicals,
            wk_kanji_subjects,
            kradfile,
            kanjidic,
            personal_radicals=personal_radicals,
            infer_phonetic=not getattr(args, "no_infer", False),
            personal_decompositions=personal_decompositions,
            reading_overrides=reading_overrides,
        )

        # Apply one-shot --primary override
        if getattr(args, "primary", None):
            profile.important_reading = args.primary

        # Show the profile first
        print(format_profile(profile))
        print()
        print("── Generating mnemonic... ──")
        print()

        user_msg = build_prompt(
            profile, user_context=args.context, sound_mnemonics=sound_mnemonics
        )
        mnemonic_text = _stream_mnemonic(client, args.model, user_msg)

        # Auto-save immediately
        save_mnemonic(char, mnemonic_text, args.model)

        if args.no_interactive:
            continue

        # Interactive refinement loop
        while True:
            print()
            choice = input("[a]ccept / [r]etry / [e]dit / [q]uit: ").strip().lower()

            if choice == "a":
                break
            elif choice == "r":
                print()
                print("── Regenerating mnemonic... ──")
                print()
                mnemonic_text = _stream_mnemonic(client, args.model, user_msg)
                save_mnemonic(char, mnemonic_text, args.model)
            elif choice == "e":
                edited = _edit_mnemonic(mnemonic_text)
                if edited:
                    mnemonic_text = edited
                    save_mnemonic(char, mnemonic_text, args.model)
            elif choice == "q":
                break


def cmd_prompt(
    args,
    kanji_db,
    phonetic_db,
    wk_kanji_db,
    wk_radicals,
    wk_kanji_subjects,
    kradfile,
    kanjidic,
    personal_radicals,
    personal_decompositions,
    reading_overrides,
    sound_mnemonics,
):
    """Show the assembled prompt without calling the LLM."""
    for char in args.kanji:
        profile = lookup_kanji(
            char,
            kanji_db,
            phonetic_db,
            wk_kanji_db,
            wk_radicals,
            wk_kanji_subjects,
            kradfile,
            kanjidic,
            personal_radicals=personal_radicals,
            infer_phonetic=not getattr(args, "no_infer", False),
            personal_decompositions=personal_decompositions,
            reading_overrides=reading_overrides,
        )
        print("── SYSTEM PROMPT ──")
        print(get_system_prompt())
        print()
        print("── USER MESSAGE ──")
        print(
            build_prompt(
                profile, user_context=args.context, sound_mnemonics=sound_mnemonics
            )
        )
        print()


def cmd_decompose(
    args,
    kanji_db,
    phonetic_db,
    wk_kanji_db,
    wk_radicals,
    wk_kanji_subjects,
    kradfile,
    kanjidic,
    personal_radicals,
    personal_decompositions,
    reading_overrides,
    sound_mnemonics,
):
    """Set, show, or remove a personal kanji decomposition."""
    char = args.kanji

    # --- Remove mode ---
    if args.remove:
        removed = remove_personal_decomposition(char)
        if removed:
            print(f"Removed personal decomposition for {char}")
        else:
            print(f"No personal decomposition saved for {char}")
        return

    # --- Show mode (no parts, no -p/-s) ---
    if not args.parts and not args.phonetic and not args.semantic:
        pd = personal_decompositions.get(char)
        if not pd:
            print(f"No personal decomposition saved for {char}")
            return
        parts_display = []
        for p in pd["parts"]:
            label = p
            if p == pd.get("semantic"):
                label += " (semantic)"
            elif p == pd.get("phonetic"):
                label += " (phonetic)"
            parts_display.append(label)
        print(f"{char} → {', '.join(parts_display)}")
        return

    # --- Resolve parts ---
    resolved_parts = []
    for part in args.parts:
        resolved = _resolve_part(part, wk_radicals, personal_radicals)
        if resolved is None:
            print(
                f'Error: "{part}" is not a known radical name. '
                f"Use 'kanji name <radical> {part}' to add it first.",
                file=sys.stderr,
            )
            sys.exit(1)
        resolved_parts.append(resolved)

    # Resolve -p and -s values
    phonetic = None
    if args.phonetic:
        phonetic = _resolve_part(args.phonetic, wk_radicals, personal_radicals)
        if phonetic is None:
            print(
                f'Error: "{args.phonetic}" is not a known radical name. '
                f"Use 'kanji name <radical> {args.phonetic}' to add it first.",
                file=sys.stderr,
            )
            sys.exit(1)

    semantic = None
    if args.semantic:
        semantic = _resolve_part(args.semantic, wk_radicals, personal_radicals)
        if semantic is None:
            print(
                f'Error: "{args.semantic}" is not a known radical name. '
                f"Use 'kanji name <radical> {args.semantic}' to add it first.",
                file=sys.stderr,
            )
            sys.exit(1)

    # Merge -p/-s into parts list and enforce ordering: semantic first, phonetic last
    if semantic:
        if semantic in resolved_parts:
            resolved_parts.remove(semantic)
        resolved_parts.insert(0, semantic)
    if phonetic:
        if phonetic in resolved_parts:
            resolved_parts.remove(phonetic)
        resolved_parts.append(phonetic)

    # Save
    save_personal_decomposition(
        char, resolved_parts, phonetic=phonetic, semantic=semantic
    )

    # Print confirmation with resolved names
    parts_display = []
    for p in resolved_parts:
        name = _resolve_name(p, wk_radicals, personal_radicals, wk_kanji_db, kanjidic)
        label = f"{p}"
        if name:
            label += f" ({name})"
        if p == semantic:
            label += " [semantic]"
        elif p == phonetic:
            label += " [phonetic]"
        parts_display.append(label)
    print(f"Saved: {char} → {', '.join(parts_display)}")


def _resolve_part(part, wk_radicals, personal_radicals):
    """Resolve a part string to a character. Single chars pass through; words are reverse-looked-up."""
    if len(part) == 1:
        return part
    return reverse_lookup_radical(part, wk_radicals, personal_radicals)


def _resolve_name(char, wk_radicals, personal_radicals, wk_kanji_db, kanjidic):
    """Get the display name for a component character."""
    if personal_radicals and char in personal_radicals:
        return personal_radicals[char]
    rad_info = wk_radicals.get(char)
    if rad_info:
        return rad_info["name"]
    wk_entry = wk_kanji_db.get(char)
    if wk_entry:
        return wk_entry.get("meaning")
    if kanjidic:
        kd = kanjidic.get(char, {})
        if kd.get("meanings"):
            return kd["meanings"][0]
    return None


def cmd_name(args):
    """Save a personal radical name."""
    save_personal_radical(args.radical, args.name)
    print(f"Saved: {args.radical} → {args.name}")


def cmd_names(args):
    """List all personal radical names."""
    data = load_personal_radicals()
    if not data:
        print("No personal radical names yet.")
        print("Use 'kanji name <radical> <name>' to add one.")
        return
    for char, name in data.items():
        print(f"  {char} → {name}")


def cmd_reading(args):
    """Save, show, or remove a reading override for a kanji."""
    if args.remove:
        removed = remove_reading_override(args.kanji)
        if removed:
            print(f"Removed reading override for {args.kanji}")
        else:
            print(f"No reading override for {args.kanji}")
        return
    if args.reading_type:
        save_reading_override(args.kanji, args.reading_type)
        print(f"Saved: {args.kanji} → primary reading: {args.reading_type}")
        return
    # Show current override
    overrides = load_reading_overrides()
    if args.kanji in overrides:
        print(f"{args.kanji} → primary reading: {overrides[args.kanji]}")
    else:
        print(f"No reading override for {args.kanji}")
        print("Use 'kanji reading <kanji> onyomi|kunyomi' to set one.")


def cmd_readings(args):
    """List all reading overrides."""
    data = load_reading_overrides()
    if not data:
        print("No reading overrides yet.")
        print("Use 'kanji reading <kanji> onyomi|kunyomi' to add one.")
        return
    for kanji, reading_type in data.items():
        print(f"  {kanji} → {reading_type}")


def cmd_sounds(args):
    """List all sound mnemonics (merged WK + personal)."""
    from .data import load_personal_sound_mnemonics

    personal = load_personal_sound_mnemonics()

    if getattr(args, "personal", False):
        if not personal:
            print("No personal sound mnemonics yet.")
            print("Use 'kanji sound <reading> <character> <description>' to add one.")
            return
        for reading, info in sorted(personal.items()):
            print(f"  {reading} → {info['character']} ({info['description']})")
        return

    wk = load_wk_sound_mnemonics()
    merged = merge_sound_mnemonics(wk, personal)
    if not merged:
        print("No sound mnemonics available.")
        return
    for reading, info in sorted(merged.items()):
        annotation = " [personal]" if reading in personal else ""
        print(f"  {reading} → {info['character']} ({info['description']}){annotation}")


def cmd_sound(args):
    """Save, show, or remove a personal sound mnemonic."""
    if args.remove:
        removed = remove_personal_sound_mnemonic(args.reading)
        if removed:
            print(f"Removed personal sound mnemonic for {args.reading}")
        else:
            print(f"No personal sound mnemonic for {args.reading}")
        return
    if args.character and args.description:
        save_personal_sound_mnemonic(args.reading, args.character, args.description)
        print(f"Saved: {args.reading} → {args.character} ({args.description})")
        return
    if args.character:
        print(
            "Error: Both character and description are required to save a sound mnemonic."
        )
        print("Usage: kanji sound <reading> <character> <description>")
        return
    # Show current personal sound mnemonic
    from .data import load_personal_sound_mnemonics

    personal = load_personal_sound_mnemonics()
    if args.reading in personal:
        info = personal[args.reading]
        print(f"{args.reading} → {info['character']} ({info['description']})")
    else:
        print(f"No personal sound mnemonic for {args.reading}")
        print("Use 'kanji sound <reading> <character> <description>' to add one.")


def cmd_show(args):
    """Display saved mnemonics for given kanji."""
    for char in args.kanji:
        entry = load_mnemonic_for_kanji(char)
        if entry:
            print(f"═══ {char} ═══")
            print(entry["mnemonic"])
            print()
            print(f"Model: {entry['model']}")
            print(f"Saved: {entry['timestamp']}")
        else:
            print(f"No saved mnemonic for {char}")
        print()


def cmd_clear_cache(_args, *_data):
    clear_cache()


def main():
    parser = argparse.ArgumentParser(
        prog="kanji",
        description="Generate kanji mnemonics using WaniKani radicals and phonetic-semantic data",
    )
    parser.add_argument(
        "--model",
        default="claude-sonnet-4-6",
        help="Anthropic model to use (default: claude-sonnet-4-6)",
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # --- memorize (default) ---
    p_memorize = subparsers.add_parser(
        "memorize", aliases=["m"], help="Generate a mnemonic"
    )
    p_memorize.add_argument("kanji", nargs="+", help="One or more kanji characters")
    p_memorize.add_argument(
        "-c",
        "--context",
        help="Extra context to include (e.g., 'I always mix this up with 待')",
    )
    p_memorize.add_argument(
        "-n",
        "--no-interactive",
        action="store_true",
        default=False,
        help="Save mnemonic without interactive prompt",
    )
    p_memorize.add_argument(
        "--no-infer",
        action="store_true",
        default=False,
        help="Disable KRADFILE-based phonetic inference",
    )
    p_memorize.add_argument(
        "--primary",
        choices=["onyomi", "kunyomi"],
        default=None,
        help="Override which reading type the mnemonic focuses on (one-shot, not saved)",
    )

    # --- lookup ---
    p_lookup = subparsers.add_parser(
        "lookup", aliases=["l"], help="Show kanji profile without LLM call"
    )
    p_lookup.add_argument("kanji", nargs="+", help="One or more kanji characters")
    p_lookup.add_argument(
        "--no-infer",
        action="store_true",
        default=False,
        help="Disable KRADFILE-based phonetic inference",
    )
    p_lookup.add_argument(
        "--all-decomp",
        action="store_true",
        default=False,
        help="Show both personal and auto-detected decompositions",
    )
    p_lookup.add_argument(
        "--sound",
        action="store_true",
        default=False,
        help="Show relevant sound mnemonics for this kanji's readings",
    )

    # --- prompt ---
    p_prompt = subparsers.add_parser(
        "prompt", aliases=["p"], help="Show the assembled prompt (debug)"
    )
    p_prompt.add_argument("kanji", nargs="+", help="One or more kanji characters")
    p_prompt.add_argument("-c", "--context", help="Extra context to include")
    p_prompt.add_argument(
        "--no-infer",
        action="store_true",
        default=False,
        help="Disable KRADFILE-based phonetic inference",
    )

    # --- decompose ---
    p_decompose = subparsers.add_parser(
        "decompose",
        aliases=["d"],
        help="Set, show, or remove a personal kanji decomposition",
    )
    p_decompose.add_argument("kanji", help="A single kanji character")
    p_decompose.add_argument(
        "parts",
        nargs="*",
        help="Component parts (kanji characters or radical names)",
    )
    p_decompose.add_argument(
        "-p", "--phonetic", help="Mark a component as the phonetic component"
    )
    p_decompose.add_argument(
        "-s", "--semantic", help="Mark a component as the semantic component"
    )
    p_decompose.add_argument(
        "--remove",
        "--rm",
        action="store_true",
        default=False,
        help="Remove the personal decomposition for this kanji",
    )

    # --- name ---
    p_name = subparsers.add_parser("name", help="Add or update a personal radical name")
    p_name.add_argument("radical", help="The radical character")
    p_name.add_argument("name", help="Your name for this radical")

    # --- names ---
    subparsers.add_parser("names", help="List all personal radical names")

    # --- reading ---
    p_reading = subparsers.add_parser(
        "reading", help="Set, show, or remove a primary reading override"
    )
    p_reading.add_argument("kanji", help="A single kanji character")
    p_reading.add_argument(
        "reading_type",
        nargs="?",
        choices=["onyomi", "kunyomi"],
        default=None,
        help="Set the primary reading type (onyomi or kunyomi)",
    )
    p_reading.add_argument(
        "--remove",
        "--rm",
        action="store_true",
        default=False,
        help="Remove the reading override for this kanji",
    )

    # --- readings ---
    subparsers.add_parser("readings", help="List all reading overrides")

    # --- sound ---
    p_sound = subparsers.add_parser(
        "sound", help="Add, show, or remove a personal sound mnemonic"
    )
    p_sound.add_argument("reading", help="The hiragana reading (e.g. こう)")
    p_sound.add_argument("character", nargs="?", default=None, help="Character name")
    p_sound.add_argument("description", nargs="?", default=None, help="Description")
    p_sound.add_argument(
        "--remove",
        "--rm",
        action="store_true",
        default=False,
        help="Remove the personal sound mnemonic for this reading",
    )

    # --- sounds ---
    p_sounds = subparsers.add_parser("sounds", help="List all sound mnemonics")
    p_sounds.add_argument(
        "--personal",
        action="store_true",
        default=False,
        help="Show only personal sound mnemonics",
    )

    # --- show ---
    p_show = subparsers.add_parser(
        "show", aliases=["s"], help="Show saved mnemonic for a kanji"
    )
    p_show.add_argument("kanji", nargs="+", help="One or more kanji characters")

    # --- clear-cache ---
    subparsers.add_parser("clear-cache", help="Remove cached database files")

    args = parser.parse_args()

    if not args.command:
        # Default: if bare kanji given, treat as mnemonic
        parser.print_help()
        sys.exit(1)

    if args.command == "clear-cache":
        cmd_clear_cache(args)
        return

    if args.command == "name":
        cmd_name(args)
        return

    if args.command == "names":
        cmd_names(args)
        return

    if args.command in ("show", "s"):
        cmd_show(args)
        return

    if args.command == "reading":
        cmd_reading(args)
        return

    if args.command == "readings":
        cmd_readings(args)
        return

    if args.command == "sound":
        cmd_sound(args)
        return

    if args.command == "sounds":
        cmd_sounds(args)
        return

    wk_api_key = get_wk_api_key()
    data = load_all_data(wk_api_key)

    dispatch = {
        "memorize": cmd_memorize,
        "m": cmd_memorize,
        "lookup": cmd_lookup,
        "l": cmd_lookup,
        "prompt": cmd_prompt,
        "p": cmd_prompt,
        "decompose": cmd_decompose,
        "d": cmd_decompose,
    }
    dispatch[args.command](args, *data)


if __name__ == "__main__":
    main()
