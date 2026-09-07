"""Contract and logic tests for the entities declared in
``goga/topics/git/CODEMANIFEST`` with ``location: publish.py``:

- ``resolve_ref_commit(ref)`` — resolve a revision string into the commit
  it names
- ``commit_file_on_base(base, path, content, message)`` — build one commit
  that adds a single file on top of a parent commit, without touching the
  working copy
- ``create_branch_at_commit(branch_name, commit)`` — create a branch at a
  commit without switching to it
- ``delete_local_branch(branch_name)`` — delete a local branch
- ``delete_remote_branch(branch_name)`` — delete a branch on the origin
  remote
- ``push_branch(branch_name)`` — publish the branch to origin with upstream
  binding
- ``origin_configured()`` — the strict origin probe

The subprocess call is mocked at the import point per the ``convention``
practice — no git binary and no repository are touched; the quarantined
index is the one real filesystem object (``tempfile.mkstemp`` inside the
``.git`` directory the test provides).
"""

from __future__ import annotations

import inspect
import subprocess
import typing
from pathlib import Path
from unittest import mock

import pytest
from goga.topics.git import (
    commit_file_on_base,
    create_branch_at_commit,
    delete_local_branch,
    delete_remote_branch,
    origin_configured,
    push_branch,
    resolve_ref_commit,
)

_TODO_PATH = ".goga/history/2026/feature-foo/todo.md"
_TODO_CONTENT = "Payment retry\n"
_TODO_MESSAGE = "goga: create topic feature-foo"


def _git_answer(stdout: str = "") -> subprocess.CompletedProcess[str]:
    """A successful git invocation answering ``stdout``."""
    return subprocess.CompletedProcess(args=["git"], returncode=0, stdout=stdout, stderr="")


def _commands_of(run: mock.Mock) -> list[list[str]]:
    """The argv list of every invocation the mock received."""
    return [call.args[0] for call in run.call_args_list]


# --- Contract tests ---


class TestPublishContract:
    def test_entities_are_importable_from_the_cell_facade(self) -> None:
        """All six publish routines live on the cell facade."""
        import goga.topics.git as cell

        assert cell.resolve_ref_commit is resolve_ref_commit
        assert cell.commit_file_on_base is commit_file_on_base
        assert cell.create_branch_at_commit is create_branch_at_commit
        assert cell.delete_local_branch is delete_local_branch
        assert cell.delete_remote_branch is delete_remote_branch
        assert cell.push_branch is push_branch
        assert cell.origin_configured is origin_configured
        for name in (
            "resolve_ref_commit",
            "commit_file_on_base",
            "create_branch_at_commit",
            "delete_local_branch",
            "delete_remote_branch",
            "push_branch",
            "origin_configured",
        ):
            assert name in cell.__all__

    def test_declared_signatures(self) -> None:
        """The routines take exactly the declared parameters."""
        assert list(inspect.signature(resolve_ref_commit).parameters) == ["ref"]
        assert list(inspect.signature(commit_file_on_base).parameters) == ["base", "path", "content", "message"]
        assert list(inspect.signature(create_branch_at_commit).parameters) == ["branch_name", "commit"]
        assert list(inspect.signature(delete_local_branch).parameters) == ["branch_name"]
        assert list(inspect.signature(delete_remote_branch).parameters) == ["branch_name"]
        assert list(inspect.signature(push_branch).parameters) == ["branch_name"]
        assert list(inspect.signature(origin_configured).parameters) == []

    def test_parameters_are_positional_or_keyword_with_contract_hints(self) -> None:
        """No extras, no defaults, and the declared type hints."""
        hints = {
            resolve_ref_commit: {"ref": str, "return": str},
            commit_file_on_base: {"base": str, "path": str, "content": str, "message": str, "return": str},
            create_branch_at_commit: {"branch_name": str, "commit": str, "return": type(None)},
            delete_local_branch: {"branch_name": str, "return": type(None)},
            delete_remote_branch: {"branch_name": str, "return": type(None)},
            push_branch: {"branch_name": str, "return": type(None)},
            origin_configured: {"return": bool},
        }

        for routine, declared in hints.items():
            parameters = inspect.signature(routine).parameters
            assert all(
                parameter.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD for parameter in parameters.values()
            ), routine
            assert all(parameter.default is inspect.Parameter.empty for parameter in parameters.values()), routine
            assert typing.get_type_hints(routine) == declared, routine

    def test_delete_remote_branch_callable_with_name(self) -> None:
        """The routine binds as ``delete_remote_branch("name")`` and returns None."""
        run = mock.Mock(return_value=_git_answer())

        with mock.patch("goga.topics.git.publish.subprocess.run", run):
            result = delete_remote_branch("name")

        assert result is None


# --- Logic tests ---


class TestResolveRefCommit:
    def test_resolve_ref_commit_returns_peeled_commit(self) -> None:
        """``^{commit}`` peels annotated tags — the hash is a commit hash."""
        run = mock.Mock(return_value=_git_answer("1a2b3c4d5e6f7890\n"))

        with mock.patch("goga.topics.git.publish.subprocess.run", run):
            commit = resolve_ref_commit("origin/main")

        assert commit == "1a2b3c4d5e6f7890"
        assert run.call_args.args[0] == ["git", "rev-parse", "--verify", "origin/main^{commit}"]

    def test_resolve_ref_commit_propagates_git_failure(self) -> None:
        """An unresolvable revision raises raw — the cell never wraps."""
        failure = subprocess.CalledProcessError(128, ["git", "rev-parse"], stderr="fatal: Needed a single revision")

        with (
            mock.patch("goga.topics.git.publish.subprocess.run", side_effect=failure),
            pytest.raises(subprocess.CalledProcessError),
        ):
            resolve_ref_commit("origin/absent")


class TestCommitFileOnBase:
    def test_commit_file_on_base_builds_commit_through_quarantined_index(self, tmp_path: Path) -> None:
        """The six-step chain — one quarantined index, nothing left behind."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        def answer_by_argv(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
            stdout = {
                ("rev-parse", "--git-dir"): str(git_dir),
                ("hash-object", "-w", "--stdin"): "<blob>",
                ("write-tree",): "<tree>",
                ("commit-tree", "<tree>", "-p", "<base>", "-m", _TODO_MESSAGE): "<commit>",
            }.get(tuple(command[1:]), "")
            return subprocess.CompletedProcess(args=command, returncode=0, stdout=stdout, stderr="")

        run = mock.Mock(side_effect=answer_by_argv)

        with mock.patch("goga.topics.git.publish.subprocess.run", run):
            commit = commit_file_on_base("<base>", _TODO_PATH, _TODO_CONTENT, _TODO_MESSAGE)

        assert commit == "<commit>"
        assert _commands_of(run) == [
            ["git", "rev-parse", "--git-dir"],
            ["git", "read-tree", "<base>"],
            ["git", "hash-object", "-w", "--stdin"],
            ["git", "update-index", "--add", "--cacheinfo", f"100644,<blob>,{_TODO_PATH}"],
            ["git", "write-tree"],
            ["git", "commit-tree", "<tree>", "-p", "<base>", "-m", _TODO_MESSAGE],
        ]

        quarantined = {"read-tree", "update-index", "write-tree"}

        for call in run.call_args_list:
            env = call.kwargs["env"]
            assert env["GIT_TERMINAL_PROMPT"] == "0"
            if call.args[0][1] in quarantined:
                assert "GIT_INDEX_FILE" in env
            else:
                assert "GIT_INDEX_FILE" not in env
            assert call.kwargs["encoding"] == "utf-8"

        index = Path(run.call_args_list[1].kwargs["env"]["GIT_INDEX_FILE"])
        assert index.parent == git_dir
        assert index.name.startswith("goga-publish-index-")
        assert not index.exists()

        assert run.call_args_list[2].kwargs["input"] == _TODO_CONTENT

    def test_commit_file_on_base_removes_temporary_index_on_failure(self, tmp_path: Path) -> None:
        """A failed chain still leaves no index behind — the ``finally`` unlink."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        def answer_by_argv(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
            argv = tuple(command[1:])
            if argv == ("write-tree",):
                raise subprocess.CalledProcessError(128, command, stderr="fatal: unable to write tree")
            stdout = str(git_dir) if argv == ("rev-parse", "--git-dir") else ""
            return subprocess.CompletedProcess(args=command, returncode=0, stdout=stdout, stderr="")

        run = mock.Mock(side_effect=answer_by_argv)

        with (
            mock.patch("goga.topics.git.publish.subprocess.run", run),
            pytest.raises(subprocess.CalledProcessError),
        ):
            commit_file_on_base("<base>", _TODO_PATH, _TODO_CONTENT, _TODO_MESSAGE)

        index = Path(run.call_args_list[1].kwargs["env"]["GIT_INDEX_FILE"])
        assert index.parent == git_dir
        assert not index.exists()

    def test_commit_file_on_base_empty_message_never_waits_for_stdin(self, tmp_path: Path) -> None:
        """An empty template completes instead of waiting on the caller's stdin.

        ``commit-tree -m ""`` counts the empty ``-m`` as "no message
        supplied" and falls back to reading the message from stdin. Without
        the devnull redirect the invocation inherited the caller's stdin —
        a terminal or an open pipe under a harness, neither of which ever
        reaches EOF — and the publish cycle hung forever with no output and
        no error. The invocations that legitimately need stdin pass
        ``input`` explicitly and keep their pipe.
        """
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        def answer_by_argv(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
            stdout = {
                ("rev-parse", "--git-dir"): str(git_dir),
                ("hash-object", "-w", "--stdin"): "<blob>",
                ("write-tree",): "<tree>",
                ("commit-tree", "<tree>", "-p", "<base>", "-m", ""): "<commit>",
            }.get(tuple(command[1:]), "")
            return subprocess.CompletedProcess(args=command, returncode=0, stdout=stdout, stderr="")

        run = mock.Mock(side_effect=answer_by_argv)

        with mock.patch("goga.topics.git.publish.subprocess.run", run):
            commit = commit_file_on_base("<base>", _TODO_PATH, _TODO_CONTENT, "")

        assert commit == "<commit>"
        for call in run.call_args_list:
            if call.kwargs.get("input") is None:
                assert call.kwargs["stdin"] == subprocess.DEVNULL
            else:
                # The explicit ``input`` routes the invocation through a
                # pipe — a second stdin would make ``subprocess.run`` raise.
                assert call.kwargs["stdin"] is None
        # The empty message reached git verbatim — no error, no substitution.
        assert run.call_args_list[-1].args[0][-1] == ""


class TestBranchAndPushMutations:
    def test_create_branch_at_commit_creates_ref_without_switch(self) -> None:
        """The plant pins ``refs/heads`` and leaves the working copy alone."""
        run = mock.Mock(return_value=_git_answer())

        with mock.patch("goga.topics.git.publish.subprocess.run", run):
            result = create_branch_at_commit("Feature/Foo_Bar", "<commit>")

        assert result is None
        assert run.call_count == 1
        assert run.call_args.args[0] == ["git", "update-ref", "--stdin", "-z"]
        assert run.call_args.kwargs["input"] == "create refs/heads/Feature/Foo_Bar\0<commit>\0"
        assert run.call_args.kwargs["env"]["GIT_TERMINAL_PROMPT"] == "0"

    def test_create_branch_at_commit_stream_cannot_move_an_existing_ref(self) -> None:
        """The plant is create-only — a plain ``update-ref <ref> <commit>``
        would move an existing ref, and the occupancy oracle can miss one
        (git lengthens the display name of ``refs/heads/v1`` to ``heads/v1``
        when a tag of the same name exists; a concurrent writer can plant the
        name in between). The moved branch would then be deleted by the
        caller's rollback — real work lost behind a push error. The ``create``
        stream refuses an existing ref before anything is mutated.
        """
        run = mock.Mock(return_value=_git_answer())

        with mock.patch("goga.topics.git.publish.subprocess.run", run):
            create_branch_at_commit("--mirror", "<commit>")

        stream = run.call_args.kwargs["input"]
        assert stream == "create refs/heads/--mirror\0<commit>\0"
        # A dash-leading name stays a ref in the stream — never an option.
        assert not stream.split("\0")[0].split(" ", 1)[1].startswith("-")

    def test_create_branch_at_commit_stream_cannot_split_a_second_command(self) -> None:
        """A newline inside the name stays one refname — never a second command.

        The line-oriented stream splits on ``LF``, so a machine-generated
        name carrying a newline would open a second command of the same
        transaction — ``create refs/heads/x <oid>`` followed by ``update
        refs/heads/main <oid>`` silently moves the user's branch. The NUL
        delimiters keep the verbatim name one token, so git's own refname
        validation owns it instead of the stream parser.
        """
        run = mock.Mock(return_value=_git_answer())

        with mock.patch("goga.topics.git.publish.subprocess.run", run):
            create_branch_at_commit("evil <oid>\nupdate refs/heads/main", "<commit>")

        stream = run.call_args.kwargs["input"]
        # The whole name sits inside the single NUL-delimited refname slot.
        tokens = stream.split("\0")
        assert tokens[0] == "create refs/heads/evil <oid>\nupdate refs/heads/main"
        assert tokens[1] == "<commit>"
        # No LF ever terminates a command — only the two NULs delimit fields.
        assert stream.count("\n") == 1

    def test_delete_local_branch_deletes_ref(self) -> None:
        """The rollback addresses the same ``refs/heads`` ref the plant created."""
        run = mock.Mock(return_value=_git_answer())

        with mock.patch("goga.topics.git.publish.subprocess.run", run):
            delete_local_branch("Feature/Foo_Bar")

        assert run.call_args.args[0] == ["git", "update-ref", "-d", "refs/heads/Feature/Foo_Bar"]

    def test_push_branch_pushes_with_upstream_binding(self) -> None:
        """Exactly the named branch, ``-u`` present, origin hardcoded."""
        run = mock.Mock(return_value=_git_answer())

        with mock.patch("goga.topics.git.publish.subprocess.run", run):
            push_branch("Feature/Foo_Bar")

        assert run.call_count == 1
        assert run.call_args.args[0] == [
            "git",
            "push",
            "--no-follow-tags",
            "-u",
            "origin",
            "refs/heads/Feature/Foo_Bar:refs/heads/Feature/Foo_Bar",
        ]

    def test_push_branch_does_not_follow_tags(self) -> None:
        """``--no-follow-tags`` holds the no-tags line under user config.

        The refspec alone names exactly one branch, but git's
        ``push.followTags`` config pushes local-only annotated tags sitting
        on the pushed commits alongside the refspec — the contract forbids
        publishing anything but the named branch, so the explicit negation
        overrides the user's config.
        """
        run = mock.Mock(return_value=_git_answer())

        with mock.patch("goga.topics.git.publish.subprocess.run", run):
            push_branch("Feature/Foo_Bar")

        assert "--no-follow-tags" in run.call_args.args[0]

    def test_push_branch_refspec_cannot_be_parsed_as_an_option(self) -> None:
        """A dash-leading branch name stays a refspec — never a push option.

        Git accepts ``refs/heads/--mirror`` and the plant creates names
        verbatim, so a bare-name argv would hand git ``push -u origin
        --mirror``: git would then sync and prune every remote ref while
        reporting success. The ``refs/heads/...:refs/heads/...`` form starts
        with ``r`` and can only ever name exactly the one branch.
        """
        run = mock.Mock(return_value=_git_answer())

        with mock.patch("goga.topics.git.publish.subprocess.run", run):
            push_branch("--mirror")

        refspec = run.call_args.args[0][-1]
        assert refspec == "refs/heads/--mirror:refs/heads/--mirror"
        assert not refspec.startswith("-")


class TestDeleteRemoteBranch:
    def test_delete_remote_branch_pushes_full_refspec(self) -> None:
        """One deletion push addressing the branch through its full ref.

        A short name that starts with a dash would be parsed as a push
        option — after ``--delete`` a bare ``--mirror`` does not name a
        branch anymore. The ``refs/heads/...`` refspec can never start
        with a dash, so exactly the named branch goes.
        """
        run = mock.Mock(return_value=_git_answer())

        with mock.patch("goga.topics.git.publish.subprocess.run", run):
            delete_remote_branch("feature-foo")

        assert run.call_count == 1
        assert run.call_args.args[0] == [
            "git",
            "push",
            "origin",
            "--delete",
            "refs/heads/feature-foo",
        ]

    def test_delete_remote_branch_refspec_cannot_be_parsed_as_an_option(self) -> None:
        """A dash-leading branch name stays a refspec — never a push option.

        Git accepts ``refs/heads/--mirror`` and the plant creates names
        verbatim, so a bare-name argv would hand git ``push origin
        --delete --mirror``: after ``--delete`` the bare ``--mirror`` no
        longer names a branch, and ``--repo`` or ``--all`` would act at
        all. The ``refs/heads/...`` refspec can never start with a dash.
        """
        run = mock.Mock(return_value=_git_answer())

        with mock.patch("goga.topics.git.publish.subprocess.run", run):
            delete_remote_branch("--mirror")

        refspec = run.call_args.args[0][-1]
        assert refspec == "refs/heads/--mirror"
        assert not refspec.startswith("-")

    def test_delete_remote_branch_git_failure_propagates_raw(self) -> None:
        """A rejected deletion push raises raw — the cell never wraps.

        The caller (``delete_topics``) owns the failure policy: it restores
        the local branch at the captured commit and renders one clean
        error, so a wrap here would bury the git reason under a second
        exception layer.
        """
        failure = subprocess.CalledProcessError(1, ["git", "push", "origin"], stderr=b"deny")

        with (
            mock.patch("goga.topics.git.publish.subprocess.run", side_effect=failure),
            pytest.raises(subprocess.CalledProcessError) as raised,
        ):
            delete_remote_branch("feature-foo")

        assert raised.value is failure


class TestOriginConfigured:
    def test_origin_configured_true_when_configured(self) -> None:
        """A readable origin remote URL reads True."""
        run = mock.Mock(return_value=_git_answer("git@github.com:o/r.git\n"))

        with mock.patch("goga.topics.git.publish.subprocess.run", run):
            configured = origin_configured()

        assert configured is True
        assert run.call_args.args[0] == ["git", "remote", "get-url", "origin"]

    @pytest.mark.parametrize(
        "failure",
        [
            subprocess.CalledProcessError(2, ["git", "remote", "get-url", "origin"]),
            FileNotFoundError("git"),
        ],
        ids=["no-origin-remote", "no-git-binary"],
    )
    def test_origin_configured_false_without_origin(self, failure: Exception) -> None:
        """The probe never raises — both failure shapes read False."""
        with mock.patch("goga.topics.git.publish.subprocess.run", side_effect=failure):
            assert origin_configured() is False
