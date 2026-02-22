"""Tests for interactive mnemonic refinement loop (bd-2y4).

TDD tests defining the API contract for:
- Mnemonic storage (save/load to ~/.config/kanji/mnemonics.json)
- Interactive accept/retry/edit/quit loop in cmd_memorize
- --no-interactive flag
- 'kanji show' subcommand
"""

import argparse
import json
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def config_dir(tmp_path, monkeypatch):
    """Redirect CONFIG_DIR to a temp directory for mnemonic storage."""
    cfg = tmp_path / "config" / "kanji"
    cfg.mkdir(parents=True)
    monkeypatch.setattr("kanji_mnemonic.data.CONFIG_DIR", cfg)
    return cfg


@pytest.fixture
def mnemonics_file(config_dir):
    """Create a mnemonics.json file with sample data."""
    data = {
        "語": {
            "mnemonic": "Say something to five mouths and they will speak your language.",
            "model": "claude-sonnet-4-20250514",
            "timestamp": "2025-06-01T12:00:00",
        },
        "山": {
            "mnemonic": "Three peaks rising from the earth form a mountain.",
            "model": "claude-sonnet-4-20250514",
            "timestamp": "2025-06-01T13:00:00",
        },
    }
    (config_dir / "mnemonics.json").write_text(
        json.dumps(data, ensure_ascii=False), encoding="utf-8"
    )
    return config_dir / "mnemonics.json"


def _make_mock_client(text_chunks):
    """Create a mock Anthropic client whose stream yields the given text chunks."""
    mock_client = MagicMock()
    mock_stream = MagicMock()
    mock_stream.__enter__ = MagicMock(return_value=mock_stream)
    mock_stream.__exit__ = MagicMock(return_value=False)
    mock_stream.text_stream = iter(text_chunks)
    mock_client.messages.stream.return_value = mock_stream
    return mock_client


def _make_mock_stream(text_chunks):
    """Create a single mock stream context manager."""
    mock_stream = MagicMock()
    mock_stream.__enter__ = MagicMock(return_value=mock_stream)
    mock_stream.__exit__ = MagicMock(return_value=False)
    mock_stream.text_stream = iter(text_chunks)
    return mock_stream


# ---------------------------------------------------------------------------
# Tests: load_mnemonics()
# ---------------------------------------------------------------------------


class TestLoadMnemonics:
    """Tests for load_mnemonics() in data.py."""

    def test_loads_existing_file(self, config_dir, mnemonics_file):
        from kanji_mnemonic.data import load_mnemonics

        result = load_mnemonics()
        assert "語" in result
        assert "山" in result
        assert (
            result["語"]["mnemonic"]
            == "Say something to five mouths and they will speak your language."
        )
        assert result["語"]["model"] == "claude-sonnet-4-20250514"
        assert result["語"]["timestamp"] == "2025-06-01T12:00:00"

    def test_returns_empty_dict_when_file_missing(self, config_dir):
        """No mnemonics.json file -> empty dict, no error."""
        from kanji_mnemonic.data import load_mnemonics

        result = load_mnemonics()
        assert result == {}

    def test_returns_empty_dict_for_empty_json(self, config_dir):
        """mnemonics.json exists but contains empty object."""
        from kanji_mnemonic.data import load_mnemonics

        (config_dir / "mnemonics.json").write_text("{}", encoding="utf-8")
        result = load_mnemonics()
        assert result == {}


# ---------------------------------------------------------------------------
# Tests: load_mnemonic_for_kanji()
# ---------------------------------------------------------------------------


class TestLoadMnemonicForKanji:
    """Tests for load_mnemonic_for_kanji() in data.py."""

    def test_returns_entry_for_saved_kanji(self, config_dir, mnemonics_file):
        from kanji_mnemonic.data import load_mnemonic_for_kanji

        result = load_mnemonic_for_kanji("語")
        assert result is not None
        assert (
            result["mnemonic"]
            == "Say something to five mouths and they will speak your language."
        )
        assert result["model"] == "claude-sonnet-4-20250514"
        assert result["timestamp"] == "2025-06-01T12:00:00"

    def test_returns_none_for_unsaved_kanji(self, config_dir, mnemonics_file):
        from kanji_mnemonic.data import load_mnemonic_for_kanji

        result = load_mnemonic_for_kanji("龘")
        assert result is None

    def test_returns_none_when_file_missing(self, config_dir):
        from kanji_mnemonic.data import load_mnemonic_for_kanji

        result = load_mnemonic_for_kanji("語")
        assert result is None


# ---------------------------------------------------------------------------
# Tests: save_mnemonic()
# ---------------------------------------------------------------------------


class TestSaveMnemonic:
    """Tests for save_mnemonic() in data.py."""

    def test_saves_new_mnemonic(self, config_dir):
        from kanji_mnemonic.data import save_mnemonic

        save_mnemonic("語", "A great mnemonic", "claude-sonnet-4-20250514")
        data = json.loads((config_dir / "mnemonics.json").read_text(encoding="utf-8"))
        assert "語" in data
        assert data["語"]["mnemonic"] == "A great mnemonic"
        assert data["語"]["model"] == "claude-sonnet-4-20250514"
        assert "timestamp" in data["語"]

    def test_updates_existing_mnemonic(self, config_dir, mnemonics_file):
        from kanji_mnemonic.data import save_mnemonic

        save_mnemonic("語", "Updated mnemonic", "claude-haiku-4-5-20251001")
        data = json.loads((config_dir / "mnemonics.json").read_text(encoding="utf-8"))
        assert data["語"]["mnemonic"] == "Updated mnemonic"
        assert data["語"]["model"] == "claude-haiku-4-5-20251001"
        # Other entries untouched
        assert (
            data["山"]["mnemonic"]
            == "Three peaks rising from the earth form a mountain."
        )

    def test_creates_directory_if_missing(self, tmp_path, monkeypatch):
        from kanji_mnemonic.data import save_mnemonic

        cfg = tmp_path / "nonexistent" / "config"
        monkeypatch.setattr("kanji_mnemonic.data.CONFIG_DIR", cfg)
        save_mnemonic("語", "A mnemonic", "test-model")
        assert (cfg / "mnemonics.json").exists()
        data = json.loads((cfg / "mnemonics.json").read_text(encoding="utf-8"))
        assert data["語"]["mnemonic"] == "A mnemonic"

    def test_timestamp_is_iso_format(self, config_dir):
        from kanji_mnemonic.data import save_mnemonic

        save_mnemonic("語", "A mnemonic", "test-model")
        data = json.loads((config_dir / "mnemonics.json").read_text(encoding="utf-8"))
        # Should not raise
        datetime.fromisoformat(data["語"]["timestamp"])

    def test_storage_format_structure(self, config_dir):
        """Validate the exact JSON schema: {kanji: {mnemonic, model, timestamp}}."""
        from kanji_mnemonic.data import save_mnemonic

        save_mnemonic("語", "Test mnemonic", "test-model")
        data = json.loads((config_dir / "mnemonics.json").read_text(encoding="utf-8"))
        entry = data["語"]
        assert set(entry.keys()) == {"mnemonic", "model", "timestamp"}
        assert isinstance(entry["mnemonic"], str)
        assert isinstance(entry["model"], str)
        assert isinstance(entry["timestamp"], str)


# ---------------------------------------------------------------------------
# Tests: Interactive loop — accept
# ---------------------------------------------------------------------------


class TestInteractiveAccept:
    """Tests for the accept path in the interactive refinement loop."""

    def test_accept_keeps_saved_mnemonic(
        self,
        config_dir,
        monkeypatch,
        sample_kanji_db,
        sample_phonetic_db,
        sample_wk_kanji_db,
        sample_wk_radicals,
        sample_wk_kanji_subjects,
        sample_kradfile,
    ):
        """Typing 'a' at the prompt keeps the auto-saved mnemonic."""
        from kanji_mnemonic.cli import cmd_memorize
        from kanji_mnemonic.data import load_mnemonics

        mock_client = _make_mock_client(["Generated ", "mnemonic ", "text"])
        monkeypatch.setattr(
            "kanji_mnemonic.cli.get_anthropic_client", lambda: mock_client
        )
        monkeypatch.setattr("builtins.input", MagicMock(return_value="a"))

        args = argparse.Namespace(
            kanji=["語"], context=None, model="test-model", no_interactive=False
        )
        cmd_memorize(
            args,
            sample_kanji_db,
            sample_phonetic_db,
            sample_wk_kanji_db,
            sample_wk_radicals,
            sample_wk_kanji_subjects,
            sample_kradfile,
            None,
            {},
            {},
        )

        saved = load_mnemonics()
        assert "語" in saved
        assert saved["語"]["mnemonic"] == "Generated mnemonic text"

    def test_accept_prints_streamed_mnemonic(
        self,
        config_dir,
        capsys,
        monkeypatch,
        sample_kanji_db,
        sample_phonetic_db,
        sample_wk_kanji_db,
        sample_wk_radicals,
        sample_wk_kanji_subjects,
        sample_kradfile,
    ):
        """The streamed text appears in stdout before the prompt."""
        from kanji_mnemonic.cli import cmd_memorize

        mock_client = _make_mock_client(["Hello ", "world"])
        monkeypatch.setattr(
            "kanji_mnemonic.cli.get_anthropic_client", lambda: mock_client
        )
        monkeypatch.setattr("builtins.input", MagicMock(return_value="a"))

        args = argparse.Namespace(
            kanji=["語"], context=None, model="test-model", no_interactive=False
        )
        cmd_memorize(
            args,
            sample_kanji_db,
            sample_phonetic_db,
            sample_wk_kanji_db,
            sample_wk_radicals,
            sample_wk_kanji_subjects,
            sample_kradfile,
            None,
            {},
            {},
        )

        output = capsys.readouterr().out
        assert "Hello world" in output


# ---------------------------------------------------------------------------
# Tests: Interactive loop — retry
# ---------------------------------------------------------------------------


class TestInteractiveRetry:
    """Tests for the retry path in the interactive refinement loop."""

    def test_retry_regenerates_then_accept(
        self,
        config_dir,
        monkeypatch,
        sample_kanji_db,
        sample_phonetic_db,
        sample_wk_kanji_db,
        sample_wk_radicals,
        sample_wk_kanji_subjects,
        sample_kradfile,
    ):
        """Typing 'r' triggers a second stream call, then 'a' accepts."""
        from kanji_mnemonic.cli import cmd_memorize

        stream1 = _make_mock_stream(["First ", "attempt"])
        stream2 = _make_mock_stream(["Second ", "attempt"])
        mock_client = MagicMock()
        mock_client.messages.stream.side_effect = [stream1, stream2]

        monkeypatch.setattr(
            "kanji_mnemonic.cli.get_anthropic_client", lambda: mock_client
        )
        monkeypatch.setattr("builtins.input", MagicMock(side_effect=["r", "a"]))

        args = argparse.Namespace(
            kanji=["語"], context=None, model="test-model", no_interactive=False
        )
        cmd_memorize(
            args,
            sample_kanji_db,
            sample_phonetic_db,
            sample_wk_kanji_db,
            sample_wk_radicals,
            sample_wk_kanji_subjects,
            sample_kradfile,
            None,
            {},
            {},
        )

        assert mock_client.messages.stream.call_count == 2

    def test_retry_overwrites_previous_save(
        self,
        config_dir,
        monkeypatch,
        sample_kanji_db,
        sample_phonetic_db,
        sample_wk_kanji_db,
        sample_wk_radicals,
        sample_wk_kanji_subjects,
        sample_kradfile,
    ):
        """After retry, the saved mnemonic is the new one, not the original."""
        from kanji_mnemonic.cli import cmd_memorize
        from kanji_mnemonic.data import load_mnemonics

        stream1 = _make_mock_stream(["First ", "attempt"])
        stream2 = _make_mock_stream(["Second ", "attempt"])
        mock_client = MagicMock()
        mock_client.messages.stream.side_effect = [stream1, stream2]

        monkeypatch.setattr(
            "kanji_mnemonic.cli.get_anthropic_client", lambda: mock_client
        )
        monkeypatch.setattr("builtins.input", MagicMock(side_effect=["r", "a"]))

        args = argparse.Namespace(
            kanji=["語"], context=None, model="test-model", no_interactive=False
        )
        cmd_memorize(
            args,
            sample_kanji_db,
            sample_phonetic_db,
            sample_wk_kanji_db,
            sample_wk_radicals,
            sample_wk_kanji_subjects,
            sample_kradfile,
            None,
            {},
            {},
        )

        saved = load_mnemonics()
        assert saved["語"]["mnemonic"] == "Second attempt"


# ---------------------------------------------------------------------------
# Tests: Interactive loop — edit
# ---------------------------------------------------------------------------


class TestInteractiveEdit:
    """Tests for the edit path in the interactive refinement loop."""

    def test_edit_opens_editor_and_saves_result(
        self,
        config_dir,
        monkeypatch,
        sample_kanji_db,
        sample_phonetic_db,
        sample_wk_kanji_db,
        sample_wk_radicals,
        sample_wk_kanji_subjects,
        sample_kradfile,
    ):
        """Typing 'e' launches EDITOR; edited content replaces the saved mnemonic."""
        from kanji_mnemonic.cli import cmd_memorize
        from kanji_mnemonic.data import load_mnemonics

        mock_client = _make_mock_client(["Original ", "text"])
        monkeypatch.setattr(
            "kanji_mnemonic.cli.get_anthropic_client", lambda: mock_client
        )
        monkeypatch.setattr("builtins.input", MagicMock(side_effect=["e", "a"]))

        def fake_editor(cmd):
            # cmd is ["editor", "/tmp/xxx"] or similar
            Path(cmd[-1]).write_text("Edited mnemonic text", encoding="utf-8")
            return 0

        monkeypatch.setattr("subprocess.call", fake_editor)
        monkeypatch.setenv("EDITOR", "fake-editor")

        args = argparse.Namespace(
            kanji=["語"], context=None, model="test-model", no_interactive=False
        )
        cmd_memorize(
            args,
            sample_kanji_db,
            sample_phonetic_db,
            sample_wk_kanji_db,
            sample_wk_radicals,
            sample_wk_kanji_subjects,
            sample_kradfile,
            None,
            {},
            {},
        )

        saved = load_mnemonics()
        assert saved["語"]["mnemonic"] == "Edited mnemonic text"

    def test_edit_falls_back_to_vi_when_no_editor(
        self,
        config_dir,
        monkeypatch,
        sample_kanji_db,
        sample_phonetic_db,
        sample_wk_kanji_db,
        sample_wk_radicals,
        sample_wk_kanji_subjects,
        sample_kradfile,
    ):
        """When $EDITOR is not set, falls back to vi."""
        from kanji_mnemonic.cli import cmd_memorize

        mock_client = _make_mock_client(["Some ", "text"])
        monkeypatch.setattr(
            "kanji_mnemonic.cli.get_anthropic_client", lambda: mock_client
        )
        monkeypatch.setattr("builtins.input", MagicMock(side_effect=["e", "a"]))
        monkeypatch.delenv("EDITOR", raising=False)
        monkeypatch.delenv("VISUAL", raising=False)

        captured_cmd = []

        def fake_editor(cmd):
            captured_cmd.extend(cmd)
            # Write back the same content so the mnemonic isn't empty
            Path(cmd[-1]).write_text("Some text", encoding="utf-8")
            return 0

        monkeypatch.setattr("subprocess.call", fake_editor)

        args = argparse.Namespace(
            kanji=["語"], context=None, model="test-model", no_interactive=False
        )
        cmd_memorize(
            args,
            sample_kanji_db,
            sample_phonetic_db,
            sample_wk_kanji_db,
            sample_wk_radicals,
            sample_wk_kanji_subjects,
            sample_kradfile,
            None,
            {},
            {},
        )

        assert captured_cmd[0] == "vi"

    def test_edit_preserves_original_on_empty_result(
        self,
        config_dir,
        monkeypatch,
        sample_kanji_db,
        sample_phonetic_db,
        sample_wk_kanji_db,
        sample_wk_radicals,
        sample_wk_kanji_subjects,
        sample_kradfile,
    ):
        """If the editor produces an empty file, the original mnemonic is kept."""
        from kanji_mnemonic.cli import cmd_memorize
        from kanji_mnemonic.data import load_mnemonics

        mock_client = _make_mock_client(["Original ", "text"])
        monkeypatch.setattr(
            "kanji_mnemonic.cli.get_anthropic_client", lambda: mock_client
        )
        monkeypatch.setattr("builtins.input", MagicMock(side_effect=["e", "a"]))
        monkeypatch.setenv("EDITOR", "fake-editor")

        def fake_editor(cmd):
            # Write empty content
            Path(cmd[-1]).write_text("", encoding="utf-8")
            return 0

        monkeypatch.setattr("subprocess.call", fake_editor)

        args = argparse.Namespace(
            kanji=["語"], context=None, model="test-model", no_interactive=False
        )
        cmd_memorize(
            args,
            sample_kanji_db,
            sample_phonetic_db,
            sample_wk_kanji_db,
            sample_wk_radicals,
            sample_wk_kanji_subjects,
            sample_kradfile,
            None,
            {},
            {},
        )

        saved = load_mnemonics()
        assert saved["語"]["mnemonic"] == "Original text"


# ---------------------------------------------------------------------------
# Tests: Interactive loop — quit
# ---------------------------------------------------------------------------


class TestInteractiveQuit:
    """Tests for the quit path in the interactive refinement loop."""

    def test_quit_keeps_saved_mnemonic(
        self,
        config_dir,
        monkeypatch,
        sample_kanji_db,
        sample_phonetic_db,
        sample_wk_kanji_db,
        sample_wk_radicals,
        sample_wk_kanji_subjects,
        sample_kradfile,
    ):
        """Typing 'q' exits the loop but the auto-saved mnemonic remains."""
        from kanji_mnemonic.cli import cmd_memorize
        from kanji_mnemonic.data import load_mnemonics

        mock_client = _make_mock_client(["Quit ", "test"])
        monkeypatch.setattr(
            "kanji_mnemonic.cli.get_anthropic_client", lambda: mock_client
        )
        monkeypatch.setattr("builtins.input", MagicMock(return_value="q"))

        args = argparse.Namespace(
            kanji=["語"], context=None, model="test-model", no_interactive=False
        )
        cmd_memorize(
            args,
            sample_kanji_db,
            sample_phonetic_db,
            sample_wk_kanji_db,
            sample_wk_radicals,
            sample_wk_kanji_subjects,
            sample_kradfile,
            None,
            {},
            {},
        )

        saved = load_mnemonics()
        assert "語" in saved
        assert saved["語"]["mnemonic"] == "Quit test"

    def test_quit_exits_without_error(
        self,
        config_dir,
        capsys,
        monkeypatch,
        sample_kanji_db,
        sample_phonetic_db,
        sample_wk_kanji_db,
        sample_wk_radicals,
        sample_wk_kanji_subjects,
        sample_kradfile,
    ):
        """Quit does not raise an exception or produce error output."""
        from kanji_mnemonic.cli import cmd_memorize

        mock_client = _make_mock_client(["Quit ", "test"])
        monkeypatch.setattr(
            "kanji_mnemonic.cli.get_anthropic_client", lambda: mock_client
        )
        monkeypatch.setattr("builtins.input", MagicMock(return_value="q"))

        args = argparse.Namespace(
            kanji=["語"], context=None, model="test-model", no_interactive=False
        )
        cmd_memorize(
            args,
            sample_kanji_db,
            sample_phonetic_db,
            sample_wk_kanji_db,
            sample_wk_radicals,
            sample_wk_kanji_subjects,
            sample_kradfile,
            None,
            {},
            {},
        )

        captured = capsys.readouterr()
        assert captured.err == ""


# ---------------------------------------------------------------------------
# Tests: --no-interactive flag
# ---------------------------------------------------------------------------


class TestNoInteractive:
    """Tests for the --no-interactive / -n flag."""

    def test_no_interactive_saves_and_returns(
        self,
        config_dir,
        monkeypatch,
        sample_kanji_db,
        sample_phonetic_db,
        sample_wk_kanji_db,
        sample_wk_radicals,
        sample_wk_kanji_subjects,
        sample_kradfile,
    ):
        """With --no-interactive, the mnemonic is saved without prompting."""
        from kanji_mnemonic.cli import cmd_memorize
        from kanji_mnemonic.data import load_mnemonics

        mock_client = _make_mock_client(["Auto ", "saved"])
        monkeypatch.setattr(
            "kanji_mnemonic.cli.get_anthropic_client", lambda: mock_client
        )
        mock_input = MagicMock()
        monkeypatch.setattr("builtins.input", mock_input)

        args = argparse.Namespace(
            kanji=["語"], context=None, model="test-model", no_interactive=True
        )
        cmd_memorize(
            args,
            sample_kanji_db,
            sample_phonetic_db,
            sample_wk_kanji_db,
            sample_wk_radicals,
            sample_wk_kanji_subjects,
            sample_kradfile,
            None,
            {},
            {},
        )

        mock_input.assert_not_called()
        saved = load_mnemonics()
        assert saved["語"]["mnemonic"] == "Auto saved"

    def test_no_interactive_prints_mnemonic(
        self,
        config_dir,
        capsys,
        monkeypatch,
        sample_kanji_db,
        sample_phonetic_db,
        sample_wk_kanji_db,
        sample_wk_radicals,
        sample_wk_kanji_subjects,
        sample_kradfile,
    ):
        """The streamed mnemonic is still printed to stdout in non-interactive mode."""
        from kanji_mnemonic.cli import cmd_memorize

        mock_client = _make_mock_client(["Printed ", "text"])
        monkeypatch.setattr(
            "kanji_mnemonic.cli.get_anthropic_client", lambda: mock_client
        )
        monkeypatch.setattr("builtins.input", MagicMock())

        args = argparse.Namespace(
            kanji=["語"], context=None, model="test-model", no_interactive=True
        )
        cmd_memorize(
            args,
            sample_kanji_db,
            sample_phonetic_db,
            sample_wk_kanji_db,
            sample_wk_radicals,
            sample_wk_kanji_subjects,
            sample_kradfile,
            None,
            {},
            {},
        )

        output = capsys.readouterr().out
        assert "Printed text" in output

    def test_no_interactive_flag_parsing(self, monkeypatch):
        """'kanji memorize -n' and '--no-interactive' set args.no_interactive=True."""
        from kanji_mnemonic.cli import main

        mock_data = ({}, {}, {}, {}, {}, {}, {}, {}, {})
        monkeypatch.setattr("kanji_mnemonic.cli.get_wk_api_key", lambda: None)
        monkeypatch.setattr("kanji_mnemonic.cli.load_all_data", lambda key: mock_data)

        mock_cmd = MagicMock()
        monkeypatch.setattr("kanji_mnemonic.cli.cmd_memorize", mock_cmd)

        monkeypatch.setattr("sys.argv", ["kanji", "memorize", "-n", "語"])
        main()

        mock_cmd.assert_called_once()
        args = mock_cmd.call_args[0][0]
        assert args.no_interactive is True


# ---------------------------------------------------------------------------
# Tests: cmd_show subcommand
# ---------------------------------------------------------------------------


class TestCmdShow:
    """Tests for 'kanji show' CLI command."""

    def test_show_displays_saved_mnemonic(self, config_dir, mnemonics_file, capsys):
        from kanji_mnemonic.cli import cmd_show

        args = argparse.Namespace(kanji=["語"])
        cmd_show(args)

        output = capsys.readouterr().out
        assert "語" in output
        assert (
            "Say something to five mouths and they will speak your language." in output
        )

    def test_show_includes_model_and_timestamp(
        self, config_dir, mnemonics_file, capsys
    ):
        from kanji_mnemonic.cli import cmd_show

        args = argparse.Namespace(kanji=["語"])
        cmd_show(args)

        output = capsys.readouterr().out
        assert "claude-sonnet-4-20250514" in output
        assert "2025-06-01" in output

    def test_show_not_found_message(self, config_dir, capsys):
        from kanji_mnemonic.cli import cmd_show

        args = argparse.Namespace(kanji=["龘"])
        cmd_show(args)

        output = capsys.readouterr().out
        assert "龘" in output
        # Should indicate no saved mnemonic
        assert "no saved mnemonic" in output.lower() or "not found" in output.lower()


# ---------------------------------------------------------------------------
# Tests: show command dispatch
# ---------------------------------------------------------------------------


class TestShowCommandDispatch:
    """Tests for main() routing to show command."""

    def _setup_mocks(self, monkeypatch):
        mock_data = ({}, {}, {}, {}, {}, {}, {}, {}, {})
        monkeypatch.setattr("kanji_mnemonic.cli.get_wk_api_key", lambda: None)
        monkeypatch.setattr("kanji_mnemonic.cli.load_all_data", lambda key: mock_data)

    def test_show_command_dispatch(self, monkeypatch, config_dir):
        """'kanji show 語' dispatches to cmd_show with correct args."""
        from kanji_mnemonic.cli import main

        self._setup_mocks(monkeypatch)
        mock_cmd = MagicMock()
        monkeypatch.setattr("kanji_mnemonic.cli.cmd_show", mock_cmd)
        monkeypatch.setattr("sys.argv", ["kanji", "show", "語"])
        main()
        mock_cmd.assert_called_once()
        args = mock_cmd.call_args[0][0]
        assert args.kanji == ["語"]

    def test_show_alias_s_dispatch(self, monkeypatch, config_dir):
        """'kanji s 語' dispatches to cmd_show (alias)."""
        from kanji_mnemonic.cli import main

        self._setup_mocks(monkeypatch)
        mock_cmd = MagicMock()
        monkeypatch.setattr("kanji_mnemonic.cli.cmd_show", mock_cmd)
        monkeypatch.setattr("sys.argv", ["kanji", "s", "語"])
        main()
        mock_cmd.assert_called_once()

    def test_show_skips_data_loading(self, monkeypatch, config_dir):
        """'kanji show' does NOT call load_all_data."""
        from kanji_mnemonic.cli import main

        mock_load = MagicMock()
        monkeypatch.setattr("kanji_mnemonic.cli.load_all_data", mock_load)

        mock_cmd = MagicMock()
        monkeypatch.setattr("kanji_mnemonic.cli.cmd_show", mock_cmd)

        monkeypatch.setattr("sys.argv", ["kanji", "show", "語"])
        main()

        mock_load.assert_not_called()


# ---------------------------------------------------------------------------
# Tests: Auto-save timing
# ---------------------------------------------------------------------------


class TestAutoSaveTiming:
    """Tests that mnemonic is saved before the interactive prompt."""

    def test_mnemonic_saved_before_prompt(
        self,
        config_dir,
        monkeypatch,
        sample_kanji_db,
        sample_phonetic_db,
        sample_wk_kanji_db,
        sample_wk_radicals,
        sample_wk_kanji_subjects,
        sample_kradfile,
    ):
        """The mnemonic is written to disk before input() is called."""
        from kanji_mnemonic.cli import cmd_memorize

        mock_client = _make_mock_client(["Saved ", "first"])
        monkeypatch.setattr(
            "kanji_mnemonic.cli.get_anthropic_client", lambda: mock_client
        )

        def check_file_exists_then_accept(prompt=""):
            # At the time input() is called, the mnemonic should already be on disk
            path = config_dir / "mnemonics.json"
            assert path.exists(), "mnemonics.json should exist before input() is called"
            data = json.loads(path.read_text(encoding="utf-8"))
            assert "語" in data, "語 entry should exist before input() is called"
            assert data["語"]["mnemonic"] == "Saved first"
            return "a"

        monkeypatch.setattr("builtins.input", check_file_exists_then_accept)

        args = argparse.Namespace(
            kanji=["語"], context=None, model="test-model", no_interactive=False
        )
        cmd_memorize(
            args,
            sample_kanji_db,
            sample_phonetic_db,
            sample_wk_kanji_db,
            sample_wk_radicals,
            sample_wk_kanji_subjects,
            sample_kradfile,
            None,
            {},
            {},
        )
