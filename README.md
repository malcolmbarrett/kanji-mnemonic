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

# Copy the example env file and fill in your keys
cp .env.example .env
# Then edit .env with your keys:
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

```bash
kanji --model claude-haiku-4-5-20241022 m 詠
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
  Phonetic component: 化 (WK: change)
  Family readings: か, け, げ
  Other kanji in this family:
    貨 — currency (か)
    靴 — shoes (か)
```

## Data sources

- **Keisei databases**: Phonetic-semantic composition data from [mwil/wanikani-userscripts](https://github.com/mwil/wanikani-userscripts)
- **WaniKani API**: Radical names and kanji component mappings
- **Claude**: Mnemonic generation

## Cache location

Data is cached at `~/.cache/kanji-mnemonic/`. Override with `KANJI_MNEMONIC_CACHE` env var.
