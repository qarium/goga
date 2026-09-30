"""Integration: the topics command driving the real board pipeline.

Cross-package coverage (the topics command facade through the real
``goga.topics.board`` domain) moved from tests/commands/topics/test_topics.py
per the integration-suite placement rule. Only the git boundary inside
``goga.topics.board`` is canned; the deterministic scale comes from the shared
``builtin_scale`` fixture of ``tests/conftest.py``.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from unittest import mock

import pytest
from click.testing import CliRunner
from goga.commands.topics import topics
from goga.history import current_year
from goga.history.statuses import StatusScale
from goga.topics import board as topics_board
from goga.topics.git import BranchRef

# --- Integration tests (the real board pipeline through the real command) ---


def _trees_reader(trees: dict[str, list[str]]) -> Callable[..., list[str]]:
    """A ``read_ref_tree_paths`` stand-in answering by ref display name."""

    def read(ref: str, prefix: str) -> list[str]:
        assert prefix == ".goga/history/", "the board reads under the history root only"
        return [path for path in trees.get(ref, []) if path.startswith(prefix)]

    return read


def _files_reader(files: dict[tuple[str, str], str]) -> Callable[..., str | None]:
    """A ``read_ref_file`` stand-in answering by ``(ref, path)``.

    A key missing from the dict answers ``None`` — the mirror of the
    ``read_ref_file`` absence contract.
    """

    def read(ref: str, path: str) -> str | None:
        return files.get((ref, path))

    return read


def _base_inventory() -> list[BranchRef]:
    """The design-scenario inventory: two locals, two remote-tracking refs."""
    return [
        BranchRef(name="feat/a", remote=False),
        BranchRef(name="origin/feat/a", remote=True),
        BranchRef(name="origin/feat/b", remote=True),
        BranchRef(name="main", remote=False),
    ]


def _base_trees(year: str) -> dict[str, list[str]]:
    """The design-scenario ref trees: one planned topic, one defined topic."""
    return {
        "feat/a": [f".goga/history/{year}/feat-a/plan.md"],
        "origin/feat/a": [f".goga/history/{year}/feat-a/plan.md"],
        "origin/feat/b": [f".goga/history/{year}/feat-b/prd.md"],
        "main": ["README.md"],
    }


def _wire_domain_board(  # noqa: PLR0913, PLR0917 — the five board patch points plus the scenario files
    monkeypatch: pytest.MonkeyPatch,
    scale: StatusScale,
    inventory: list[BranchRef],
    trees: dict[str, list[str]],
    current: str | None,
    files: dict[tuple[str, str], str] | None = None,
) -> None:
    """Patch the five git-boundary import points inside ``goga.topics.board``.

    The command imports the facade functions, whose internals resolve these
    module-level names — patching here wires the REAL domain pipeline
    behind the canned git boundary, the ``_wire_board`` pattern of
    ``tests/topics/test_board.py``.

    Without ``files`` every ref todo reads as ``None`` — no todo.md at
    any ref.
    """
    monkeypatch.setattr(topics_board, "assemble_status_scale", lambda: scale)
    monkeypatch.setattr(topics_board, "list_branch_refs", lambda: inventory)
    monkeypatch.setattr(topics_board, "resolve_current_branch_name", lambda: current)
    monkeypatch.setattr(topics_board, "read_ref_tree_paths", _trees_reader(trees))
    monkeypatch.setattr(topics_board, "read_ref_file", _files_reader(files or {}))


def _base_scenario(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, scale: StatusScale) -> None:
    """Wire the base scenario: the working-copy topic and the canned git boundary."""
    year = current_year()
    working = tmp_path / ".goga" / "history" / year / "feat-a" / "plan.md"
    working.parent.mkdir(parents=True, exist_ok=True)
    working.write_text("artifact", encoding="utf-8")
    _wire_domain_board(monkeypatch, scale, _base_inventory(), _base_trees(year), "feat/a")


class TestTopicsBoardFlow:
    """Cross-entity: the real domain board pipeline through the real command.

    Only the git boundary inside ``goga.topics.board`` is canned, so these
    tests verify the wiring the unit tests mock away: the facade-import
    path, the collect-to-aggregate projection, the view dispatch, and the
    renderers — all real. ``COLUMNS`` is pinned to 100, so the
    four-column default grid caps every column at 22 and every line fits
    100 columns.
    """

    def test_default_view_renders_the_aggregated_entries(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, builtin_scale: StatusScale
    ) -> None:
        """board renders the real collect-to-aggregate pipeline as the four-column table."""
        monkeypatch.chdir(tmp_path)
        _base_scenario(monkeypatch, tmp_path, builtin_scale)

        with mock.patch.dict("os.environ", {"COLUMNS": "100"}):
            result = CliRunner().invoke(topics, ["board"])

        assert result.exit_code == 0
        lines = result.output.splitlines()
        header_cells = [cell.strip() for cell in lines[0].split("|") if cell.strip()]
        assert header_cells == ["Topic", "Branch", "Hosts", "Statuses"]
        # The current branch carries the marker; the remote own branch stays
        # visible in the branch column; both statuses render.
        assert "* feat-a" in result.output
        assert "origin/feat/b" in result.output
        assert "[defined]" in result.output
        assert "[planned]" in result.output
        assert all(len(line) <= 100 for line in lines)

    def test_per_host_view_renders_the_audit_records(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, builtin_scale: StatusScale
    ) -> None:
        """board --per-host renders the collected records as the three-column audit table."""
        monkeypatch.chdir(tmp_path)
        _base_scenario(monkeypatch, tmp_path, builtin_scale)

        with mock.patch.dict("os.environ", {"COLUMNS": "100"}):
            result = CliRunner().invoke(topics, ["board", "--per-host"])

        assert result.exit_code == 0
        lines = result.output.splitlines()
        header_cells = [cell.strip() for cell in lines[0].split("|") if cell.strip()]
        assert header_cells == ["Topic", "Branch", "Statuses"]
        # One row per record of the twin-collapsed pair: the marked local
        # feat-a row and the remote feat-b row — the remote twin is gone.
        assert "* feat-a" in result.output
        assert "feat-b" in result.output
        assert "origin/feat/a" not in result.output

    def test_json_view_prints_the_aggregated_entries(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, builtin_scale: StatusScale
    ) -> None:
        """board --json prints the pretty-printed projection of the aggregated entries."""
        monkeypatch.chdir(tmp_path)
        _base_scenario(monkeypatch, tmp_path, builtin_scale)

        result = CliRunner().invoke(topics, ["board", "--json"])

        assert result.exit_code == 0
        assert result.output.startswith("[\n    {")
        payload = json.loads(result.output)
        assert len(payload) == 2
        assert {item["topic"]: item["hosts"] for item in payload} == {
            "feat-a": ["feat/a"],
            "feat-b": ["origin/feat/b"],
        }

    def test_host_filter_through_the_whole_stack(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, builtin_scale: StatusScale
    ) -> None:
        """--host filters the rendered entries; an unknown name is the empty board, never an error."""
        monkeypatch.chdir(tmp_path)
        _base_scenario(monkeypatch, tmp_path, builtin_scale)

        with mock.patch.dict("os.environ", {"COLUMNS": "100"}):
            filtered = CliRunner().invoke(topics, ["board", "--host", "feat/a"])
            unknown = CliRunner().invoke(topics, ["board", "--host", "no-such-branch"])

        assert filtered.exit_code == 0
        assert "* feat-a" in filtered.output
        assert "feat-b" not in filtered.output
        assert unknown.exit_code == 0
        assert unknown.output == ""
