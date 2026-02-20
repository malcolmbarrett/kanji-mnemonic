# Install kanji CLI globally via uv tool
install:
    uv tool install --editable .

# Reinstall (after code changes)
reinstall:
    uv tool install --editable --force .

# Uninstall the global CLI
uninstall:
    uv tool uninstall kanji-mnemonic

# Sync project dependencies
sync:
    uv sync

# Clear cached kanji databases
clear-cache:
    kanji clear-cache

# Quick lookup (no LLM)
lookup *KANJI:
    kanji lookup {{KANJI}}

# Generate mnemonic
memorize *ARGS:
    kanji memorize {{ARGS}}

# Run tests
test *ARGS:
    uv run pytest {{ARGS}}

# Run tests with coverage
test-cov *ARGS:
    uv run pytest --cov=kanji_mnemonic --cov-report=term-missing {{ARGS}}
