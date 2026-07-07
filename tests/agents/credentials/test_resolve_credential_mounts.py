from __future__ import annotations

from pathlib import Path

import pytest
from goga.agents import resolve_credential_mounts as facade_fn
from goga.agents.credentials.resolve import resolve_credential_mounts as leaf_fn

# The routine resolves `~` via Path.expanduser(), which reads the HOME
# environment variable (NOT a monkeypatched Path.home). Redirecting $HOME to a
# temporary directory is therefore the correct way to control which credential
# files are detected in tests — it works uniformly across CPython 3.12/3.13.
CLAUDE_HOST_REL = Path(".claude/.credentials.json")
CODEX_HOST_REL = Path(".codex/auth.json")
OPENCODE_HOST_REL = Path(".local/share/opencode/auth.json")

CLAUDE_CONTAINER = "/home/goga/.claude/.credentials.json"
CODEX_CONTAINER = "/home/goga/.codex/auth.json"
OPENCODE_CONTAINER = "/home/goga/.local/share/opencode/auth.json"


def _write_credential(home: Path, rel: Path) -> None:
    """Create a credential file (and its parent dirs) under the fake home."""
    target = home / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("{}")


class TestResolveCredentialMountsContract:
    def test_facade_exports_resolve_credential_mounts(self) -> None:
        """The facade exposes `resolve_credential_mounts` as a callable.

        Per `goga/agents/CODEMANIFEST` re-export `->resolve_credential_mounts: {}`,
        the facade `goga.agents` is the single stable import point for the
        routine; the name must be importable directly and bound to a callable.
        """
        assert callable(facade_fn)

    def test_facade_consistent_with_leaf(self) -> None:
        """The facade re-exports the leaf callable itself (identity, not a copy)."""
        assert facade_fn is leaf_fn

    def test_callable_without_args(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """The routine is called with no arguments and returns without raising.

        Detection must never raise, even when nothing is present; an empty home
        yields an empty list.
        """
        monkeypatch.setenv("HOME", str(tmp_path))

        result = facade_fn()

        assert isinstance(result, list)

    def test_return_type_is_list_of_str_str_tuples(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Every returned item is a tuple[str, str] pair."""
        _write_credential(tmp_path, CODEX_HOST_REL)
        monkeypatch.setenv("HOME", str(tmp_path))

        result = facade_fn()

        assert isinstance(result, list)
        assert len(result) == 1
        host_path, container_path = result[0]
        assert isinstance(host_path, str)
        assert isinstance(container_path, str)

    def test_order_when_all_present(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Container paths follow the fixed table order: claude → codex → opencode."""
        _write_credential(tmp_path, CLAUDE_HOST_REL)
        _write_credential(tmp_path, CODEX_HOST_REL)
        _write_credential(tmp_path, OPENCODE_HOST_REL)
        monkeypatch.setenv("HOME", str(tmp_path))

        result = facade_fn()

        container_paths = [container for _, container in result]
        assert container_paths == [CLAUDE_CONTAINER, CODEX_CONTAINER, OPENCODE_CONTAINER]


class TestResolveCredentialMountsLogic:
    def test_resolve_credential_mounts_all_present(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """All three credential files present → three tuples, correct container paths."""
        _write_credential(tmp_path, CLAUDE_HOST_REL)
        _write_credential(tmp_path, CODEX_HOST_REL)
        _write_credential(tmp_path, OPENCODE_HOST_REL)
        monkeypatch.setenv("HOME", str(tmp_path))

        result = leaf_fn()

        assert len(result) == 3
        # host paths resolve against the redirected home
        assert result[0][0] == str(tmp_path / CLAUDE_HOST_REL)
        assert result[0][1] == CLAUDE_CONTAINER
        assert result[1][0] == str(tmp_path / CODEX_HOST_REL)
        assert result[1][1] == CODEX_CONTAINER
        assert result[2][0] == str(tmp_path / OPENCODE_HOST_REL)
        assert result[2][1] == OPENCODE_CONTAINER
        assert all(isinstance(host, str) and isinstance(container, str) for host, container in result)

    def test_resolve_credential_mounts_none_present(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """An empty home yields an empty list (no error surfaced)."""
        monkeypatch.setenv("HOME", str(tmp_path))

        result = leaf_fn()

        assert result == []

    def test_resolve_credential_mounts_partial_presence(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Only codex present → exactly one tuple with the codex container path."""
        _write_credential(tmp_path, CODEX_HOST_REL)
        monkeypatch.setenv("HOME", str(tmp_path))

        result = leaf_fn()

        assert len(result) == 1
        assert result[0][1] == CODEX_CONTAINER
