"""Assemble the prompt for LLM-based mnemonic generation."""

from .lookup import KanjiProfile, format_profile

SYSTEM_PROMPT_BASE = """\
You are a mnemonic generator for Japanese kanji, designed for someone who has studied \
all of WaniKani's radicals and kanji. You create vivid, memorable mnemonics in the \
WaniKani style.

## Your approach

### For meaning mnemonics:
- Use the WaniKani radical names as characters, objects, or actions in a short story
- The story should make the kanji's meaning feel inevitable from the components
- Keep it punchy — 2-4 sentences max
- Be concrete and visual, not abstract
- Humor, absurdity, and strong sensory details help memorability

### For reading mnemonics:
- The primary reading should be woven into the story via English wordplay or sound-alikes
- For on'yomi: find an English word/name/phrase that sounds like the reading
- For kun'yomi: same approach, find a phonetic hook
- When "Sound mnemonic characters" are listed for a reading, use those words/names \
as the phonetic hook — they are WaniKani's standard mnemonic words for those sounds

### For phonetic-semantic compounds:
- Lead with the phonetic-semantic relationship: "This kanji combines [semantic] for \
meaning and [phonetic] for the reading [X], which it shares with [other kanji in family]."
- Then give a shorter mnemonic focused mainly on the meaning, since the reading is \
already explained by the phonetic component
- Mention the phonetic family so the learner can build connections

### General guidelines:
- Never use romaji in the mnemonic — use hiragana for readings
- Bold the key reading hook word in the reading mnemonic
- If there are multiple important readings, address the primary one first, \
then briefly address the secondary
- If you don't recognize a component, say so — don't fabricate radical names
"""


def _katakana_to_hiragana(text: str) -> str:
    """Convert katakana to hiragana (ゴ → ご)."""
    return "".join(chr(ord(c) - 0x60) if "\u30a1" <= c <= "\u30f6" else c for c in text)


def _get_relevant_sound_mnemonics(profile: KanjiProfile, sound_mnemonics: dict) -> dict:
    """Find sound mnemonics relevant to this kanji's readings.

    Matches on'yomi (converted from katakana to hiragana) and kun'yomi stems
    (before the dot) against the sound mnemonics database (keyed in hiragana).
    Returns {reading: {"character": ..., "description": ...}}.

    When ``profile.important_reading`` is set (``"onyomi"`` or ``"kunyomi"``),
    only returns sound mnemonics for that reading type.
    """
    relevant = {}
    include_onyomi = profile.important_reading in (None, "onyomi")
    include_kunyomi = profile.important_reading in (None, "kunyomi")

    if include_onyomi:
        for reading in profile.onyomi:
            hiragana = _katakana_to_hiragana(reading)
            if hiragana in sound_mnemonics:
                relevant[hiragana] = sound_mnemonics[hiragana]
    if include_kunyomi:
        for reading in profile.kunyomi:
            # Strip okurigana: "かた.る" -> "かた"
            stem = reading.split(".")[0]
            if stem in sound_mnemonics:
                relevant[stem] = sound_mnemonics[stem]
    return relevant


def build_prompt(
    profile: KanjiProfile,
    user_context: str | None = None,
    sound_mnemonics: dict | None = None,
) -> str:
    """Build the user message for mnemonic generation."""
    parts = []

    parts.append("Generate a mnemonic for this kanji:\n")
    parts.append(format_profile(profile))

    if sound_mnemonics:
        relevant = _get_relevant_sound_mnemonics(profile, sound_mnemonics)
        if relevant:
            parts.append("\n── Sound mnemonic characters for this kanji ──")
            for reading, info in relevant.items():
                parts.append(
                    f"  {reading} → {info['character']} ({info['description']})"
                )

    if user_context:
        parts.append(f"\n── Additional context from user ──\n{user_context}")

    parts.append("\n── Please generate ──")
    parts.append(
        "1. **Meaning mnemonic**: A short story connecting the WK radical names to the meaning"
    )
    parts.append(
        "2. **Reading mnemonic**: A story/hook for remembering the primary reading"
    )

    if (
        profile.keisei_type in ("comp_phonetic", "comp_phonetic_inferred")
        and profile.phonetic_family
    ):
        parts.append(
            "3. **Phonetic family note**: A brief note about the phonetic pattern to reinforce"
        )

    return "\n".join(parts)


def get_system_prompt() -> str:
    return SYSTEM_PROMPT_BASE
