"""Contract and logic tests for the entities declared in
``goga/topics/CODEMANIFEST`` with ``location: creation.py``:

- ``check_branch_occupancy(branch_name, slug, year)`` — the three-oracle
  occupancy check of a fresh-work name
- ``check_slug_occupancy(slug, year)`` — the branch-tree occupancy oracle of
  a topic slug
- ``create_topic(branch_name, base_ref, todo, publish, commit_message,
  year, switch)`` — the fresh-work creation procedure off an explicit base
  with its editor-sourced todo and its publication ask: the quarantined
  no-switch plant by default, the working-copy switch path under the flag
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
    """Make stdin a non-terminal — the value-less todo must abort cleanly."""
    monkeypatch.setattr(sys, "stdin", mock.Mock(**{"isatty.return_value": False}))


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
        """``enter_topic_todo(topic, year=None) -> bool`` — binds as declared."""
        signature = inspect.signature(enter_topic_todo)
        assert list(signature.parameters) == ["topic", "year"]
        assert all(
            parameter.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD for parameter in signature.parameters.values()
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
        """``create_topic(branch_name, base_ref, todo, publish, commit_message, year, switch) -> str``
        with the defaults ``None/False/None/None/False``."""
        signature = inspect.signature(create_topic)
        assert list(signature.parameters) == [
            "branch_name",
            "base_ref",
            "todo",
            "publish",
            "commit_message",
            "year",
            "switch",
        ]
        assert all(
            parameter.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD for parameter in signature.parameters.values()
        )
        assert signature.parameters["todo"].default is None
        assert signature.parameters["publish"].default is False
        assert signature.parameters["commit_message"].default is None
        assert signature.parameters["year"].default is None
        assert signature.parameters["switch"].default is False
        hints = typing.get_type_hints(create_topic)
        assert hints == {
            "branch_name": str,
            "base_ref": str,
            "todo": str | None,
            "publish": bool,
            "commit_message": str | None,
            "year": str | None,
            "switch": bool,
            "return": str,
        }
        signature.bind("b", "origin/main", todo="t", publish=False, commit_message=None, year="2026", switch=True)
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
            mock.call.plant("feature-foo", "Fix.", "c0ffee", "feature-foo", "2026", None),
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
        the built-in message — the template argument stays None.
        """
        monkeypatch.chdir(tmp_path)
        wired = _wire_creation(monkeypatch, base_commit="abc123")

        create_topic("feat-a", "origin/main", todo="T", year="2026")

        wired.resolve_ref_commit.assert_called_once_with("origin/main")
        wired.plant.assert_called_once_with("feat-a", "T", "abc123", "feat-a", "2026", None)

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
        name, the resolved todo, the base, the template, and the year;
        none of the local mutations runs.
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
        published.assert_called_once_with("feature-foo", "Fix.", "origin/main", None, "2026")
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
        wired.plant.assert_called_once_with("feature-foo", "Fix.", "c0ffee", "feature-foo", "2026", None)
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

    def test_create_topic_todo_non_tty_clean_error(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """No todo value without a terminal is a clean error naming the
        value option — before any mutation."""
        monkeypatch.chdir(tmp_path)
        wired = _wire_creation(monkeypatch)
        marker = tmp_path / "editor-launched"
        _editor_script(monkeypatch, tmp_path, f"touch '{marker}'")
        _non_interactive(monkeypatch)

        with pytest.raises(click.ClickException, match="--todo"):
            create_topic("feature-foo", "origin/main", year="2026")

        assert not marker.exists()
        wired.create_branch.assert_not_called()
        wired.checkout.assert_not_called()

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
        published.assert_called_once_with("feature-foo", "From editor.\n", "origin/main", None, "2026")
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
        wired.plant.assert_called_once_with("Feature/Foo_Bar", "T", "c0ffee", "feature-foo-bar", "2026", None)

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
            "Feature/Foo_Bar", "Payment retry", "c0ffee", "feature-foo-bar", "2026", None
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
