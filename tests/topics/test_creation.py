"""Contract and logic tests for the entities declared in
``goga/topics/CODEMANIFEST`` with ``location: creation.py``:

- ``check_branch_occupancy(branch_name, slug, year)`` — the three-oracle
  occupancy check of a fresh-work name
- ``create_topic(branch_name, year, title)`` — the fresh-work creation
  procedure with its optional topic title file

The git boundary is mocked at the import point per the ``convention``
practice — no git binary and no repository are touched. The filesystem
scenarios (the topic oracle and the created directory) run against ``tmp_path``
with the real history path routines; the scale is never assembled — creation
is not a status consumer.
"""

from __future__ import annotations

import inspect
import subprocess
import sys
import typing
from pathlib import Path
from unittest import mock

import click
import pytest
from goga.topics import check_branch_occupancy, create_topic, creation
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


# --- Contract tests ---


class TestCreationContract:
    def test_entities_are_importable_from_the_cell_facade(self) -> None:
        """Both routines live on the cell facade and in ``__all__``."""
        import goga.topics as cell

        assert cell.create_topic is create_topic
        assert cell.check_branch_occupancy is check_branch_occupancy
        expected = {
            "BoardRecord",
            "SwitchCandidate",
            "check_branch_occupancy",
            "collect_topic_board",
            "create_topic",
            "ensure_topic",
            "resolve_switch_candidates",
            "switch_topic",
        }
        assert set(cell.__all__) == expected

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

    def test_create_topic_signature(self) -> None:
        """``create_topic(branch_name, year=None, title=None) -> str``."""
        signature = inspect.signature(create_topic)
        assert list(signature.parameters) == ["branch_name", "year", "title"]
        assert all(
            parameter.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
            for parameter in signature.parameters.values()
        )
        assert signature.parameters["year"].default is None
        assert signature.parameters["title"].default is None
        hints = typing.get_type_hints(create_topic)
        assert hints == {
            "branch_name": str,
            "year": str | None,
            "title": str | None,
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

    def test_create_topic_with_title_fresh_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A free name with a title: the branch, the directory, the title file."""
        monkeypatch.chdir(tmp_path)
        create_and_switch = _wire_inventory(monkeypatch, [], current="main")

        result = create_topic("Feature/Foo_Bar", "2026", "Payment retry")

        assert result == "Created branch Feature/Foo_Bar and topic 2026/feature-foo-bar"
        create_and_switch.assert_called_once_with("Feature/Foo_Bar")
        title_file = (
            tmp_path / ".goga" / "history" / "2026" / "feature-foo-bar" / "title.txt"
        )
        assert title_file.read_bytes() == b"Payment retry\n"

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

    def test_create_topic_with_title_idempotent_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The current host with an explicit title: ensure, overwrite, no switch."""
        monkeypatch.chdir(tmp_path)
        topic_dir = _topic_dir(tmp_path, "2026", "feature-foo")
        (topic_dir / "title.txt").write_text("Old\n", encoding="utf-8")
        create_and_switch = _wire_inventory(monkeypatch, [], current="feature-foo")

        result = create_topic("feature-foo", "2026", "New title")

        assert result == "Branch feature-foo already hosts topic 2026/feature-foo"
        create_and_switch.assert_not_called()
        assert (topic_dir / "title.txt").read_text(encoding="utf-8") == "New title\n"

    def test_create_topic_empty_title_writes_bare_newline(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An explicit empty title writes the file — the empty string is not None."""
        monkeypatch.chdir(tmp_path)
        create_and_switch = _wire_inventory(monkeypatch, [], current="main")

        result = create_topic("feat-a", "2026", "")

        assert result == "Created branch feat-a and topic 2026/feat-a"
        create_and_switch.assert_called_once_with("feat-a")
        title_file = tmp_path / ".goga" / "history" / "2026" / "feat-a" / "title.txt"
        # The explicit empty title creates the file — one bare newline, which
        # earns the new status and renders as an empty title cell.
        assert title_file.read_bytes() == b"\n"

    def test_create_topic_empty_title_overwrites_on_idempotent_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An explicit empty title overwrites an existing title on the current host."""
        monkeypatch.chdir(tmp_path)
        topic_dir = _topic_dir(tmp_path, "2026", "feature-foo")
        (topic_dir / "title.txt").write_text("Old\n", encoding="utf-8")
        create_and_switch = _wire_inventory(monkeypatch, [], current="feature-foo")

        result = create_topic("feature-foo", "2026", "")

        assert result == "Branch feature-foo already hosts topic 2026/feature-foo"
        create_and_switch.assert_not_called()
        assert (topic_dir / "title.txt").read_bytes() == b"\n"

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
            "branch 'feat/x' already exists — run 'goga topics status' to see the board"
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

    def test_create_topic_title_write_failure_is_clean_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A failing title write becomes the generalized clean error."""
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
            "cannot create the topic directory or write the title file"
            in raised.value.message
        )
        # The traced order — the branch mutation runs before the title write.
        create_and_switch.assert_called_once_with("Feature/Foo_Bar")

    def test_create_topic_title_survives_reask(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The title is a procedure parameter — a re-asked name keeps it."""
        monkeypatch.chdir(tmp_path)
        prompt = _interactive(monkeypatch, ["Feature/Foo_Bar"])
        create_and_switch = _wire_inventory(monkeypatch, [], current="main")

        result = create_topic("ББ", "2026", "T")

        assert result == "Created branch Feature/Foo_Bar and topic 2026/feature-foo-bar"
        create_and_switch.assert_called_once_with("Feature/Foo_Bar")
        assert prompt.call_count == 1
        title_file = (
            tmp_path / ".goga" / "history" / "2026" / "feature-foo-bar" / "title.txt"
        )
        assert title_file.read_text(encoding="utf-8") == "T\n"


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
            "cannot create the topic directory or write the title file"
            in raised.value.message
        )
        assert "feat-x" in raised.value.message
        # The traced order — the branch mutation runs before the directory.
        create_and_switch.assert_called_once_with("feat-x")
