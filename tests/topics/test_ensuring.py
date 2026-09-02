"""Contract and logic tests for the entity declared in
``goga/topics/CODEMANIFEST`` with ``location: ensuring.py``:

- ``ensure_topic(identifier, todo, year)`` — the switch-or-create orchestration

The git boundary is mocked at the import point per the ``convention``
practice — no git binary and no repository are touched. The resolution runs
real through the switching module's patched import points where the scenario
walks the inventory and is mocked at ``goga.topics.ensuring``'s import point
where the scenario pins an exact candidate list; the switch tail is
``switch_topic`` mocked at its import point in ``ensuring`` (its own
orchestration is the switching suite's concern); the fast creation mocks the
occupancy oracles, ``create_and_switch_branch``, and the todo entry at their
import points in ``ensuring`` — with the topic-directory creation real on a
``tmp_path`` tree where the design says so. The scale is the
``builtin_scale`` fixture.
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
from goga.history import current_year
from goga.history.statuses import StatusScale
from goga.topics import SwitchCandidate, board, ensure_topic, ensuring, switching
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


def _wire_resolver(monkeypatch: pytest.MonkeyPatch, candidates: list[SwitchCandidate]) -> mock.Mock:
    """Patch the resolution at its import point in ``ensuring``.

    Returns:
        The resolver as a recording mock answering the pinned candidates.
    """
    resolver = mock.Mock(return_value=candidates)
    monkeypatch.setattr(ensuring, "resolve_switch_candidates", resolver)
    return resolver


def _wire_mutations(monkeypatch: pytest.MonkeyPatch, clean: bool = True) -> tuple[mock.Mock, mock.Mock, mock.Mock]:
    """Patch the switch mutations at their import points in ``switching``.

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


def _wire_switch(monkeypatch: pytest.MonkeyPatch, line: str) -> mock.Mock:
    """Patch the switch orchestration at its import point in ``ensuring``.

    Returns:
        ``switch_topic`` as a recording mock answering the given result line.
    """
    switch = mock.Mock(return_value=line)
    monkeypatch.setattr(ensuring, "switch_topic", switch)
    return switch


def _wire_fast_creation(
    monkeypatch: pytest.MonkeyPatch,
    occupied: str | None = None,
    real_dir: bool = False,
) -> tuple[mock.Mock, mock.Mock | None]:
    """Patch the fast-creation boundary at ``ensuring``'s import points.

    Args:
        monkeypatch: The patch fixture.
        occupied: The branch-oracle answer — a conflict reason or ``None``.
        real_dir: Keep ``ensure_topic_dir`` real (the on-disk scenarios).

    Returns:
        The create-and-switch mutation and the topic-directory creation as
        recording mocks — the directory-creation mock is ``None`` when
        ``real_dir`` left the real routine in place.
    """
    monkeypatch.setattr(ensuring, "check_branch_occupancy", mock.Mock(return_value=occupied))
    monkeypatch.setattr(ensuring, "check_slug_occupancy", mock.Mock(return_value=None))
    create_and_switch = mock.Mock()
    monkeypatch.setattr(ensuring, "create_and_switch_branch", create_and_switch)
    if real_dir:
        return create_and_switch, None

    ensure_dir = mock.Mock()
    monkeypatch.setattr(ensuring, "ensure_topic_dir", ensure_dir)
    return create_and_switch, ensure_dir


def _wire_current(monkeypatch: pytest.MonkeyPatch, current: str | None) -> mock.Mock:
    """Patch the current-branch read at its import point in ``ensuring``.

    Returns:
        The reader as a recording mock answering the given branch name.
    """
    resolver = mock.Mock(return_value=current)
    monkeypatch.setattr(ensuring, "resolve_current_branch_name", resolver)
    return resolver


def _wire_entry(monkeypatch: pytest.MonkeyPatch) -> mock.Mock:
    """Patch the todo entry at its import point in ``ensuring``.

    Returns:
        ``enter_topic_todo`` as a recording mock.
    """
    entry = mock.Mock()
    monkeypatch.setattr(ensuring, "enter_topic_todo", entry)
    return entry


def _non_interactive(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make stdin a non-terminal — the todo entry must abort cleanly."""
    monkeypatch.setattr(sys, "stdin", mock.Mock(**{"isatty.return_value": False}))


def _interactive(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make stdin a terminal — the todo entry of the ensure is reachable."""
    monkeypatch.setattr(sys, "stdin", mock.Mock(**{"isatty.return_value": True}))


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
        """``ensure_topic(identifier, todo=False, year=None) -> str``."""
        signature = inspect.signature(ensure_topic)
        assert list(signature.parameters) == ["identifier", "todo", "year"]
        assert all(
            parameter.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD for parameter in signature.parameters.values()
        )
        assert signature.parameters["todo"].default is False
        assert signature.parameters["year"].default is None
        hints = typing.get_type_hints(ensure_topic)
        assert hints == {"identifier": str, "todo": bool, "year": str | None, "return": str}

    def test_ensure_topic_single_argument_call_still_binds(self) -> None:
        """The pipeline caller ``ensure_topic(topic)`` stays compatible."""
        inspect.signature(ensure_topic).bind("history-com")


# --- Logic tests: the fast creation at zero candidates ---


class TestEnsureTopicFastCreation:
    def test_ensure_topic_fast_creation_from_current_head(
        self,
        builtin_scale: StatusScale,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Nothing hosts the identifier: the branch named as entered comes
        off the current HEAD, then the topic directory, then — under
        ``todo`` — the entry; the line carries the name as entered and the
        normalized slug."""
        monkeypatch.chdir(tmp_path)
        inventory = [BranchRef(name="main", remote=False)]
        trees = {"main": ["README.md"]}
        _wire_resolution(monkeypatch, builtin_scale, inventory, trees, "main")
        create_and_switch, ensure_dir = _wire_fast_creation(monkeypatch)
        entry = _wire_entry(monkeypatch)
        _interactive(monkeypatch)
        order = mock.Mock()
        order.attach_mock(create_and_switch, "create_and_switch")
        order.attach_mock(ensure_dir, "ensure_topic_dir")
        order.attach_mock(entry, "entry")

        result = ensure_topic("Feature/Foo_Bar", todo=True, year="2026")

        assert result == "Created branch Feature/Foo_Bar and topic 2026/feature-foo-bar"
        create_and_switch.assert_called_once_with("Feature/Foo_Bar")
        ensure_dir.assert_called_once_with("Feature/Foo_Bar", "2026")
        entry.assert_called_once_with("Feature/Foo_Bar", "2026")
        assert order.mock_calls == [
            mock.call.create_and_switch("Feature/Foo_Bar"),
            mock.call.ensure_topic_dir("Feature/Foo_Bar", "2026"),
            mock.call.entry("Feature/Foo_Bar", "2026"),
        ]
        # The fast creation is local-only and asks nothing: the publication
        # primitives have no place here, and the old create_topic delegation
        # must not leak back in.
        assert not hasattr(ensuring, "resolve_ref_commit")
        assert not hasattr(ensuring, "push_branch")
        assert not hasattr(ensuring, "create_topic")

    def test_ensure_topic_fast_creation_writes_the_real_topic_directory(
        self,
        builtin_scale: StatusScale,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The fast creation creates the real topic directory of the year —
        and without ``todo`` no entry runs (no terminal needed)."""
        monkeypatch.chdir(tmp_path)
        inventory = [BranchRef(name="main", remote=False)]
        trees = {"main": [".goga/history/2026/other/prd.md"]}
        _wire_resolution(monkeypatch, builtin_scale, inventory, trees, "main")
        create_and_switch, _ensure_dir = _wire_fast_creation(monkeypatch, real_dir=True)
        entry = _wire_entry(monkeypatch)

        result = ensure_topic("prune-history-and-new-status", year="2026")

        assert result == ("Created branch prune-history-and-new-status and topic 2026/prune-history-and-new-status")
        create_and_switch.assert_called_once_with("prune-history-and-new-status")
        entry.assert_not_called()
        assert (tmp_path / ".goga" / "history" / "2026" / "prune-history-and-new-status").is_dir()

    def test_ensure_topic_occupied_name_clean_error(
        self,
        builtin_scale: StatusScale,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """An occupancy conflict at zero candidates: a clean error carrying
        the reason and the board hint — nothing created."""
        monkeypatch.chdir(tmp_path)
        inventory = [BranchRef(name="main", remote=False)]
        trees = {"main": ["README.md"]}
        _wire_resolution(monkeypatch, builtin_scale, inventory, trees, "main")
        create_and_switch, ensure_dir = _wire_fast_creation(monkeypatch, occupied="branch 'x' exists")

        with pytest.raises(click.ClickException) as raised:
            ensure_topic("x", year="2026")

        assert raised.value.message == "branch 'x' exists — run 'goga topics board' to see the board"
        create_and_switch.assert_not_called()
        ensure_dir.assert_not_called()

    def test_ensure_topic_empty_slug_identifier_error(
        self,
        builtin_scale: StatusScale,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """An identifier normalizing to an empty slug is a clean error — a
        name git would accept but the history tree cannot address must not
        create a branch that can never host a topic directory."""
        monkeypatch.chdir(tmp_path)
        inventory = [BranchRef(name="main", remote=False)]
        trees = {"main": ["README.md"]}
        _wire_resolution(monkeypatch, builtin_scale, inventory, trees, "main")
        create_and_switch, ensure_dir = _wire_fast_creation(monkeypatch)
        create_and_switch.side_effect = AssertionError("an empty-slug name must not create a branch")

        with pytest.raises(click.ClickException, match="empty topic slug"):
            ensure_topic("???", year="2026")

        create_and_switch.assert_not_called()
        ensure_dir.assert_not_called()


# --- Logic tests: the delegated switch at non-empty candidates ---


class TestEnsureTopicSwitch:
    def test_ensure_topic_single_candidate_switches_without_creation(
        self,
        builtin_scale: StatusScale,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A hosted identifier takes the delegated switch without the entry
        — the fast creation never runs."""
        monkeypatch.chdir(tmp_path)
        inventory = [
            BranchRef(name="feat/a", remote=False),
            BranchRef(name="main", remote=False),
        ]
        trees = {"feat/a": [".goga/history/2026/feat-a/plan.md"], "main": ["README.md"]}
        _wire_resolution(monkeypatch, builtin_scale, inventory, trees, "main")
        switch = _wire_switch(monkeypatch, "Switched to branch feat/a")
        create_and_switch, _ensure_dir = _wire_fast_creation(monkeypatch)

        result = ensure_topic("feat/a", year="2026")

        assert result == "Switched to branch feat/a"
        switch.assert_called_once_with("feat/a", todo=False, year="2026")
        create_and_switch.assert_not_called()

    def test_ensure_topic_multiple_candidates_delegates_the_choice_to_switch(
        self,
        builtin_scale: StatusScale,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Several candidates: the delegated switch orchestration owns the
        numbered choice — its non-terminal abort propagates, and ambiguity
        never escapes into creation."""
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
        _cleanliness, checkout, _remote_creation = _wire_mutations(monkeypatch, clean=True)
        create_and_switch, _ensure_dir = _wire_fast_creation(monkeypatch)
        _non_interactive(monkeypatch)

        with pytest.raises(click.ClickException) as raised:
            ensure_topic("feat", year="2026")

        assert "1)" in raised.value.message
        assert "2)" in raised.value.message
        checkout.assert_not_called()
        create_and_switch.assert_not_called()


# --- Logic tests: the todo entry of the ensured work ---


class TestEnsureTopicTodo:
    def test_ensure_topic_switch_branch_without_topic_creates_dir_then_enters(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``todo`` on a branch without a topic: the delegated switch runs
        without the entry, then the topic directory is created and the fresh
        entry follows — the fast process is never interrupted."""
        monkeypatch.chdir(tmp_path)
        candidate = SwitchCandidate(branch="feature-foo", topic=None, statuses=[], current=True, remote=False)
        _wire_resolver(monkeypatch, [candidate])
        switch = _wire_switch(monkeypatch, "Already on branch feature-foo")
        _wire_current(monkeypatch, "feature-foo")
        ensure_dir = mock.Mock()
        monkeypatch.setattr(ensuring, "ensure_topic_dir", ensure_dir)
        entry = _wire_entry(monkeypatch)
        _interactive(monkeypatch)
        order = mock.Mock()
        order.attach_mock(ensure_dir, "ensure_topic_dir")
        order.attach_mock(entry, "entry")

        result = ensure_topic("feature-foo", todo=True, year="2026")

        assert result == "Already on branch feature-foo"
        switch.assert_called_once_with("feature-foo", todo=False, year="2026")
        ensure_dir.assert_called_once_with("feature-foo", "2026")
        entry.assert_called_once_with("feature-foo", "2026")
        assert order.mock_calls == [
            mock.call.ensure_topic_dir("feature-foo", "2026"),
            mock.call.entry("feature-foo", "2026"),
        ]

    def test_ensure_topic_todo_enters_resolved_topic_not_branch_slug(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The hosted topic comes from the resolution candidate — a topic
        merged into another branch is entered as itself; no directory of
        the hosting branch's name is ever created."""
        monkeypatch.chdir(tmp_path)
        candidate = SwitchCandidate(branch="main", topic="feature-x", statuses=["todo"], current=False, remote=False)
        _wire_resolver(monkeypatch, [candidate])
        _wire_switch(monkeypatch, "Switched to branch main")
        _wire_current(monkeypatch, "main")
        ensure_dir = mock.Mock()
        monkeypatch.setattr(ensuring, "ensure_topic_dir", ensure_dir)
        entry = _wire_entry(monkeypatch)
        _interactive(monkeypatch)

        result = ensure_topic("feature-x", todo=True, year="2026")

        assert result == "Switched to branch main"
        entry.assert_called_once_with("feature-x", "2026")
        ensure_dir.assert_not_called()
        assert not (tmp_path / ".goga" / "history" / "2026" / "main").exists()

    def test_ensure_topic_todo_matches_remote_candidate_by_short_name(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A remote-tracking candidate matches the current branch by its
        short name — the local branch the switch created."""
        monkeypatch.chdir(tmp_path)
        candidate = SwitchCandidate(
            branch="origin/feature-x", topic="feature-x", statuses=["todo"], current=False, remote=True
        )
        _wire_resolver(monkeypatch, [candidate])
        _wire_switch(monkeypatch, "Created branch feature-x from origin/feature-x")
        _wire_current(monkeypatch, "feature-x")
        ensure_dir = mock.Mock()
        monkeypatch.setattr(ensuring, "ensure_topic_dir", ensure_dir)
        entry = _wire_entry(monkeypatch)
        _interactive(monkeypatch)

        result = ensure_topic("feature-x", todo=True, year="2026")

        assert result == "Created branch feature-x from origin/feature-x"
        entry.assert_called_once_with("feature-x", "2026")
        ensure_dir.assert_not_called()

    def test_ensure_topic_todo_empty_slug_branch_without_topic_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A no-topic branch whose name normalizes to an empty slug is a
        clean error — the history facade's ``ValueError`` never escapes the
        module, and nothing is created or entered."""
        monkeypatch.chdir(tmp_path)
        candidate = SwitchCandidate(branch="Тема", topic=None, statuses=[], current=False, remote=False)
        _wire_resolver(monkeypatch, [candidate])
        _wire_switch(monkeypatch, "Switched to branch Тема")
        _wire_current(monkeypatch, "Тема")
        ensure_dir = mock.Mock()
        monkeypatch.setattr(ensuring, "ensure_topic_dir", ensure_dir)
        entry = _wire_entry(monkeypatch)
        _interactive(monkeypatch)

        with pytest.raises(click.ClickException) as raised:
            ensure_topic("Тема", todo=True, year="2026")

        assert raised.value.message == "branch name 'Тема' normalizes to an empty topic slug"
        ensure_dir.assert_not_called()
        entry.assert_not_called()

    def test_ensure_topic_todo_idempotent_enters_the_hosted_topic(
        self,
        builtin_scale: StatusScale,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Already on the host: the delegated switch returns the idempotent
        line and the entry runs for the hosted topic of the working copy."""
        monkeypatch.chdir(tmp_path)
        _working_copy_topic(tmp_path, current_year(), "feat-a", ["plan.md"])
        _wire_resolution(monkeypatch, builtin_scale, _twin_inventory(), _twin_trees(), "feat/a")
        _wire_switch(monkeypatch, "Already on branch feat/a")
        _wire_current(monkeypatch, "feat/a")
        entry = _wire_entry(monkeypatch)
        _interactive(monkeypatch)

        result = ensure_topic("feat/a", todo=True)

        assert result == "Already on branch feat/a"
        entry.assert_called_once_with("feat-a", None)

    def test_ensure_topic_todo_non_tty_error_before_action(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``todo=True`` without a terminal: the clean error fires before
        any action — ordering, not just the error."""
        monkeypatch.chdir(tmp_path)
        _non_interactive(monkeypatch)
        resolver = mock.Mock(side_effect=AssertionError("the resolution must not run"))
        monkeypatch.setattr(ensuring, "resolve_switch_candidates", resolver)

        with pytest.raises(click.ClickException, match="interactive"):
            ensure_topic("anything", todo=True)

        resolver.assert_not_called()
