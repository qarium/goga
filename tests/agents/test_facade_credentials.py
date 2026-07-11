"""Integration tests for the ``goga.agents`` facade credential-mount flow.

Pins the cross-entity contract from ``goga/agents/CODEMANIFEST``: the facade
re-exports BOTH ``resolve_wrapper_path`` and ``resolve_credential_mounts``, and
the credential routine flows end-to-end from a credential file on disk to a
single ``(host_path, container_path)`` tuple with the fixed in-container path.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from goga.agents import resolve_credential_mounts, resolve_wrapper_path


class TestAgentsFacadeCredentialsIntegration:
    def test_facade_re_exports_both_routines(self) -> None:
        """The facade exposes both the wrapper and credential routines as callables.

        Per the ``goga/agents/CODEMANIFEST`` re-exports
        ``->resolve_wrapper_path: {}`` and ``->resolve_credential_mounts: {}``,
        the facade ``goga.agents`` is the single stable import point for both
        routines. Importing both names from the facade package must succeed and
        bind each to a callable object.
        """
        assert callable(resolve_wrapper_path)
        assert callable(resolve_credential_mounts)

    def test_resolve_wrapper_path_returns_canonical_path(self) -> None:
        """Sanity: the re-exported wrapper routine still resolves agent→wrapper path."""
        assert resolve_wrapper_path("codex") == "/home/goga/bin/codex-as-claude.sh"

    def test_end_to_end_codex_credential_detected(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """A codex credential under the redirected home yields exactly one tuple.

        The flow is exercised end-to-end: a credential file on disk is detected
        by the real ``resolve_credential_mounts`` and returned as a single
        ``(host_path, container_path)`` tuple with the fixed codex container path.
        ``resolve_credential_mounts`` resolves ``~`` via ``Path.expanduser()``,
        which reads ``$HOME`` directly on CPython 3.12+ (a ``Path.home`` patch has
        no effect), so the home is redirected via ``$HOME`` to isolate detection
        from the host's real credential files.
        """
        codex = tmp_path / ".codex" / "auth.json"
        codex.parent.mkdir(parents=True, exist_ok=True)
        codex.write_text("{}")
        monkeypatch.setenv("HOME", str(tmp_path))

        result = resolve_credential_mounts()

        assert isinstance(result, list)
        assert len(result) == 1
        host_path, container_path = result[0]
        assert isinstance(host_path, str)
        assert isinstance(container_path, str)
        assert container_path == "/home/goga/.codex/auth.json"
        assert host_path == str(tmp_path / ".codex" / "auth.json")
