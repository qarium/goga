"""Contract and logic tests for the entities declared in
``goga/topics/CODEMANIFEST`` with ``location: switching.py``:

- ``SwitchCandidate(branch, topic, statuses, current, remote)`` — one
  candidate of a switch-identifier resolution
- ``resolve_switch_candidates(identifier, year)`` — the read-only resolution
- ``switch_topic(identifier, year)`` — the switching orchestration

The git boundary is mocked at the import point per the ``convention``
practice — no git binary and no repository are touched. The ref-tree
helper shared with the board is mocked at its owner (``goga.topics.board``);
the working-copy scenarios use ``tmp_path`` + ``monkeypatch.chdir`` with the
real history path routines, and the scale is the ``builtin_scale`` fixture.
"""

from __future__ import annotations

import dataclasses
import inspect
import subprocess
import sys
import typing
from collections.abc import Callable
from pathlib import Path
from unittest import mock

import click
import pytest
from goga.history import current_year
from goga.history.statuses import StatusScale
from goga.topics import (
    SwitchCandidate,
    board,
    resolve_switch_candidates,
    switch_topic,
    switching,
)
from goga.topics.git import BranchRef

from tests.conftest import is_kw_only_dataclass

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


def _non_interactive(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make stdin a non-terminal — the re-ask path must abort cleanly."""
    monkeypatch.setattr(sys, "stdin", mock.Mock(**{"isatty.return_value": False}))


def _interactive(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make stdin a terminal — the todo entry of the switch is reachable."""
    monkeypatch.setattr(sys, "stdin", mock.Mock(**{"isatty.return_value": True}))


def _wire_entry(monkeypatch: pytest.MonkeyPatch) -> mock.Mock:
    """Patch the todo entry at its import point in ``switching``.

    Returns:
        The entry — a recording mock.
    """
    entry = mock.Mock(return_value=True)
    monkeypatch.setattr(switching, "enter_topic_todo", entry)
    return entry


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


class TestSwitchingContract:
    def test_entities_are_importable_from_the_cell_facade(self) -> None:
        """``SwitchCandidate`` and the two switch routines live on the cell facade."""
        import goga.topics as cell

        assert cell.SwitchCandidate is SwitchCandidate
        assert cell.resolve_switch_candidates is resolve_switch_candidates
        assert cell.switch_topic is switch_topic
        for name in ("SwitchCandidate", "resolve_switch_candidates", "switch_topic"):
            assert name in cell.__all__

    def test_switch_candidate_is_a_frozen_kw_only_dataclass(self) -> None:
        """``@dataclass(frozen=True, kw_only=True)`` with the five declared fields."""
        assert dataclasses.is_dataclass(SwitchCandidate)
        assert SwitchCandidate.__dataclass_params__.frozen is True
        assert is_kw_only_dataclass(SwitchCandidate)
        assert typing.get_type_hints(SwitchCandidate) == {
            "branch": str,
            "topic": str | None,
            "statuses": list[str],
            "current": bool,
            "remote": bool,
        }
        candidate = SwitchCandidate(branch="feat/a", topic="feat-a", statuses=["planned"], current=True, remote=False)
        assert candidate.branch == "feat/a"
        assert candidate.topic == "feat-a"
        assert candidate.statuses == ["planned"]
        assert candidate.current is True
        assert candidate.remote is False
        with pytest.raises(dataclasses.FrozenInstanceError):
            candidate.branch = "other"  # type: ignore[misc]
        with pytest.raises(TypeError):
            SwitchCandidate("feat/a", "feat-a", ["planned"], True, False)  # type: ignore[misc]

    def test_resolve_switch_candidates_signature(self) -> None:
        """``resolve_switch_candidates(identifier, year=None) -> list[...]``."""
        signature = inspect.signature(resolve_switch_candidates)
        assert list(signature.parameters) == ["identifier", "year"]
        assert all(
            parameter.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD for parameter in signature.parameters.values()
        )
        assert signature.parameters["year"].default is None
        hints = typing.get_type_hints(resolve_switch_candidates)
        assert hints == {
            "identifier": str,
            "year": str | None,
            "return": list[SwitchCandidate],
        }

    def test_switch_topic_signature(self) -> None:
        """``switch_topic(identifier, todo=False, year=None) -> str``."""
        signature = inspect.signature(switch_topic)
        assert list(signature.parameters) == ["identifier", "todo", "year"]
        assert all(
            parameter.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD for parameter in signature.parameters.values()
        )
        assert signature.parameters["todo"].default is False
        assert signature.parameters["year"].default is None
        hints = typing.get_type_hints(switch_topic)
        assert hints == {"identifier": str, "todo": bool, "year": str | None, "return": str}


# --- Logic tests: resolution ---


class TestResolveSwitchCandidates:
    def test_resolve_switch_candidates_exact_before_prefix(
        self,
        builtin_scale: StatusScale,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """An exact tier always excludes the prefix tier of the same input."""
        monkeypatch.chdir(tmp_path)
        inventory = [
            BranchRef(name="feat/a", remote=False),
            BranchRef(name="feat/ab", remote=False),
            BranchRef(name="main", remote=False),
        ]
        trees = {
            "feat/a": [".goga/history/2026/feat-a/plan.md"],
            "feat/ab": [".goga/history/2026/feat-ab/prd.md"],
            "main": ["README.md"],
        }
        _wire_resolution(monkeypatch, builtin_scale, inventory, trees, None)

        exact_branch = resolve_switch_candidates("feat/a", "2026")
        assert [(c.branch, c.topic) for c in exact_branch] == [("feat/a", "feat-a")]

        exact_slug = resolve_switch_candidates("feat-ab", "2026")
        assert [(c.branch, c.topic) for c in exact_slug] == [("feat/ab", "feat-ab")]

        prefix = resolve_switch_candidates("feat", "2026")
        assert [(c.branch, c.topic) for c in prefix] == [
            ("feat/a", "feat-a"),
            ("feat/ab", "feat-ab"),
        ]

    def test_resolve_switch_candidates_branch_without_topic(
        self,
        builtin_scale: StatusScale,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A branch without a topic is a valid candidate — ``q4:A``."""
        monkeypatch.chdir(tmp_path)
        inventory = [
            BranchRef(name="feat/a", remote=False),
            BranchRef(name="main", remote=False),
        ]
        trees = {"feat/a": [".goga/history/2026/feat-a/plan.md"], "main": ["README.md"]}
        _wire_resolution(monkeypatch, builtin_scale, inventory, trees, None)

        candidates = resolve_switch_candidates("main", "2026")

        assert len(candidates) == 1
        assert candidates[0].branch == "main"
        assert candidates[0].topic is None
        assert candidates[0].statuses == []

    def test_resolve_switch_candidates_empty_slug_identifier(
        self,
        builtin_scale: StatusScale,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A non-ASCII identifier resolves by exact branch name only."""
        monkeypatch.chdir(tmp_path)
        inventory = [
            BranchRef(name="🚀", remote=False),
            BranchRef(name="feat/a", remote=False),
        ]
        trees = {"feat/a": [".goga/history/2026/feat-a/plan.md"]}
        _wire_resolution(monkeypatch, builtin_scale, inventory, trees, "🚀")

        candidates = resolve_switch_candidates("🚀", "2026")

        assert [(c.branch, c.topic, c.statuses) for c in candidates] == [("🚀", None, [])]

    def test_resolve_switch_candidates_orders_local_before_remote(
        self,
        builtin_scale: StatusScale,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Within a tier: locals first, then by branch, then by topic."""
        monkeypatch.chdir(tmp_path)
        inventory = [
            BranchRef(name="origin/zz", remote=True),
            BranchRef(name="feat/a", remote=False),
            BranchRef(name="origin/aa", remote=True),
        ]
        trees = {
            "feat/a": [".goga/history/2026/feat-x/plan.md"],
            "origin/aa": [".goga/history/2026/feat-x/prd.md"],
            "origin/zz": [".goga/history/2026/feat-x/adr.md"],
        }
        _wire_resolution(monkeypatch, builtin_scale, inventory, trees, None)

        candidates = resolve_switch_candidates("feat-x", "2026")

        assert [(c.branch, c.remote, c.statuses) for c in candidates] == [
            ("feat/a", False, ["planned"]),
            ("origin/aa", True, ["defined"]),
            ("origin/zz", True, ["discovered"]),
        ]

    def test_resolve_switch_candidates_local_beats_remote_twin(
        self,
        builtin_scale: StatusScale,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A branch and its remote twin hosting one slug resolve to the local
        branch — an unambiguous slug never reaches a prompt."""
        monkeypatch.chdir(tmp_path)
        _wire_resolution(monkeypatch, builtin_scale, _twin_inventory(), _twin_trees(), None)

        candidates = resolve_switch_candidates("feat-a", "2026")

        assert [(c.branch, c.remote) for c in candidates] == [("feat/a", False)]

    def test_resolve_switch_candidates_branch_appears_once(
        self,
        builtin_scale: StatusScale,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A branch hosting several topics of the year is one candidate — the
        branch never repeats in the tier list."""
        monkeypatch.chdir(tmp_path)
        inventory = [
            BranchRef(name="main", remote=False),
            BranchRef(name="other", remote=False),
        ]
        trees = {
            "main": [
                ".goga/history/2026/feat-b/plan.md",
                ".goga/history/2026/feat-a/prd.md",
            ],
            "other": ["README.md"],
        }
        _wire_resolution(monkeypatch, builtin_scale, inventory, trees, "other")

        candidates = resolve_switch_candidates("main", "2026")

        # The first entry of the tier order (branch, then topic) carries the
        # branch — the alphabetically first hosted topic.
        assert [(c.branch, c.topic, c.statuses) for c in candidates] == [("main", "feat-a", ["defined"])]

    def test_resolve_switch_candidates_working_copy_of_current_branch(
        self,
        builtin_scale: StatusScale,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The current branch's statuses come from the working copy."""
        monkeypatch.chdir(tmp_path)
        _working_copy_topic(tmp_path, "2026", "feat-a", ["plan.md"])
        inventory = [
            BranchRef(name="feat/a", remote=False),
            BranchRef(name="origin/other", remote=True),
        ]
        trees = {
            "feat/a": [".goga/history/2026/feat-a/notes.txt"],
            "origin/other": [".goga/history/2026/feat-a/notes.txt"],
        }
        _wire_resolution(monkeypatch, builtin_scale, inventory, trees, "feat/a")

        candidates = resolve_switch_candidates("feat-a", "2026")

        # The uncommitted plan.md is visible on the current branch; the same
        # topic on another ref reads the ref tree only.
        assert [(c.branch, c.statuses, c.current) for c in candidates] == [
            ("feat/a", ["planned"], True),
            ("origin/other", ["empty"], False),
        ]


# --- Logic tests: switching ---


class TestSwitchTopic:
    def test_switch_topic_single_candidate_switches(
        self,
        builtin_scale: StatusScale,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """One local candidate, clean tree: checkout and the result line."""
        monkeypatch.chdir(tmp_path)
        inventory = [
            BranchRef(name="feat/a", remote=False),
            BranchRef(name="main", remote=False),
        ]
        trees = {"feat/a": [".goga/history/2026/feat-a/plan.md"], "main": ["README.md"]}
        _wire_resolution(monkeypatch, builtin_scale, inventory, trees, "main")
        _cleanliness, checkout, _creation = _wire_mutations(monkeypatch, clean=True)

        result = switch_topic("feat/a", year="2026")

        assert result == "Switched to branch feat/a"
        checkout.assert_called_once_with("feat/a")

    def test_switch_topic_slug_with_pushed_twin_switches_local(
        self,
        builtin_scale: StatusScale,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A slug hosted by a branch and its remote twin checks out the local
        branch — the twin never turns an unambiguous switch into a prompt."""
        monkeypatch.chdir(tmp_path)
        inventory = [
            BranchRef(name="main", remote=False),
            BranchRef(name="feat/a", remote=False),
            BranchRef(name="origin/feat/a", remote=True),
        ]
        trees = {**_twin_trees(), "main": ["README.md"]}
        _wire_resolution(monkeypatch, builtin_scale, inventory, trees, "main")
        _cleanliness, checkout, creation = _wire_mutations(monkeypatch, clean=True)

        result = switch_topic("feat-a", year="2026")

        assert result == "Switched to branch feat/a"
        checkout.assert_called_once_with("feat/a")
        creation.assert_not_called()

    def test_switch_topic_branch_hosting_several_topics_switches(
        self,
        builtin_scale: StatusScale,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """An exact branch name hosting several topics of the year is one
        candidate — the switch proceeds without a selection prompt."""
        monkeypatch.chdir(tmp_path)
        inventory = [
            BranchRef(name="main", remote=False),
            BranchRef(name="other", remote=False),
        ]
        trees = {
            "main": [
                ".goga/history/2026/feat-b/plan.md",
                ".goga/history/2026/feat-a/prd.md",
            ],
            "other": ["README.md"],
        }
        _wire_resolution(monkeypatch, builtin_scale, inventory, trees, "other")
        _cleanliness, checkout, _creation = _wire_mutations(monkeypatch, clean=True)

        result = switch_topic("main", year="2026")

        assert result == "Switched to branch main"
        checkout.assert_called_once_with("main")

    def test_switch_topic_idempotent_when_already_on_host(
        self,
        builtin_scale: StatusScale,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Already on the host: idempotent success, no probe, no mutation."""
        monkeypatch.chdir(tmp_path)
        _working_copy_topic(tmp_path, "2026", "feat-a", ["plan.md"])
        _wire_resolution(monkeypatch, builtin_scale, _twin_inventory(), _twin_trees(), "feat/a")
        cleanliness, checkout, creation = _wire_mutations(monkeypatch, clean=True)

        result = switch_topic("feat/a")

        assert result == "Already on branch feat/a"
        cleanliness.assert_not_called()
        checkout.assert_not_called()
        creation.assert_not_called()

    def test_switch_topic_dirty_tree_clean_error(
        self,
        builtin_scale: StatusScale,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A dirty working tree is a clean error — and no git switch."""
        monkeypatch.chdir(tmp_path)
        inventory = [
            BranchRef(name="feat/a", remote=False),
            BranchRef(name="main", remote=False),
        ]
        trees = {"feat/a": [".goga/history/2026/feat-a/plan.md"], "main": ["README.md"]}
        _wire_resolution(monkeypatch, builtin_scale, inventory, trees, "main")
        _cleanliness, checkout, _creation = _wire_mutations(monkeypatch, clean=False)

        with pytest.raises(click.ClickException) as raised:
            switch_topic("feat/a", year="2026")

        assert raised.value.message == "working tree is dirty — commit or stash before switching"
        checkout.assert_not_called()

    def test_switch_topic_remote_only_creates_branch(
        self,
        builtin_scale: StatusScale,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A remote-only host: the local branch is created from the ref."""
        monkeypatch.chdir(tmp_path)
        inventory = [BranchRef(name="origin/feat/b", remote=True)]
        trees = {"origin/feat/b": [".goga/history/2026/feat-b/prd.md"]}
        _wire_resolution(monkeypatch, builtin_scale, inventory, trees, None)
        _cleanliness, checkout, creation = _wire_mutations(monkeypatch, clean=True)

        result = switch_topic("feat-b", year="2026")

        assert result == "Created branch feat/b from origin/feat/b"
        checkout.assert_not_called()
        creation.assert_called_once_with(BranchRef(name="origin/feat/b", remote=True))

    def test_switch_topic_multiple_candidates_prompt(
        self,
        builtin_scale: StatusScale,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Several candidates: the numbered list, then the number prompt."""
        monkeypatch.chdir(tmp_path)
        inventory = [
            BranchRef(name="feat/a", remote=False),
            BranchRef(name="feat/ab", remote=False),
        ]
        trees = {
            "feat/a": [".goga/history/2026/feat-a/plan.md"],
            "feat/ab": [".goga/history/2026/feat-ab/prd.md"],
        }
        _wire_resolution(monkeypatch, builtin_scale, inventory, trees, None)
        _cleanliness, checkout, _creation = _wire_mutations(monkeypatch, clean=True)
        monkeypatch.setattr(sys, "stdin", mock.Mock(**{"isatty.return_value": True}))
        prompt = mock.Mock(return_value=2)
        monkeypatch.setattr(click, "prompt", prompt)

        result = switch_topic("feat", year="2026")

        assert result == "Switched to branch feat/ab"
        checkout.assert_called_once_with("feat/ab")
        assert prompt.call_args.args[0] == "Select a branch by number"
        prompt_type = prompt.call_args.kwargs["type"]
        assert isinstance(prompt_type, click.IntRange)
        assert (prompt_type.min, prompt_type.max) == (1, 2)
        captured = capsys.readouterr()
        assert "1) feat/a (feat-a) [planned]" in captured.out
        assert "2) feat/ab (feat-ab) [defined]" in captured.out

    def test_switch_topic_prompt_rejects_out_of_range_input(
        self,
        builtin_scale: StatusScale,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """The prompt is bounded by ``IntRange(1, N)`` — a bad answer re-asks."""
        monkeypatch.chdir(tmp_path)
        inventory = [
            BranchRef(name="feat/a", remote=False),
            BranchRef(name="feat/ab", remote=False),
        ]
        trees = {
            "feat/a": [".goga/history/2026/feat-a/plan.md"],
            "feat/ab": [".goga/history/2026/feat-ab/prd.md"],
        }
        _wire_resolution(monkeypatch, builtin_scale, inventory, trees, None)
        _cleanliness, checkout, _creation = _wire_mutations(monkeypatch, clean=True)
        monkeypatch.setattr(sys, "stdin", mock.Mock(**{"isatty.return_value": True}))
        answers = iter(["9", "2"])
        monkeypatch.setattr(click.termui, "visible_prompt_func", lambda _text: next(answers))

        result = switch_topic("feat", year="2026")

        assert result == "Switched to branch feat/ab"
        checkout.assert_called_once_with("feat/ab")
        assert next(answers, None) is None, "both answers were consumed by the re-asking prompt"
        captured = capsys.readouterr()
        # The out-of-range complaint came through click's own error echo.
        assert "not in the range" in captured.out + captured.err

    def test_switch_topic_no_candidates_clean_error(
        self,
        builtin_scale: StatusScale,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """An identifier nothing hosts is a clean error with a board hint."""
        monkeypatch.chdir(tmp_path)
        inventory = [BranchRef(name="main", remote=False)]
        _wire_resolution(monkeypatch, builtin_scale, inventory, {"main": ["README.md"]}, None)
        _cleanliness, checkout, _creation = _wire_mutations(monkeypatch, clean=True)

        with pytest.raises(click.ClickException) as raised:
            switch_topic("nope")

        assert raised.value.message == ("no branch hosts 'nope' — run 'goga topics board' to see the board")
        checkout.assert_not_called()

    def test_switch_topic_non_interactive_multiple_candidates_fails_with_list(
        self,
        builtin_scale: StatusScale,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Several candidates without a terminal: the list is the clean error."""
        monkeypatch.chdir(tmp_path)
        inventory = [
            BranchRef(name="feat/a", remote=False),
            BranchRef(name="feat/ab", remote=False),
        ]
        trees = {
            "feat/a": [".goga/history/2026/feat-a/plan.md"],
            "feat/ab": [".goga/history/2026/feat-ab/prd.md"],
        }
        _wire_resolution(monkeypatch, builtin_scale, inventory, trees, None)
        cleanliness, checkout, creation = _wire_mutations(monkeypatch, clean=True)
        monkeypatch.setattr(sys, "stdin", mock.Mock(**{"isatty.return_value": False}))

        with pytest.raises(click.ClickException) as raised:
            switch_topic("feat", year="2026")

        assert "feat/a" in raised.value.message
        assert "feat/ab" in raised.value.message
        assert "1)" in raised.value.message
        assert "2)" in raised.value.message
        cleanliness.assert_not_called()
        checkout.assert_not_called()
        creation.assert_not_called()


# --- Logic tests: switching with the todo entry ---


class TestSwitchTopicTodo:
    def test_switch_topic_todo_enters_after_switch(
        self,
        builtin_scale: StatusScale,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """``todo=True``: the checkout runs first, then the entry of the switched topic."""
        monkeypatch.chdir(tmp_path)
        inventory = [
            BranchRef(name="feature-foo", remote=False),
            BranchRef(name="main", remote=False),
        ]
        trees = {
            "feature-foo": [".goga/history/2026/feature-foo/plan.md"],
            "main": ["README.md"],
        }
        _wire_resolution(monkeypatch, builtin_scale, inventory, trees, "main")
        _cleanliness, checkout, _creation = _wire_mutations(monkeypatch, clean=True)
        entry = _wire_entry(monkeypatch)
        _interactive(monkeypatch)
        order = mock.Mock()
        order.attach_mock(checkout, "checkout")
        order.attach_mock(entry, "entry")

        result = switch_topic("feature-foo", todo=True, year="2026")

        assert result == "Switched to branch feature-foo"
        entry.assert_called_once_with("feature-foo", "2026")
        assert order.mock_calls == [
            mock.call.checkout("feature-foo"),
            mock.call.entry("feature-foo", "2026"),
        ]

    def test_switch_topic_todo_idempotent_still_enters(
        self,
        builtin_scale: StatusScale,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Already on the host under ``todo=True``: the idempotent line — the
        entry still runs, without a cleanliness probe or a checkout."""
        monkeypatch.chdir(tmp_path)
        _working_copy_topic(tmp_path, current_year(), "feature-foo", ["plan.md"])
        inventory = [BranchRef(name="feature-foo", remote=False)]
        trees = {"feature-foo": [".goga/history/2026/feature-foo/plan.md"]}
        _wire_resolution(monkeypatch, builtin_scale, inventory, trees, "feature-foo")
        cleanliness, checkout, creation = _wire_mutations(monkeypatch, clean=True)
        entry = _wire_entry(monkeypatch)
        _interactive(monkeypatch)

        result = switch_topic("feature-foo", todo=True)

        assert result == "Already on branch feature-foo"
        entry.assert_called_once_with("feature-foo", None)
        cleanliness.assert_not_called()
        checkout.assert_not_called()
        creation.assert_not_called()

    def test_switch_topic_todo_candidate_without_topic_error(
        self,
        builtin_scale: StatusScale,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """``todo=True`` on a candidate without a topic: a clean error after
        the choice — switching creates nothing."""
        monkeypatch.chdir(tmp_path)
        inventory = [
            BranchRef(name="feature-foo", remote=False),
            BranchRef(name="main", remote=False),
        ]
        trees = {"feature-foo": ["README.md"], "main": ["README.md"]}
        _wire_resolution(monkeypatch, builtin_scale, inventory, trees, "main")
        cleanliness, checkout, creation = _wire_mutations(monkeypatch, clean=True)
        entry = _wire_entry(monkeypatch)
        _interactive(monkeypatch)

        with pytest.raises(click.ClickException, match="topic"):
            switch_topic("feature-foo", todo=True, year="2026")

        cleanliness.assert_not_called()
        checkout.assert_not_called()
        creation.assert_not_called()
        entry.assert_not_called()

    def test_switch_topic_todo_non_tty_error_before_resolution(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``todo=True`` without a terminal: the clean error fires before any
        resolution — ordering, not just the error."""
        monkeypatch.chdir(tmp_path)
        _non_interactive(monkeypatch)
        resolver = mock.Mock(side_effect=AssertionError("the resolution must not run"))
        monkeypatch.setattr(switching, "resolve_switch_candidates", resolver)

        with pytest.raises(click.ClickException, match="interactive"):
            switch_topic("anything", todo=True)

        resolver.assert_not_called()

    def test_switch_topic_several_candidates_non_tty_with_todo(
        self,
        builtin_scale: StatusScale,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Several candidates, no terminal, ``todo=True``: the todo check
        fires first — the error names the terminal, not the candidate list."""
        monkeypatch.chdir(tmp_path)
        inventory = [
            BranchRef(name="feat/a", remote=False),
            BranchRef(name="feat/ab", remote=False),
        ]
        trees = {
            "feat/a": [".goga/history/2026/feat-a/plan.md"],
            "feat/ab": [".goga/history/2026/feat-ab/prd.md"],
        }
        _wire_resolution(monkeypatch, builtin_scale, inventory, trees, None)
        cleanliness, checkout, creation = _wire_mutations(monkeypatch, clean=True)
        _non_interactive(monkeypatch)

        with pytest.raises(click.ClickException) as raised:
            switch_topic("feat", todo=True, year="2026")

        assert "interactive" in raised.value.message
        assert "1)" not in raised.value.message
        assert "feat/a" not in raised.value.message
        cleanliness.assert_not_called()
        checkout.assert_not_called()
        creation.assert_not_called()


# --- Infrastructure boundary ---


class TestSwitchingInfrastructureBoundary:
    def test_git_failure_surfaces_as_clean_error(
        self,
        builtin_scale: StatusScale,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A git infrastructure failure with stderr becomes a ``ClickException``."""
        monkeypatch.chdir(tmp_path)
        failure = subprocess.CalledProcessError(
            returncode=128, cmd=["git", "for-each-ref"], stderr="fatal: not a git repository"
        )
        monkeypatch.setattr(switching, "assemble_status_scale", lambda: builtin_scale)
        monkeypatch.setattr(switching, "list_branch_refs", mock.Mock(side_effect=failure))

        with pytest.raises(click.ClickException) as raised:
            resolve_switch_candidates("feat/a", "2026")

        assert "fatal: not a git repository" in raised.value.message

    def test_missing_git_binary_at_resolution_surfaces_as_clean_error(
        self,
        builtin_scale: StatusScale,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A missing git binary during the resolution is a clean error."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(switching, "assemble_status_scale", lambda: builtin_scale)
        monkeypatch.setattr(switching, "list_branch_refs", mock.Mock(side_effect=FileNotFoundError("git")))

        with pytest.raises(click.ClickException) as raised:
            resolve_switch_candidates("feat/a", "2026")

        assert "git is not available" in raised.value.message

    def test_broken_tool_package_import_surfaces_as_clean_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The fatal scale-assembly ``ImportError`` keeps its package name."""
        monkeypatch.chdir(tmp_path)
        broken = ImportError("package goga_tool_bad failed to import: boom")
        monkeypatch.setattr(switching, "assemble_status_scale", mock.Mock(side_effect=broken))

        with pytest.raises(click.ClickException) as raised:
            switch_topic("feat/a", year="2026")

        assert raised.value.message == "package goga_tool_bad failed to import: boom"

    def test_switch_mutation_failure_surfaces_as_clean_error(
        self,
        builtin_scale: StatusScale,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A failing checkout mutation becomes a ``ClickException``."""
        monkeypatch.chdir(tmp_path)
        inventory = [
            BranchRef(name="feat/a", remote=False),
            BranchRef(name="main", remote=False),
        ]
        trees = {"feat/a": [".goga/history/2026/feat-a/plan.md"], "main": ["README.md"]}
        _wire_resolution(monkeypatch, builtin_scale, inventory, trees, "main")
        monkeypatch.setattr(switching, "is_working_tree_clean", mock.Mock(return_value=True))
        failure = subprocess.CalledProcessError(
            returncode=1, cmd=["git", "switch", "feat/a"], stderr="error: cannot switch"
        )
        monkeypatch.setattr(switching, "checkout_local_branch", mock.Mock(side_effect=failure))

        with pytest.raises(click.ClickException) as raised:
            switch_topic("feat/a", year="2026")

        assert "error: cannot switch" in raised.value.message

    def test_missing_git_binary_at_mutation_surfaces_as_clean_error(
        self,
        builtin_scale: StatusScale,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A missing git binary during the mutation phase is a clean error."""
        monkeypatch.chdir(tmp_path)
        inventory = [
            BranchRef(name="feat/a", remote=False),
            BranchRef(name="main", remote=False),
        ]
        trees = {"feat/a": [".goga/history/2026/feat-a/plan.md"], "main": ["README.md"]}
        _wire_resolution(monkeypatch, builtin_scale, inventory, trees, "main")
        monkeypatch.setattr(switching, "is_working_tree_clean", mock.Mock(side_effect=FileNotFoundError("git")))

        with pytest.raises(click.ClickException) as raised:
            switch_topic("feat/a", year="2026")

        assert "git" in raised.value.message

    def test_broken_import_after_resolution_surfaces_as_clean_error(
        self,
        builtin_scale: StatusScale,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A fatal ``ImportError`` after the resolution is a clean error.

        The scale of a command run assembles inside the resolution, so the
        orchestration wrapper's own ``ImportError`` boundary is probed here:
        the cleanliness check raising it after the candidates resolved.
        """
        monkeypatch.chdir(tmp_path)
        inventory = [
            BranchRef(name="feat/a", remote=False),
            BranchRef(name="main", remote=False),
        ]
        trees = {"feat/a": [".goga/history/2026/feat-a/plan.md"], "main": ["README.md"]}
        _wire_resolution(monkeypatch, builtin_scale, inventory, trees, "main")
        broken = ImportError("package goga_tool_bad failed to import: boom")
        monkeypatch.setattr(switching, "is_working_tree_clean", mock.Mock(side_effect=broken))

        with pytest.raises(click.ClickException) as raised:
            switch_topic("feat/a", year="2026")

        assert raised.value.message == "package goga_tool_bad failed to import: boom"

    def test_selection_prompt_abort_leaves_repository_untouched(
        self,
        builtin_scale: StatusScale,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Ctrl-C at the selection prompt propagates as ``click.Abort`` — no mutation."""
        monkeypatch.chdir(tmp_path)
        inventory = [
            BranchRef(name="feat/a", remote=False),
            BranchRef(name="feat/b", remote=False),
            BranchRef(name="main", remote=False),
        ]
        trees = {
            "feat/a": [".goga/history/2026/feat-a/plan.md"],
            "feat/b": [".goga/history/2026/feat-b/plan.md"],
            "main": ["README.md"],
        }
        _wire_resolution(monkeypatch, builtin_scale, inventory, trees, "main")
        monkeypatch.setattr(sys, "stdin", mock.Mock(**{"isatty.return_value": True}))
        monkeypatch.setattr(click, "prompt", mock.Mock(side_effect=click.Abort()))
        cleanliness, checkout, creation = _wire_mutations(monkeypatch)

        with pytest.raises(click.Abort):
            switch_topic("feat", year="2026")

        cleanliness.assert_not_called()
        checkout.assert_not_called()
        creation.assert_not_called()
