"""Contract and logic tests for the entities declared in
``goga/topics/CODEMANIFEST`` with ``location: creation.py``:

- ``check_branch_occupancy(branch_name, slug, year)`` — the three-oracle
  occupancy check of a fresh-work name
- ``check_slug_occupancy(slug, year)`` — the branch-tree occupancy oracle of
  a topic slug
- ``create_topic(branch_name, year, todo)`` — the fresh-work creation
  procedure with its optional topic todo file
- ``enter_topic_todo(topic, year)`` — the editor session over the topic's
  todo.md and the write of the saved text, without a commit

The git boundary is mocked at the import point per the ``convention``
practice — no git binary and no repository are touched. The filesystem
scenarios (the topic oracle and the created directory) run against ``tmp_path``
with the real history path routines; the scale is never assembled — creation
is not a status consumer. The editor session is mocked with a shell script
exported as ``$EDITOR`` per the ``editor`` practice and the TTY detection
with a ``sys.stdin`` stand-in — a real editor never launches in tests.
"""

from __future__ import annotations

import inspect
import subprocess
import sys
import typing
from collections.abc import Callable
from pathlib import Path
from unittest import mock

import click
import pytest
from goga.topics import (
    check_branch_occupancy,
    check_slug_occupancy,
    create_topic,
    creation,
    enter_topic_todo,
)
from goga.topics.git import BranchRef

# --- Shared scenario helpers ---


def _wire_inventory(
    monkeypatch: pytest.MonkeyPatch,
    inventory: list[BranchRef],
    current: str | None = None,
) -> mock.Mock:
    """Patch creation's import points: the inventory and the create mutation.

    Returns:
        The create-and-switch mutation as a recording mock — the only git
        mutation of the procedure.
    """
    monkeypatch.setattr(creation, "list_branch_refs", lambda: inventory)
    monkeypatch.setattr(creation, "resolve_current_branch_name", lambda: current)
    create_and_switch = mock.Mock()
    monkeypatch.setattr(creation, "create_and_switch_branch", create_and_switch)
    return create_and_switch


def _non_interactive(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make stdin a non-terminal — the re-ask path must abort cleanly."""
    monkeypatch.setattr(sys, "stdin", mock.Mock(**{"isatty.return_value": False}))


def _interactive(
    monkeypatch: pytest.MonkeyPatch, answers: list[str]
) -> mock.Mock:
    """Make stdin a terminal and answer the re-ask prompts in order."""
    monkeypatch.setattr(sys, "stdin", mock.Mock(**{"isatty.return_value": True}))
    prompt = mock.Mock(side_effect=answers)
    monkeypatch.setattr(click, "prompt", prompt)
    return prompt


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
            "BoardRecord",
            "DeleteTarget",
            "SwitchCandidate",
            "check_branch_occupancy",
            "check_slug_occupancy",
            "collect_topic_board",
            "create_topic",
            "delete_topics",
            "ensure_topic",
            "enter_topic_todo",
            "publish_topic",
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
            parameter.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
            for parameter in signature.parameters.values()
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
            parameter.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
            for parameter in signature.parameters.values()
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
        """``enter_topic_todo(topic, year=None) -> bool`` — binds as declared."""
        signature = inspect.signature(enter_topic_todo)
        assert list(signature.parameters) == ["topic", "year"]
        assert all(
            parameter.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
            for parameter in signature.parameters.values()
        )
        assert signature.parameters["year"].default is None
        hints = typing.get_type_hints(enter_topic_todo)
        assert hints == {
            "topic": str,
            "year": str | None,
            "return": bool,
        }
        signature.bind("feature-foo", year="2026")

    def test_create_topic_signature(self) -> None:
        """``create_topic(branch_name, year=None, todo=None) -> str``."""
        signature = inspect.signature(create_topic)
        assert list(signature.parameters) == ["branch_name", "year", "todo"]
        assert all(
            parameter.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
            for parameter in signature.parameters.values()
        )
        assert signature.parameters["year"].default is None
        assert signature.parameters["todo"].default is None
        hints = typing.get_type_hints(create_topic)
        assert hints == {
            "branch_name": str,
            "year": str | None,
            "todo": str | None,
            "return": str,
        }

    def test_no_cleanliness_probe_in_creation(self) -> None:
        """Creation owns no cleanliness policy — no probe is imported."""
        assert not hasattr(creation, "is_working_tree_clean")


# --- Logic tests: the occupancy oracles ---


class TestCheckBranchOccupancy:
    def test_check_branch_occupancy_oracle_order(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The first occupied oracle wins — remote twin before the topic dir."""
        monkeypatch.chdir(tmp_path)
        inventory = [BranchRef(name="origin/feat/x", remote=True)]
        _topic_dir(tmp_path, "2026", "feat-x")
        _wire_inventory(monkeypatch, inventory)

        conflict = check_branch_occupancy("feat/x", "feat-x", "2026")

        assert conflict == "remote-tracking branch 'feat/x' already exists"

    def test_check_branch_occupancy_local_ref_oracle(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
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

    def test_check_branch_occupancy_topic_dir_oracle(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
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

    def test_check_branch_occupancy_free_everywhere(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
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
        reader = mock.Mock(
            side_effect=[[], [".goga/history/2026/feature-foo/todo.md"]]
        )
        listing = _wire_slug_oracle(monkeypatch, inventory, reader)

        conflict = check_slug_occupancy("feature-foo", "2026")

        assert conflict == (
            "topic 'feature-foo' of 2026 is already hosted by branch 'beta'"
        )
        assert reader.call_args.args == ("beta", ".goga/history/2026/feature-foo/")
        listing.assert_called_once_with()

    def test_check_slug_occupancy_stops_at_first_hit(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
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

        assert conflict == (
            "topic 'feature-foo' of 2026 is already hosted by branch 'alpha'"
        )
        assert reader.call_count == 1

    def test_check_slug_occupancy_free_slug_returns_none(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
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

        assert conflict == (
            "topic 'feature-foo' of 2026 is already hosted by branch 'alpha'"
        )
        assert reader.call_args.args == ("alpha", ".goga/history/2026/feature-foo/")


# --- Logic tests: the creation procedure ---


class TestCreateTopic:
    def test_create_topic_creates_branch_and_dir(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A free name: verbatim branch creation plus the slug directory."""
        monkeypatch.chdir(tmp_path)
        create_and_switch = _wire_inventory(monkeypatch, [], current="main")

        result = create_topic("Feature/Foo_Bar", year="2025")

        assert result == "Created branch Feature/Foo_Bar and topic 2025/feature-foo-bar"
        create_and_switch.assert_called_once_with("Feature/Foo_Bar")
        assert (tmp_path / ".goga" / "history" / "2025" / "feature-foo-bar").is_dir()

    def test_create_topic_default_year_is_current(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Without a year the topic directory lands in the current one."""
        monkeypatch.chdir(tmp_path)
        create_and_switch = _wire_inventory(monkeypatch, [], current="main")
        monkeypatch.setattr(creation, "current_year", lambda: "2026")

        result = create_topic("Feature/Foo_Bar")

        assert result == "Created branch Feature/Foo_Bar and topic 2026/feature-foo-bar"
        create_and_switch.assert_called_once_with("Feature/Foo_Bar")
        assert (tmp_path / ".goga" / "history" / "2026" / "feature-foo-bar").is_dir()

    def test_create_topic_with_todo_fresh_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A free name with a todo: the branch, the directory, the todo file."""
        monkeypatch.chdir(tmp_path)
        create_and_switch = _wire_inventory(monkeypatch, [], current="main")

        result = create_topic("Feature/Foo_Bar", "2026", "Payment retry")

        assert result == "Created branch Feature/Foo_Bar and topic 2026/feature-foo-bar"
        create_and_switch.assert_called_once_with("Feature/Foo_Bar")
        todo_file = (
            tmp_path / ".goga" / "history" / "2026" / "feature-foo-bar" / "todo.md"
        )
        assert todo_file.read_bytes() == b"Payment retry\n"

    def test_create_topic_writes_multiline_todo(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A multi-line todo: the file carries the text verbatim plus one newline."""
        monkeypatch.chdir(tmp_path)
        create_and_switch = _wire_inventory(monkeypatch, [], current="main")

        result = create_topic(
            "Feature/Foo_Bar",
            year="2026",
            todo="Fix payment retries.\n\nRetries ignore the cap.",
        )

        assert result == "Created branch Feature/Foo_Bar and topic 2026/feature-foo-bar"
        create_and_switch.assert_called_once_with("Feature/Foo_Bar")
        topic_dir = tmp_path / ".goga" / "history" / "2026" / "feature-foo-bar"
        # Empty lines inside the text stay as entered; one trailing newline.
        assert (topic_dir / "todo.md").read_bytes() == (
            b"Fix payment retries.\n\nRetries ignore the cap.\n"
        )
        # The todo file is the single artifact of the topic directory.
        assert [path.name for path in topic_dir.iterdir()] == ["todo.md"]

    def test_create_topic_whitespace_todo_writes_verbatim(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A whitespace-only todo is a non-empty text — it passes the gate and is written verbatim."""
        monkeypatch.chdir(tmp_path)
        create_and_switch = _wire_inventory(monkeypatch, [], current="main")

        result = create_topic("feat-a", year="2026", todo="  ")

        assert result == "Created branch feat-a and topic 2026/feat-a"
        create_and_switch.assert_called_once_with("feat-a")
        topic_dir = tmp_path / ".goga" / "history" / "2026" / "feat-a"
        assert (topic_dir / "todo.md").read_bytes() == b"  \n"

    def test_create_topic_idempotent_current_host(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The current branch already hosting the slug: success, no mutation."""
        monkeypatch.chdir(tmp_path)
        create_and_switch = _wire_inventory(
            monkeypatch, [], current="feature-foo-bar"
        )
        ensure_dir = mock.Mock(
            side_effect=lambda name, _year: _topic_dir(tmp_path, "2026", name.lower())
        )
        monkeypatch.setattr(creation, "ensure_topic_dir", ensure_dir)
        monkeypatch.setattr(creation, "current_year", lambda: "2026")

        result = create_topic("feature-foo-bar")

        assert result == "Branch feature-foo-bar already hosts topic 2026/feature-foo-bar"
        create_and_switch.assert_not_called()
        ensure_dir.assert_not_called()

    def test_create_topic_without_todo_writes_no_todo_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A free name without a todo: the topic directory carries no todo file."""
        monkeypatch.chdir(tmp_path)
        _wire_inventory(monkeypatch, [], current="main")
        monkeypatch.setattr(creation, "current_year", lambda: "2026")

        result = create_topic("Feature/Foo_Bar")

        assert result == "Created branch Feature/Foo_Bar and topic 2026/feature-foo-bar"
        topic_dir = tmp_path / ".goga" / "history" / "2026" / "feature-foo-bar"
        assert topic_dir.is_dir()
        assert not (topic_dir / "todo.md").exists()

    def test_create_topic_empty_string_todo_writes_nothing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An empty todo string writes no file — truthiness, not ``is not None``."""
        monkeypatch.chdir(tmp_path)
        # A genuinely free name over tmp_path: the inventory is empty and the
        # real topic oracle finds no directory.
        create_and_switch = _wire_inventory(monkeypatch, [], current="main")

        result = create_topic("feat-a", year="2026", todo="")

        assert result == "Created branch feat-a and topic 2026/feat-a"
        create_and_switch.assert_called_once_with("feat-a")
        topic_dir = tmp_path / ".goga" / "history" / "2026" / "feat-a"
        assert topic_dir.is_dir()
        # The empty string never creates the file — no bare-newline todo.md.
        assert not (topic_dir / "todo.md").exists()

    @pytest.mark.parametrize("todo", [None, ""])
    def test_create_topic_idempotent_without_todo_leaves_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, todo: str | None
    ) -> None:
        """The idempotent path without a todo: an existing todo file stays verbatim.

        ``None`` and the empty string behave alike — neither creates nor
        overwrites; the regression guard against the old
        ``if title is not None`` condition, where ``""`` wiped the file.
        """
        monkeypatch.chdir(tmp_path)
        topic_dir = _topic_dir(tmp_path, "2026", "feat-a")
        (topic_dir / "todo.md").write_text("Old\n", encoding="utf-8")
        create_and_switch = _wire_inventory(monkeypatch, [], current="feat-a")

        result = create_topic("feat-a", year="2026", todo=todo)

        assert result == "Branch feat-a already hosts topic 2026/feat-a"
        create_and_switch.assert_not_called()
        assert (topic_dir / "todo.md").read_text(encoding="utf-8") == "Old\n"

    def test_create_topic_idempotent_overwrites_todo(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The current host with an explicit todo: ensure, overwrite, no switch."""
        monkeypatch.chdir(tmp_path)
        topic_dir = _topic_dir(tmp_path, "2026", "feat-a")
        (topic_dir / "todo.md").write_text("Old\n", encoding="utf-8")
        create_and_switch = _wire_inventory(monkeypatch, [], current="feat-a")

        result = create_topic("feat-a", year="2026", todo="New summary")

        assert result == "Branch feat-a already hosts topic 2026/feat-a"
        create_and_switch.assert_not_called()
        assert (topic_dir / "todo.md").read_text(encoding="utf-8") == "New summary\n"

    def test_create_topic_occupied_non_interactive_clean_error(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """An occupancy conflict without a terminal: the reason and the hint."""
        monkeypatch.chdir(tmp_path)
        _non_interactive(monkeypatch)
        create_and_switch = _wire_inventory(monkeypatch, [], current="main")
        inventory = [BranchRef(name="feat/x", remote=False)]
        monkeypatch.setattr(creation, "list_branch_refs", lambda: inventory)

        with pytest.raises(click.ClickException) as raised:
            create_topic("feat/x")

        assert raised.value.message == (
            "branch 'feat/x' already exists — run 'goga topics board' to see the board"
        )
        create_and_switch.assert_not_called()
        assert not (tmp_path / ".goga" / "history").exists()

    def test_create_topic_empty_slug_non_interactive_clean_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A name that normalizes to nothing: the reason, no prompt, no work."""
        monkeypatch.chdir(tmp_path)
        _non_interactive(monkeypatch)
        create_and_switch = _wire_inventory(monkeypatch, [], current="main")
        prompt = mock.Mock()
        monkeypatch.setattr(click, "prompt", prompt)

        with pytest.raises(click.ClickException) as raised:
            create_topic("🚀")

        assert raised.value.message == (
            "branch name '🚀' normalizes to an empty topic slug"
        )
        prompt.assert_not_called()
        create_and_switch.assert_not_called()

    def test_create_topic_empty_slug_reask(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """An unusable name on a terminal: the cycle restarts until a good one."""
        monkeypatch.chdir(tmp_path)
        prompt = _interactive(monkeypatch, ["???", "good-name"])
        create_and_switch = _wire_inventory(monkeypatch, [], current="main")
        monkeypatch.setattr(creation, "current_year", lambda: "2026")

        result = create_topic("!!!")

        assert result == "Created branch good-name and topic 2026/good-name"
        assert prompt.call_count == 2
        assert prompt.call_args.args[0] == "New branch name"
        create_and_switch.assert_called_once_with("good-name")
        assert (tmp_path / ".goga" / "history" / "2026" / "good-name").is_dir()
        stderr = capsys.readouterr().err
        assert "branch name '!!!' normalizes to an empty topic slug" in stderr
        assert "branch name '???' normalizes to an empty topic slug" in stderr

    def test_create_topic_occupied_reask_creates_second_name(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """An occupied name on a terminal: the conflict goes to stderr, then re-ask."""
        monkeypatch.chdir(tmp_path)
        _interactive(monkeypatch, ["feat/other"])
        inventory = [BranchRef(name="feat/x", remote=False)]
        create_and_switch = _wire_inventory(
            monkeypatch, inventory, current="main"
        )
        monkeypatch.setattr(creation, "current_year", lambda: "2026")

        result = create_topic("feat/x")

        assert result == "Created branch feat/other and topic 2026/feat-other"
        create_and_switch.assert_called_once_with("feat/other")
        stderr = capsys.readouterr().err
        assert "branch 'feat/x' already exists" in stderr

    def test_create_topic_reask_abort_leaves_repository_untouched(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Ctrl-C at the re-ask prompt propagates as ``click.Abort`` — nothing is created."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(sys, "stdin", mock.Mock(**{"isatty.return_value": True}))
        monkeypatch.setattr(click, "prompt", mock.Mock(side_effect=click.Abort()))
        create_and_switch = _wire_inventory(monkeypatch, [], current="main")

        with pytest.raises(click.Abort):
            create_topic("!!!")

        create_and_switch.assert_not_called()
        assert not (tmp_path / ".goga").exists()

    def test_create_topic_todo_write_failure_is_clean_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A failing todo write becomes the generalized clean error."""
        monkeypatch.chdir(tmp_path)
        create_and_switch = _wire_inventory(monkeypatch, [], current="main")
        monkeypatch.setattr(
            creation,
            "resolve_topic_file",
            mock.Mock(side_effect=OSError("disk full")),
        )

        with pytest.raises(click.ClickException) as raised:
            create_topic("Feature/Foo_Bar", "2026", "T")

        assert (
            "cannot create the topic directory or write the todo file"
            in raised.value.message
        )
        # The traced order — the branch mutation runs before the todo write.
        create_and_switch.assert_called_once_with("Feature/Foo_Bar")

    def test_create_topic_todo_survives_reask(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The todo is a procedure parameter — a re-asked name keeps it."""
        monkeypatch.chdir(tmp_path)
        prompt = _interactive(monkeypatch, ["Feature/Foo_Bar"])
        create_and_switch = _wire_inventory(monkeypatch, [], current="main")

        result = create_topic("ББ", "2026", "T")

        assert result == "Created branch Feature/Foo_Bar and topic 2026/feature-foo-bar"
        create_and_switch.assert_called_once_with("Feature/Foo_Bar")
        assert prompt.call_count == 1
        todo_file = (
            tmp_path / ".goga" / "history" / "2026" / "feature-foo-bar" / "todo.md"
        )
        assert todo_file.read_text(encoding="utf-8") == "T\n"


# --- Logic tests: the todo entry of a topic ---


class TestEnterTopicTodo:
    def test_enter_topic_todo_edits_existing_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An existing todo.md seeds the session; the saved text overwrites it.

        Variant: a cancelled session — an editor that never writes —
        returns False and leaves the file verbatim.
        """
        monkeypatch.chdir(tmp_path)
        todo_file = _topic_dir(tmp_path, "2026", "feature-foo") / "todo.md"
        _tty(monkeypatch)

        todo_file.write_text("Old line.\n", encoding="utf-8")
        _editor_script(monkeypatch, tmp_path, "printf 'New line.\\n' > \"$1\"")
        assert enter_topic_todo("feature-foo", year="2026") is True
        assert todo_file.read_text(encoding="utf-8") == "New line.\n"

        todo_file.write_text("Old line.\n", encoding="utf-8")
        _editor_script(monkeypatch, tmp_path, "exit 0")
        assert enter_topic_todo("feature-foo", year="2026") is False
        assert todo_file.read_text(encoding="utf-8") == "Old line.\n"

    def test_enter_topic_todo_seeds_existing_content(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
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

    def test_enter_topic_todo_missing_file_empty_entry(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
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

    def test_missing_git_binary_surfaces_as_clean_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A missing git binary is a clean error on both public entries."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(
            creation, "list_branch_refs", mock.Mock(side_effect=FileNotFoundError("git"))
        )

        with pytest.raises(click.ClickException) as raised:
            check_branch_occupancy("feat/x", "feat-x", "2026")

        assert "git" in raised.value.message

    def test_create_mutation_failure_surfaces_as_clean_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A failing create-and-switch becomes a ``ClickException``."""
        monkeypatch.chdir(tmp_path)
        failure = subprocess.CalledProcessError(
            returncode=128,
            cmd=["git", "switch", "-c", "feat/x"],
            stderr="fatal: invalid branch name",
        )
        monkeypatch.setattr(
            creation, "create_and_switch_branch", mock.Mock(side_effect=failure)
        )
        monkeypatch.setattr(creation, "list_branch_refs", lambda: [])
        monkeypatch.setattr(creation, "resolve_current_branch_name", lambda: "main")

        with pytest.raises(click.ClickException) as raised:
            create_topic("feat/x", year="2026")

        assert "fatal: invalid branch name" in raised.value.message
        assert not (tmp_path / ".goga" / "history" / "2026" / "feat-x").exists()

    def test_missing_git_binary_at_creation_surfaces_as_clean_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A missing git binary during the create mutation is a clean error."""
        monkeypatch.chdir(tmp_path)
        _wire_inventory(monkeypatch, [], current="main")
        monkeypatch.setattr(
            creation, "create_and_switch_branch", mock.Mock(side_effect=FileNotFoundError("git"))
        )

        with pytest.raises(click.ClickException) as raised:
            create_topic("feat/x", year="2026")

        assert "git" in raised.value.message

    def test_stray_file_at_topic_path_surfaces_as_clean_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A stray file named like the slug occupies no topic — the mkdir failure is a clean error.

        The history oracle counts directories only, so the name is free and
        the branch is created first; ``ensure_topic_dir`` then fails on the
        file, and the boundary turns the ``OSError`` into a clean error
        instead of a traceback.
        """
        monkeypatch.chdir(tmp_path)
        year_dir = tmp_path / ".goga" / "history" / "2026"
        year_dir.mkdir(parents=True)
        (year_dir / "feat-x").write_text("not a topic", encoding="utf-8")
        create_and_switch = _wire_inventory(monkeypatch, [], current="main")

        with pytest.raises(click.ClickException) as raised:
            create_topic("feat-x", year="2026")

        assert (
            "cannot create the topic directory or write the todo file"
            in raised.value.message
        )
        assert "feat-x" in raised.value.message
        # The traced order — the branch mutation runs before the directory.
        create_and_switch.assert_called_once_with("feat-x")
