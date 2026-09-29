"""Contract and logic tests for the entities declared in
``goga/topics/git/CODEMANIFEST`` with ``location: exchange.py``:

- ``require_git_version()`` — the git version gate of the exchange
- ``is_ancestor(ancestor, descendant)`` — commit containment
- ``resolve_commit_tree(revision)`` — the tree a revision carries
- ``merge_tree(ours, theirs, merge_base)`` — the three-way merge as a tree
- ``create_commit_from_tree(tree, parents, message)`` — a commit over a
  ready tree
- ``replay_commits(onto, until)`` — the plumbing replay of a commit range
- ``point_branch_at_commit(branch_name, commit)`` — the single-ref planting

The subprocess call is mocked at the import point per the ``convention``
practice — no git binary and no repository are touched.
"""

from __future__ import annotations

import inspect
import subprocess
import typing
from typing import Any
from unittest import mock

import pytest
from goga.topics.git.exchange import (
    create_commit_from_tree,
    is_ancestor,
    merge_tree,
    point_branch_at_commit,
    replay_commits,
    require_git_version,
    resolve_commit_tree,
)

_IDENT_SEP = "\x1f"
_AUTHOR_LINE = f"Ann{_IDENT_SEP}ann@x.io{_IDENT_SEP}2026-01-02T03:04:05+00:00{_IDENT_SEP}Do the thing\n"


def _git_answer(stdout: str = "", returncode: int = 0) -> subprocess.CompletedProcess[str]:
    """A successful git invocation answering ``stdout``."""
    return subprocess.CompletedProcess(args=["git"], returncode=returncode, stdout=stdout, stderr="")


def _commands_of(run: mock.Mock) -> list[list[str]]:
    """The argv list of every invocation the mock received."""
    return [call.args[0] for call in run.call_args_list]


def _calls_of(run: mock.Mock, subcommand: str) -> list[Any]:
    """The recorded calls of one git subcommand."""
    return [call for call in run.call_args_list if call.args[0][1] == subcommand]


def _replay_run(
    rev_list: str,
    shows: list[str],
    trees: list[str],
    commits: list[str],
    merge_returncode: int = 0,
) -> mock.Mock:
    """A scripted git answering one replay chain per subcommand.

    ``shows``, ``trees``, and ``commits`` are consumed in call order —
    one entry per replayed commit for ``show`` and ``merge-tree``, one
    per built commit for ``commit-tree``.
    """
    remaining_shows, remaining_trees, remaining_commits = list(shows), list(trees), list(commits)

    def answer_by_argv(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        if command[1] == "rev-list":
            stdout, returncode = rev_list, 0
        elif command[1] == "show":
            stdout, returncode = remaining_shows.pop(0), 0
        elif command[1] == "merge-tree":
            stdout, returncode = remaining_trees.pop(0) + "\n", merge_returncode
        else:
            stdout, returncode = remaining_commits.pop(0) + "\n", 0

        return subprocess.CompletedProcess(args=command, returncode=returncode, stdout=stdout, stderr="")

    return mock.Mock(side_effect=answer_by_argv)


# --- Contract tests ---


class TestExchangeContract:
    def test_module_declares_the_exchange_routines(self) -> None:
        """The seven routines live in ``goga.topics.git.exchange``."""
        import goga.topics.git.exchange as module

        assert module.require_git_version is require_git_version
        assert module.is_ancestor is is_ancestor
        assert module.resolve_commit_tree is resolve_commit_tree
        assert module.merge_tree is merge_tree
        assert module.create_commit_from_tree is create_commit_from_tree
        assert module.replay_commits is replay_commits
        assert module.point_branch_at_commit is point_branch_at_commit

    def test_declared_signatures(self) -> None:
        """The routines take exactly the declared parameters."""
        assert list(inspect.signature(require_git_version).parameters) == []
        assert list(inspect.signature(is_ancestor).parameters) == ["ancestor", "descendant"]
        assert list(inspect.signature(resolve_commit_tree).parameters) == ["revision"]
        assert list(inspect.signature(merge_tree).parameters) == ["ours", "theirs", "merge_base"]
        assert list(inspect.signature(create_commit_from_tree).parameters) == ["tree", "parents", "message"]
        assert list(inspect.signature(replay_commits).parameters) == ["onto", "until"]
        assert list(inspect.signature(point_branch_at_commit).parameters) == ["branch_name", "commit"]

    def test_parameters_are_positional_or_keyword_with_contract_hints(self) -> None:
        """No extras, only ``merge_base`` defaults, and the declared type hints."""
        hints = {
            require_git_version: {"return": type(None)},
            is_ancestor: {"ancestor": str, "descendant": str, "return": bool},
            resolve_commit_tree: {"revision": str, "return": str},
            merge_tree: {"ours": str, "theirs": str, "merge_base": str | None, "return": str | None},
            create_commit_from_tree: {"tree": str, "parents": list[str], "message": str, "return": str},
            replay_commits: {"onto": str, "until": str, "return": str | None},
            point_branch_at_commit: {"branch_name": str, "commit": str, "return": type(None)},
        }

        for routine, declared in hints.items():
            parameters = inspect.signature(routine).parameters

            assert all(
                parameter.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD for parameter in parameters.values()
            ), routine
            assert all(
                parameter.default is inspect.Parameter.empty
                for name, parameter in parameters.items()
                if name != "merge_base"
            ), routine
            if "merge_base" in parameters:
                assert parameters["merge_base"].default is None, routine
            assert typing.get_type_hints(routine) == declared, routine

    def test_single_shot_routines_run_exactly_one_invocation(self) -> None:
        """Six routines are single-invocation wrappers of the contract."""
        scenarios = [
            (require_git_version, (), "git version 2.43.0\n"),
            (is_ancestor, ("aa1", "cc3"), ""),
            (resolve_commit_tree, ("cc3",), "tree-oid-1\n"),
            (merge_tree, ("cc3", "aa1"), "tree-oid-1\n"),
            (create_commit_from_tree, ("tree-oid-1", ["cc3"], "m"), "ee5\n"),
            (point_branch_at_commit, ("main", "ee5"), ""),
        ]

        for routine, arguments, stdout in scenarios:
            run = mock.Mock(return_value=_git_answer(stdout))

            with mock.patch("goga.topics.git.exchange.subprocess.run", run):
                routine(*arguments)

            assert run.call_count == 1, routine

    def test_replay_commits_is_a_per_commit_chain(self) -> None:
        """The replay reads, merges, and commits once per replayed commit."""
        run = _replay_run(
            rev_list="c1 c0\n",
            shows=[_AUTHOR_LINE],
            trees=["t1"],
            commits=["f1"],
        )

        with mock.patch("goga.topics.git.exchange.subprocess.run", run):
            assert replay_commits("aa1", "cc3") == "f1"

        assert [command[1] for command in _commands_of(run)] == ["rev-list", "show", "merge-tree", "commit-tree"]


# --- Logic tests ---


class TestRequireGitVersion:
    def test_require_git_version_passes_modern_git(self) -> None:
        """A modern git passes the gate — one read-only invocation."""
        run = mock.Mock(return_value=_git_answer("git version 2.43.0 (Apple Git-151)\n"))

        with mock.patch("goga.topics.git.exchange.subprocess.run", run):
            result = require_git_version()

        assert result is None
        assert run.call_count == 1
        assert run.call_args.args[0] == ["git", "version"]

    def test_require_git_version_rejects_old_git(self) -> None:
        """An old git fails the gate naming the required and present versions."""
        run = mock.Mock(return_value=_git_answer("git version 2.35.1\n"))

        with (
            mock.patch("goga.topics.git.exchange.subprocess.run", run),
            pytest.raises(RuntimeError) as raised,
        ):
            require_git_version()

        assert "2.40" in str(raised.value)
        assert "2.35.1" in str(raised.value)

    def test_require_git_version_rejects_git_lacking_merge_base(self) -> None:
        """A 2.38/2.39 git fails the gate — the replay's ``--merge-base=`` needs 2.40."""
        run = mock.Mock(return_value=_git_answer("git version 2.39.5\n"))

        with (
            mock.patch("goga.topics.git.exchange.subprocess.run", run),
            pytest.raises(RuntimeError) as raised,
        ):
            require_git_version()

        assert "2.40" in str(raised.value)
        assert "2.39.5" in str(raised.value)

    def test_require_git_version_unparsable_output_is_gate_failure(self) -> None:
        """A version output nothing parses is the gate failure — never a silent pass."""
        run = mock.Mock(return_value=_git_answer("not a git at all\n"))

        with (
            mock.patch("goga.topics.git.exchange.subprocess.run", run),
            pytest.raises(RuntimeError) as raised,
        ):
            require_git_version()

        assert "unparsable" in str(raised.value)
        assert "not a git at all" in str(raised.value)


class TestIsAncestor:
    def test_is_ancestor_maps_exit_codes(self) -> None:
        """rc 0 reads True, rc 1 False, anything else is the raw failure."""
        for returncode, expected in ((0, True), (1, False)):
            run = mock.Mock(return_value=_git_answer(returncode=returncode))

            with mock.patch("goga.topics.git.exchange.subprocess.run", run):
                contains = is_ancestor("aa1", "cc3")

            assert contains is expected
            assert run.call_args.args[0] == ["git", "merge-base", "--is-ancestor", "aa1", "cc3"]
            # The containment oracle never raises on a normal answer.
            assert run.call_args.kwargs["check"] is False

        run = mock.Mock(return_value=_git_answer(returncode=128))

        with (
            mock.patch("goga.topics.git.exchange.subprocess.run", run),
            pytest.raises(subprocess.CalledProcessError),
        ):
            is_ancestor("aa1", "cc3")


class TestResolveCommitTree:
    def test_resolve_commit_tree_peels_to_tree(self) -> None:
        """``^{tree}`` peels the revision into the tree it carries."""
        run = mock.Mock(return_value=_git_answer("tree-oid-1\n"))

        with mock.patch("goga.topics.git.exchange.subprocess.run", run):
            tree = resolve_commit_tree("cc3")

        assert tree == "tree-oid-1"
        assert run.call_count == 1
        assert run.call_args.args[0] == ["git", "rev-parse", "--verify", "cc3^{tree}"]


class TestMergeTree:
    def test_merge_tree_clean_and_conflict(self) -> None:
        """A clean merge yields the first stdout line; a conflict is None."""
        run = mock.Mock(return_value=_git_answer("tree-oid-1\n\n"))

        with mock.patch("goga.topics.git.exchange.subprocess.run", run):
            tree = merge_tree("cc3", "aa1")

        assert tree == "tree-oid-1"
        assert run.call_count == 1
        assert run.call_args.args[0] == ["git", "merge-tree", "--write-tree", "cc3", "aa1"]

        run = mock.Mock(return_value=_git_answer(returncode=1))

        with mock.patch("goga.topics.git.exchange.subprocess.run", run):
            assert merge_tree("cc3", "aa1") is None

        assert run.call_count == 1

        run = mock.Mock(return_value=_git_answer("tree-oid-1\n"))

        with mock.patch("goga.topics.git.exchange.subprocess.run", run):
            merge_tree("cc3", "aa1", "bb2")

        assert run.call_count == 1
        assert "--merge-base=bb2" in run.call_args.args[0]

    def test_merge_tree_infrastructure_failure_propagates_raw(self) -> None:
        """An exit status above the conflict signal is the raw infrastructure failure."""
        run = mock.Mock(return_value=_git_answer(returncode=128))

        with (
            mock.patch("goga.topics.git.exchange.subprocess.run", run),
            pytest.raises(subprocess.CalledProcessError),
        ):
            merge_tree("cc3", "aa1")

        assert run.call_args.kwargs["check"] is False


class TestCreateCommitFromTree:
    def test_create_commit_from_tree_argv_order(self) -> None:
        """Tree first, one ``-p`` per parent in order, the message last."""
        run = mock.Mock(return_value=_git_answer("ee5\n"))

        with mock.patch("goga.topics.git.exchange.subprocess.run", run):
            commit = create_commit_from_tree("tree-oid-1", ["cc3", "aa1"], "Update topic 'feat-x'")

        assert commit == "ee5"
        assert run.call_args.args[0] == [
            "git",
            "commit-tree",
            "tree-oid-1",
            "-p",
            "cc3",
            "-p",
            "aa1",
            "-m",
            "Update topic 'feat-x'",
        ]
        # ``commit-tree -m`` reads the operand from stdin otherwise and hangs.
        assert run.call_args.kwargs["stdin"] is subprocess.DEVNULL


class TestReplayCommits:
    def test_replay_commits_preserves_author_and_message(self) -> None:
        """The replayed commit carries the original author and message verbatim."""
        run = _replay_run(rev_list="c1 c0\n", shows=[_AUTHOR_LINE], trees=["t1"], commits=["f1"])

        with mock.patch("goga.topics.git.exchange.subprocess.run", run):
            tip = replay_commits("aa1", "cc3")

        assert tip == "f1"

        rev_list_argv = _calls_of(run, "rev-list")[0].args[0]

        assert rev_list_argv[-2:] == ["cc3", "^aa1"]
        assert "--reverse" in rev_list_argv
        assert "--no-merges" in rev_list_argv

        build = _calls_of(run, "commit-tree")[0]

        assert build.args[0] == ["git", "commit-tree", "t1", "-p", "aa1", "-m", "Do the thing"]

        env = build.kwargs["env"]

        assert env["GIT_AUTHOR_NAME"] == "Ann"
        assert env["GIT_AUTHOR_EMAIL"] == "ann@x.io"
        assert env["GIT_AUTHOR_DATE"] == "2026-01-02T03:04:05+00:00"

    def test_replay_commits_two_commit_chain_chains_running_result(self) -> None:
        """Each step merges onto the running result with its own first parent."""
        run = _replay_run(
            rev_list="c1 c0\nc2 c1\n",
            shows=[_AUTHOR_LINE, _AUTHOR_LINE],
            trees=["t1", "t2"],
            commits=["f1", "f2"],
        )

        with mock.patch("goga.topics.git.exchange.subprocess.run", run):
            tip = replay_commits("aa1", "cc3")

        assert tip == "f2"

        merge_tree_calls = _calls_of(run, "merge-tree")

        assert merge_tree_calls[0].args[0] == ["git", "merge-tree", "--write-tree", "--merge-base=c0", "aa1", "c1"]
        assert merge_tree_calls[1].args[0] == ["git", "merge-tree", "--write-tree", "--merge-base=c1", "f1", "c2"]

        build_calls = _calls_of(run, "commit-tree")

        assert build_calls[1].args[0][:4] == ["git", "commit-tree", "t2", "-p"]
        assert build_calls[1].args[0][4] == "f1"

    def test_replay_commits_conflict_returns_none(self) -> None:
        """A conflicting step reads as the None signal — nothing committed."""
        run = _replay_run(
            rev_list="c1 c0\n",
            shows=[_AUTHOR_LINE],
            trees=["t1"],
            commits=["f1"],
            merge_returncode=1,
        )

        with mock.patch("goga.topics.git.exchange.subprocess.run", run):
            tip = replay_commits("aa1", "cc3")

        assert tip is None
        assert _calls_of(run, "commit-tree") == []

    def test_replay_commits_enumerates_without_merge_commits(self) -> None:
        """The enumeration drops merge commits — the flattening of the real ``git rebase``.

        ``git rebase`` replays the non-merge commits of the range alone;
        a merge commit replayed as a step would re-apply the base delta
        its own side already carried and refuse rebases the real command
        completes — the pre-flight must answer the real command's
        question.
        """
        run = _replay_run(rev_list="c1 c0\n", shows=[_AUTHOR_LINE], trees=["t1"], commits=["f1"])

        with mock.patch("goga.topics.git.exchange.subprocess.run", run):
            replay_commits("aa1", "cc3")

        rev_list_argv = _calls_of(run, "rev-list")[0].args[0]

        assert "--no-merges" in rev_list_argv

    def test_replay_commits_empty_range_returns_onto(self) -> None:
        """A fully-carried line reads as ``onto`` itself — not as a conflict."""
        run = _replay_run(rev_list="", shows=[], trees=[], commits=[])

        with mock.patch("goga.topics.git.exchange.subprocess.run", run):
            tip = replay_commits("aa1", "aa1")

        assert tip == "aa1"
        assert _calls_of(run, "commit-tree") == []

    def test_replay_commits_skips_blank_listing_lines(self) -> None:
        """A trailing blank line of the listing is skipped, never split as a commit."""
        run = _replay_run(rev_list="c1 c0\n\n", shows=[_AUTHOR_LINE], trees=["t1"], commits=["f1"])

        with mock.patch("goga.topics.git.exchange.subprocess.run", run):
            tip = replay_commits("aa1", "cc3")

        assert tip == "f1"
        assert len(_calls_of(run, "show")) == 1

    def test_replay_commits_root_commit_merges_without_explicit_base(self) -> None:
        """A parentless commit of the range merges with no explicit base — never an unpack crash."""
        run = _replay_run(rev_list="c1\n", shows=[_AUTHOR_LINE], trees=["t1"], commits=["f1"])

        with mock.patch("goga.topics.git.exchange.subprocess.run", run):
            tip = replay_commits("aa1", "cc3")

        assert tip == "f1"
        assert _calls_of(run, "merge-tree")[0].args[0] == ["git", "merge-tree", "--write-tree", "aa1", "c1"]

    def test_replay_commits_preserves_trailing_blank_lines_of_the_message(self) -> None:
        """Only git's one terminator newline is stripped — message-borne newlines replay verbatim.

        The identity format ends in ``%B`` and git appends exactly one
        terminator newline after it; every further trailing newline is
        message content the replay must carry unchanged.
        """
        show = f"Ann{_IDENT_SEP}ann@x.io{_IDENT_SEP}2026-01-02T03:04:05+00:00{_IDENT_SEP}Do the thing\n\n\n"
        run = _replay_run(rev_list="c1 c0\n", shows=[show], trees=["t1"], commits=["f1"])

        with mock.patch("goga.topics.git.exchange.subprocess.run", run):
            tip = replay_commits("aa1", "cc3")

        assert tip == "f1"
        assert _calls_of(run, "commit-tree")[0].args[0] == [
            "git",
            "commit-tree",
            "t1",
            "-p",
            "aa1",
            "-m",
            "Do the thing\n\n",
        ]


class TestPointBranchAtCommit:
    def test_point_branch_at_commit_single_ref_update(self) -> None:
        """The plant is exactly one ref update pinning ``refs/heads``."""
        run = mock.Mock(return_value=_git_answer())

        with mock.patch("goga.topics.git.exchange.subprocess.run", run):
            result = point_branch_at_commit("main", "ee5")

        assert result is None
        assert run.call_count == 1
        assert run.call_args.args[0] == ["git", "update-ref", "refs/heads/main", "ee5"]
