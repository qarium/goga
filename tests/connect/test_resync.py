from __future__ import annotations

import importlib
import os
from pathlib import Path
from unittest import mock

import pytest
import yaml
from goga.connect import resync_registered_agents

_connect_module = importlib.import_module("goga.connect.connect")


def _write_registry(goga_home: Path, agents: dict[str, dict[str, bool]]) -> None:
    goga_home.mkdir(parents=True, exist_ok=True)
    (goga_home / "connect.yml").write_text(yaml.dump({"agents": agents}))


class TestResyncLogicPositive:
    """Positive behavioral scenarios (missing/empty registry, per-agent force, D1)."""

    def test_resync_missing_registry_returns_zero(self, tmp_path: Path) -> None:
        goga_home = tmp_path / ".goga"
        with mock.patch.object(_connect_module, "connect") as mock_connect:
            rc = resync_registered_agents(goga_home)
        assert rc == 0
        mock_connect.assert_not_called()

    def test_resync_empty_agents_returns_zero(self, tmp_path: Path) -> None:
        goga_home = tmp_path / ".goga"
        _write_registry(goga_home, {})
        with mock.patch.object(_connect_module, "connect") as mock_connect:
            rc = resync_registered_agents(goga_home)
        assert rc == 0
        mock_connect.assert_not_called()

    def test_resync_applies_per_agent_force_overwrite(self, tmp_path: Path) -> None:
        goga_home = tmp_path / ".goga"
        _write_registry(
            goga_home,
            {"claude": {"force_overwrite": False}, "codex": {"force_overwrite": True}},
        )
        with (
            mock.patch("pathlib.Path.home", return_value=goga_home.parent),
            mock.patch.object(_connect_module, "connect", return_value=0) as mock_connect,
        ):
            rc = resync_registered_agents(goga_home)
        assert rc == 0
        assert mock_connect.call_args_list == [
            mock.call(agents=["claude"], force_overwrite=False),
            mock.call(agents=["codex"], force_overwrite=True),
        ]

    def test_resync_overrides_home_to_goga_home_parent(self, tmp_path: Path) -> None:
        """D1: ``$HOME`` must point at ``goga_home.parent`` while ``connect`` runs.

        ``connect()`` resolves its central ``~/.goga`` root and each agent's
        target dir via ``Path.home()`` (which reads ``$HOME``). The re-sync only
        targets the owning installation if ``$HOME`` is redirected to
        ``goga_home.parent`` while ``connect()`` runs, and restored afterwards.
        """
        goga_home = tmp_path / "owner" / ".goga"
        _write_registry(goga_home, {"claude": {"force_overwrite": False}})

        seen: dict[str, Path] = {}
        original_home = os.environ.get("HOME")

        def fake_connect(agents: list[str], force_overwrite: bool = False) -> int:
            seen["home"] = Path.home()
            return 0

        with mock.patch.object(_connect_module, "connect", new=fake_connect):
            rc = resync_registered_agents(goga_home)

        assert rc == 0
        assert seen["home"] == goga_home.parent
        assert os.environ.get("HOME") == original_home


class TestResyncLogicNegative:
    """Negative behavioral scenarios (malformed registry)."""

    def test_resync_malformed_registry_returns_nonzero(self, tmp_path: Path) -> None:
        goga_home = tmp_path / ".goga"
        goga_home.mkdir(parents=True, exist_ok=True)
        (goga_home / "connect.yml").write_text("agents: [unclosed")
        with mock.patch.object(_connect_module, "connect") as mock_connect:
            rc = resync_registered_agents(goga_home)
        assert rc != 0
        mock_connect.assert_not_called()


class TestResyncLogicEdge:
    """Edge-case behavioral scenarios (partial failure, non-mapping top level)."""

    def test_resync_partial_failure_continues_and_returns_first(self, tmp_path: Path) -> None:
        goga_home = tmp_path / ".goga"
        _write_registry(
            goga_home,
            {
                "claude": {"force_overwrite": False},
                "codex": {"force_overwrite": False},
                "cursor": {"force_overwrite": False},
            },
        )
        with (
            mock.patch("pathlib.Path.home", return_value=goga_home.parent),
            mock.patch.object(_connect_module, "connect", side_effect=[1, 0, 0]) as mock_connect,
        ):
            rc = resync_registered_agents(goga_home)
        assert rc == 1
        assert mock_connect.call_count == 3

    def test_resync_non_mapping_top_level_returns_zero(self, tmp_path: Path) -> None:
        """A scalar/list at the YAML top level is treated as an empty registry.

        The ``isinstance(loaded, dict)`` guard turns any non-mapping document into
        a no-op rather than a parse failure (the document is valid YAML, just not
        the expected shape).
        """
        goga_home = tmp_path / ".goga"
        goga_home.mkdir(parents=True, exist_ok=True)
        (goga_home / "connect.yml").write_text("just a string")
        with mock.patch.object(_connect_module, "connect") as mock_connect:
            rc = resync_registered_agents(goga_home)
        assert rc == 0
        mock_connect.assert_not_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
