"""Contract and logic tests for the entity declared in
``goga/topics/CODEMANIFEST`` with ``location: ensuring.py``:

- ``ensure_topic(identifier, year)`` — the switch-or-create orchestration

The git boundary is mocked at the import point per the ``convention``
practice — no git binary and no repository are touched. The ref-tree
helper shared with the board is mocked at its owner (``goga.topics.board``);
the working-copy scenarios use ``tmp_path`` + ``monkeypatch.chdir`` with the
real history path routines, and the scale is the ``builtin_scale`` fixture.
The creation fallback of ``ensure_topic`` runs the REAL ``create_topic``
with its git boundary patched at ``goga.topics.creation``'s import points —
the same wiring the creation tests use.
"""

from __future__ import annotations

import inspect
import sys
import typing
from collections.abc import Callable
from pathlib import Path
from unittest import mock

import click
import pytest
from goga.history.statuses import StatusScale
from goga.topics import board, creation, ensure_topic, switching
from goga.topics.git import BranchRef

# --- Shared scenario helpers ---


def _trees_reader(trees: dict[str, list[str]]) -> Callable[..., list[str]]:
    """A ``read_ref_tree_paths`` stand-in answering by ref display name."""

    def read(ref: str, prefix: str) -> list[str]:
        assert prefix == ".goga/history/", "the resolution reads under the history root only"
        return [path for path in trees.get(ref, []) if path.startswith(prefix)]

    return read


def _wire_resolution(
    monkeypatch: pytest.MonkeyPatch,
    scale: StatusScale,
    inventory: list[BranchRef],
    trees: dict[str, list[str]],
    current: str | None,
) -> None:
    """Patch the resolution's import points: scale, git inventory, trees, branch."""
    monkeypatch.setattr(switching, "assemble_status_scale", lambda: scale)
    monkeypatch.setattr(switching, "list_branch_refs", lambda: inventory)
    monkeypatch.setattr(switching, "resolve_current_branch_name", lambda: current)
    monkeypatch.setattr(board, "read_ref_tree_paths", _trees_reader(trees))


def _wire_mutations(monkeypatch: pytest.MonkeyPatch, clean: bool = True) -> tuple[mock.Mock, mock.Mock, mock.Mock]:
    """Patch the switch mutations at their import points.

    Returns:
        The cleanliness probe, the local checkout, and the remote-tracking
        branch creation — all as recording mocks.
    """
    cleanliness = mock.Mock(return_value=clean)
    checkout = mock.Mock()
    remote_creation = mock.Mock()
    monkeypatch.setattr(switching, "is_working_tree_clean", cleanliness)
    monkeypatch.setattr(switching, "checkout_local_branch", checkout)
    monkeypatch.setattr(switching, "create_branch_from_remote_tracking", remote_creation)
    return cleanliness, checkout, remote_creation


def _wire_creation_boundary(
    monkeypatch: pytest.MonkeyPatch,
    inventory: list[BranchRef],
    current: str | None,
) -> mock.Mock:
    """Patch the creation fallback's import points inside ``goga.topics.creation``.

    Returns:
        The create-and-switch mutation as a recording mock — the only git
        mutation of the fallback.
    """
    monkeypatch.setattr(creation, "list_branch_refs", lambda: inventory)
    monkeypatch.setattr(creation, "resolve_current_branch_name", lambda: current)
    create_and_switch = mock.Mock()
    monkeypatch.setattr(creation, "create_and_switch_branch", create_and_switch)
    return create_and_switch


def _non_interactive(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make stdin a non-terminal — the re-ask path must abort cleanly."""
    monkeypatch.setattr(sys, "stdin", mock.Mock(**{"isatty.return_value": False}))


def _working_copy_topic(cwd: Path, year: str, slug: str, artifacts: list[str]) -> None:
    """Create the working-copy topic directory with its artifact files."""
    for artifact in artifacts:
        path = cwd / ".goga" / "history" / year / slug / artifact
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("artifact", encoding="utf-8")


def _twin_inventory() -> list[BranchRef]:
    """The design-scenario inventory: a local branch and its remote twin."""
    return [
        BranchRef(name="feat/a", remote=False),
        BranchRef(name="origin/feat/a", remote=True),
    ]


def _twin_trees() -> dict[str, list[str]]:
    """The design-scenario ref trees: one planned topic on both refs."""
    return {
        "feat/a": [".goga/history/2026/feat-a/plan.md"],
        "origin/feat/a": [".goga/history/2026/feat-a/plan.md"],
    }


# --- Contract tests ---


class TestEnsuringContract:
    def test_ensure_topic_is_importable_from_the_cell_facade(self) -> None:
        """``ensure_topic`` lives on the cell facade."""
        import goga.topics as cell

        assert cell.ensure_topic is ensure_topic
        assert "ensure_topic" in cell.__all__

    def test_ensure_topic_signature(self) -> None:
        """``ensure_topic(identifier, year=None) -> str``."""
        signature = inspect.signature(ensure_topic)
        assert list(signature.parameters) == ["identifier", "year"]
        assert all(
            parameter.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD for parameter in signature.parameters.values()
        )
        assert signature.parameters["year"].default is None
        hints = typing.get_type_hints(ensure_topic)
        assert hints == {"identifier": str, "year": str | None, "return": str}


# --- Logic tests ---


class TestEnsureTopic:
    def test_ensure_topic_zero_candidates_creates_fresh_work(
        self,
        builtin_scale: StatusScale,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Nothing hosts the identifier: the fallback creates the branch as
        entered and the topic directory of the year — the creation line."""
        monkeypatch.chdir(tmp_path)
        inventory = [BranchRef(name="main", remote=False)]
        trees = {"main": [".goga/history/2026/other/prd.md"]}
        _wire_resolution(monkeypatch, builtin_scale, inventory, trees, "main")
        _wire_mutations(monkeypatch, clean=True)
        create_and_switch = _wire_creation_boundary(monkeypatch, inventory, "main")

        result = ensure_topic("prune-history-and-new-status", "2026")

        assert result == "Created branch prune-history-and-new-status and topic 2026/prune-history-and-new-status"
        create_and_switch.assert_called_once_with("prune-history-and-new-status")
        assert (tmp_path / ".goga" / "history" / "2026" / "prune-history-and-new-status").is_dir()

    def test_ensure_topic_remote_tracking_twin_is_occupied(
        self,
        builtin_scale: StatusScale,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A remote-tracking twin of the name occupies it: clean error with
        the board hint, nothing created."""
        monkeypatch.chdir(tmp_path)
        inventory = [
            BranchRef(name="main", remote=False),
            BranchRef(name="origin/new-work", remote=True),
        ]
        trees = {"main": ["README.md"]}
        _wire_resolution(monkeypatch, builtin_scale, inventory, trees, "main")
        _wire_mutations(monkeypatch, clean=True)
        create_and_switch = _wire_creation_boundary(monkeypatch, inventory, "main")
        _non_interactive(monkeypatch)

        with pytest.raises(click.ClickException) as raised:
            ensure_topic("new-work", "2026")

        assert raised.value.message == (
            "remote-tracking branch 'new-work' already exists — run 'goga topics status' to see the board"
        )
        create_and_switch.assert_not_called()

    def test_ensure_topic_single_candidate_switches_without_creation(
        self,
        builtin_scale: StatusScale,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A hosted identifier takes the plain switch — the fallback never runs."""
        monkeypatch.chdir(tmp_path)
        inventory = [
            BranchRef(name="feat/a", remote=False),
            BranchRef(name="main", remote=False),
        ]
        trees = {"feat/a": [".goga/history/2026/feat-a/plan.md"], "main": ["README.md"]}
        _wire_resolution(monkeypatch, builtin_scale, inventory, trees, "main")
        _cleanliness, checkout, _remote_creation = _wire_mutations(monkeypatch, clean=True)
        create_and_switch = _wire_creation_boundary(monkeypatch, inventory, "main")

        result = ensure_topic("feat/a", "2026")

        assert result == "Switched to branch feat/a"
        checkout.assert_called_once_with("feat/a")
        create_and_switch.assert_not_called()

    def test_ensure_topic_idempotent_when_already_on_host(
        self,
        builtin_scale: StatusScale,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Already on the hosting branch: idempotent success, no probe, no
        mutation — creation included."""
        monkeypatch.chdir(tmp_path)
        _working_copy_topic(tmp_path, "2026", "feat-a", ["plan.md"])
        _wire_resolution(monkeypatch, builtin_scale, _twin_inventory(), _twin_trees(), "feat/a")
        cleanliness, checkout, _remote_creation = _wire_mutations(monkeypatch, clean=True)
        create_and_switch = _wire_creation_boundary(monkeypatch, _twin_inventory(), "feat/a")

        result = ensure_topic("feat/a")

        assert result == "Already on branch feat/a"
        cleanliness.assert_not_called()
        checkout.assert_not_called()
        create_and_switch.assert_not_called()

    def test_ensure_topic_multiple_candidates_fail_with_list_not_creation(
        self,
        builtin_scale: StatusScale,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Several candidates without a terminal fail with the numbered list —
        ambiguity never escapes into creation."""
        monkeypatch.chdir(tmp_path)
        inventory = [
            BranchRef(name="feat/a", remote=False),
            BranchRef(name="feat/ab", remote=False),
            BranchRef(name="main", remote=False),
        ]
        trees = {
            "feat/a": [".goga/history/2026/feat-a/plan.md"],
            "feat/ab": [".goga/history/2026/feat-ab/plan.md"],
            "main": ["README.md"],
        }
        _wire_resolution(monkeypatch, builtin_scale, inventory, trees, "main")
        cleanliness, checkout, _remote_creation = _wire_mutations(monkeypatch, clean=True)
        create_and_switch = _wire_creation_boundary(monkeypatch, inventory, "main")
        _non_interactive(monkeypatch)

        with pytest.raises(click.ClickException) as raised:
            ensure_topic("feat", "2026")

        assert "1)" in raised.value.message
        assert "2)" in raised.value.message
        cleanliness.assert_not_called()
        checkout.assert_not_called()
        create_and_switch.assert_not_called()

    def test_ensure_topic_empty_slug_identifier_clean_error(
        self,
        builtin_scale: StatusScale,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """An identifier normalizing to an empty slug is a clean error — no
        branch, no topic directory."""
        monkeypatch.chdir(tmp_path)
        inventory = [BranchRef(name="main", remote=False)]
        trees = {"main": ["README.md"]}
        _wire_resolution(monkeypatch, builtin_scale, inventory, trees, "main")
        _wire_mutations(monkeypatch, clean=True)
        create_and_switch = _wire_creation_boundary(monkeypatch, inventory, "main")
        _non_interactive(monkeypatch)

        with pytest.raises(click.ClickException) as raised:
            ensure_topic("БББ", "2026")

        assert raised.value.message == "branch name 'БББ' normalizes to an empty topic slug"
        create_and_switch.assert_not_called()
        assert not (tmp_path / ".goga" / "history" / "2026").exists()
