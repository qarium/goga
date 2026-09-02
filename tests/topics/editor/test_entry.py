"""Contract and logic tests for the entities declared in
``goga/topics/editor/CODEMANIFEST`` with ``location: entry.py``:

- ``edit_text(initial=None)`` — the interactive multi-line text entry
  session in the external editor

The editor is mocked with a shell script exported as ``$EDITOR`` per
the ``editor`` practice and the TTY detection with a ``sys.stdin``
stand-in — a real editor never launches in tests. The session's
temporary file lives in the system temp directory and is unlinked by
the editor facility, so the working tree of the test repository stays
untouched.
"""

from __future__ import annotations

import inspect
import sys
import typing
from pathlib import Path
from unittest import mock

import click
import pytest
from goga.topics.editor import edit_text

# --- Contract tests ---


class TestEntryContract:
    def test_edit_text_is_importable_from_the_cell_facade(self) -> None:
        """``edit_text`` lives on the cell facade as the only export."""
        import goga.topics.editor as cell

        assert cell.edit_text is edit_text
        assert cell.__all__ == ["edit_text"]

    def test_declared_signature(self) -> None:
        """The routine takes exactly the declared parameter."""
        assert list(inspect.signature(edit_text).parameters) == ["initial"]

    def test_parameter_is_positional_or_keyword_with_contract_hints(self) -> None:
        """``initial`` binds positionally and by keyword, defaults to None."""
        parameters = inspect.signature(edit_text).parameters
        parameter = parameters["initial"]

        assert parameter.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
        assert parameter.default is None
        assert typing.get_type_hints(edit_text) == {"initial": str | None, "return": str | None}

        signature = inspect.signature(edit_text)
        signature.bind()
        signature.bind("text")
        signature.bind(initial="text")


# --- Editor and terminal stand-ins ---


def _editor_script(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, body: str) -> None:
    """Export ``$EDITOR`` as an executable shell script running ``body``."""
    editors = tmp_path / "editors"
    editors.mkdir(exist_ok=True)

    script = editors / "editor-mock.sh"
    script.write_text(f"#!/bin/sh\n{body}\n", encoding="utf-8")
    script.chmod(0o755)

    monkeypatch.delenv("VISUAL", raising=False)
    monkeypatch.setenv("EDITOR", str(script))


def _tty(monkeypatch: pytest.MonkeyPatch, isatty: bool) -> None:
    """Stand in for ``sys.stdin`` with a pinned TTY answer."""
    monkeypatch.setattr(sys, "stdin", mock.Mock(**{"isatty.return_value": isatty}))


def _repo(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """An empty repository working tree as the current directory."""
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.chdir(repo)

    return repo


def _tree_of(repo: Path) -> list[str]:
    """Every path of the working tree, relative and sorted."""
    return sorted(str(path.relative_to(repo)) for path in repo.rglob("*"))


# --- Logic tests ---


class TestEditText:
    def test_edit_text_saves_text_as_entered(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """The saved text comes back verbatim — interior blank line kept, nothing trimmed."""
        _editor_script(monkeypatch, tmp_path, "printf 'Fix retries.\\n\\nIgnore the cap.\\n' > \"$1\"")
        _tty(monkeypatch, isatty=True)

        assert edit_text() == "Fix retries.\n\nIgnore the cap.\n"

    def test_edit_text_unchanged_save_cancels(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """An editor that never writes cancels the entry — the working tree untouched."""
        repo = _repo(monkeypatch, tmp_path)
        _editor_script(monkeypatch, tmp_path, "exit 0")
        _tty(monkeypatch, isatty=True)

        assert edit_text(initial="Old text.\n") is None
        assert _tree_of(repo) == []

    def test_edit_text_initial_without_newline_normalized(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """A prefill without a trailing newline is normalized before the equality check."""
        _tty(monkeypatch, isatty=True)

        _editor_script(monkeypatch, tmp_path, "exit 0")
        assert edit_text(initial="Old text.") is None

        _editor_script(monkeypatch, tmp_path, "printf 'Old text.\\n' > \"$1\"")
        assert edit_text(initial="Old text.") is None

    def test_edit_text_non_tty_clean_error(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """No terminal — a clean error before the hint and the editor launch."""
        marker = tmp_path / "editors" / "launched.marker"
        marker.parent.mkdir(exist_ok=True)
        _editor_script(monkeypatch, tmp_path, f"printf launched > '{marker}'")
        _tty(monkeypatch, isatty=False)

        with pytest.raises(click.ClickException, match="interactive"):
            edit_text("text")

        assert not marker.exists()

    def test_edit_text_failed_editor_clean_error(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """A non-zero editor exit is a clean error — no working-tree file touched."""
        repo = _repo(monkeypatch, tmp_path)
        _editor_script(monkeypatch, tmp_path, "exit 3")
        _tty(monkeypatch, isatty=True)

        with pytest.raises(click.ClickException, match="Editing failed"):
            edit_text("text")

        assert _tree_of(repo) == []

    def test_edit_text_blank_only_save_cancels(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """A saved file of only blank lines cancels the entry."""
        _editor_script(monkeypatch, tmp_path, "printf '\\n\\n  \\n' > \"$1\"")
        _tty(monkeypatch, isatty=True)

        assert edit_text() is None
