"""End-to-end integration tests for the topic workflows of one year.

These exercise the cross-cell paths of the usability-for-topic-workaround
feature over its real surfaces — no domain routine and no renderer is
mocked, only the boundaries the environment cannot provide:

    goga topics board --year Y
                  -> goga.commands.topics.topics.board
                  -> goga.topics.collect_topic_board
                  -> [goga.history.assemble_status_scale (real tool packages)
                      goga.topics.git.list_branch_refs / read_ref_tree_paths
                      goga.history.resolve_topic_status (working copy)]
                  -> goga.commands.topics.render_topic_board

    goga history status -s <tool>.<name>
                  -> goga.commands.history.history.status
                  -> goga.history.assemble_status_scale
                  -> goga.history.collect_topic_statuses
                  -> goga.commands.history.render_topic_statuses

    goga pipeline -t/--topic — the removed -b/--branch regression, and the
    mutating chains of ``switch_topic``/``create_topic`` through the real git
    cell: checkout, remote-tracking branch creation, and branch-plus-directory
    creation.

    publish_topic — the quarantined fast path over the real git cell: the
    todo commit is built off a pushed ``origin/main`` while the working
    copy, the index, and HEAD stay as they are, the branch is planted and
    pushed to a real bare ``origin``, and the failed-push scenario breaks
    the push URL to prove the full rollback of the planted branch.

Git is real: the git-dependent scenarios run in a throwaway repository
under ``tmp_path`` (``git init`` plus commits, with ``git update-ref``
manufacturing the remote-tracking twin) and skip when no git binary is
available. The status-scale assembly runs for real against the installed
``goga_tool_*`` packages; the qualified-name filter scenario first checks
that a registered tool status truly exists in ``assemble_status_scale()``
and falls back to a fake ``goga_tool_*`` module in ``sys.modules`` plus a
patched packages map otherwise — the command surface, the domain, and the
assembly stay the real ones either way.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path
from types import ModuleType
from typing import Any
from unittest import mock

import click
import pytest
from click.testing import CliRunner
from goga.cli import app
from goga.commands.history import history
from goga.commands.topics import topics
from goga.history import assemble_status_scale, current_year
from goga.topics import create_topic, publish_topic, switch_topic
from goga.topics import switching as topics_switching

# The scenarios drive real git — skip them where no git binary exists.
requires_git = pytest.mark.skipif(shutil.which("git") is None, reason="git binary is not available")

_GIT_IDENTITY = [
    "-c",
    "user.email=goga@example.com",
    "-c",
    "user.name=goga tests",
]


def _git(root: Path, *args: str) -> None:
    """Run one git command in the throwaway repository.

    Args:
        root: The repository root.
        *args: The git arguments.
    """
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True)


def _git_out(root: Path, *args: str) -> str:
    """Run one git command in the throwaway repository and capture stdout.

    Args:
        root: The repository root.
        *args: The git arguments.

    Returns:
        The stripped stdout of the command.
    """
    result = subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True
    )
    return result.stdout.strip()


def _worktree_snapshot(root: Path) -> list[str]:
    """List every working-copy path of the throwaway repository.

    Args:
        root: The repository root.

    Returns:
        The sorted repository-relative posix paths of every file and
        directory below ``root`` — the ``.git`` directory excluded, the
        state the user sees and the quarantine invariant protects.
    """
    return sorted(
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.relative_to(root).parts[0] != ".git"
    )


def _write(root: Path, relative: str) -> None:
    """Create one artifact file of the throwaway history tree.

    Args:
        root: The repository root.
        relative: The file path relative to the root, directories included.
    """
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("integration\n", encoding="utf-8")


def _current_branch(root: Path) -> str:
    """Read the checked-out branch of the throwaway repository.

    Args:
        root: The repository root.

    Returns:
        The current branch name as git reports it.
    """
    result = subprocess.run(
        ["git", "branch", "--show-current"], cwd=root, check=True, capture_output=True, text=True
    )
    return result.stdout.strip()


def _add_solo_branch(root: Path) -> None:
    """Add a branch hosting exactly one topic of its own.

    An orphan branch — its tree carries no other topic of the year, so it
    resolves unambiguously by branch name and by slug alike, unlike the
    chained ``feat-b`` which also carries the shared ``feat-a`` history.

    Args:
        root: The repository root of an already initialized topic repo.
    """
    _git(root, "switch", "-q", "--orphan", "solo")
    _write(root, ".goga/history/2025/solo/prd.md")
    _git(root, "add", ".goga")
    _git(root, *_GIT_IDENTITY, "commit", "-qm", "topic solo")
    _git(root, "switch", "-q", "feat-a")


def _init_topic_repo(root: Path) -> None:
    """Build the throwaway repository the board and switch scenarios share.

    A ``feat-a`` branch hosting the ``feat-a`` topic of 2025 with
    ``prd.md`` and ``plan.md`` committed, a ``feat-b`` branch created from
    it that adds the ``feat-b`` topic with ``prd.md`` (and so also carries
    the shared ``feat-a`` history in its ref tree), the checkout back onto
    ``feat-a``, and a remote-tracking twin of ``feat-a`` — the input of the
    twin collapse.

    Args:
        root: The empty directory the repository is built in.
    """
    _git(root, "init", "-q", "-b", "feat-a")
    _write(root, ".goga/history/2025/feat-a/prd.md")
    _write(root, ".goga/history/2025/feat-a/plan.md")
    _git(root, "add", ".goga")
    _git(root, *_GIT_IDENTITY, "commit", "-qm", "topic feat-a")
    _git(root, "update-ref", "refs/remotes/origin/feat-a", "HEAD")
    _git(root, "switch", "-q", "-c", "feat-b")
    _write(root, ".goga/history/2025/feat-b/prd.md")
    _git(root, "add", ".goga")
    _git(root, *_GIT_IDENTITY, "commit", "-qm", "topic feat-b")
    _git(root, "switch", "-q", "feat-a")


def _init_publish_repo(root: Path) -> Path:
    """Build the throwaway repository the publish scenarios share.

    A ``main`` branch with one tracked-file commit, a bare ``origin``
    sibling wired in as the ``origin`` remote with ``origin/main``
    materialized through a real push, and the git identity committed to
    the repository config — the domain's ``commit-tree`` invocation carries
    no ``-c`` identity of its own, so an unset identity would fail there.

    Args:
        root: The empty directory the repository is built in.

    Returns:
        The path of the bare origin repository.
    """
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "goga@example.com")
    _git(root, "config", "user.name", "goga tests")
    (root / "tracked.txt").write_text("base\n", encoding="utf-8")
    _git(root, "add", "tracked.txt")
    _git(root, *_GIT_IDENTITY, "commit", "-qm", "base")
    origin = root.parent / f"{root.name}-origin.git"
    _git(root, "init", "-q", "--bare", str(origin))
    _git(root, "remote", "add", "origin", str(origin))
    _git(root, "push", "-q", "origin", "main")
    return origin


def _board_rows(output: str, columns: int = 3) -> list[tuple[str, ...]]:
    """Parse the rendered board into its data rows.

    Args:
        output: The captured stdout of ``goga topics board``.
        columns: The text-column count of the table — 3 without ``--info``,
            4 with it (the todo column between branch and statuses).

    Returns:
        The cell tuples of the data rows — the header and separator rows
        dropped, every cell stripped.
    """
    lines = [line for line in output.splitlines() if line.startswith("|")]
    rows = []
    for line in lines[2:]:
        cells = line.split("|")
        rows.append(tuple(cell.strip() for cell in cells[1 : columns + 1]))
    return rows


@requires_git
class TestTopicsBoard:
    """``goga topics board --year Y`` over a real repository and scale."""

    def test_board_renders_topics_statuses_and_current_marker(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The board table carries the topics, their artifact statuses, and
        the current marker — exit 0."""
        _init_topic_repo(tmp_path)
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("COLUMNS", "120")

        result = CliRunner().invoke(topics, ["--year", "2025", "board"])

        assert result.exit_code == 0
        rows = _board_rows(result.output)
        # feat-b reads from its ref tree (defined, the shallowest artifact);
        # the current feat-a row reads the working copy (planned outranks
        # prd.md); feat-b also hosts the shared feat-a topic of the year.
        assert rows == [
            ("feat-b", "feat-b", "[defined]"),
            ("* feat-a", "feat-a", "[planned]"),
            ("feat-a", "feat-b", "[planned]"),
        ]
        # The remote-tracking twin collapsed into the local row.
        assert "origin/feat-a" not in result.output

    def test_board_empty_year_prints_nothing_and_exits_zero(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A year without topics renders nothing — an empty board is not an
        error."""
        _init_topic_repo(tmp_path)
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("COLUMNS", "120")

        result = CliRunner().invoke(topics, ["--year", "2030", "board"])

        assert result.exit_code == 0
        assert result.output == ""


class TestHistoryStatusToolFilter:
    """``goga history status -s <tool>.<name>`` against the real assembly."""

    def test_qualified_tool_status_validates_and_filters(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A registered tool status validates by its qualified name and
        keeps exactly the topics carrying it.

        The enumeration is pinned before the first assembly and counts its
        calls: the fake package is the only one read whatever the machine has
        installed, and every CLI run assembles the registry exactly once.
        """
        package = ModuleType("goga_tool_fake")

        def register_hooks(hooks: Any) -> None:
            hooks.subscribe(
                "statuses",
                "register_statuses",
                "published",
                lambda context: context.register("published", "fake/published.md", after="planned"),
            )

        package.register_hooks = register_hooks
        monkeypatch.setitem(sys.modules, "goga_tool_fake", package)
        enumeration = mock.MagicMock(return_value={"goga_tool_fake": ["goga-tool-fake"]})
        monkeypatch.setattr("goga.hooks.tools.packages.packages_distributions", enumeration)
        qualified = "fake.published"
        artifact = "fake/published.md"

        # True registration: the qualified name assembles into the scale.
        assert qualified in [stage.name for stage in assemble_status_scale().stages]
        assert enumeration.call_count == 1

        (tmp_path / ".goga/history/2026/demo-topic").mkdir(parents=True)
        _write(tmp_path, f".goga/history/2026/demo-topic/{artifact}")
        _write(tmp_path, ".goga/history/2026/other-topic/prd.md")
        monkeypatch.chdir(tmp_path)

        filtered = CliRunner().invoke(history, ["status", "2026", "-s", qualified])
        unfiltered = CliRunner().invoke(history, ["status", "2026"])

        assert filtered.exit_code == 0
        assert unfiltered.exit_code == 0
        # One build per run — the direct assembly plus one per CLI run.
        assert enumeration.call_count == 3
        assert filtered.output == f"demo-topic [{qualified}]\n"
        assert "other-topic" not in filtered.output
        assert "other-topic [defined]" in unfiltered.output


class TestUnmigratedStatusCallback:
    """A tool package still on the removed ``register_topic_statuses`` callback."""

    def test_old_status_callback_is_silently_ignored(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A package without ``register_hooks`` loses its statuses quietly.

        The old ``register_topic_statuses`` callback no longer exists and is
        never called (ADR): the migrated package's statuses assemble into the
        scale, the unmigrated one contributes nothing, and stderr carries no
        error about it — the quiet loss the migration note of ``docs/tools.md``
        announces.
        """

        def register_hooks(hooks: Any) -> None:
            hooks.subscribe(
                "statuses",
                "register_statuses",
                "published",
                lambda context: context.register("published", "published.md", after="planned"),
            )

        new_package = ModuleType("goga_tool_newtool")
        new_package.register_hooks = register_hooks
        old_package = ModuleType("goga_tool_oldtool")
        old_package.register_topic_statuses = lambda _statuses: None

        monkeypatch.setitem(sys.modules, "goga_tool_newtool", new_package)
        monkeypatch.setitem(sys.modules, "goga_tool_oldtool", old_package)

        with mock.patch(
            "goga.hooks.tools.packages.packages_distributions",
            return_value={
                "goga_tool_newtool": ["goga-tool-newtool"],
                "goga_tool_oldtool": ["goga-tool-oldtool"],
            },
        ):
            names = [stage.name for stage in assemble_status_scale().stages]

        assert "newtool.published" in names
        assert "oldtool.published" not in names
        assert "oldtool" not in capsys.readouterr().err


class TestPipelineTopicProcedureRegression:
    """The removed ``-b/--branch`` and the ``-t/--topic`` that replaced it."""

    def test_pipeline_help_carries_topic_and_not_branch(self) -> None:
        """``--help`` shows ``-t/--topic``; no ``-b`` option remains."""
        result = CliRunner().invoke(app, ["pipeline", "--help"])

        assert result.exit_code == 0
        assert "-t" in result.output
        assert "--topic" in result.output
        assert "-b" not in result.output

    def test_pipeline_branch_option_is_rejected(self) -> None:
        """``goga pipeline -b x dev`` fails at parsing — unknown option."""
        result = CliRunner().invoke(app, ["pipeline", "-b", "x", "dev"])

        assert result.exit_code != 0
        assert "No such option" in result.output
        assert "-b" in result.output


@requires_git
class TestSwitchTopicIdempotentChain:
    """The switch chain of the domain over the real git cell."""

    def test_switch_on_current_host_is_idempotent_without_mutations(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Already hosting the work returns the idempotent line — no
        cleanliness probe, no git mutation."""
        _init_topic_repo(tmp_path)
        monkeypatch.chdir(tmp_path)

        with (
            mock.patch.object(topics_switching, "is_working_tree_clean") as clean_probe,
            mock.patch.object(topics_switching, "checkout_local_branch") as checkout,
            mock.patch.object(topics_switching, "create_branch_from_remote_tracking") as create_branch,
        ):
            clean_probe.return_value = True
            line = switch_topic("feat-a", year="2025")

        assert line == "Already on branch feat-a"
        assert clean_probe.called is False
        assert checkout.called is False
        assert create_branch.called is False

    def test_switch_by_slug_checks_out_local_host(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A slug identifier resolves to its single local host and checks it out for real."""
        _init_topic_repo(tmp_path)
        _add_solo_branch(tmp_path)
        monkeypatch.chdir(tmp_path)

        line = switch_topic("solo", year="2025")

        assert line == "Switched to branch solo"
        assert _current_branch(tmp_path) == "solo"

    def test_switch_by_branch_name_hosting_several_topics_switches(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An exact branch name is one candidate even when the branch hosts
        several topics of the year — the switch needs no terminal."""
        _init_topic_repo(tmp_path)
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(sys, "stdin", mock.Mock(**{"isatty.return_value": False}))

        line = switch_topic("feat-b", year="2025")

        assert line == "Switched to branch feat-b"
        assert _current_branch(tmp_path) == "feat-b"

    def test_switch_ambiguous_slug_lists_candidates_without_terminal(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A slug hosted by several distinct branches is genuinely ambiguous —
        the numbered list is the non-interactive error, and nothing is mutated."""
        _init_topic_repo(tmp_path)
        _git(tmp_path, "switch", "-q", "-c", "one")
        _write(tmp_path, ".goga/history/2025/shared/prd.md")
        _git(tmp_path, "add", ".goga")
        _git(tmp_path, *_GIT_IDENTITY, "commit", "-qm", "topic shared")
        _git(tmp_path, "switch", "-q", "-c", "two")
        _git(tmp_path, "switch", "-q", "feat-a")
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(sys, "stdin", mock.Mock(**{"isatty.return_value": False}))

        with pytest.raises(click.ClickException, match=r"(?s)1\) one.*2\) two"):
            switch_topic("shared", year="2025")

        assert _current_branch(tmp_path) == "feat-a"

    def test_switch_by_slug_with_pushed_twin_switches_and_is_idempotent(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A slug hosted by a branch and its pushed remote twin resolves to the
        local branch — from another branch and again on the host."""
        _init_topic_repo(tmp_path)
        _git(tmp_path, "switch", "-q", "--orphan", "work/x")
        _write(tmp_path, ".goga/history/2025/work-x/plan.md")
        _git(tmp_path, "add", ".goga")
        _git(tmp_path, *_GIT_IDENTITY, "commit", "-qm", "topic work-x")
        _git(tmp_path, "update-ref", "refs/remotes/origin/work/x", "HEAD")
        _git(tmp_path, "switch", "-q", "feat-a")
        monkeypatch.chdir(tmp_path)

        line = switch_topic("work-x", year="2025")
        idempotent = switch_topic("work-x", year="2025")

        assert line == "Switched to branch work/x"
        assert idempotent == "Already on branch work/x"
        assert _current_branch(tmp_path) == "work/x"

    def test_switch_by_slug_creates_branch_from_remote_tracking(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A slug hosted only by a remote-tracking ref creates the local branch from it."""
        _init_topic_repo(tmp_path)
        _git(tmp_path, "switch", "-q", "feat-b")
        _git(tmp_path, "branch", "-D", "feat-a")
        monkeypatch.chdir(tmp_path)

        line = switch_topic("feat-a", year="2025")

        assert line == "Created branch feat-a from origin/feat-a"
        assert _current_branch(tmp_path) == "feat-a"

    def test_switch_refuses_dirty_working_tree(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A dirty working tree is a clean error — the repository stays put."""
        _init_topic_repo(tmp_path)
        _add_solo_branch(tmp_path)
        (tmp_path / "uncommitted.txt").write_text("dirty\n", encoding="utf-8")
        monkeypatch.chdir(tmp_path)

        with pytest.raises(click.ClickException, match="dirty"):
            switch_topic("solo", year="2025")

        assert _current_branch(tmp_path) == "feat-a"


@requires_git
class TestCreateTopicRealGit:
    """``goga topics create`` over the real git cell and path routines."""

    def test_create_topic_creates_branch_and_topic_directory(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A free name creates the branch verbatim and the topic directory of the year."""
        _init_topic_repo(tmp_path)
        monkeypatch.chdir(tmp_path)

        line = create_topic("Feature/Foo_Bar", year="2025")

        assert line == "Created branch Feature/Foo_Bar and topic 2025/feature-foo-bar"
        assert _current_branch(tmp_path) == "Feature/Foo_Bar"
        assert (tmp_path / ".goga" / "history" / "2025" / "feature-foo-bar").is_dir()

    def test_create_topic_occupied_local_branch_reasks_non_interactively(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An existing branch name is a clean occupancy error — nothing is created."""
        _init_topic_repo(tmp_path)
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(
            sys, "stdin", mock.Mock(**{"isatty.return_value": False})
        )

        with pytest.raises(click.ClickException, match="already exists"):
            create_topic("feat-b", year="2025")

        assert _current_branch(tmp_path) == "feat-a"
        assert not (tmp_path / ".goga" / "history" / "2025" / "feat-b").exists()

    def test_create_topic_empty_todo_writes_no_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An empty todo creates the branch and the topic directory — and no todo.md."""
        _init_topic_repo(tmp_path)
        monkeypatch.chdir(tmp_path)

        line = create_topic("feat-empty", year="2025", todo="")

        assert line == "Created branch feat-empty and topic 2025/feat-empty"
        assert _current_branch(tmp_path) == "feat-empty"
        topic_dir = tmp_path / ".goga" / "history" / "2025" / "feat-empty"
        assert topic_dir.is_dir()
        assert not (topic_dir / "todo.md").exists()


@requires_git
class TestTopicsBoardTodos:
    """The todo column of ``goga topics board --info`` over real reads."""

    def test_board_survives_hand_edited_non_utf8_todos(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Todo summaries outside UTF-8 render with the replacement character.

        Both todo.md reads — the working copy through pathlib and the ref
        tree through ``git show`` — degrade the bytes instead of raising
        through the clean-error boundary, or one hand-edited file would
        break the whole board. The leading marker line never qualifies, so
        the summary the board shows is the degraded line the normalization
        picked.
        """
        _init_topic_repo(tmp_path)
        # The committed side: feat-b's todo lives in its ref tree only.
        _git(tmp_path, "switch", "-q", "feat-b")
        (tmp_path / ".goga" / "history" / "2025" / "feat-b" / "todo.md").write_bytes(
            b"###\nRem\xffote\n"
        )
        _git(tmp_path, "add", ".goga")
        _git(tmp_path, *_GIT_IDENTITY, "commit", "-qm", "feat-b todo")
        _git(tmp_path, "switch", "-q", "feat-a")
        # The uncommitted side: the current branch's working-copy todo.
        (tmp_path / ".goga" / "history" / "2025" / "feat-a" / "todo.md").write_bytes(
            b"###\nPay\xffment\n"
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("COLUMNS", "120")

        result = CliRunner().invoke(topics, ["--year", "2025", "board", "--info"])

        assert result.exit_code == 0
        assert "Pay�ment" in result.output
        assert "Rem�ote" in result.output

    def test_create_todo_then_board_info_shows_summary_and_todo_status(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``create --todo`` and ``board --info`` close the loop over real git.

        The written todo.md carries the multi-line todo verbatim plus one
        trailing newline, the board reads the topic through it — the
        ``[todo]`` status — and the summary column shows the first line the
        ``#``-marker normalization qualifies, not the raw first line.
        """
        _init_topic_repo(tmp_path)
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("COLUMNS", "120")

        created = CliRunner().invoke(
            topics,
            [
                "--year",
                "2025",
                "create",
                "feat-new",
                "--todo",
                "###\n# Pay retry cap\n\nRetries ignore the cap.",
            ],
        )

        assert created.exit_code == 0
        assert created.output == "Created branch feat-new and topic 2025/feat-new\n"
        assert (
            tmp_path / ".goga" / "history" / "2025" / "feat-new" / "todo.md"
        ).read_bytes() == b"###\n# Pay retry cap\n\nRetries ignore the cap.\n"

        result = CliRunner().invoke(topics, ["--year", "2025", "board", "--info"])

        assert result.exit_code == 0
        assert ("* feat-new", "feat-new", "Pay retry cap", "[todo]") in _board_rows(
            result.output, columns=4
        )

    def test_board_old_title_txt_only_topic_is_empty_status(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A topic whose tree carries only the retired title.txt reads ``[empty]``.

        title.txt stopped being an axis artifact, so the topic has nothing
        the scale recognizes — no status, no todo summary — the clean break
        over real git, with the legacy file left on disk untouched.
        """
        _init_topic_repo(tmp_path)
        _git(tmp_path, "switch", "-q", "-c", "legacy")
        legacy_file = tmp_path / ".goga" / "history" / "2025" / "legacy-work" / "title.txt"
        legacy_file.parent.mkdir(parents=True)
        legacy_file.write_text("Retired artifact\n", encoding="utf-8")
        _git(tmp_path, "add", ".goga")
        _git(tmp_path, *_GIT_IDENTITY, "commit", "-qm", "legacy topic")
        _git(tmp_path, "switch", "-q", "feat-a")
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("COLUMNS", "120")

        result = CliRunner().invoke(topics, ["--year", "2025", "board", "--info"])

        assert result.exit_code == 0
        assert ("legacy-work", "legacy", "", "[empty]") in _board_rows(
            result.output, columns=4
        )
        # The legacy file stays byte-exact in its ref tree — the board read
        # it and dropped it as an unknown artifact, it never rewrote it.
        assert (
            _git_out(tmp_path, "show", "legacy:.goga/history/2025/legacy-work/title.txt")
            == "Retired artifact"
        )


@requires_git
class TestHistoryPrune:
    """``goga history prune`` over the real branch inventory and tree."""

    def test_prune_over_real_git_deletes_orphans_keeps_hosted(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The real ``for-each-ref`` inventory protects hosted topics; the orphans go."""
        _init_topic_repo(tmp_path)
        # The switch back onto feat-a removed feat-b's directory from the
        # working tree — restore it untracked, so both hosted topics are
        # live candidates the real inventory must protect.
        _write(tmp_path, ".goga/history/2025/feat-b/prd.md")
        _write(tmp_path, ".goga/history/2025/orphan-c/prd.md")
        _write(tmp_path, ".goga/history/2025/done-d/completed/plan.md")
        monkeypatch.chdir(tmp_path)

        dry = CliRunner().invoke(history, ["prune", "2025", "--dry-run"])

        assert dry.exit_code == 0
        assert dry.output.splitlines() == ["done-d", "orphan-c"]
        assert (tmp_path / ".goga/history/2025/orphan-c/prd.md").exists()

        wet = CliRunner().invoke(history, ["prune", "2025"])

        assert wet.exit_code == 0
        assert wet.output.splitlines() == ["done-d", "orphan-c"]
        assert not (tmp_path / ".goga/history/2025/orphan-c").exists()
        assert not (tmp_path / ".goga/history/2025/done-d").exists()
        # The branch-hosted topics survive; a done orphan goes regardless.
        assert (tmp_path / ".goga/history/2025/feat-a").is_dir()
        assert (tmp_path / ".goga/history/2025/feat-b").is_dir()

    def test_prune_remote_only_host_protects_over_real_git(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A remote-tracking ref alone protects its topic — no local branch needed."""
        _init_topic_repo(tmp_path)
        # A throwaway branch supplies the tree, then keeps only its remote twin.
        _git(tmp_path, "switch", "-q", "-c", "throwaway")
        _write(tmp_path, ".goga/history/2025/remote-only/prd.md")
        _git(tmp_path, "add", ".goga")
        _git(tmp_path, *_GIT_IDENTITY, "commit", "-qm", "remote-only topic")
        _git(tmp_path, "update-ref", "refs/remotes/origin/remote-only", "HEAD")
        _git(tmp_path, "switch", "-q", "feat-a")
        _git(tmp_path, "branch", "-qD", "throwaway")
        # The topic directory is present in the working tree, untracked.
        _write(tmp_path, ".goga/history/2025/remote-only/prd.md")
        monkeypatch.chdir(tmp_path)

        result = CliRunner().invoke(history, ["prune", "2025", "--dry-run"])

        assert result.exit_code == 0
        assert result.output == ""
        assert (tmp_path / ".goga/history/2025/remote-only/prd.md").exists()


@requires_git
class TestPublishTopicRealGit:
    """``publish_topic`` over the real git cell — the quarantined fast path.

    No domain routine and no git routine is mocked: the CLI-less scenarios
    drive the whole chain ``publish_topic`` → ``goga.topics.git`` → real
    git against a throwaway repository with a real bare ``origin``.
    """

    def test_publish_end_to_end_leaves_user_state_untouched(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A publish over a dirty tree leaves HEAD, the status, and the
        working copy identical — the topic exists only in the pushed branch."""
        _init_publish_repo(tmp_path)
        # The uncommitted modification the quarantine invariant must survive.
        (tmp_path / "tracked.txt").write_text("wip\n", encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        year = current_year()
        before = (
            _git_out(tmp_path, "rev-parse", "HEAD"),
            _git_out(tmp_path, "status", "--porcelain"),
            _worktree_snapshot(tmp_path),
        )

        line = publish_topic(
            "Feature/Foo_Bar", "Payment retry", "origin/main", "goga: create topic {slug}"
        )

        after = (
            _git_out(tmp_path, "rev-parse", "HEAD"),
            _git_out(tmp_path, "status", "--porcelain"),
            _worktree_snapshot(tmp_path),
        )
        assert before == after
        # The topic directory exists in the pushed branch, never on disk.
        assert not (tmp_path / ".goga").exists()
        assert line == f"Created branch Feature/Foo_Bar and published topic {year}/feature-foo-bar"
        assert "\n" not in line

    def test_publish_creates_single_todo_commit_and_shows_on_remote_board(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The published branch carries exactly the todo commit — upstream
        bound to origin and visible on the remote board with the ``todo`` status."""
        _init_publish_repo(tmp_path)
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("COLUMNS", "120")
        year = current_year()
        topic_path = f".goga/history/{year}/feature-foo-bar/todo.md"

        publish_topic(
            "Feature/Foo_Bar", "Payment retry", "origin/main", "goga: create topic {slug}"
        )

        assert _git_out(tmp_path, "rev-list", "--count", "origin/main..Feature/Foo_Bar") == "1"
        assert _git_out(tmp_path, "show", "--name-only", "--format=", "Feature/Foo_Bar").splitlines() == [
            topic_path
        ]
        assert (
            _git_out(tmp_path, "show", "-s", "--format=%s", "Feature/Foo_Bar")
            == "goga: create topic feature-foo-bar"
        )
        assert _git_out(tmp_path, "show", f"Feature/Foo_Bar:{topic_path}") == "Payment retry"
        assert _git_out(tmp_path, "config", "branch.Feature/Foo_Bar.remote") == "origin"
        # The local branch stays after the push.
        assert _git_out(tmp_path, "rev-parse", "--verify", "refs/heads/Feature/Foo_Bar")
        _git(tmp_path, "fetch", "-q", "origin")

        result = CliRunner().invoke(topics, ["--year", year, "board", "--remote", "--info"])

        assert result.exit_code == 0
        assert _board_rows(result.output, columns=4) == [
            ("feature-foo-bar", "origin/Feature/Foo_Bar", "Payment retry", "[todo]")
        ]

    def test_publish_failed_push_rolls_back_and_rerun_succeeds(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A failed push deletes the planted branch and disturbs nothing —
        the freed name carries the immediate re-run of the same cycle."""
        origin = _init_publish_repo(tmp_path)
        _git(tmp_path, "remote", "set-url", "--push", "origin", "../does-not-exist.git")
        monkeypatch.chdir(tmp_path)
        porcelain_before = _git_out(tmp_path, "status", "--porcelain")

        with pytest.raises(click.ClickException, match="git failed:"):
            publish_topic(
                "Feature/Foo_Bar", "Payment retry", "origin/main", "goga: create topic {slug}"
            )

        assert "Feature/Foo_Bar" not in _git_out(tmp_path, "for-each-ref", "refs/heads")
        assert _git_out(tmp_path, "status", "--porcelain") == porcelain_before

        _git(tmp_path, "remote", "set-url", "--push", "origin", str(origin))
        line = publish_topic(
            "Feature/Foo_Bar", "Payment retry", "origin/main", "goga: create topic {slug}"
        )

        assert "refs/heads/Feature/Foo_Bar" in _git_out(tmp_path, "for-each-ref", "refs/heads")
        assert _git_out(tmp_path, "rev-parse", "--verify", "refs/remotes/origin/Feature/Foo_Bar")
        assert "published topic" in line

    def test_publish_non_ascii_todo_survives_utf8(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A non-ASCII todo round-trips byte-exact — UTF-8 with one
        trailing newline, in the branch tree and on the remote board."""
        _init_publish_repo(tmp_path)
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("COLUMNS", "120")
        year = current_year()
        topic_path = f".goga/history/{year}/feature-foo-bar/todo.md"

        publish_topic(
            "Feature/Foo_Bar", "Оплата повторно", "origin/main", "goga: create topic {slug}"
        )

        shown = subprocess.run(
            ["git", "show", f"Feature/Foo_Bar:{topic_path}"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        assert shown.stdout.decode("utf-8") == "Оплата повторно\n"
        assert shown.stdout == "Оплата повторно\n".encode("utf-8")  # noqa: UP012 — the codec is the contract
        assert len(shown.stdout) == 30
        _git(tmp_path, "fetch", "-q", "origin")

        result = CliRunner().invoke(topics, ["--year", year, "board", "--remote", "--info"])

        assert result.exit_code == 0
        assert "Оплата" in result.output
        assert ("feature-foo-bar", "origin/Feature/Foo_Bar", "Оплата повторно", "[todo]") in _board_rows(
            result.output, columns=4
        )

    def test_publish_slug_hosted_by_another_branch_is_blocked(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The branch-tree oracle over real git: a slug already hosted by
        another branch blocks the publish — nothing is planted or pushed."""
        _init_publish_repo(tmp_path)
        year = current_year()
        _git(tmp_path, "switch", "-q", "-c", "Host_Branch")
        _write(tmp_path, f".goga/history/{year}/feature-foo-bar/prd.md")
        _git(tmp_path, "add", ".goga")
        _git(tmp_path, *_GIT_IDENTITY, "commit", "-qm", "host topic")
        _git(tmp_path, "switch", "-q", "main")
        monkeypatch.chdir(tmp_path)
        heads_before = _git_out(tmp_path, "for-each-ref", "refs/heads")

        with pytest.raises(click.ClickException) as raised:
            publish_topic("Feature/Foo_Bar", "T", "origin/main", "m")

        assert raised.value.message == (
            f"topic 'feature-foo-bar' of {year} is already hosted by branch 'Host_Branch'"
            " — run 'goga topics board' to see the board"
        )
        assert _git_out(tmp_path, "for-each-ref", "refs/heads") == heads_before
        assert "Feature/Foo_Bar" not in _git_out(tmp_path, "for-each-ref", "refs/heads")

    def test_publish_from_a_subdirectory_still_sees_the_branch_tree_conflict(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The branch-tree oracle reads the root tree from any directory.

        The publication write is root-relative (``--cacheinfo`` stages at
        the repository root regardless of the working directory), so the
        oracle must probe the same tree from a subdirectory — a bare
        pathspec resolves against the working directory there and the probe
        would read nothing, publishing a duplicate of an already-hosted
        topic to origin.
        """
        _init_publish_repo(tmp_path)
        year = current_year()
        _git(tmp_path, "switch", "-q", "-c", "Host_Branch")
        _write(tmp_path, f".goga/history/{year}/feature-foo-bar/prd.md")
        _git(tmp_path, "add", ".goga")
        _git(tmp_path, *_GIT_IDENTITY, "commit", "-qm", "host topic")
        _git(tmp_path, "switch", "-q", "main")
        heads_before = _git_out(tmp_path, "for-each-ref", "refs/heads")
        nested = tmp_path / "nested"
        nested.mkdir()
        monkeypatch.chdir(nested)

        with pytest.raises(click.ClickException) as raised:
            publish_topic("Feature/Foo_Bar", "T", "origin/main", "m")

        assert raised.value.message == (
            f"topic 'feature-foo-bar' of {year} is already hosted by branch 'Host_Branch'"
            " — run 'goga topics board' to see the board"
        )
        assert _git_out(tmp_path, "for-each-ref", "refs/heads") == heads_before
        assert "Feature/Foo_Bar" not in _git_out(tmp_path, "for-each-ref", "refs/heads")
        assert "Feature/Foo_Bar" not in _git_out(tmp_path, "ls-remote", "--heads", "origin")

    def test_publish_sibling_slug_is_not_a_conflict(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A sibling slug sharing only the prefix text stays free.

        ``feature-foo-bar`` hosted by another branch must not block
        ``feature-foo`` — the trailing slash of the probe prefix against
        real git pathspec filtering, not an emulated reader.
        """
        _init_publish_repo(tmp_path)
        year = current_year()
        _git(tmp_path, "switch", "-q", "-c", "Host_Branch")
        _write(tmp_path, f".goga/history/{year}/feature-foo-bar/prd.md")
        _git(tmp_path, "add", ".goga")
        _git(tmp_path, *_GIT_IDENTITY, "commit", "-qm", "host sibling topic")
        _git(tmp_path, "switch", "-q", "main")
        monkeypatch.chdir(tmp_path)

        line = publish_topic("Feature/Foo", "T", "origin/main", "m")

        assert line == f"Created branch Feature/Foo and published topic {year}/feature-foo"

    def test_publish_slug_hosted_only_on_origin_is_blocked(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A slug hosted only by a remote-tracking ref blocks the publish.

        The name differs from the remote ref's short name, so the branch
        oracle stays free and the conflict comes from the branch-tree oracle
        alone — a topic hosted only on ``origin`` blocks the slug.
        """
        _init_publish_repo(tmp_path)
        year = current_year()
        _git(tmp_path, "switch", "-q", "-c", "throwaway")
        _write(tmp_path, f".goga/history/{year}/remote-only/prd.md")
        _git(tmp_path, "add", ".goga")
        _git(tmp_path, *_GIT_IDENTITY, "commit", "-qm", "remote-only topic")
        _git(tmp_path, "update-ref", "refs/remotes/origin/Remote_Only", "HEAD")
        _git(tmp_path, "switch", "-q", "main")
        _git(tmp_path, "branch", "-qD", "throwaway")
        monkeypatch.chdir(tmp_path)

        with pytest.raises(click.ClickException) as raised:
            publish_topic("Remote/Only", "T", "origin/main", "m")

        assert raised.value.message == (
            f"topic 'remote-only' of {year} is already hosted by branch 'origin/Remote_Only'"
            " — run 'goga topics board' to see the board"
        )

    def test_publish_name_the_oracle_misses_never_deletes_real_work(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An occupied name the inventory oracle cannot see is stopped by the
        create-only plant — the pre-existing branch survives.

        A tag of the same name makes git lengthen the display name of
        ``refs/heads/v1`` to ``heads/v1``, so no oracle reports the name
        occupied. A plant that moved the ref would push the new commit over
        ``v1`` and then delete the branch on the push failure — the real
        commit lost behind the push error. The plant refuses instead.
        """
        _init_publish_repo(tmp_path)
        _git(tmp_path, "branch", "v1")
        _git(tmp_path, "tag", "v1")
        before = _git_out(tmp_path, "rev-parse", "refs/heads/v1")
        monkeypatch.chdir(tmp_path)

        with pytest.raises(click.ClickException, match="reference already exists"):
            publish_topic("v1", "Todo", "origin/main", "goga: create topic {slug}")

        assert _git_out(tmp_path, "rev-parse", "refs/heads/v1") == before
        assert "refs/remotes/origin/v1" not in _git_out(tmp_path, "for-each-ref", "refs/remotes/origin")

    def test_publish_non_utf8_remote_output_rolls_back_and_surfaces_clean_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A remote message outside UTF-8 neither pierces the boundary nor
        strands the planted branch.

        The push of a rejecting ``pre-receive`` hook answers with bytes a
        strict UTF-8 reader cannot decode — a ``UnicodeDecodeError`` is a
        ``ValueError``, it matches no handler of the domain, so strict
        decoding would pierce the clean-error boundary *and* skip the
        rollback. The replacement-character decoding keeps both guarantees.
        """
        origin = _init_publish_repo(tmp_path)
        hook = origin / "hooks" / "pre-receive"
        hook.write_text('#!/bin/sh\nprintf "erreur: \\377\\376\\n" >&2\nexit 1\n')
        hook.chmod(0o755)
        monkeypatch.chdir(tmp_path)

        with pytest.raises(click.ClickException, match="remote rejected"):
            publish_topic("Feature/Foo_Bar", "Todo", "origin/main", "goga: create topic {slug}")

        # The planted branch was rolled back — nothing of the cycle survives.
        assert "refs/heads/Feature/Foo_Bar" not in _git_out(
            tmp_path, "for-each-ref", "refs/heads"
        )
        assert not (tmp_path / ".goga").exists()

    def test_publish_newline_in_name_cannot_inject_a_second_command(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A newline inside the name never rewrites another ref.

        The line-oriented ``update-ref --stdin`` stream splits commands on
        ``LF``, so a machine-generated name carrying ``... <oid> LF update
        refs/heads/main`` would open a second command of the transaction and
        silently move the user's ``main`` behind a garbled error. The NUL
        framing keeps the verbatim name one token, so git's own refname
        validation rejects it as one clean error before any mutation.
        """
        _init_publish_repo(tmp_path)
        monkeypatch.chdir(tmp_path)
        base = _git_out(tmp_path, "rev-parse", "HEAD")
        injected = f"evil {base}\nupdate refs/heads/main"

        with pytest.raises(click.ClickException, match="invalid ref format"):
            publish_topic(injected, "Todo", "origin/main", "goga: create topic {slug}")

        assert _git_out(tmp_path, "rev-parse", "refs/heads/main") == base
        assert _git_out(tmp_path, "for-each-ref", "--format=%(refname)", "refs/heads") == "refs/heads/main"
        assert "refs/remotes/origin/evil" not in _git_out(
            tmp_path, "for-each-ref", "refs/remotes/origin"
        )

    def test_publish_empty_template_does_not_wait_for_stdin(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An explicitly empty commit template publishes without waiting on stdin.

        ``commit-tree -m ""`` reads its message from stdin when the ``-m``
        argument is empty, and the runner used to leave that stdin
        inherited from the caller: under a terminal or a harness-held open
        pipe — neither ever reaching EOF — the publish hung forever with no
        output. The cycle must complete — the empty template becomes the
        commit message verbatim while the non-empty todo still carries the
        todo.md payload of the published branch.
        """
        _init_publish_repo(tmp_path)
        monkeypatch.chdir(tmp_path)
        year = current_year()

        # fd 0 becomes a pipe nobody writes to — EOF never arrives, the
        # exact descriptor a terminal or a held stdin provides. The cycle
        # runs on a thread so a regression surfaces as this test's failure
        # instead of a timeout of the whole session.
        read_fd, write_fd = os.pipe()
        saved_stdin = os.dup(0)
        lines: list[str] = []
        failure: list[BaseException] = []

        def cycle() -> None:
            try:
                os.dup2(read_fd, 0)
                lines.append(
                    publish_topic("Feature/Foo_Bar", "Payment retry", "origin/main", "")
                )
            except BaseException as exc:  # recorded, re-raised on the main thread below
                failure.append(exc)
            finally:
                os.dup2(saved_stdin, 0)

        thread = threading.Thread(target=cycle, daemon=True)
        thread.start()
        thread.join(timeout=30)
        alive = thread.is_alive()
        os.close(read_fd)
        os.close(write_fd)
        os.close(saved_stdin)

        assert not alive, (
            "publish_topic with an empty template never returned — "
            "a git invocation is waiting on the caller's stdin"
        )
        if failure:
            raise failure[0]
        assert lines[0] == (
            f"Created branch Feature/Foo_Bar and published topic {year}/feature-foo-bar"
        )
        # The published commit carries the empty message verbatim.
        assert _git_out(tmp_path, "show", "-s", "--format=%s", "Feature/Foo_Bar") == ""
        assert (
            _git_out(
                tmp_path, "show", f"Feature/Foo_Bar:.goga/history/{year}/feature-foo-bar/todo.md"
            )
            == "Payment retry"
        )
