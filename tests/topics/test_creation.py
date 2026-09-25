"""Contract and logic tests for the entities declared in
``goga/topics/CODEMANIFEST`` with ``location: creation.py``:

- ``check_branch_occupancy(branch_name, slug, year)`` — the three-oracle
  occupancy check of a fresh-work name
- ``check_slug_occupancy(slug, year)`` — the branch-tree occupancy oracle of
  a topic slug
- ``create_topic(branch_name, base_ref, todo, todo_from_stdin, publish,
  commit_message, year, switch)`` — the fresh-work creation procedure off
  an explicit base with its todo acquisition ladder — a value, else the
  declared piped stdin, else the editor, else the path rules — and its
  publication ask, skipped when the todo came from stdin: the
  quarantined no-switch plant by default, the working-copy switch path
  under the flag
- ``enter_topic_todo(topic, year, branch)`` — the editor session over the
  topic's todo.md and the write of the saved text, without a commit: the
  saved text passes through the todo-entry amendment before the write and
  the completed entry emits its notification after it

The git boundary is mocked at the import point per the ``convention``
practice — no git binary and no repository are touched. The filesystem
scenarios (the topic oracle and the created directory) run against ``tmp_path``
with the real history path routines; the scale is never assembled — creation
is not a status consumer. The editor session is mocked with a shell script
exported as ``$EDITOR`` per the ``editor`` practice and the TTY detection
with a ``sys.stdin`` stand-in — a real editor never launches in tests; the
piped stdin of the ladder is modeled with a ``TextIOWrapper`` over
``BytesIO`` (a subclass reports the terminal while its guarded pipe
records every read). The
checkpoint scenarios stub ``edit_text`` on the creation module and run the
delivery for real over the platform-environment fixtures of the local
conftest — the recording hooks assert the fired actions and their facts.
"""

from __future__ import annotations

import inspect
import io
import subprocess
import sys
import typing
from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest import mock

import click
import pytest
from goga.topics import (
    check_branch_occupancy,
    check_slug_occupancy,
    create_topic,
    creation,
    enter_topic_todo,
    publishing,
)
from goga.topics.git import BranchRef

# --- Shared scenario helpers ---


def _wire_inventory(
    monkeypatch: pytest.MonkeyPatch,
    inventory: list[BranchRef],
    current: str | None = None,
) -> None:
    """Patch creation's import points: the inventory and the current branch."""
    monkeypatch.setattr(creation, "list_branch_refs", lambda: inventory)
    monkeypatch.setattr(creation, "resolve_current_branch_name", lambda: current)


def _wire_creation(
    monkeypatch: pytest.MonkeyPatch,
    current: str = "main",
    base_commit: str = "c0ffee",
) -> mock.Mock:
    """Patch creation's import points: a free inventory, the current
    branch, the base resolution, and the create/checkout mutations, plus
    the quarantined plant the no-switch path reaches through publishing.

    Returns:
        A recording parent mock whose ``resolve_ref_commit``,
        ``create_branch``, ``checkout``, and ``plant`` children are the
        wired touchpoints — ``mock_calls`` captures the procedure's order.
    """
    wired = mock.Mock()
    wired.resolve_ref_commit.return_value = base_commit
    _wire_inventory(monkeypatch, [], current)
    monkeypatch.setattr(creation, "resolve_ref_commit", wired.resolve_ref_commit)
    monkeypatch.setattr(creation, "create_branch_at_commit", wired.create_branch)
    monkeypatch.setattr(creation, "checkout_local_branch", wired.checkout)
    monkeypatch.setattr(publishing, "_plant_topic_branch", wired.plant)
    return wired


def _non_interactive(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make stdin a non-terminal with a real empty buffer — the ladder
    reads the pipe and the empty read leaves no content."""
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(b"")))


def _piped_stdin(monkeypatch: pytest.MonkeyPatch, data: bytes) -> io.TextIOWrapper:
    """Make stdin a non-terminal pipe carrying ``data`` — the readable
    buffer of the piped-todo scenarios.

    Args:
        monkeypatch: the pytest patcher restoring stdin on teardown.
        data: The raw bytes the pipe carries.

    Returns:
        The installed wrapper — its ``buffer`` is the readable pipe.
    """
    wrapper = io.TextIOWrapper(io.BytesIO(data))
    monkeypatch.setattr(sys, "stdin", wrapper)
    return wrapper


class _CountingPipe(io.BytesIO):
    """A pipe buffer recording every read through a mock delegate."""

    def __init__(self, data: bytes) -> None:
        super().__init__(data)
        self.reads = mock.MagicMock(side_effect=self._read_all)

    def _read_all(self, size: int = -1) -> bytes:
        return io.BytesIO.read(self, size)

    def read(self, size: int = -1) -> bytes:
        return self.reads(size)


class _TtyStdin(io.TextIOWrapper):
    """A terminal stdin — ``isatty`` reports True while the pipe behind
    the wrapper stays guarded: every buffer read lands on the ``pipe``
    mock, so a read of a terminal stdin is visible."""

    def __init__(self) -> None:
        super().__init__(io.BytesIO(b""))
        self.pipe = mock.MagicMock()

    @property
    def buffer(self) -> mock.MagicMock:  # type: ignore[override]
        """The guarded pipe — a read here is a read of a terminal stdin."""
        return self.pipe

    def isatty(self) -> bool:
        return True


def _topic_dir(cwd: Path, year: str, slug: str) -> Path:
    """Create the working-copy topic directory of the oracle scenarios."""
    path = cwd / ".goga" / "history" / year / slug
    path.mkdir(parents=True, exist_ok=True)
    return path


def _editor_script(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, body: str) -> None:
    """Export ``$EDITOR`` as an executable shell script running ``body``."""
    editors = tmp_path / "editors"
    editors.mkdir(exist_ok=True)
    script = editors / "editor-mock.sh"
    script.write_text(f"#!/bin/sh\n{body}\n", encoding="utf-8")
    script.chmod(0o755)
    monkeypatch.delenv("VISUAL", raising=False)
    monkeypatch.setenv("EDITOR", str(script))


def _tty(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make stdin a terminal — the editor session launches."""
    monkeypatch.setattr(sys, "stdin", mock.Mock(**{"isatty.return_value": True}))


def _wire_slug_oracle(
    monkeypatch: pytest.MonkeyPatch,
    inventory: list[BranchRef],
    reader: Callable[[str, str], list[str]],
) -> mock.Mock:
    """Patch creation's import points: the inventory and the tree reader.

    Returns:
        The branch-ref listing as a recording mock — the oracle's only
        other git touchpoint.
    """
    listing = mock.Mock(return_value=inventory)
    monkeypatch.setattr(creation, "list_branch_refs", listing)
    monkeypatch.setattr(creation, "read_ref_tree_paths", reader)
    return listing


RecordedEntry = Callable[..., list[tuple[str, str, object]]]
"""The recording-hooks factory of the local conftest."""

InstallToolPackage = Callable[[str, Callable[[Any], None] | None], object]
"""The fake-package installing factory of the local conftest."""


def _subscribe(*subscriptions: tuple[str, Callable[..., None]]) -> Callable[[Any], None]:
    """Build a facade callback subscribing each hook on its topics action.

    Each pair is one subscription — the topics action name and the hook;
    the hook's ``__name__`` is its hook name, so the walk warnings name the
    functions the test declares.

    Args:
        subscriptions: The (action, hook) pairs to subscribe.

    Returns:
        The ``register_hooks`` callback of one fake tool package.
    """

    def register_hooks(hooks: Any) -> None:
        for action, hook in subscriptions:
            hooks.subscribe("topics", action, hook.__name__, hook)

    return register_hooks


def _stub_edit_text(monkeypatch: pytest.MonkeyPatch, saved: str | None) -> None:
    """Stub the editor session on the creation module — a scripted save.

    Args:
        monkeypatch: the pytest patcher restoring the session on teardown.
        saved: The text the session returns — None is the cancelled entry.
    """
    monkeypatch.setattr(creation, "edit_text", lambda _initial=None: saved)


# --- Contract tests ---


class TestCreationContract:
    def test_entities_are_importable_from_the_cell_facade(self) -> None:
        """Both routines live on the cell facade and in ``__all__``."""
        import goga.topics as cell

        assert cell.create_topic is create_topic
        assert cell.check_branch_occupancy is check_branch_occupancy
        assert cell.check_slug_occupancy is check_slug_occupancy
        assert cell.enter_topic_todo is enter_topic_todo
        expected = {
            "BoardEntry",
            "BoardRecord",
            "DeleteTarget",
            "SwitchCandidate",
            "aggregate_topic_board",
            "check_branch_occupancy",
            "check_slug_occupancy",
            "collect_topic_board",
            "create_topic",
            "delete_topics",
            "ensure_topic",
            "enter_topic_todo",
            "publish_topic",
            "resolve_clear_targets",
            "resolve_delete_targets",
            "resolve_switch_candidates",
            "switch_topic",
        }
        assert set(cell.__all__) == expected

    def test_check_slug_occupancy_signature(self) -> None:
        """``check_slug_occupancy(slug, year=None)``."""
        signature = inspect.signature(check_slug_occupancy)
        assert list(signature.parameters) == ["slug", "year"]
        assert all(
            parameter.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD for parameter in signature.parameters.values()
        )
        assert signature.parameters["year"].default is None
        hints = typing.get_type_hints(check_slug_occupancy)
        assert hints == {
            "slug": str,
            "year": str | None,
            "return": str | None,
        }

    def test_check_branch_occupancy_signature(self) -> None:
        """``check_branch_occupancy(branch_name, slug, year=None)``."""
        signature = inspect.signature(check_branch_occupancy)
        assert list(signature.parameters) == ["branch_name", "slug", "year"]
        assert all(
            parameter.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD for parameter in signature.parameters.values()
        )
        assert signature.parameters["year"].default is None
        hints = typing.get_type_hints(check_branch_occupancy)
        assert hints == {
            "branch_name": str,
            "slug": str,
            "year": str | None,
            "return": str | None,
        }

    def test_enter_topic_todo_signature(self) -> None:
        """``enter_topic_todo(topic, year=None, branch=None) -> bool`` — binds as declared."""
        signature = inspect.signature(enter_topic_todo)
        assert list(signature.parameters) == ["topic", "year", "branch"]
        assert all(
            parameter.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD for parameter in signature.parameters.values()
        )
        assert signature.parameters["year"].default is None
        assert signature.parameters["branch"].default is None
        hints = typing.get_type_hints(enter_topic_todo)
        assert hints == {
            "topic": str,
            "year": str | None,
            "branch": str | None,
            "return": bool,
        }
        signature.bind("feature-foo", year="2026", branch="feature-foo")
        signature.bind("feature-foo")

    def test_create_topic_signature(self) -> None:
        """``create_topic(branch_name, base_ref, todo, todo_from_stdin, publish,
        commit_message, year, switch) -> str`` with the defaults
        ``None/False/False/None/None/False``."""
        signature = inspect.signature(create_topic)
        assert list(signature.parameters) == [
            "branch_name",
            "base_ref",
            "todo",
            "todo_from_stdin",
            "publish",
            "commit_message",
            "year",
            "switch",
        ]
        assert all(
            parameter.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD for parameter in signature.parameters.values()
        )
        assert signature.parameters["todo"].default is None
        assert signature.parameters["todo_from_stdin"].default is False
        assert signature.parameters["publish"].default is False
        assert signature.parameters["commit_message"].default is None
        assert signature.parameters["year"].default is None
        assert signature.parameters["switch"].default is False
        hints = typing.get_type_hints(create_topic)
        assert hints == {
            "branch_name": str,
            "base_ref": str,
            "todo": str | None,
            "todo_from_stdin": bool,
            "publish": bool,
            "commit_message": str | None,
            "year": str | None,
            "switch": bool,
            "return": str,
        }
        signature.bind(
            "b",
            "origin/main",
            todo="t",
            todo_from_stdin=True,
            publish=False,
            commit_message=None,
            year="2026",
            switch=True,
        )
        signature.bind("b", "HEAD")

    def test_no_cleanliness_probe_in_creation(self) -> None:
        """Creation owns no cleanliness policy — no probe is imported."""
        assert not hasattr(creation, "is_working_tree_clean")


# --- Logic tests: the occupancy oracles ---


class TestCheckBranchOccupancy:
    def test_check_branch_occupancy_oracle_order(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """The first occupied oracle wins — remote twin before the topic dir."""
        monkeypatch.chdir(tmp_path)
        inventory = [BranchRef(name="origin/feat/x", remote=True)]
        _topic_dir(tmp_path, "2026", "feat-x")
        _wire_inventory(monkeypatch, inventory)

        conflict = check_branch_occupancy("feat/x", "feat-x", "2026")

        assert conflict == "remote-tracking branch 'feat/x' already exists"

    def test_check_branch_occupancy_local_ref_oracle(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """A local branch of the name occupies it — the first oracle."""
        monkeypatch.chdir(tmp_path)
        inventory = [
            BranchRef(name="feat/x", remote=False),
            BranchRef(name="origin/feat/x", remote=True),
        ]
        _topic_dir(tmp_path, "2026", "feat-x")
        _wire_inventory(monkeypatch, inventory)

        conflict = check_branch_occupancy("feat/x", "feat-x", "2026")

        assert conflict == "branch 'feat/x' already exists"

    def test_check_branch_occupancy_topic_dir_oracle(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """The topic directory of the year occupies the slug — the last oracle."""
        monkeypatch.chdir(tmp_path)
        _wire_inventory(monkeypatch, [])
        _topic_dir(tmp_path, "2026", "feat-x")

        conflict = check_branch_occupancy("feat/x", "feat-x", "2026")

        assert conflict == "history topic 'feat-x' already exists for 2026"

    def test_check_branch_occupancy_topic_of_another_year_is_free(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The topic oracle is year-scoped — another year's topic is free."""
        monkeypatch.chdir(tmp_path)
        _wire_inventory(monkeypatch, [])
        _topic_dir(tmp_path, "2025", "feat-x")

        assert check_branch_occupancy("feat/x", "feat-x", "2026") is None

    def test_check_branch_occupancy_default_year_is_current(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``year=None`` resolves to the current year — the reported one."""
        monkeypatch.chdir(tmp_path)
        _wire_inventory(monkeypatch, [])
        _topic_dir(tmp_path, "2026", "feat-x")
        monkeypatch.setattr(creation, "current_year", lambda: "2026")

        conflict = check_branch_occupancy("feat/x", "feat-x")

        assert conflict == "history topic 'feat-x' already exists for 2026"

    def test_check_branch_occupancy_free_everywhere(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Every oracle free — ``None``, not an error."""
        monkeypatch.chdir(tmp_path)
        inventory = [BranchRef(name="origin/feat/other", remote=True)]
        _wire_inventory(monkeypatch, inventory)

        assert check_branch_occupancy("feat/x", "feat-x", "2026") is None


# --- Logic tests: the branch-tree slug oracle ---


class TestCheckSlugOccupancy:
    def test_check_slug_occupancy_returns_first_hosting_branch(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The first ref whose tree carries the topic directory names the conflict."""
        monkeypatch.chdir(tmp_path)
        inventory = [
            BranchRef(name="alpha", remote=False),
            BranchRef(name="beta", remote=True),
        ]
        reader = mock.Mock(side_effect=[[], [".goga/history/2026/feature-foo/todo.md"]])
        listing = _wire_slug_oracle(monkeypatch, inventory, reader)

        conflict = check_slug_occupancy("feature-foo", "2026")

        assert conflict == ("topic 'feature-foo' of 2026 is already hosted by branch 'beta'")
        assert reader.call_args.args == ("beta", ".goga/history/2026/feature-foo/")
        listing.assert_called_once_with()

    def test_check_slug_occupancy_stops_at_first_hit(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """The first occupied ref wins — the remaining refs are not probed."""
        monkeypatch.chdir(tmp_path)
        inventory = [
            BranchRef(name="alpha", remote=False),
            BranchRef(name="beta", remote=False),
            BranchRef(name="gamma", remote=False),
        ]
        reader = mock.Mock(
            side_effect=[
                [".goga/history/2026/feature-foo/todo.md"],
                [".goga/history/2026/feature-foo/todo.md"],
                [".goga/history/2026/feature-foo/todo.md"],
            ]
        )
        _wire_slug_oracle(monkeypatch, inventory, reader)

        conflict = check_slug_occupancy("feature-foo", "2026")

        assert conflict == ("topic 'feature-foo' of 2026 is already hosted by branch 'alpha'")
        assert reader.call_count == 1

    def test_check_slug_occupancy_free_slug_returns_none(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """No ref hosts the slug — None, one probe per ref."""
        monkeypatch.chdir(tmp_path)
        inventory = [
            BranchRef(name="alpha", remote=False),
            BranchRef(name="origin/beta", remote=True),
        ]
        reader = mock.Mock(return_value=[])
        listing = _wire_slug_oracle(monkeypatch, inventory, reader)

        assert check_slug_occupancy("feature-foo", "2026") is None
        assert reader.call_count == 2
        listing.assert_called_once_with()

    def test_check_slug_occupancy_does_not_match_sibling_slug_prefix(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A sibling slug sharing the prefix text hosts nothing — the trailing slash.

        The real ``startswith`` filter lives inside the reader, which is
        mocked away here — the emulation keeps the oracle honest about what
        the reader contract returns.
        """
        monkeypatch.chdir(tmp_path)
        inventory = [BranchRef(name="alpha", remote=False)]
        paths = [".goga/history/2026/feature-foo-bar/todo.md"]
        received: list[str] = []

        def emulate_reader(ref: str, prefix: str) -> list[str]:
            received.append(prefix)
            return [path for path in paths if path.startswith(prefix)]

        _wire_slug_oracle(monkeypatch, inventory, emulate_reader)

        assert check_slug_occupancy("feature-foo", "2026") is None
        assert received == [".goga/history/2026/feature-foo/"]

    def test_check_slug_occupancy_ignores_disk_only_topics(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A topic living only in the working copy is invisible to this oracle."""
        monkeypatch.chdir(tmp_path)
        topic_dir = _topic_dir(tmp_path, "2026", "feature-foo")
        (topic_dir / "todo.md").write_text("On disk only\n", encoding="utf-8")
        inventory = [BranchRef(name="alpha", remote=False)]
        reader = mock.Mock(return_value=[])
        _wire_slug_oracle(monkeypatch, inventory, reader)

        assert check_slug_occupancy("feature-foo", "2026") is None

    def test_check_slug_occupancy_default_year_is_current(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``year=None`` resolves to the current year — the probe is year-scoped."""
        monkeypatch.chdir(tmp_path)
        inventory = [BranchRef(name="alpha", remote=False)]
        reader = mock.Mock(return_value=[".goga/history/2026/feature-foo/todo.md"])
        _wire_slug_oracle(monkeypatch, inventory, reader)
        monkeypatch.setattr(creation, "current_year", lambda: "2026")

        conflict = check_slug_occupancy("feature-foo")

        assert conflict == ("topic 'feature-foo' of 2026 is already hosted by branch 'alpha'")
        assert reader.call_args.args == ("alpha", ".goga/history/2026/feature-foo/")


# --- Logic tests: the creation procedure ---


class TestCreateTopic:
    def test_create_topic_no_switch_path_order(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """The default path quarantines the topic into the branch — no switch.

        The preflight resolves the base once, the quarantined plant builds
        one commit carrying todo.md on it and plants the branch there, and
        nothing else runs: no checkout, no working-copy directory, no
        working-copy todo file — the declined publication ask keeps the
        work local.
        """
        monkeypatch.chdir(tmp_path)
        wired = _wire_creation(monkeypatch, current="main", base_commit="c0ffee")
        _tty(monkeypatch)
        monkeypatch.setattr(click, "confirm", mock.Mock(return_value=False))

        result = create_topic("feature-foo", "origin/main", todo="Fix.", year="2026")

        assert result == "Created branch feature-foo and topic 2026/feature-foo"
        assert wired.mock_calls == [
            mock.call.resolve_ref_commit("origin/main"),
            mock.call.plant("feature-foo", "Fix.", "c0ffee", "feature-foo", "2026", "goga: create topic feature-foo"),
        ]
        assert not (tmp_path / ".goga" / "history" / "2026").exists()

    def test_create_topic_switch_path_order(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """The switch path runs its actions in the fixed order.

        The branch is planted at the base commit the preflight resolved,
        the checkout follows, then the topic directory, and the todo
        write is the last action of the path — the declined publication
        ask keeps the work local and the quarantined plant never runs.
        """
        monkeypatch.chdir(tmp_path)
        wired = _wire_creation(monkeypatch, current="main", base_commit="c0ffee")
        wired.ensure_topic_dir.side_effect = lambda name, year: _topic_dir(tmp_path, year, name)
        monkeypatch.setattr(creation, "ensure_topic_dir", wired.ensure_topic_dir)
        _tty(monkeypatch)
        monkeypatch.setattr(click, "confirm", mock.Mock(return_value=False))

        result = create_topic("feature-foo", "origin/main", todo="Fix.", year="2026", switch=True)

        assert result == "Created branch feature-foo and topic 2026/feature-foo"
        assert wired.mock_calls == [
            mock.call.resolve_ref_commit("origin/main"),
            mock.call.create_branch("feature-foo", "c0ffee"),
            mock.call.checkout("feature-foo"),
            mock.call.ensure_topic_dir("feature-foo", "2026"),
        ]
        todo_file = tmp_path / ".goga" / "history" / "2026" / "feature-foo" / "todo.md"
        assert todo_file.read_text(encoding="utf-8") == "Fix.\n"

    def test_create_topic_base_passed_to_the_plant(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """The base is resolved once and the quarantined commit is built on it.

        The no-switch default hands the plant the resolved base commit and
        the final message of the amendment — the applied built-in default
        when no hook amended it.
        """
        monkeypatch.chdir(tmp_path)
        wired = _wire_creation(monkeypatch, base_commit="abc123")

        create_topic("feat-a", "origin/main", todo="T", year="2026")

        wired.resolve_ref_commit.assert_called_once_with("origin/main")
        wired.plant.assert_called_once_with("feat-a", "T", "abc123", "feat-a", "2026", "goga: create topic feat-a")

    def test_create_topic_switch_path_plants_at_the_base_commit(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The switch path plants the branch at the once-resolved base commit."""
        monkeypatch.chdir(tmp_path)
        wired = _wire_creation(monkeypatch, base_commit="abc123")

        create_topic("feat-a", "origin/main", todo="T", year="2026", switch=True)

        wired.resolve_ref_commit.assert_called_once_with("origin/main")
        wired.create_branch.assert_called_once_with("feat-a", "abc123")
        wired.plant.assert_not_called()

    def test_create_topic_publication_ask_yes_delegates(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """An accepted ask delegates the whole work to the publication cycle.

        The delegation reaches ``publish_topic`` at its definition site —
        the call-time import resolves the patched attribute — with the
        name, the resolved todo, the base, the applied template (the
        amendment's final message), and the year; none of the local
        mutations runs.
        """
        monkeypatch.chdir(tmp_path)
        wired = _wire_creation(monkeypatch)
        confirm = mock.Mock(return_value=True)
        monkeypatch.setattr(click, "confirm", confirm)
        published = mock.Mock(return_value="published line")
        monkeypatch.setattr(publishing, "publish_topic", published)
        _tty(monkeypatch)

        result = create_topic("feature-foo", "origin/main", todo="Fix.", year="2026")

        assert result == "published line"
        confirm.assert_called_once_with("Publish the branch to origin?")
        published.assert_called_once_with(
            "feature-foo", "Fix.", "origin/main", "goga: create topic feature-foo", "2026"
        )
        wired.create_branch.assert_not_called()
        wired.checkout.assert_not_called()

    def test_create_topic_publication_ask_empty_answer_is_no(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An empty answer at the ask reads the default no — the work stays local.

        The local outcome of the declined ask is the no-switch plant — no
        checkout runs.
        """
        monkeypatch.chdir(tmp_path)
        wired = _wire_creation(monkeypatch)
        _tty(monkeypatch)
        monkeypatch.setattr(click.termui, "visible_prompt_func", mock.Mock(return_value=""))

        result = create_topic("feature-foo", "origin/main", todo="Fix.", year="2026")

        assert result == "Created branch feature-foo and topic 2026/feature-foo"
        wired.plant.assert_called_once_with(
            "feature-foo", "Fix.", "c0ffee", "feature-foo", "2026", "goga: create topic feature-foo"
        )
        wired.checkout.assert_not_called()

    def test_create_topic_failed_checkout_rolls_back_the_plant(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A failed checkout deletes the planted branch — no stranded name.

        The pre-rework ``git switch -c`` was atomic; the plant-then-checkout
        split is not. A stranded plant would block the retry (the occupancy
        oracle answers "already exists") and the deletion flow cannot
        remove it (a bare branch hosts no topic) — the rollback mirrors
        ``publish_topic``'s push-failure tail.
        """
        monkeypatch.chdir(tmp_path)
        wired = _wire_creation(monkeypatch)
        monkeypatch.setattr(creation, "delete_local_branch", wired.delete_branch)
        wired.checkout.side_effect = subprocess.CalledProcessError(
            1,
            ["git", "switch", "feature-foo"],
            stderr=b"error: Your local changes would be overwritten by checkout",
        )

        with pytest.raises(click.ClickException, match="overwritten by checkout"):
            create_topic("feature-foo", "origin/main", todo="Fix.", year="2026", switch=True)

        wired.delete_branch.assert_called_once_with("feature-foo")

    def test_create_topic_rollback_failure_still_surfaces_checkout_reason(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A broken rollback is suppressed — the checkout reason surfaces."""
        monkeypatch.chdir(tmp_path)
        wired = _wire_creation(monkeypatch)
        monkeypatch.setattr(creation, "delete_local_branch", wired.delete_branch)
        wired.checkout.side_effect = subprocess.CalledProcessError(
            1, ["git", "switch", "feature-foo"], stderr=b"checkout refused"
        )
        wired.delete_branch.side_effect = subprocess.CalledProcessError(
            1, ["git", "update-ref", "-d"], stderr=b"ref lock"
        )

        with pytest.raises(click.ClickException) as raised:
            create_topic("feature-foo", "origin/main", todo="Fix.", year="2026", switch=True)

        assert "checkout refused" in raised.value.message
        assert "ref lock" not in raised.value.message

    def test_create_topic_editor_todo_on_tty(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Without a value the terminal opens the editor; the saved text is
        written with exactly one trailing newline.

        The editor's read-back already ends with a newline — the shared
        write helper must not double it. The switch path carries the text
        into the working copy.
        """
        monkeypatch.chdir(tmp_path)
        _wire_creation(monkeypatch)
        _editor_script(monkeypatch, tmp_path, "printf 'From editor.\\n' > \"$1\"")
        _tty(monkeypatch)
        monkeypatch.setattr(click, "confirm", mock.Mock(return_value=False))

        result = create_topic("feature-foo", "HEAD", year="2026", switch=True)

        assert result == "Created branch feature-foo and topic 2026/feature-foo"
        todo_file = tmp_path / ".goga" / "history" / "2026" / "feature-foo" / "todo.md"
        assert todo_file.read_text(encoding="utf-8") == "From editor.\n"

    def test_create_topic_base_resolved_in_preflight_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An unresolvable base is a preflight error — before any input.

        The editor sentinel never launches: a failing base must not waste
        an entered todo, and no mutation runs.
        """
        monkeypatch.chdir(tmp_path)
        wired = _wire_creation(monkeypatch)
        wired.resolve_ref_commit.side_effect = subprocess.CalledProcessError(
            128, ["git", "rev-parse", "no-such-ref"], stderr=b"fatal: bad revision"
        )
        marker = tmp_path / "editor-launched"
        _editor_script(monkeypatch, tmp_path, f"touch '{marker}'")
        _tty(monkeypatch)

        with pytest.raises(click.ClickException, match="bad revision"):
            create_topic("feature-foo", "no-such-ref", year="2026")

        assert not marker.exists()
        wired.create_branch.assert_not_called()
        wired.checkout.assert_not_called()

    def test_create_topic_empty_slug_preflight_error(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """An empty slug is the first preflight error — nothing else runs.

        The current-branch check, the occupancy oracles, the base
        resolution, and the editor all stay untouched.
        """
        monkeypatch.chdir(tmp_path)
        wired = _wire_creation(monkeypatch)
        probes = mock.Mock()
        monkeypatch.setattr(creation, "resolve_current_branch_name", probes.current_branch)
        monkeypatch.setattr(creation, "check_branch_occupancy", probes.branch_oracle)
        monkeypatch.setattr(creation, "check_slug_occupancy", probes.slug_oracle)
        marker = tmp_path / "editor-launched"
        _editor_script(monkeypatch, tmp_path, f"touch '{marker}'")
        _tty(monkeypatch)

        with pytest.raises(click.ClickException, match="empty topic slug"):
            create_topic("???", "origin/main", todo="x", year="2026")

        probes.assert_not_called()
        wired.resolve_ref_commit.assert_not_called()
        wired.create_branch.assert_not_called()
        assert not marker.exists()

    def test_create_topic_todo_value_wins_over_piped_stdin(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A todo value wins the ladder — the piped channel stays unread.

        The counting pipe would satisfy the declaration, but the value
        rung returns before any read: the recorded read count is zero
        and the written todo is the value.
        """
        monkeypatch.chdir(tmp_path)
        _wire_creation(monkeypatch)
        monkeypatch.setattr(creation, "current_year", lambda: "2026")
        pipe = _CountingPipe(b"piped\n")
        monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(pipe))

        result = create_topic("Feature/Foo", "HEAD", todo="Value.", switch=True)

        assert result == "Created branch Feature/Foo and topic 2026/feature-foo"
        assert pipe.reads.call_count == 0
        todo_file = tmp_path / ".goga" / "history" / "2026" / "feature-foo" / "todo.md"
        assert todo_file.read_text(encoding="utf-8") == "Value.\n"

    def test_create_topic_todo_from_stdin_with_content(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A declared piped todo becomes the todo verbatim — no editor, no ask.

        The piped text already ends in one newline and the write keeps
        exactly that one; the call runs fully non-interactive.
        """
        monkeypatch.chdir(tmp_path)
        _wire_creation(monkeypatch)
        monkeypatch.setattr(creation, "current_year", lambda: "2026")
        _piped_stdin(monkeypatch, b"First\nSecond\n")
        editor = mock.MagicMock()
        monkeypatch.setattr(creation, "edit_text", editor)
        confirm = mock.MagicMock()
        monkeypatch.setattr(click, "confirm", confirm)

        result = create_topic("Feature/Foo", "HEAD", todo_from_stdin=True, switch=True)

        assert result == "Created branch Feature/Foo and topic 2026/feature-foo"
        todo_file = tmp_path / ".goga" / "history" / "2026" / "feature-foo" / "todo.md"
        assert todo_file.read_text(encoding="utf-8") == "First\nSecond\n"
        editor.assert_not_called()
        confirm.assert_not_called()

    def test_create_topic_publication_ask_skipped_when_todo_came_from_stdin(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A stdin-sourced todo never triggers the publication ask.

        The confirm would answer yes and hand the work to the fast cycle;
        the skipped ask keeps the quarantined plant local, carrying the
        verbatim piped todo — the ``wired.plant`` touchpoint records it.
        """
        monkeypatch.chdir(tmp_path)
        wired = _wire_creation(monkeypatch)
        monkeypatch.setattr(creation, "current_year", lambda: "2026")
        _piped_stdin(monkeypatch, b"First\n")
        confirm = mock.MagicMock(return_value=True)
        monkeypatch.setattr(click, "confirm", confirm)

        result = create_topic("Feature/Foo", "HEAD", todo_from_stdin=True)

        assert result == "Created branch Feature/Foo and topic 2026/feature-foo"
        confirm.assert_not_called()
        wired.plant.assert_called_once_with(
            "Feature/Foo", "First\n", "c0ffee", "feature-foo", "2026", "goga: create topic feature-foo"
        )

    def test_create_topic_amendment_receives_stdin_todo(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        recording_hooks: RecordedEntry,
    ) -> None:
        """The stdin todo passes through the same creation amendment.

        The amendment context carries the verbatim piped text and the
        notification follows the completed path with its checked-out
        fact — the source of the todo changes nothing downstream.
        """
        monkeypatch.chdir(tmp_path)
        _wire_creation(monkeypatch)
        _piped_stdin(monkeypatch, b"Piped todo.\n")
        records = recording_hooks(("amend_creation", "topic_created"))

        result = create_topic("Feature/Foo", "HEAD", todo_from_stdin=True, switch=True)

        assert result == "Created branch Feature/Foo and topic 2026/feature-foo"
        assert [entry[1] for entry in records] == ["amend_creation", "topic_created"]
        amendment, created = records[0][2], records[1][2]
        assert amendment.todo == "Piped todo.\n"  # type: ignore[attr-defined]
        assert created.checked_out is True  # type: ignore[attr-defined]

    def test_create_topic_piped_content_without_declaration_is_clean_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Piped content with no declared source is never silently ignored.

        The old immediate-error policy of a value-less todo on a
        non-terminal is gone — this is the ladder's content rule: a pipe
        carrying content while neither a value nor the declaration was
        given is one clean error naming the todo option, before any
        mutation and before the editor.
        """
        monkeypatch.chdir(tmp_path)
        wired = _wire_creation(monkeypatch)
        _piped_stdin(monkeypatch, b"piped content\n")
        editor = mock.MagicMock()
        monkeypatch.setattr(creation, "edit_text", editor)

        with pytest.raises(click.ClickException, match="--todo"):
            create_topic("Feature/Foo", "HEAD", switch=True)

        editor.assert_not_called()
        wired.create_branch.assert_not_called()
        wired.checkout.assert_not_called()

    def test_create_topic_stdin_non_utf8_is_clean_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Piped bytes outside UTF-8 are one clean error naming the todo.

        The decode converts at the decode site — the error must surface
        as the clean boundary, not a raw ``UnicodeDecodeError``.
        """
        monkeypatch.chdir(tmp_path)
        wired = _wire_creation(monkeypatch)
        _piped_stdin(monkeypatch, b"\xff\xfe\n")

        with pytest.raises(click.ClickException, match="--todo"):
            create_topic("Feature/Foo", "HEAD", todo_from_stdin=True, switch=True)

        wired.create_branch.assert_not_called()
        wired.checkout.assert_not_called()
        assert not (tmp_path / ".goga").exists()

    def test_create_topic_headless_no_switch_without_todo_is_local_todo_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Headless with a bare pipe and no declaration the ladder leaves no
        todo — the path rules decide.

        The no-switch work exists only through its committed todo.md, so
        the local-todo error fires naming the todo sources — the value,
        the piped stdin — and the switch form; nothing mutated.
        """
        monkeypatch.chdir(tmp_path)
        wired = _wire_creation(monkeypatch)
        _non_interactive(monkeypatch)

        with pytest.raises(click.ClickException) as raised:
            create_topic("Feature/Foo", "HEAD")

        assert "the local creation needs a todo" in raised.value.message
        assert "--todo" in raised.value.message
        assert "stdin" in raised.value.message
        assert "--switch" in raised.value.message
        wired.create_branch.assert_not_called()
        wired.plant.assert_not_called()

    def test_create_topic_tty_stdin_never_read(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """A terminal stdin is never read — the editor rung resolves the todo.

        The guarded pipe mock makes any buffer read visible; the editor
        session supplies the todo and the write lands its saved text.
        """
        monkeypatch.chdir(tmp_path)
        _wire_creation(monkeypatch)
        monkeypatch.setattr(creation, "current_year", lambda: "2026")
        stdin = _TtyStdin()
        monkeypatch.setattr(sys, "stdin", stdin)
        _stub_edit_text(monkeypatch, "Editor text.")
        monkeypatch.setattr(click, "confirm", mock.Mock(return_value=False))

        result = create_topic("Feature/Foo", "HEAD", switch=True)

        assert result == "Created branch Feature/Foo and topic 2026/feature-foo"
        stdin.pipe.read.assert_not_called()
        todo_file = tmp_path / ".goga" / "history" / "2026" / "feature-foo" / "todo.md"
        assert todo_file.read_text(encoding="utf-8") == "Editor text.\n"

    def test_create_topic_declared_bare_stdin_falls_to_editor(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The declaration with a terminal stdin reads nothing — the editor
        rung resolves the todo.

        The read sits behind the non-terminal branch of the ladder, so a
        declared bare pipe on a terminal is the editor's case.
        """
        monkeypatch.chdir(tmp_path)
        _wire_creation(monkeypatch)
        monkeypatch.setattr(creation, "current_year", lambda: "2026")
        stdin = _TtyStdin()
        monkeypatch.setattr(sys, "stdin", stdin)
        _stub_edit_text(monkeypatch, "Typed.")
        monkeypatch.setattr(click, "confirm", mock.Mock(return_value=False))

        result = create_topic("Feature/Foo", "HEAD", todo_from_stdin=True, switch=True)

        assert result == "Created branch Feature/Foo and topic 2026/feature-foo"
        stdin.pipe.read.assert_not_called()
        todo_file = tmp_path / ".goga" / "history" / "2026" / "feature-foo" / "todo.md"
        assert todo_file.read_text(encoding="utf-8") == "Typed.\n"

    def test_create_topic_whitespace_only_stdin_counts_as_bare(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Whitespace-only piped content is bare — the strip decides, the
        content is never trimmed.

        The pipe carries non-empty bytes, so a byte-emptiness check
        would take it for content and fail here with the never-ignored
        clean error; the ladder falls through instead, the headless
        editor never opens, and the switch path needs no todo.
        """
        monkeypatch.chdir(tmp_path)
        _wire_creation(monkeypatch)
        monkeypatch.setattr(creation, "current_year", lambda: "2026")
        _piped_stdin(monkeypatch, b"\n  \t\n")
        editor = mock.MagicMock()
        monkeypatch.setattr(creation, "edit_text", editor)

        result = create_topic("Feature/Foo", "HEAD", todo_from_stdin=True, switch=True)

        assert result == "Created branch Feature/Foo and topic 2026/feature-foo"
        editor.assert_not_called()
        assert not (tmp_path / ".goga" / "history" / "2026" / "feature-foo" / "todo.md").exists()

    def test_create_topic_publish_without_todo_error(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """The publication path with a cancelled editor entry is a clean
        error asking for the todo — a todo-less publish never happens."""
        monkeypatch.chdir(tmp_path)
        wired = _wire_creation(monkeypatch)
        _editor_script(monkeypatch, tmp_path, "exit 0")
        _tty(monkeypatch)

        with pytest.raises(click.ClickException, match="needs a todo"):
            create_topic("feature-foo", "origin/main", publish=True, year="2026")

        wired.create_branch.assert_not_called()
        wired.checkout.assert_not_called()

    def test_create_topic_publish_with_editor_todo_delegates_without_ask(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``publish=True`` delegates the editor-resolved todo — never the ask.

        The fast cycle must receive the resolved text (the editor's
        read-back, trailing newline and all), not the absent value option,
        and the confirm never fires: ``--publish`` is ask-free by contract.
        The template travels applied — the amendment's final message.
        """
        monkeypatch.chdir(tmp_path)
        wired = _wire_creation(monkeypatch)
        _editor_script(monkeypatch, tmp_path, "printf 'From editor.\\n' > \"$1\"")
        _tty(monkeypatch)
        confirm = mock.Mock()
        monkeypatch.setattr(click, "confirm", confirm)
        published = mock.Mock(return_value="published line")
        monkeypatch.setattr(publishing, "publish_topic", published)

        result = create_topic("feature-foo", "origin/main", publish=True, year="2026")

        assert result == "published line"
        published.assert_called_once_with(
            "feature-foo", "From editor.\n", "origin/main", "goga: create topic feature-foo", "2026"
        )
        confirm.assert_not_called()
        wired.create_branch.assert_not_called()
        wired.checkout.assert_not_called()

    def test_create_topic_current_branch_same_slug_is_conflict(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The current branch hosting the slug is a conflict — the
        idempotent path is abolished; no input, no mutation."""
        monkeypatch.chdir(tmp_path)
        wired = _wire_creation(monkeypatch, current="feature-foo")
        marker = tmp_path / "editor-launched"
        _editor_script(monkeypatch, tmp_path, f"touch '{marker}'")
        _tty(monkeypatch)

        with pytest.raises(click.ClickException, match="already hosts"):
            create_topic("feature-foo", "origin/main", todo="x")

        assert not marker.exists()
        wired.create_branch.assert_not_called()

    def test_create_topic_occupied_name_error_no_reask(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """An occupancy conflict is one clean error with the board hint —
        the abolished re-ask must not resurrect."""
        monkeypatch.chdir(tmp_path)
        _tty(monkeypatch)
        _editor_script(monkeypatch, tmp_path, "exit 0")
        prompt = mock.Mock()
        monkeypatch.setattr(click, "prompt", prompt)
        wired = _wire_creation(monkeypatch, current="main")
        monkeypatch.setattr(
            creation,
            "list_branch_refs",
            lambda: [BranchRef(name="feat/x", remote=False)],
        )

        with pytest.raises(click.ClickException) as raised:
            create_topic("feat/x", "HEAD")

        assert raised.value.message == ("branch 'feat/x' already exists — run 'goga topics board' to see the board")
        prompt.assert_not_called()
        wired.create_branch.assert_not_called()
        assert not (tmp_path / ".goga" / "history").exists()

    def test_create_topic_creates_branch_and_dir_with_cancelled_entry(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A free name with a cancelled editor entry on the switch path: the
        verbatim branch and the slug directory — and no todo file."""
        monkeypatch.chdir(tmp_path)
        wired = _wire_creation(monkeypatch, current="main")
        _editor_script(monkeypatch, tmp_path, "exit 0")
        _tty(monkeypatch)

        result = create_topic("Feature/Foo_Bar", "HEAD", year="2025", switch=True)

        assert result == "Created branch Feature/Foo_Bar and topic 2025/feature-foo-bar"
        wired.create_branch.assert_called_once_with("Feature/Foo_Bar", "c0ffee")
        wired.checkout.assert_called_once_with("Feature/Foo_Bar")
        topic_dir = tmp_path / ".goga" / "history" / "2025" / "feature-foo-bar"
        assert topic_dir.is_dir()
        assert not (topic_dir / "todo.md").exists()

    def test_create_topic_no_switch_cancelled_entry_is_clean_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A cancelled editor entry on the default path is a clean error.

        Git keeps no empty directories — without a committed todo.md the
        no-switch work exists in no tree, so the todo is required exactly
        as it is under the publication; the error names the two ways out.
        """
        monkeypatch.chdir(tmp_path)
        wired = _wire_creation(monkeypatch, current="main")
        _editor_script(monkeypatch, tmp_path, "exit 0")
        _tty(monkeypatch)

        with pytest.raises(click.ClickException) as raised:
            create_topic("Feature/Foo_Bar", "HEAD", year="2025")

        assert "the local creation needs a todo" in raised.value.message
        assert "todo.md" in raised.value.message
        wired.plant.assert_not_called()
        wired.create_branch.assert_not_called()
        wired.checkout.assert_not_called()

    def test_create_topic_default_year_is_current(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Without a year the topic of the switch-path directory lands in the current one."""
        monkeypatch.chdir(tmp_path)
        _wire_creation(monkeypatch, current="main")
        _editor_script(monkeypatch, tmp_path, "exit 0")
        _tty(monkeypatch)
        monkeypatch.setattr(creation, "current_year", lambda: "2026")

        result = create_topic("Feature/Foo_Bar", "HEAD", switch=True)

        assert result == "Created branch Feature/Foo_Bar and topic 2026/feature-foo-bar"
        assert (tmp_path / ".goga" / "history" / "2026" / "feature-foo-bar").is_dir()

    def test_create_topic_no_switch_default_year_is_current(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Without a year the quarantined commit carries the current year's path."""
        monkeypatch.chdir(tmp_path)
        wired = _wire_creation(monkeypatch, current="main")
        monkeypatch.setattr(creation, "current_year", lambda: "2026")

        result = create_topic("Feature/Foo_Bar", "HEAD", todo="T")

        assert result == "Created branch Feature/Foo_Bar and topic 2026/feature-foo-bar"
        wired.plant.assert_called_once_with(
            "Feature/Foo_Bar", "T", "c0ffee", "feature-foo-bar", "2026", "goga: create topic feature-foo-bar"
        )

    def test_create_topic_with_todo_value(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """A free name with a todo value: the quarantined plant, nothing on disk.

        The default path hands the resolved todo to the plant — the
        working copy keeps no directory and no file.
        """
        monkeypatch.chdir(tmp_path)
        wired = _wire_creation(monkeypatch, current="main")

        result = create_topic("Feature/Foo_Bar", "HEAD", todo="Payment retry", year="2026")

        assert result == "Created branch Feature/Foo_Bar and topic 2026/feature-foo-bar"
        wired.plant.assert_called_once_with(
            "Feature/Foo_Bar",
            "Payment retry",
            "c0ffee",
            "feature-foo-bar",
            "2026",
            "goga: create topic feature-foo-bar",
        )
        wired.checkout.assert_not_called()
        assert not (tmp_path / ".goga" / "history" / "2026" / "feature-foo-bar").exists()

    def test_create_topic_with_todo_value_switch_writes_the_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A free name with a todo value on the switch path: the branch, the
        directory, the todo file."""
        monkeypatch.chdir(tmp_path)
        _wire_creation(monkeypatch, current="main")

        result = create_topic("Feature/Foo_Bar", "HEAD", todo="Payment retry", year="2026", switch=True)

        assert result == "Created branch Feature/Foo_Bar and topic 2026/feature-foo-bar"
        todo_file = tmp_path / ".goga" / "history" / "2026" / "feature-foo-bar" / "todo.md"
        assert todo_file.read_bytes() == b"Payment retry\n"

    def test_create_topic_writes_multiline_todo(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """A multi-line todo on the switch path: the file carries the text
        verbatim plus one newline."""
        monkeypatch.chdir(tmp_path)
        _wire_creation(monkeypatch, current="main")

        result = create_topic(
            "Feature/Foo_Bar",
            "HEAD",
            year="2026",
            todo="Fix payment retries.\n\nRetries ignore the cap.",
            switch=True,
        )

        assert result == "Created branch Feature/Foo_Bar and topic 2026/feature-foo-bar"
        topic_dir = tmp_path / ".goga" / "history" / "2026" / "feature-foo-bar"
        # Empty lines inside the text stay as entered; one trailing newline.
        assert (topic_dir / "todo.md").read_bytes() == (b"Fix payment retries.\n\nRetries ignore the cap.\n")
        # The todo file is the single artifact of the topic directory.
        assert [path.name for path in topic_dir.iterdir()] == ["todo.md"]

    def test_create_topic_whitespace_todo_writes_verbatim(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A whitespace-only todo is a non-empty text — the switch path
        writes it verbatim."""
        monkeypatch.chdir(tmp_path)
        _wire_creation(monkeypatch, current="main")

        result = create_topic("feat-a", "HEAD", year="2026", todo="  ", switch=True)

        assert result == "Created branch feat-a and topic 2026/feat-a"
        topic_dir = tmp_path / ".goga" / "history" / "2026" / "feat-a"
        assert (topic_dir / "todo.md").read_bytes() == b"  \n"

    def test_create_topic_todo_write_failure_is_clean_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A failing todo write of the switch path becomes the generalized
        clean error."""
        monkeypatch.chdir(tmp_path)
        wired = _wire_creation(monkeypatch, current="main")
        monkeypatch.setattr(
            creation,
            "resolve_topic_file",
            mock.Mock(side_effect=OSError("disk full")),
        )

        with pytest.raises(click.ClickException) as raised:
            create_topic("Feature/Foo_Bar", "HEAD", todo="T", year="2026", switch=True)

        assert "cannot create the topic directory or write the todo file" in raised.value.message
        # The traced order — the branch mutations run before the todo write.
        wired.create_branch.assert_called_once_with("Feature/Foo_Bar", "c0ffee")

    def test_create_topic_no_switch_emits_created_with_commit_hash(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        recording_hooks: RecordedEntry,
    ) -> None:
        """The no-switch path amends before the plant and emits after it.

        The hash comes from the plant's existing return — no new git read —
        and every fact comes from the operation's own data: the identity
        from the slug, the resolved year, and the name as entered; the
        message the commit lands is the message the notification reports.
        """

        monkeypatch.chdir(tmp_path)
        wired = _wire_creation(monkeypatch, current="main", base_commit="c0ffee")
        wired.plant.return_value = "deadbeef"
        _tty(monkeypatch)
        _stub_edit_text(monkeypatch, "the todo")
        monkeypatch.setattr(click, "confirm", mock.Mock(return_value=False))
        records = recording_hooks(("amend_creation", "topic_created"))

        result = create_topic("Feature/Foo_Bar", "HEAD", todo=None, year="2026")

        assert result == "Created branch Feature/Foo_Bar and topic 2026/feature-foo-bar"
        wired.plant.assert_called_once_with(
            "Feature/Foo_Bar", "the todo", "c0ffee", "feature-foo-bar", "2026", "goga: create topic feature-foo-bar"
        )
        assert [entry[1] for entry in records] == ["amend_creation", "topic_created"]
        amendment, created = records[0][2], records[1][2]
        assert amendment.checked_out is False  # type: ignore[attr-defined]
        assert amendment.published is False  # type: ignore[attr-defined]
        assert amendment.commit_message == "goga: create topic feature-foo-bar"  # type: ignore[attr-defined]
        assert amendment.todo == "the todo"  # type: ignore[attr-defined]
        assert amendment.identity.slug == "feature-foo-bar"  # type: ignore[attr-defined]
        assert amendment.identity.branch == "Feature/Foo_Bar"  # type: ignore[attr-defined]
        assert created.checked_out is False  # type: ignore[attr-defined]
        assert created.published is False  # type: ignore[attr-defined]
        assert created.todo == "the todo"  # type: ignore[attr-defined]
        assert created.commit_message == "goga: create topic feature-foo-bar"  # type: ignore[attr-defined]
        assert created.commit_hash == "deadbeef"  # type: ignore[attr-defined]
        assert created.identity.home_path == ".goga/history/2026/feature-foo-bar"  # type: ignore[attr-defined]

    def test_create_topic_failed_preflight_fires_nothing(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        recording_hooks: RecordedEntry,
    ) -> None:
        """A failed creation fires nothing — the amendment delivers only
        immediately before the first mutation, never before the decisions."""
        monkeypatch.chdir(tmp_path)
        _wire_creation(monkeypatch, current="main")
        monkeypatch.setattr(
            creation,
            "check_branch_occupancy",
            mock.Mock(return_value="branch 'Feature/Foo_Bar' already exists"),
        )
        records = recording_hooks()

        with pytest.raises(click.ClickException, match="already exists"):
            create_topic("Feature/Foo_Bar", "HEAD", todo="x", year="2026")

        assert records == []

    def test_create_topic_switch_path_amended_null_todo_degrades_gracefully(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        recording_hooks: RecordedEntry,
        install_tool_package: InstallToolPackage,
    ) -> None:
        """The switch path's todo is optional — a nulled amended todo writes
        nothing and the notification reports the truth."""

        def amender(context: object) -> None:
            context.amend(None, None)  # type: ignore[attr-defined]

        monkeypatch.chdir(tmp_path)
        wired = _wire_creation(monkeypatch, current="main")
        records = recording_hooks("topic_created")
        install_tool_package("goga_tool_two", register_hooks=_subscribe(("amend_creation", amender)))

        result = create_topic("Feature/Foo_Bar", "HEAD", todo="the todo", switch=True, year="2026")

        assert result == "Created branch Feature/Foo_Bar and topic 2026/feature-foo-bar"
        wired.create_branch.assert_called_once_with("Feature/Foo_Bar", "c0ffee")
        wired.checkout.assert_called_once_with("Feature/Foo_Bar")
        assert len(records) == 1
        context = records[0][2]
        assert context.todo is None  # type: ignore[attr-defined]
        assert context.checked_out is True  # type: ignore[attr-defined]
        assert context.published is False  # type: ignore[attr-defined]
        assert context.commit_message is None  # type: ignore[attr-defined]
        assert context.commit_hash is None  # type: ignore[attr-defined]
        todo_file = tmp_path / ".goga" / "history" / "2026" / "feature-foo-bar" / "todo.md"
        assert not todo_file.exists()

    def test_create_topic_no_switch_amended_values_land_in_plant_and_event(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        recording_hooks: RecordedEntry,
        install_tool_package: InstallToolPackage,
    ) -> None:
        """The committed content and the commit message are the final
        amended values — the plant lands the amended pair in git and the
        creation notification reports the same pair, not the draft."""

        def amender(context: object) -> None:
            context.amend("amended message", "amended todo")  # type: ignore[attr-defined]

        monkeypatch.chdir(tmp_path)
        wired = _wire_creation(monkeypatch, current="main", base_commit="c0ffee")
        wired.plant.return_value = "deadbeef"
        install_tool_package("goga_tool_two", register_hooks=_subscribe(("amend_creation", amender)))
        records = recording_hooks(("amend_creation", "topic_created"))

        result = create_topic("Feature/Foo_Bar", "HEAD", todo="the todo", year="2026")

        assert result == "Created branch Feature/Foo_Bar and topic 2026/feature-foo-bar"
        wired.plant.assert_called_once_with(
            "Feature/Foo_Bar", "amended todo", "c0ffee", "feature-foo-bar", "2026", "amended message"
        )
        assert [entry[1] for entry in records] == ["amend_creation", "topic_created"]
        created = records[1][2]
        assert created.todo == "amended todo"  # type: ignore[attr-defined]
        assert created.commit_message == "amended message"  # type: ignore[attr-defined]
        assert created.commit_hash == "deadbeef"  # type: ignore[attr-defined]

    def test_create_topic_no_switch_nulled_amended_todo_is_clean_error_before_mutations(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        recording_hooks: RecordedEntry,
        install_tool_package: InstallToolPackage,
    ) -> None:
        """D5 — a hook nulled the todo of a path that needs one: the guard
        fires before any mutation, the creation emits nothing, and the
        error is the same clean one as the resolved-todo guard."""

        def nuller(context: object) -> None:
            context.amend("message only", None)  # type: ignore[attr-defined]

        monkeypatch.chdir(tmp_path)
        wired = _wire_creation(monkeypatch, current="main")
        install_tool_package("goga_tool_two", register_hooks=_subscribe(("amend_creation", nuller)))
        records = recording_hooks()

        with pytest.raises(click.ClickException) as raised:
            create_topic("Feature/Foo_Bar", "HEAD", todo="the todo", year="2026")

        assert raised.value.message == (
            "the local creation needs a todo — the board reads the topic through todo.md; "
            "pass --todo/-t with a value, or pipe the todo into stdin and pass the value-less --todo, "
            "or --switch/-s to create on the spot without one"
        )
        wired.plant.assert_not_called()
        wired.create_branch.assert_not_called()
        assert [entry[1] for entry in records] == ["amend_creation"]

    def test_create_topic_no_switch_nulled_amended_message_falls_back_to_default(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        recording_hooks: RecordedEntry,
        install_tool_package: InstallToolPackage,
    ) -> None:
        """D3 — a hook nulled only the message: the plant lands the
        built-in default template and the notification reports the same
        default, one value in the commit and the event alike."""

        def nuller(context: object) -> None:
            context.amend(None, "amended todo")  # type: ignore[attr-defined]

        monkeypatch.chdir(tmp_path)
        wired = _wire_creation(monkeypatch, current="main")
        wired.plant.return_value = "deadbeef"
        install_tool_package("goga_tool_two", register_hooks=_subscribe(("amend_creation", nuller)))
        records = recording_hooks(("amend_creation", "topic_created"))

        result = create_topic("Feature/Foo_Bar", "HEAD", todo="the todo", year="2026")

        assert result == "Created branch Feature/Foo_Bar and topic 2026/feature-foo-bar"
        # The plant receives the nulled message and applies its built-in
        # default — the event reports the same applied default.
        wired.plant.assert_called_once_with(
            "Feature/Foo_Bar", "amended todo", "c0ffee", "feature-foo-bar", "2026", None
        )
        created = records[1][2]
        assert created.todo == "amended todo"  # type: ignore[attr-defined]
        assert created.commit_message == "goga: create topic feature-foo-bar"  # type: ignore[attr-defined]
        assert created.commit_hash == "deadbeef"  # type: ignore[attr-defined]

    def test_create_topic_publication_path_fires_its_pair_through_the_delegation(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        recording_hooks: RecordedEntry,
        install_tool_package: InstallToolPackage,
    ) -> None:
        """The publication branch delegates whole: the creation amendment
        delivers here with the path's facts, the amended pair travels into
        the delegated publication, and the delegation fires the
        publication pair itself after its push — every checkpoint exactly
        once, nothing fires twice.

        The delegated cycle re-runs its own preflight over publishing's
        import points — the wiring pins them, so the real delegation runs
        behind the recording hooks.
        """

        def amender(context: object) -> None:
            seen.append((context.commit_message, context.todo))  # type: ignore[attr-defined]
            context.amend("amended message", "amended todo")  # type: ignore[attr-defined]

        seen: list[tuple[str | None, str | None]] = []
        monkeypatch.chdir(tmp_path)
        wired = _wire_creation(monkeypatch, current="main", base_commit="c0ffee")
        wired.plant.return_value = "deadbeef"
        monkeypatch.setattr(publishing, "resolve_current_branch_name", mock.Mock(return_value="main"))
        monkeypatch.setattr(publishing, "check_branch_occupancy", mock.Mock(return_value=None))
        monkeypatch.setattr(publishing, "check_slug_occupancy", mock.Mock(return_value=None))
        monkeypatch.setattr(publishing, "origin_configured", mock.Mock(return_value=True))
        monkeypatch.setattr(publishing, "resolve_ref_commit", mock.Mock(return_value="c0ffee"))
        monkeypatch.setattr(publishing, "push_branch", mock.Mock())
        install_tool_package("goga_tool_two", register_hooks=_subscribe(("amend_creation", amender)))
        records = recording_hooks()

        result = create_topic("Feature/Foo_Bar", "HEAD", todo="the todo", publish=True, year="2026")

        assert result == "Created branch Feature/Foo_Bar and published topic 2026/feature-foo-bar"
        assert [entry[1] for entry in records] == ["amend_creation", "topic_created", "topic_published"]
        amendment = records[0][2]
        assert amendment.checked_out is False  # type: ignore[attr-defined]
        assert amendment.published is True  # type: ignore[attr-defined]
        assert amendment.identity.branch == "Feature/Foo_Bar"  # type: ignore[attr-defined]
        # The applied default template is the draft the hook received —
        # the recorder's own content reads show the final amended pair.
        assert seen == [("goga: create topic feature-foo-bar", "the todo")]
        # The amended pair is what the delegated plant lands in git.
        wired.plant.assert_called_once_with(
            "Feature/Foo_Bar", "amended todo", "c0ffee", "feature-foo-bar", "2026", "amended message"
        )
        created, published = records[1][2], records[2][2]
        assert created.checked_out is False  # type: ignore[attr-defined]
        assert created.published is True  # type: ignore[attr-defined]
        assert created.todo == "amended todo"  # type: ignore[attr-defined]
        assert created.commit_message == "amended message"  # type: ignore[attr-defined]
        assert created.commit_hash == "deadbeef"  # type: ignore[attr-defined]
        assert published.commit_message == "amended message"  # type: ignore[attr-defined]
        assert published.commit_hash == "deadbeef"  # type: ignore[attr-defined]
        assert published.todo == "amended todo"  # type: ignore[attr-defined]


# --- Logic tests: the todo entry of a topic ---


class TestEnterTopicTodo:
    @pytest.mark.parametrize(
        ("editor_command", "expected_result", "expected_content"),
        [
            ("printf 'New line.\\n' > \"$1\"", True, "New line.\n"),
            ("exit 0", False, "Old line.\n"),
        ],
    )
    def test_enter_topic_todo_edits_existing_file(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        editor_command: str,
        expected_result: bool,
        expected_content: str,
    ) -> None:
        """An existing todo.md seeds the session; the saved text overwrites it.

        A cancelled session — an editor that never writes — returns False
        and leaves the file verbatim.
        """
        monkeypatch.chdir(tmp_path)
        todo_file = _topic_dir(tmp_path, "2026", "feature-foo") / "todo.md"
        _tty(monkeypatch)

        todo_file.write_text("Old line.\n", encoding="utf-8")
        _editor_script(monkeypatch, tmp_path, editor_command)

        assert enter_topic_todo("feature-foo", year="2026") is expected_result
        assert todo_file.read_text(encoding="utf-8") == expected_content

    def test_enter_topic_todo_seeds_existing_content(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """The session starts from the existing todo.md — the prefill proves it.

        The editor script copies the prefilled temporary file aside instead
        of editing: the prefill must carry the existing content verbatim
        (the session's own normalization keeps the trailing newline).
        """
        monkeypatch.chdir(tmp_path)
        todo_file = _topic_dir(tmp_path, "2026", "feature-foo") / "todo.md"
        todo_file.write_text("Old line.\n", encoding="utf-8")
        prefill = tmp_path / "prefill.txt"
        _editor_script(monkeypatch, tmp_path, f"cp \"$1\" '{prefill}'")
        _tty(monkeypatch)

        assert enter_topic_todo("feature-foo", year="2026") is False
        assert prefill.read_text(encoding="utf-8") == "Old line.\n"
        assert todo_file.read_text(encoding="utf-8") == "Old line.\n"

    def test_enter_topic_todo_missing_file_empty_entry(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """A missing todo.md starts from an empty entry — the fresh-entry path.

        The topic directory exists without the file — the state after
        ``ensure`` on a branch whose tree hosts no todo yet.
        """
        monkeypatch.chdir(tmp_path)
        _topic_dir(tmp_path, "2026", "feature-foo")
        _editor_script(monkeypatch, tmp_path, "printf 'First.\\n' > \"$1\"")
        _tty(monkeypatch)

        assert enter_topic_todo("feature-foo", year="2026") is True

        todo_file = tmp_path / ".goga" / "history" / "2026" / "feature-foo" / "todo.md"
        assert todo_file.read_text(encoding="utf-8") == "First.\n"

    def test_enter_topic_todo_non_utf8_prefill_decodes_replacement(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A non-UTF-8 todo.md prefills with replacement bytes, not a traceback.

        The prefill is display data — a ``UnicodeDecodeError`` is a
        ``ValueError`` that matches none of the module's handlers, so the
        strict read would pierce the clean-error boundary of
        ``switch --todo`` and ``pipeline --todo``. The editor script only
        writes when the prefill carried the readable part, pinning that
        the file was actually read.
        """
        monkeypatch.chdir(tmp_path)
        todo_file = _topic_dir(tmp_path, "2026", "feature-foo") / "todo.md"
        todo_file.write_bytes("Old line.\n\xff\n".encode("latin-1"))
        _editor_script(
            monkeypatch,
            tmp_path,
            "grep -q 'Old line.' \"$1\" && printf 'New line.\\n' > \"$1\"",
        )
        _tty(monkeypatch)

        assert enter_topic_todo("feature-foo", year="2026") is True
        assert todo_file.read_text(encoding="utf-8") == "New line.\n"

    def test_enter_topic_todo_read_failure_is_clean_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A failing prefill read is a clean error — before the editor.

        A directory named ``todo.md`` makes ``read_text`` raise
        ``IsADirectoryError``; the boundary must fold it instead of
        letting a raw traceback reach the CLI.
        """
        monkeypatch.chdir(tmp_path)
        (_topic_dir(tmp_path, "2026", "feature-foo") / "todo.md").mkdir()
        marker = tmp_path / "editor-launched"
        _editor_script(monkeypatch, tmp_path, f"touch '{marker}'")
        _tty(monkeypatch)

        with pytest.raises(click.ClickException) as raised:
            enter_topic_todo("feature-foo", year="2026")

        assert "cannot read or write the todo file" in raised.value.message
        assert not marker.exists()

    def test_enter_topic_todo_writes_amended_text_and_emits_final(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        recording_hooks: RecordedEntry,
        install_tool_package: InstallToolPackage,
    ) -> None:
        """The saved text passes through the amendment; the file and the
        notification carry the same final amended text.

        The delivery order of the entry — amend before the write, emit
        after it — makes the written content and the reported content one
        value: the ``.usages/todo-entry.md`` clause made executable.
        """

        def amender(context: object) -> None:
            context.amend("amended text")  # type: ignore[attr-defined]

        monkeypatch.chdir(tmp_path)
        _topic_dir(tmp_path, "2026", "feature-foo")
        _stub_edit_text(monkeypatch, "saved text")
        records = recording_hooks("topic_todo_entered")
        install_tool_package("goga_tool_two", register_hooks=_subscribe(("amend_todo_entry", amender)))

        result = enter_topic_todo("feature-foo", year="2026", branch="feature-foo")

        assert result is True
        todo_file = tmp_path / ".goga" / "history" / "2026" / "feature-foo" / "todo.md"
        assert todo_file.read_text(encoding="utf-8") == "amended text\n"
        assert len(records) == 1
        context = records[0][2]
        assert context.text == "amended text"  # type: ignore[attr-defined]
        assert context.identity.branch == "feature-foo"  # type: ignore[attr-defined]

    def test_enter_topic_todo_cancelled_entry_delivers_and_emits_nothing(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        recording_hooks: RecordedEntry,
    ) -> None:
        """A cancelled entry is a non-event — the amendment moment never
        arrives, no checkpoint of the entry fires."""
        monkeypatch.chdir(tmp_path)
        _topic_dir(tmp_path, "2026", "feature-foo")
        _stub_edit_text(monkeypatch, None)
        records = recording_hooks()

        result = enter_topic_todo("feature-foo", year="2026")

        assert result is False
        todo_file = tmp_path / ".goga" / "history" / "2026" / "feature-foo" / "todo.md"
        assert not todo_file.exists()
        assert records == []

    def test_enter_topic_todo_failed_write_emits_nothing(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        recording_hooks: RecordedEntry,
    ) -> None:
        """A failed write never emits — the write-then-emit order on the
        failure path guarantees the event carries a written fact."""
        monkeypatch.chdir(tmp_path)
        _topic_dir(tmp_path, "2026", "feature-foo")
        _stub_edit_text(monkeypatch, "saved")
        monkeypatch.setattr(creation, "_write_todo", mock.Mock(side_effect=OSError("disk full")))
        records = recording_hooks("topic_todo_entered")

        with pytest.raises(click.ClickException, match="cannot read or write the todo file"):
            enter_topic_todo("feature-foo", year="2026")

        assert records == []


# --- Infrastructure boundary ---


class TestCreationInfrastructureBoundary:
    def test_git_failure_of_the_oracles_surfaces_as_clean_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A git infrastructure failure with stderr becomes a ``ClickException``."""
        monkeypatch.chdir(tmp_path)
        failure = subprocess.CalledProcessError(
            returncode=128, cmd=["git", "for-each-ref"], stderr="fatal: not a git repository"
        )
        monkeypatch.setattr(creation, "list_branch_refs", mock.Mock(side_effect=failure))

        with pytest.raises(click.ClickException) as raised:
            check_branch_occupancy("feat/x", "feat-x", "2026")

        assert "fatal: not a git repository" in raised.value.message

    def test_git_failure_of_the_slug_oracle_surfaces_as_clean_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The branch-tree oracle wraps the listing failure like its sibling.

        Both git touchpoints of the oracle share the boundary: the inventory
        listing and the per-ref tree reader.
        """
        monkeypatch.chdir(tmp_path)
        failure = subprocess.CalledProcessError(
            returncode=128, cmd=["git", "ls-tree"], stderr="fatal: not a git repository"
        )
        _wire_slug_oracle(
            monkeypatch,
            [BranchRef(name="alpha", remote=False)],
            mock.Mock(side_effect=failure),
        )

        with pytest.raises(click.ClickException) as raised:
            check_slug_occupancy("feature-foo", "2026")

        assert "fatal: not a git repository" in raised.value.message

    def test_missing_git_binary_of_the_slug_oracle_surfaces_as_clean_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A missing git binary is a clean error on the branch-tree oracle too."""
        monkeypatch.chdir(tmp_path)
        _wire_slug_oracle(
            monkeypatch,
            [BranchRef(name="alpha", remote=False)],
            mock.Mock(side_effect=FileNotFoundError("git")),
        )

        with pytest.raises(click.ClickException) as raised:
            check_slug_occupancy("feature-foo", "2026")

        assert "git" in raised.value.message

    def test_missing_git_binary_surfaces_as_clean_error(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """A missing git binary is a clean error on both public entries."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(creation, "list_branch_refs", mock.Mock(side_effect=FileNotFoundError("git")))

        with pytest.raises(click.ClickException) as raised:
            check_branch_occupancy("feat/x", "feat-x", "2026")

        assert "git" in raised.value.message

    def test_create_mutation_failure_surfaces_as_clean_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A failing branch plant of the switch path becomes a ``ClickException``."""
        monkeypatch.chdir(tmp_path)
        _wire_creation(monkeypatch, current="main")
        failure = subprocess.CalledProcessError(
            returncode=128,
            cmd=["git", "branch", "feat/x"],
            stderr="fatal: invalid branch name",
        )
        monkeypatch.setattr(creation, "create_branch_at_commit", mock.Mock(side_effect=failure))

        with pytest.raises(click.ClickException) as raised:
            create_topic("feat/x", "HEAD", todo="T", year="2026", switch=True)

        assert "fatal: invalid branch name" in raised.value.message
        assert not (tmp_path / ".goga" / "history" / "2026" / "feat-x").exists()

    def test_create_no_switch_plant_failure_surfaces_as_clean_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A failing quarantined plant of the default path becomes a ``ClickException``.

        The failure crosses the publishing module — the boundary still
        wraps it, and no working-copy artifact appears.
        """
        monkeypatch.chdir(tmp_path)
        real_plant = publishing._plant_topic_branch
        _wire_creation(monkeypatch, current="main")
        monkeypatch.setattr(publishing, "_plant_topic_branch", real_plant)
        monkeypatch.setattr(publishing, "commit_file_on_base", mock.Mock(return_value="beef00"))
        failure = subprocess.CalledProcessError(
            returncode=128,
            cmd=["git", "update-ref", "--stdin", "-z"],
            stderr="fatal: reference already exists",
        )
        monkeypatch.setattr(publishing, "create_branch_at_commit", mock.Mock(side_effect=failure))

        with pytest.raises(click.ClickException) as raised:
            create_topic("feat/x", "HEAD", todo="T", year="2026")

        assert "reference already exists" in raised.value.message
        assert not (tmp_path / ".goga" / "history" / "2026" / "feat-x").exists()

    def test_missing_git_binary_at_creation_surfaces_as_clean_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A missing git binary during the create mutation is a clean error."""
        monkeypatch.chdir(tmp_path)
        _wire_creation(monkeypatch, current="main")
        monkeypatch.setattr(
            creation,
            "create_branch_at_commit",
            mock.Mock(side_effect=FileNotFoundError("git")),
        )

        with pytest.raises(click.ClickException) as raised:
            create_topic("feat/x", "HEAD", todo="T", year="2026", switch=True)

        assert "git" in raised.value.message

    def test_stray_file_at_topic_path_surfaces_as_clean_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A stray file named like the slug occupies no topic — the mkdir failure is a clean error.

        The history oracle counts directories only, so the name is free and
        the branch mutations run first; ``ensure_topic_dir`` then fails on
        the file, and the boundary turns the ``OSError`` into a clean error
        instead of a traceback.
        """
        monkeypatch.chdir(tmp_path)
        year_dir = tmp_path / ".goga" / "history" / "2026"
        year_dir.mkdir(parents=True)
        (year_dir / "feat-x").write_text("not a topic", encoding="utf-8")
        wired = _wire_creation(monkeypatch, current="main")

        with pytest.raises(click.ClickException) as raised:
            create_topic("feat-x", "HEAD", todo="T", year="2026", switch=True)

        assert "cannot create the topic directory or write the todo file" in raised.value.message
        assert "feat-x" in raised.value.message
        # The traced order — the branch mutations run before the directory.
        wired.create_branch.assert_called_once_with("feat-x", "c0ffee")
        wired.checkout.assert_called_once_with("feat-x")

    def test_create_topic_broken_tool_package_import_surfaces_as_clean_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The fatal ``ImportError`` of the hooks-registry assembly keeps
        its package name in the clean error — the amendment checkpoint
        builds the registry on first delivery, before any mutation."""
        monkeypatch.chdir(tmp_path)
        _wire_creation(monkeypatch, current="main")
        broken = ImportError("package goga_tool_bad failed to import: boom")
        hooks = mock.Mock()
        hooks.return_value.amend_creation.side_effect = broken
        monkeypatch.setattr(creation, "TopicHooks", hooks)

        with pytest.raises(click.ClickException) as raised:
            create_topic("Feature/Foo_Bar", "HEAD", todo="T", year="2026")

        assert raised.value.message == "package goga_tool_bad failed to import: boom"

    def test_enter_topic_todo_broken_tool_package_import_surfaces_as_clean_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The entry's checkpoint pair builds the registry on first
        delivery — the fatal ``ImportError`` keeps its package name in the
        clean error."""
        monkeypatch.chdir(tmp_path)
        _topic_dir(tmp_path, "2026", "feature-foo")
        _stub_edit_text(monkeypatch, "saved")
        broken = ImportError("package goga_tool_bad failed to import: boom")
        hooks = mock.Mock()
        hooks.return_value.amend_todo_entry.side_effect = broken
        monkeypatch.setattr(creation, "TopicHooks", hooks)

        with pytest.raises(click.ClickException) as raised:
            enter_topic_todo("feature-foo", year="2026")

        assert raised.value.message == "package goga_tool_bad failed to import: boom"
