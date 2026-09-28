"""The checkout-free exchange of the topics-domain git cell.

The entities declared in the cell CODEMANIFEST with
``location: exchange.py``: the git version gate of the exchange
machinery, commit containment, the tree resolution of a revision, the
three-way merge written as a tree, the commit built over a ready tree,
the plumbing replay of a commit range with authors and messages
preserved, and the single-ref planting of a branch. The exchange path
never touches the working copy, the repository index, or HEAD — a dirty
tree and a detached HEAD do not interfere; every built object stays
dangling until the caller plants it with one ref update. The cell stays
silent — the reporting line of a fetch belongs to the calling module.
Every git invocation follows the ``git`` practice.
"""

from __future__ import annotations

import os
import re
import subprocess

_VERSION_PATTERN = re.compile(r"version (\d+)\.(\d+)(\.\d+)?")
# The floor is 2.40, not the 2.38 of ``merge-tree --write-tree``: the
# plumbing replay of the rebase path passes ``--merge-base=``, an
# option git only accepts from 2.40 — a 2.38/2.39 git would pass this
# gate and then crash inside every rebase-shaped update.
_VERSION_FLOOR = (2, 40)
_VERSION_FLOOR_TEXT = ".".join(str(part) for part in _VERSION_FLOOR)
_IDENT_SEPARATOR = "\x1f"
_IDENTITY_FORMAT = f"%an{_IDENT_SEPARATOR}%ae{_IDENT_SEPARATOR}%aI{_IDENT_SEPARATOR}%B"


def require_git_version() -> None:
    """Gate the exchange machinery on the git version floor.

    Algorithm:
        1. Ask git for its version
        2. Older than 2.40 -> a clean error naming the required and the
           present versions

    Requirements:
        Read-only and cheap — no repository state is touched.

    Constraints:
        Do not scatter the gate over entry points — the shared base
        resolution of the domain invokes it once for every exchange.

    Raises:
        RuntimeError: a git older than the floor, or a version output
            that does not parse — an unparsable output is an
            infrastructure anomaly treated as the gate failure, never a
            silent pass.
        OSError: unexpected OS-level failures of the git invocation (e.g. a
            missing git binary).
    """
    result = _run_git(["git", "version"])
    first_line = result.stdout.splitlines()[0] if result.stdout else ""

    match = _VERSION_PATTERN.search(first_line)

    if match is None:
        raise RuntimeError(
            f"goga needs git >= {_VERSION_FLOOR_TEXT} for the topic exchange "
            f"(found unparsable version output {first_line.strip()!r})"
        )

    major, minor = int(match.group(1)), int(match.group(2))

    if (major, minor) < _VERSION_FLOOR:
        present = match.group(0).removeprefix("version ")
        raise RuntimeError(
            f"goga needs git >= {_VERSION_FLOOR_TEXT} for the topic exchange (found {present})"
        )


def is_ancestor(ancestor: str, descendant: str) -> bool:
    """Decide commit containment — whether one revision carries another.

    Args:
        ancestor: The revision expected to be reachable.
        descendant: The revision expected to carry it.

    Returns:
        True when ``ancestor`` is reachable from ``descendant``.

    Algorithm:
        1. Ask git whether ``ancestor`` is an ancestor of ``descendant``
        2. Report the answer as a plain boolean

    Requirements:
        Read-only — no network, no mutation.

        Both sides accept any resolvable revision, peeled to its commit.

    Constraints:
        Do not decide what containment means for the caller — the policy
        belongs to the caller.

    Raises:
        subprocess.CalledProcessError: a git infrastructure failure of
            the containment query itself — an exit status above the
            yes/no pair, propagated raw with the git reason (the caller
            wraps it).
        OSError: unexpected OS-level failures of the git invocation (e.g. a
            missing git binary).
    """
    # The invocation never raises on a normal answer: ``merge-base
    # --is-ancestor`` reports containment as its exit status — 0 carries,
    # 1 does not — so ``check=True`` would turn every negative answer
    # into an exception. Only a status above the pair (an unresolvable
    # revision, repository damage) is a failure.
    result = _run_git(["git", "merge-base", "--is-ancestor", ancestor, descendant], check=False)

    if result.returncode == 0:
        return True

    if result.returncode == 1:
        return False

    raise subprocess.CalledProcessError(
        result.returncode,
        result.args,
        output=result.stdout,
        stderr=result.stderr,
    )


def resolve_commit_tree(revision: str) -> str:
    """Resolve a revision into the tree it carries — the content identity of a commit.

    Args:
        revision: Any resolvable revision — a commit hash, a branch, a
            tag, resolved as git resolves it.

    Returns:
        The tree oid the resolved commit carries.

    Algorithm:
        1. Ask git to resolve ``revision`` into its commit and peel to
           the tree it carries
        2. An unresolvable revision surfaces as a clean error carrying
           the git reason

    Requirements:
        Read-only — no ref is created, moved, or deleted; no network.

    Constraints:
        Do not compare trees — the equality policy belongs to the caller.

    Raises:
        subprocess.CalledProcessError: a git infrastructure failure of the
            resolution itself (propagated raw — the caller wraps it).
        OSError: unexpected OS-level failures of the git invocation (e.g. a
            missing git binary).
    """
    result = _run_git(["git", "rev-parse", "--verify", f"{revision}^{{tree}}"])
    return result.stdout.strip()


def merge_tree(ours: str, theirs: str, merge_base: str | None = None) -> str | None:
    """Build the three-way merge of two revisions as a written tree — without the working copy.

    Args:
        ours: One side of the merge.
        theirs: The other side.
        merge_base: The explicit merge base of a cherry-pick step; None —
            git computes the merge base of the pair.

    Returns:
        The written tree of the merge, or None when the merge conflicts.

    Algorithm:
        1. Ask git to write the merged tree of the pair — with the
           explicit base when given
        2. A conflicting merge yields None — a signal, not an error
        3. Return the written tree

    Requirements:
        The working copy, the index, HEAD, and every ref stay untouched —
        only new objects appear, dangling until planted.

        One git invocation per merge.

    Constraints:
        Do not commit — the tree is the caller's input.

        Do not treat a conflict as an error — the caller owns the policy.

    Raises:
        subprocess.CalledProcessError: a git infrastructure failure of
            the merge itself — an exit status above the conflict signal,
            propagated raw (the caller wraps it).
        OSError: unexpected OS-level failures of the git invocation (e.g. a
            missing git binary).
    """
    # The invocation never raises on the conflict signal: ``merge-tree
    # --write-tree`` reports a conflicted merge as exit status 1 with the
    # conflicted-file listing on stdout — that is the None answer, not an
    # exception. Only a status above it (an unresolvable side, repository
    # damage) is a failure.
    command = ["git", "merge-tree", "--write-tree"]

    if merge_base is not None:
        command.append(f"--merge-base={merge_base}")

    command += [ours, theirs]

    result = _run_git(command, check=False)

    if result.returncode == 1:
        return None

    if result.returncode != 0:
        raise subprocess.CalledProcessError(
            result.returncode,
            result.args,
            output=result.stdout,
            stderr=result.stderr,
        )

    # The tree oid is the first stdout line; the conflicted-file listing
    # and the informational messages that may follow never reach the
    # caller's tree identity.
    return result.stdout.splitlines()[0].strip()


def create_commit_from_tree(tree: str, parents: list[str], message: str) -> str:
    """Build one commit over a ready tree with its parents and the final message.

    Args:
        tree: The tree oid the commit carries.
        parents: The parent commits in order — two for a merge or a
            reconciliation, one for a squash.
        message: The final commit message — placeholders belong to the
            caller.

    Returns:
        The hash of the built commit.

    Algorithm:
        1. Ask git to create the commit with ``message`` over ``tree``
           and ``parents``, authored by the repository git identity
        2. Return the new commit hash; every git failure — an unreadable
           tree, an unset identity — surfaces as a clean error

    Requirements:
        The commit stays dangling — no ref is created, moved, or deleted.

        The working copy, the index, and HEAD stay untouched.

    Constraints:
        Do not plant branches — planting belongs to the caller.

    Raises:
        subprocess.CalledProcessError: a git infrastructure failure of the
            build itself (propagated raw — the caller wraps it).
        OSError: unexpected OS-level failures of the git invocation (e.g. a
            missing git binary).
    """
    command = ["git", "commit-tree", tree]

    for parent in parents:
        command += ["-p", parent]

    command += ["-m", message]

    return _run_git(command).stdout.strip()


def replay_commits(onto: str, until: str) -> str | None:
    """Replay the commits of one line onto a new base — the plumbing rebase of a branch.

    Args:
        onto: The new base the commits replay onto.
        until: The tip whose commits replay — the commits reachable from
            it and not from ``onto``, oldest first.

    Returns:
        The final replayed tip, or None when a step conflicts.

    Algorithm:
        1. List the commits reachable from ``until`` but not from
           ``onto``, oldest first
        2. Merge each onto the running result with its parent as the
           explicit merge base, preserving the commit's author and
           message; the committer is the repository identity
        3. A conflicting step yields None
        4. Return the final tip

    Requirements:
        Read-only w.r.t. refs — the result dangles until the caller
        plants it.

        The author and the message of every replayed commit are
        preserved verbatim.

        The pre-flight of an in-place rebase is this same call, discarded.

    Constraints:
        Do not move branches.

        Do not skip, reorder, or squash commits.

    Raises:
        subprocess.CalledProcessError: a git infrastructure failure of the
            chain itself (propagated raw — the caller wraps it).
        OSError: unexpected OS-level failures of the git invocation (e.g. a
            missing git binary).
    """
    listing = _run_git(["git", "rev-list", "--reverse", "--parents", until, f"^{onto}"]).stdout

    running = onto

    for line in listing.splitlines():
        if not line.strip():
            continue

        # A merge commit uses its first parent as the merge base — the
        # replayed step replays the commit's own change, not the merge
        # topology. A parentless commit — an unrelated-history root —
        # names no base; the merge computes the pair's own.
        parts = line.split()
        commit = parts[0]
        first_parent = parts[1] if len(parts) > 1 else None
        name, email, date, message = _read_commit_identity(commit)

        tree = merge_tree(running, commit, merge_base=first_parent)

        if tree is None:
            return None

        running = _run_git(
            ["git", "commit-tree", tree, "-p", running, "-m", message],
            extra_env={
                "GIT_AUTHOR_NAME": name,
                "GIT_AUTHOR_EMAIL": email,
                "GIT_AUTHOR_DATE": date,
            },
        ).stdout.strip()

    return running


def point_branch_at_commit(branch_name: str, commit: str) -> None:
    """Move a branch to a commit through a single ref update — the planting mutation of an exchange.

    Args:
        branch_name: The short name of the existing branch.
        commit: The commit the branch moves to.

    Algorithm:
        1. Ask git to update the branch ref to ``commit``
        2. A git failure surfaces as a clean error

    Requirements:
        Exactly one ref update — the single mutation that plants a built
        exchange result or restores a captured rollback tip.

        The working copy, the index, and HEAD stay untouched.

    Constraints:
        Do not create the branch — creation is
        ``create_branch_at_commit``; the branch must already exist.

        Do not guard the current branch — the caller owns the
        checked-out policy.

    Raises:
        subprocess.CalledProcessError: a git infrastructure failure of the
            ref update itself (propagated raw — the caller wraps it).
        OSError: unexpected OS-level failures of the git invocation (e.g. a
            missing git binary).
    """
    # The full-ref form is load-bearing: a dash-leading short name cannot
    # parse as an option once it sits behind the fully qualified
    # ``refs/heads/`` ref.
    _run_git(["git", "update-ref", f"refs/heads/{branch_name}", commit])


def _read_commit_identity(commit: str) -> tuple[str, str, str, str]:
    """Read the author name, email, date, and message of one commit verbatim.

    Args:
        commit: The commit to read.

    Returns:
        The ``(name, email, date, message)`` quadruple — the unit
        separator delimits the fields, so a message never splits.
    """
    facts = _run_git(["git", "show", "-s", f"--format={_IDENTITY_FORMAT}", commit]).stdout

    name, email, date, message = facts.rstrip("\n").split(_IDENT_SEPARATOR, 3)
    return name, email, date, message


def _run_git(
    command: list[str],
    *,
    input: str | None = None,
    check: bool = True,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run one git invocation following the ``git`` practice.

    Args:
        command: The argv of the invocation, starting with ``git``.
        input: The text to feed the invocation on stdin, if any.
        check: False for the invocations that report their answer as an
            exit status — the caller inspects the code itself.
        extra_env: Environment variables exported to the single
            invocation — the replayed author identity, never persisted.

    Returns:
        The completed invocation with captured text output.
    """
    # The devnull stdin is load-bearing exactly as in ``publish.py``:
    # ``commit-tree -m`` falls back to reading its operand from stdin
    # when the message argument reads as empty, and an inherited stdin
    # that never reaches EOF would hang the build forever. The
    # invocations that legitimately need stdin pass ``input``
    # explicitly, which routes them through a pipe instead.
    return subprocess.run(
        command,
        check=check,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        input=input,
        stdin=subprocess.DEVNULL if input is None else None,
        env={
            **os.environ,
            "GIT_TERMINAL_PROMPT": "0",
            **(extra_env or {}),
        },
    )
