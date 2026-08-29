"""End-to-end integration tests for the topic workflows of one year.

These exercise the cross-cell paths of the usability-for-topic-workaround
feature over its real surfaces — no domain routine and no renderer is
mocked, only the boundaries the environment cannot provide:

    goga topics status --year Y
                  -> goga.commands.topics.topics.status
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

import shutil
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from unittest import mock

import click
import pytest
from click.testing import CliRunner
from goga.cli import app
from goga.commands.history import history
from goga.commands.topics import topics
from goga.history import assemble_status_scale
from goga.history.statuses import assembly as statuses_assembly
from goga.topics import create_topic, switch_topic
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


def _board_rows(output: str) -> list[tuple[str, str, str]]:
    """Parse the rendered board into its data rows.

    Args:
        output: The captured stdout of ``goga topics status``.

    Returns:
        The ``(topic cell, branch, statuses)`` tuples of the data rows —
        the header and separator rows dropped, every cell stripped.
    """
    lines = [line for line in output.splitlines() if line.startswith("|")]
    rows = []
    for line in lines[2:]:
        cells = line.split("|")
        rows.append((cells[1].strip(), cells[2].strip(), cells[3].strip()))
    return rows


@requires_git
class TestTopicsStatusBoard:
    """``goga topics status --year Y`` over a real repository and scale."""

    def test_board_renders_topics_statuses_and_current_marker(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The board table carries the topics, their artifact statuses, and
        the current marker — exit 0."""
        _init_topic_repo(tmp_path)
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("COLUMNS", "120")

        result = CliRunner().invoke(topics, ["--year", "2025", "status"])

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

        result = CliRunner().invoke(topics, ["--year", "2030", "status"])

        assert result.exit_code == 0
        assert result.output == ""


class TestHistoryStatusToolFilter:
    """``goga history status -s <tool>.<name>`` against the real assembly."""

    def test_qualified_tool_status_validates_and_filters(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """A registered tool status validates by its qualified name and
        keeps exactly the topics carrying it."""
        scale = assemble_status_scale()
        qualified = next((stage.name for stage in scale.stages if "." in stage.name), None)
        if qualified is None:
            # No installed tool package registers statuses — register a fake
            # one. The command surface, the domain, and the assembly below
            # stay the real ones; only the package enumeration is pinned.
            package = ModuleType("goga_tool_fake")

            def register_topic_statuses(statuses: object) -> None:
                statuses.register("published", "fake/published.md", after="planned")

            package.register_topic_statuses = register_topic_statuses
            monkeypatch.setitem(sys.modules, "goga_tool_fake", package)
            monkeypatch.setattr(
                statuses_assembly,
                "packages_distributions",
                lambda: {"goga_tool_fake": ["goga-tool-fake"]},
            )
            qualified = "fake.published"
            artifact = "fake/published.md"
        else:
            artifact = next(stage.filepath for stage in scale.stages if stage.name == qualified)

        # True registration: the qualified name assembles into the scale.
        assert qualified in [stage.name for stage in assemble_status_scale().stages]

        (tmp_path / ".goga/history/2026/demo-topic").mkdir(parents=True)
        _write(tmp_path, f".goga/history/2026/demo-topic/{artifact}")
        _write(tmp_path, ".goga/history/2026/other-topic/prd.md")
        monkeypatch.chdir(tmp_path)

        filtered = CliRunner().invoke(history, ["status", "2026", "-s", qualified])
        unfiltered = CliRunner().invoke(history, ["status", "2026"])

        assert filtered.exit_code == 0
        assert filtered.output == f"demo-topic [{qualified}]\n"
        assert "other-topic" not in filtered.output
        assert "other-topic [defined]" in unfiltered.output


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
            line = switch_topic("feat-a", "2025")

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

        line = switch_topic("solo", "2025")

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

        line = switch_topic("feat-b", "2025")

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
            switch_topic("shared", "2025")

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

        line = switch_topic("work-x", "2025")
        idempotent = switch_topic("work-x", "2025")

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

        line = switch_topic("feat-a", "2025")

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
            switch_topic("solo", "2025")

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
