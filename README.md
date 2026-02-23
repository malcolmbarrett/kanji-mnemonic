# kanji

A CLI tool for generating kanji mnemonics using WaniKani radical names and phonetic-semantic composition data from the [Keisei script](https://github.com/mwil/wanikani-userscripts).

## How it works

Given a kanji, the tool:

1. **Decomposes** it into components using WaniKani's radical vocabulary (via the WK API)
2. **Classifies** it using the Keisei phonetic-semantic database — is it a phonetic-semantic compound, pictograph, compound indicative, etc.?
3. **Finds the phonetic family** — if the kanji is a phonetic-semantic compound, it shows you which other kanji share the same phonetic component and reading
4. **Assembles** all this context into a structured prompt
5. **Sends** it to Claude to generate a WaniKani-style mnemonic

## Setup

```bash
# Clone or download this directory, then:
cd kanji-mnemonic

# Create a .env file with your API keys:
#   ANTHROPIC_API_KEY=sk-ant-...
#   WK_API_KEY=your-wanikani-api-key

# Install as a global CLI tool
just install
```

Get your WK API key at https://www.wanikani.com/settings/personal_access_tokens. It's optional but strongly recommended — it lets the tool resolve kanji components to their WaniKani radical names. On first run, it downloads and caches the Keisei databases and WK radical data (~one-time setup).

The `.env` file is loaded from the current working directory. If you want a global config, place it at `~/.config/kanji/.env` instead.

After editing code, run `just reinstall` to pick up changes.

## Usage

### Generate a mnemonic

```bash
kanji memorize 詠
# or shorthand:
kanji m 詠
```

After generating, you'll be prompted to **[a]ccept**, **[r]etry** (regenerate), **[e]dit** (open in `$EDITOR`), or **[q]uit**. Mnemonics are auto-saved to `~/.config/kanji/mnemonics.json`.

### Multiple kanji at once

```bash
kanji m 詠 詩 誠
```

### Add personal context

```bash
kanji m 待 -c "I always confuse this with 持 because they look similar"
```

### Just look up the profile (no LLM call)

```bash
kanji lookup 詠
kanji l 詠
```

### Inspect the assembled prompt

```bash
kanji prompt 詠
kanji p 詠
```

### Use a different model

The default model is `claude-sonnet-4-6`. Override with `--model`:

```bash
kanji --model claude-haiku-4-5 m 詠
```

### Name a radical

When a component doesn't have a WaniKani name, give it your own:

```bash
kanji name 隹 "old bird"
```

### List your personal radical names

```bash
kanji names
```

### Show a saved mnemonic

```bash
kanji show 詠
kanji s 詠
```

### Set a personal decomposition

Override the auto-detected decomposition for a kanji. You can use characters or radical names as parts, and mark phonetic/semantic roles:

```bash
kanji decompose 骸 骨 亥
kanji d 骸 -s 骨 -p 亥          # mark semantic (-s) and phonetic (-p) components
kanji d 骸                       # show saved decomposition
kanji d 骸 --remove              # remove it
```

### Override the primary reading

By default, the tool infers whether on'yomi or kun'yomi is most important. Override this persistently or for a single generation:

```bash
kanji reading 詠 kunyomi         # persistent override
kanji reading 詠                 # show current override
kanji reading 詠 --remove        # remove it
kanji readings                   # list all overrides

kanji m 待 --primary kunyomi     # one-shot override (not saved)
```

### Sound mnemonics

Sound mnemonics map on'yomi readings to memorable characters/descriptions. The tool ships with WaniKani-derived defaults; you can add your own:

```bash
kanji sound こう Koichi "The WK founder"   # add personal sound mnemonic
kanji sound こう                            # show mnemonic for a reading
kanji sound こう --remove                   # remove it
kanji sounds                                # list all (WK + personal)
kanji sounds --personal                     # list only your additions
```

Sound mnemonics are automatically included in the LLM prompt when relevant to the kanji's readings.

### Additional flags

```bash
kanji m 詠 --no-infer            # disable KRADFILE-based phonetic inference
kanji l 詠 --all-decomp          # show both personal and auto-detected decompositions
kanji l 詠 --sound               # show relevant sound mnemonics for this kanji
```

### Skip the interactive prompt

By default, `memorize` enters an interactive loop where you can accept, retry, edit, or quit. Use `-n` to skip it:

```bash
kanji m -n 詠
```

### Clear cached data

```bash
kanji clear-cache
```

## Example output

```
$ kanji l 花

═══ 花 ═══
Meaning: flower
WaniKani Level: 5
On'yomi: か, け
Kun'yomi: はな
Important reading: onyomi

Type: Phonetic-Semantic Compound (形声)
WaniKani Components:
  艹 → Flowers
  化 → Change

── Phonetic-Semantic Breakdown ──
  Semantic (meaning hint): 艹 (Flowers)
  Phonetic (reading hint):  化 (Change)

── Phonetic Family ──
  Phonetic component: 化 (change)
  Family readings: か, け, げ
  Other kanji in this family:
    貨 — currency (か)
    靴 — shoes (か)
```

## Data sources

- **Keisei databases**: Phonetic-semantic composition data from [mwil/wanikani-userscripts](https://github.com/mwil/wanikani-userscripts)
- **WaniKani API**: Radical names and kanji component mappings
- **KRADFILE-u**: Visual radical decomposition for ~13k kanji (fallback for non-WK kanji)
- **Kanjidic2**: Meanings, on'yomi, kun'yomi from [jmdict-simplified](https://github.com/scriptin/jmdict-simplified) (fallback for non-WK kanji)
- **Claude**: Mnemonic generation

## File locations

- **Cache**: `~/.cache/kanji-mnemonic/` — downloaded databases (override with `KANJI_MNEMONIC_CACHE` env var)
- **Config**: `~/.config/kanji/` — personal data files (override with `KANJI_MNEMONIC_CONFIG` env var):
  - `radicals.json` — personal radical names
  - `mnemonics.json` — saved generated mnemonics
  - `decompositions.json` — personal kanji decompositions
  - `reading_overrides.json` — primary reading overrides
  - `sound_mnemonics.json` — personal sound mnemonic overrides
