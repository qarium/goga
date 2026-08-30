"""The quarantined publication of the topics-domain git cell.

The entities declared in the cell CODEMANIFEST with
``location: publish.py``: revision resolution, the quarantined building of
one commit that adds a single file on top of a parent commit, planting a
branch at a commit without switching, deleting a local branch, pushing a
branch to origin with upstream binding, and the strict origin probe. The
quarantined path never touches the working copy, the repository index, or
HEAD — a dirty tree and a detached HEAD do not interfere. Every git
invocation follows the ``git`` practice.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path


def resolve_ref_commit(ref: str) -> str:
    """Resolve a revision string into the commit it names.

    Args:
        ref: Any revision string — a branch name, a remote-tracking ref, a
            tag, or a commit hash, resolved as git resolves it.

    Returns:
        The commit hash the revision names — annotated tags peeled to
        their commit, so the hash is usable as ``commit-tree -p`` parent.

    Algorithm:
        1. Ask git to resolve ``ref`` into its commit
        2. An unresolvable revision surfaces as a clean error carrying the
           git reason

    Requirements:
        Read-only — no ref is created, moved, or deleted.

        No network — the revision resolves against the local repository
        state.

    Constraints:
        Do not fetch — a stale remote-tracking base is the caller's
        accepted condition.

    Raises:
        subprocess.CalledProcessError: a git infrastructure failure of the
            resolution itself (propagated raw — the caller wraps it).
        OSError: unexpected OS-level failures of the git invocation (e.g. a
            missing git binary).
    """
    result = _run_git(["git", "rev-parse", "--verify", f"{ref}^{{commit}}"])
    return result.stdout.strip()


def commit_file_on_base(base: str, path: str, content: str, message: str) -> str:
    """Build one commit that adds a single file on top of a parent commit —
    without touching the working copy.

    Args:
        base: The parent commit hash.
        path: The file path to add, relative to the repository root.
        content: The file content as text.
        message: The final commit message.

    Returns:
        The hash of the built commit.

    Algorithm:
        1. Build the tree of the commit in a temporary index quarantined
           from the repository — the parent tree, the new blob of ``path``
           staged over it, and the resulting tree written out
        2. Ask git to create the commit with ``message`` on the parent
           ``base``, authored by the repository git identity
        3. Return the new commit hash; every git failure — an unreadable
           parent, an unset identity — surfaces as a clean error

    Requirements:
        The working copy, the repository index, and HEAD stay untouched.

        The temporary index lives only inside the environment of a single
        git invocation — nothing persists after the build.

        No temporary directories or files are created outside ``.git``.

    Constraints:
        Do not create, move, or delete branches — the commit exists only
        as a hash until the caller plants it.

        Do not write the file to the working copy.

    Raises:
        subprocess.CalledProcessError: a git infrastructure failure of the
            chain itself (propagated raw — the caller wraps it).
        OSError: unexpected OS-level failures of the git invocation (e.g. a
            missing git binary).
    """
    git_dir = _run_git(["git", "rev-parse", "--git-dir"]).stdout.strip()
    fd, name = tempfile.mkstemp(dir=git_dir, prefix="goga-publish-index-")
    os.close(fd)
    index = Path(name)
    try:
        _run_git(["git", "read-tree", base], index=index)
        blob = _run_git(["git", "hash-object", "-w", "--stdin"], input=content).stdout.strip()
        _run_git(["git", "update-index", "--add", "--cacheinfo", f"100644,{blob},{path}"], index=index)
        tree = _run_git(["git", "write-tree"], index=index).stdout.strip()
        return _run_git(["git", "commit-tree", tree, "-p", base, "-m", message]).stdout.strip()
    finally:
        index.unlink(missing_ok=True)


def create_branch_at_commit(branch_name: str, commit: str) -> None:
    """Create a branch at a commit without switching to it.

    Args:
        branch_name: The branch name as entered by the user.
        commit: The commit the branch points to.

    Algorithm:
        1. Ask git to create the branch ``branch_name`` pointing at
           ``commit``, leaving the working copy on its current branch
        2. A git failure surfaces as a clean error

    Requirements:
        The name is taken verbatim — no normalization, no suffixing.

        The mutation is local — no network.

        The working copy, the index, and HEAD stay untouched — no switch
        happens.

    Constraints:
        Do not validate the name characters — git owns name validity.

    Raises:
        subprocess.CalledProcessError: a git infrastructure failure of the
            branch creation itself (propagated raw — the caller wraps it).
        OSError: unexpected OS-level failures of the git invocation (e.g. a
            missing git binary).
    """
    # The create-only form is load-bearing: a plain ``update-ref <ref>
    # <commit>`` moves an existing ref without complaint, and the occupancy
    # oracle can miss one — git lengthens the display name of ``refs/heads/v1``
    # to ``heads/v1`` when a tag of the same name exists, and a concurrent
    # writer can plant the name between the oracle and the plant. The moved
    # branch would then be deleted by the caller's rollback — real work lost
    # behind a push error. ``create`` refuses an existing ref (``reference
    # already exists``), so the failure surfaces as one clean error before
    # anything is mutated; the stdin stream never parses the verbatim name as
    # an option, dash-leading or not.
    _run_git(
        ["git", "update-ref", "--stdin"],
        input=f"create refs/heads/{branch_name} {commit}\n",
    )


def delete_local_branch(branch_name: str) -> None:
    """Delete a local branch.

    Args:
        branch_name: The short name of the local branch.

    Algorithm:
        1. Ask git to delete the local branch ref
        2. A git failure surfaces as a clean error

    Requirements:
        The deletion is local — no network.

        The working copy, the index, and HEAD stay untouched — a branch
        not checked out is deletable without a switch.

    Constraints:
        Do not decide whether deletion is safe — the caller owns the
        rollback policy.

    Raises:
        subprocess.CalledProcessError: a git infrastructure failure of the
            deletion itself (propagated raw — the caller wraps it).
        OSError: unexpected OS-level failures of the git invocation (e.g. a
            missing git binary).
    """
    _run_git(["git", "update-ref", "-d", f"refs/heads/{branch_name}"])


def push_branch(branch_name: str) -> None:
    """Publish a branch to the origin remote with upstream binding.

    Args:
        branch_name: The short name of the local branch.

    Algorithm:
        1. Ask git to push the branch to origin and bind its upstream
        2. A git failure propagates with its message — the caller owns the
           rollback

    Requirements:
        The push is the only network operation of the topics domain.

        The local branch stays in the repository after the push.

    Constraints:
        Do not push other branches or tags — exactly the named branch.

        Do not retry or roll back — the caller owns the failure policy.

    Raises:
        subprocess.CalledProcessError: a git infrastructure failure of the
            push itself (propagated raw — the caller wraps it).
        OSError: unexpected OS-level failures of the git invocation (e.g. a
            missing git binary).
    """
    # The full refspec is load-bearing: a bare name that starts with a dash
    # (git accepts ``refs/heads/--mirror``, and the plant creates it verbatim)
    # would be parsed as a push option — ``--mirror`` would sync and prune
    # every remote ref while ``--delete`` or ``--repo`` would act at all. The
    # refspec can never start with a dash, so exactly the named branch goes.
    # ``--no-follow-tags`` holds that no-tags line even under the user's
    # ``push.followTags`` config — a local-only annotated tag on the base
    # commit would otherwise ride along with the branch.
    _run_git([
        "git",
        "push",
        "--no-follow-tags",
        "-u",
        "origin",
        f"refs/heads/{branch_name}:refs/heads/{branch_name}",
    ])


def origin_configured() -> bool:
    """Probe whether the origin remote is configured.

    Returns:
        True when the repository has an origin remote.

    Algorithm:
        1. Ask git for the origin remote URL
        2. Report the answer as a plain boolean

    Requirements:
        Read-only — no remote state is contacted, no network.

        Strict as a probe result: an absent or unreadable origin reads
        False — the probe never raises.

    Constraints:
        Do not tolerate the absence into a success — the caller turns
        False into its own clean error.
    """
    try:
        _run_git(["git", "remote", "get-url", "origin"])
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False
    return True


def _run_git(
    command: list[str],
    *,
    input: str | None = None,
    index: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run one git invocation following the ``git`` practice.

    Args:
        command: The argv of the invocation, starting with ``git``.
        input: The text to feed the invocation on stdin, if any.
        index: The path of a quarantined index — exported to the single
            invocation through the ``GIT_INDEX_FILE`` env var, never
            written to the repository index.

    Returns:
        The completed invocation with captured text output.
    """
    return subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        input=input,
        env={
            **os.environ,
            "GIT_TERMINAL_PROMPT": "0",
            **({"GIT_INDEX_FILE": str(index)} if index is not None else {}),
        },
    )
