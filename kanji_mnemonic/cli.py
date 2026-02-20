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
    load_personal_radicals,
    load_phonetic_db,
    load_wk_kanji_db,
    save_mnemonic,
    save_personal_radical,
)
from .lookup import format_profile, lookup_kanji
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
            print("Warning: No WK_API_KEY set and no cached radical data.", file=sys.stderr)
            print("  Set WK_API_KEY for full radical name resolution.", file=sys.stderr)
            print("  Get your key at: https://www.wanikani.com/settings/personal_access_tokens", file=sys.stderr)

    personal_radicals = load_personal_radicals()

    return kanji_db, phonetic_db, wk_kanji_db, wk_radicals, wk_kanji_subjects, kradfile, kanjidic, personal_radicals


def cmd_lookup(args, kanji_db, phonetic_db, wk_kanji_db, wk_radicals, wk_kanji_subjects, kradfile, kanjidic, personal_radicals):
    """Just show the kanji profile without generating a mnemonic."""
    for char in args.kanji:
        profile = lookup_kanji(char, kanji_db, phonetic_db, wk_kanji_db, wk_radicals, wk_kanji_subjects, kradfile, kanjidic, personal_radicals=personal_radicals)
        print(format_profile(profile))
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
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write(current_text)
        tmppath = f.name
    try:
        subprocess.call([editor, tmppath])
        edited = Path(tmppath).read_text(encoding="utf-8").strip()
        return edited if edited else None
    finally:
        Path(tmppath).unlink(missing_ok=True)


def cmd_memorize(args, kanji_db, phonetic_db, wk_kanji_db, wk_radicals, wk_kanji_subjects, kradfile, kanjidic, personal_radicals):
    """Generate a mnemonic for the given kanji."""
    client = get_anthropic_client()

    for char in args.kanji:
        profile = lookup_kanji(char, kanji_db, phonetic_db, wk_kanji_db, wk_radicals, wk_kanji_subjects, kradfile, kanjidic, personal_radicals=personal_radicals)

        # Show the profile first
        print(format_profile(profile))
        print()
        print("── Generating mnemonic... ──")
        print()

        user_msg = build_prompt(profile, user_context=args.context)
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


def cmd_prompt(args, kanji_db, phonetic_db, wk_kanji_db, wk_radicals, wk_kanji_subjects, kradfile, kanjidic, personal_radicals):
    """Show the assembled prompt without calling the LLM."""
    for char in args.kanji:
        profile = lookup_kanji(char, kanji_db, phonetic_db, wk_kanji_db, wk_radicals, wk_kanji_subjects, kradfile, kanjidic, personal_radicals=personal_radicals)
        print("── SYSTEM PROMPT ──")
        print(get_system_prompt())
        print()
        print("── USER MESSAGE ──")
        print(build_prompt(profile, user_context=args.context))
        print()


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
        "--model", default="claude-sonnet-4-20250514",
        help="Anthropic model to use (default: claude-sonnet-4-20250514)",
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # --- memorize (default) ---
    p_memorize = subparsers.add_parser("memorize", aliases=["m"], help="Generate a mnemonic")
    p_memorize.add_argument("kanji", nargs="+", help="One or more kanji characters")
    p_memorize.add_argument("-c", "--context", help="Extra context to include (e.g., 'I always mix this up with 待')")
    p_memorize.add_argument("-n", "--no-interactive", action="store_true", default=False, help="Save mnemonic without interactive prompt")

    # --- lookup ---
    p_lookup = subparsers.add_parser("lookup", aliases=["l"], help="Show kanji profile without LLM call")
    p_lookup.add_argument("kanji", nargs="+", help="One or more kanji characters")

    # --- prompt ---
    p_prompt = subparsers.add_parser("prompt", aliases=["p"], help="Show the assembled prompt (debug)")
    p_prompt.add_argument("kanji", nargs="+", help="One or more kanji characters")
    p_prompt.add_argument("-c", "--context", help="Extra context to include")

    # --- name ---
    p_name = subparsers.add_parser("name", help="Add or update a personal radical name")
    p_name.add_argument("radical", help="The radical character")
    p_name.add_argument("name", help="Your name for this radical")

    # --- names ---
    subparsers.add_parser("names", help="List all personal radical names")

    # --- show ---
    p_show = subparsers.add_parser("show", aliases=["s"], help="Show saved mnemonic for a kanji")
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

    wk_api_key = get_wk_api_key()
    data = load_all_data(wk_api_key)

    dispatch = {
        "memorize": cmd_memorize,
        "m": cmd_memorize,
        "lookup": cmd_lookup,
        "l": cmd_lookup,
        "prompt": cmd_prompt,
        "p": cmd_prompt,
    }
    dispatch[args.command](args, *data)


if __name__ == "__main__":
    main()
