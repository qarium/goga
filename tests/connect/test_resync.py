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

    def test_resync_non_dict_or_keyless_entry_defaults_force_false(self, tmp_path: Path) -> None:
        """Non-dict entries and entries missing ``force_overwrite`` both default to False.

        Exercises the two defensive defaults: ``entry`` that is not a dict falls to
        ``False`` (``else`` branch of the ``isinstance(entry, dict)`` guard), and a
        dict entry without a ``force_overwrite`` key falls to ``False`` via
        ``.get("force_overwrite", False)``. Neither should crash nor hardcode True.
        """
        goga_home = tmp_path / ".goga"
        _write_registry(
            goga_home,
            {"claude": {"force_overwrite": True}, "codex": True, "cursor": {}},
        )
        with (
            mock.patch("pathlib.Path.home", return_value=goga_home.parent),
            mock.patch.object(_connect_module, "connect", return_value=0) as mock_connect,
        ):
            rc = resync_registered_agents(goga_home)
        assert rc == 0
        assert mock_connect.call_args_list == [
            mock.call(agents=["claude"], force_overwrite=True),
            mock.call(agents=["codex"], force_overwrite=False),  # non-dict entry → False
            mock.call(agents=["cursor"], force_overwrite=False),  # missing key → False
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

    def test_resync_agents_value_not_mapping_returns_zero(self, tmp_path: Path) -> None:
        """A dict top level whose ``agents:`` value is a list/scalar is a no-op.

        Distinct from the non-mapping top level: the document IS a mapping, but
        ``agents`` itself is not a mapping — the ``isinstance(agents, dict)`` guard
        turns it into a no-op (return 0), not a failure.
        """
        goga_home = tmp_path / ".goga"
        goga_home.mkdir(parents=True, exist_ok=True)
        (goga_home / "connect.yml").write_text("agents: [claude, codex]\n")
        with mock.patch.object(_connect_module, "connect") as mock_connect:
            rc = resync_registered_agents(goga_home)
        assert rc == 0
        mock_connect.assert_not_called()

    def test_resync_first_nonzero_returned_when_all_fail(self, tmp_path: Path) -> None:
        """When every agent fails, the FIRST non-zero result wins (not the last).

        The contract aggregates by remembering only the first non-zero result and
        continuing; a last-wins regression (``first_failure = rc``) would return 3
        here instead of 1.
        """
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
            mock.patch.object(_connect_module, "connect", side_effect=[1, 2, 3]) as mock_connect,
        ):
            rc = resync_registered_agents(goga_home)
        assert rc == 1
        assert mock_connect.call_count == 3

    def test_resync_restores_home_when_connect_raises(self, tmp_path: Path) -> None:
        """``$HOME`` is restored even when ``connect`` raises mid-loop (finally guarantee).

        The docstring promises ``$HOME`` is always restored on exit, even on error.
        An exception bubbling out of the loop must still run the ``finally`` block,
        and the exception itself must propagate (not be swallowed).
        """
        goga_home = tmp_path / "owner" / ".goga"
        _write_registry(goga_home, {"claude": {"force_overwrite": False}})
        original_home = os.environ.get("HOME")

        def raising_connect(agents: list[str], force_overwrite: bool = False) -> int:
            raise RuntimeError("boom")

        with (
            mock.patch("pathlib.Path.home", return_value=goga_home.parent),
            mock.patch.object(_connect_module, "connect", new=raising_connect),
            pytest.raises(RuntimeError),
        ):
            resync_registered_agents(goga_home)
        assert os.environ.get("HOME") == original_home


class TestResyncLogicUnreadableRegistry:
    """An unreadable/corrupt registry fails cleanly (non-zero) without a traceback."""

    def test_resync_directory_registry_returns_nonzero(self, tmp_path: Path) -> None:
        """``connect.yml`` existing as a directory raises IsADirectoryError (an OSError).

        The widened ``except`` catches it and returns non-zero with a diagnostic
        instead of crashing with a traceback.
        """
        goga_home = tmp_path / ".goga"
        goga_home.mkdir(parents=True, exist_ok=True)
        (goga_home / "connect.yml").mkdir()
        with mock.patch.object(_connect_module, "connect") as mock_connect:
            rc = resync_registered_agents(goga_home)
        assert rc != 0
        mock_connect.assert_not_called()

    def test_resync_corrupt_bytes_registry_returns_nonzero(self, tmp_path: Path) -> None:
        """Non-UTF-8 bytes raise UnicodeDecodeError on ``read_text()``.

        The widened ``except`` catches it (``UnicodeError``) and returns non-zero
        instead of crashing.
        """
        goga_home = tmp_path / ".goga"
        goga_home.mkdir(parents=True, exist_ok=True)
        (goga_home / "connect.yml").write_bytes(b"\xff\xfe\x00not valid utf-8")
        with mock.patch.object(_connect_module, "connect") as mock_connect:
            rc = resync_registered_agents(goga_home)
        assert rc != 0
        mock_connect.assert_not_called()


class TestResyncBanner:
    """Diagnostic banner emitted before the re-sync loop starts.

    A non-empty registry MUST print a one-line banner of the form
    ``Re-syncing <N> registered agent(s): <list>`` to stderr so the user can
    distinguish a re-sync run from a direct ``goga connect`` and see the full
    set of agents about to be processed. The banner MUST NOT be emitted for a
    missing, empty, or non-mapping registry (silent no-op).
    """

    def test_banner_lists_agents_with_count(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        goga_home = tmp_path / ".goga"
        _write_registry(
            goga_home,
            {"claude": {"force_overwrite": False}, "codex": {"force_overwrite": True}},
        )
        with (
            mock.patch("pathlib.Path.home", return_value=goga_home.parent),
            mock.patch.object(_connect_module, "connect", return_value=0),
        ):
            rc = resync_registered_agents(goga_home)

        assert rc == 0
        captured = capsys.readouterr()
        assert "Re-syncing 2 registered agent(s): claude, codex" in captured.err

    def test_banner_respects_agent_count_and_order(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        goga_home = tmp_path / ".goga"
        _write_registry(
            goga_home,
            {
                "cursor": {"force_overwrite": False},
                "claude": {"force_overwrite": False},
                "opencode": {"force_overwrite": False},
            },
        )
        with (
            mock.patch("pathlib.Path.home", return_value=goga_home.parent),
            mock.patch.object(_connect_module, "connect", return_value=0),
        ):
            rc = resync_registered_agents(goga_home)

        assert rc == 0
        captured = capsys.readouterr()
        # Count matches.
        assert "Re-syncing 3 registered agent(s)" in captured.err
        # All three agents appear in the banner (order is whatever YAML round-trip
        # produced — asserted as a set, not a sequence).
        banner_line = next(
            (line for line in captured.err.splitlines() if line.startswith("Re-syncing")),
            "",
        )
        assert "claude" in banner_line
        assert "cursor" in banner_line
        assert "opencode" in banner_line

    def test_no_banner_when_registry_missing(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        goga_home = tmp_path / ".goga"
        with mock.patch.object(_connect_module, "connect") as mock_connect:
            rc = resync_registered_agents(goga_home)

        assert rc == 0
        mock_connect.assert_not_called()
        captured = capsys.readouterr()
        assert "Re-syncing" not in captured.err

    def test_no_banner_when_agents_empty(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        goga_home = tmp_path / ".goga"
        _write_registry(goga_home, {})
        with mock.patch.object(_connect_module, "connect") as mock_connect:
            rc = resync_registered_agents(goga_home)

        assert rc == 0
        mock_connect.assert_not_called()
        captured = capsys.readouterr()
        assert "Re-syncing" not in captured.err

    def test_no_banner_on_malformed_registry(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        goga_home = tmp_path / ".goga"
        goga_home.mkdir(parents=True, exist_ok=True)
        (goga_home / "connect.yml").write_text("agents: [unclosed")
        with mock.patch.object(_connect_module, "connect") as mock_connect:
            rc = resync_registered_agents(goga_home)

        assert rc != 0
        mock_connect.assert_not_called()
        captured = capsys.readouterr()
        assert "Re-syncing" not in captured.err

    def test_no_banner_when_top_level_is_non_mapping(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        goga_home = tmp_path / ".goga"
        goga_home.mkdir(parents=True, exist_ok=True)
        (goga_home / "connect.yml").write_text("just a string")
        with mock.patch.object(_connect_module, "connect") as mock_connect:
            rc = resync_registered_agents(goga_home)

        assert rc == 0
        mock_connect.assert_not_called()
        captured = capsys.readouterr()
        assert "Re-syncing" not in captured.err


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
