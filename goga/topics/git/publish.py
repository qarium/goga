"""The quarantined publication of the topics-domain git cell.

The entities declared in the cell CODEMANIFEST with
``location: publish.py``: revision resolution, the commit-message read of
one commit, the quarantined building of one commit that adds a single
file on top of a parent commit, planting a branch at a commit without
switching, deleting a local branch, deleting a
branch on the origin remote, pushing a branch to origin with upstream
binding, the exchange network set — the targeted single-branch fetch, the
lease-protected push of a rewritten branch, the write-through push of a
built revision onto a remote branch — and the strict origin probe. The
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


def resolve_commit_message(commit: str) -> str:
    """Read the commit message of one commit — the git fact of the publication context.

    Args:
        commit: The commit hash.

    Returns:
        The commit's message text as git stores it, verbatim — the
        stored bytes, no strip, no reformat.

    Algorithm:
        1. Ask git for the commit message of ``commit``, verbatim as
           git stores it
        2. An unresolvable commit surfaces as a clean error carrying
           the git reason

    Requirements:
        Read-only — no ref, index, or working-copy mutation.

        An unresolvable commit is a clean error carrying the git
        reason.

    Constraints:
        Do not print — the caller owns all output.

    Raises:
        subprocess.CalledProcessError: a git infrastructure failure of
            the read itself (propagated raw — the caller wraps it).
        OSError: unexpected OS-level failures of the git invocation (e.g. a
            missing git binary).
    """
    # The ``format:`` form is load-bearing: the bare ``%B`` appends one
    # terminator newline beyond the stored message, so the returned text
    # would differ byte-for-byte from what the author committed. The
    # ``format:`` form adds none — ``stdout`` is the message itself, and it
    # is returned as-is.
    result = _run_git(["git", "log", "-1", "--pretty=format:%B", commit])
    return result.stdout


def commit_file_on_base(base: str, path: str, content: str, message: str) -> str:
    """Build one commit that adds a single file on top of a parent commit — without touching the working copy.

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
    #
    # The ``-z`` framing is load-bearing the same way: the line-oriented
    # stream splits on ``LF``, so a newline inside a machine-generated name
    # would open a *second* command of the same transaction — ``create
    # refs/heads/x <oid>`` followed by ``update refs/heads/main <oid>`` moves
    # the user's branch behind a garbled error. Under NUL delimiters the name
    # stays one token, so the verbatim name reaches git's own refname
    # validation — the contract that git owns name validity — and a control
    # character dies as ``invalid ref format`` before anything is mutated.
    _run_git(
        ["git", "update-ref", "--stdin", "-z"],
        input=f"create refs/heads/{branch_name}\0{commit}\0",
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


def delete_remote_branch(branch_name: str) -> None:
    """Delete a branch on the origin remote.

    Args:
        branch_name: The short name of the branch on origin.

    Algorithm:
        1. Ask git to delete the branch on the origin remote
        2. A git failure surfaces as a clean error carrying the reason

    Requirements:
        Exactly the named branch — no other branches or tags.

        The deletion is a network operation — the local branch and the
        working copy stay untouched.

    Constraints:
        Do not retry or roll back — the caller owns the failure policy.

    Raises:
        subprocess.CalledProcessError: a git infrastructure failure of the
            deletion push itself (propagated raw — the caller wraps it).
        OSError: unexpected OS-level failures of the git invocation (e.g. a
            missing git binary).
    """
    # The full refspec is load-bearing exactly as in ``push_branch``: a
    # short name that starts with a dash (git accepts
    # ``refs/heads/--mirror``, and the plant creates names verbatim) would
    # be parsed as a push option — after ``--delete`` a bare ``--mirror``
    # does not name a branch anymore, and ``--repo`` or ``--all`` would act
    # at all. The refspec can never start with a dash, so exactly the named
    # branch goes.
    _run_git(["git", "push", "origin", "--delete", f"refs/heads/{branch_name}"])


def push_branch(branch_name: str) -> None:
    """Publish a branch to the origin remote with upstream binding.

    Args:
        branch_name: The short name of the local branch.

    Algorithm:
        1. Ask git to push the branch to origin and bind its upstream
        2. A git failure propagates with its message — the caller owns the
           rollback

    Requirements:
        The push is a network operation of the topics domain.

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
    _run_git(
        [
            "git",
            "push",
            "--no-follow-tags",
            "-u",
            "origin",
            f"refs/heads/{branch_name}:refs/heads/{branch_name}",
        ]
    )


def fetch_branch(branch_name: str) -> bool:
    """Fetch exactly one branch of the origin remote into its remote-tracking ref.

    Args:
        branch_name: The short name of the branch on origin.

    Returns:
        True when the fetch refreshed the remote-tracking ref — the
        branch exists on origin and the ref now carries its tip; False
        when git reports the remote branch absent — origin carries no
        twin, whatever a stale remote-tracking ref from an earlier
        fetch still claims.

    Algorithm:
        1. Ask git to fetch the single branch through an explicit forced
           refspec
        2. A fetch naming an absent remote branch returns False — the
           twin is absent on the remote; the remote-tracking ref is left
           as it stands, so the caller must not read it as the twin
        3. Any other failure propagates with its message

    Requirements:
        Exactly one remote-tracking ref is updated — no other branch, no
        tags, no opportunistic remote-prune.

        The working copy, the repository index, and HEAD stay untouched —
        a fetch moves no local branch.

        An absent remote branch deletes nothing — the remote-tracking ref
        is left untouched and the absence is reported as the return, so
        the caller decides what a stale ref means.

        Silent — no printing: the reporting line of a fetch belongs to the
        calling module, not the cell.

    Constraints:
        Do not read the fetch as the twin's absence on any other wording —
        only git's ``couldn't find remote ref`` counts (the one wording pair
        across the supported floor of git 2.40, held stable under a
        localized environment by the invocation's ``LC_ALL=C``); a network
        outage stays a failure.

    Raises:
        subprocess.CalledProcessError: a git infrastructure failure of the
            fetch itself, the absent-branch wording excepted (propagated
            raw — the caller wraps it).
        OSError: unexpected OS-level failures of the git invocation (e.g. a
            missing git binary).
    """
    # The leading ``+`` is load-bearing: without it git refuses a
    # non-fast-forward update of the remote-tracking ref, so a twin left
    # behind the local branch (a base that moved ahead on the remote would
    # be the reverse case) would keep the stale value and the exchange
    # would reconcile against a projection it never refreshed. The fetch
    # exists to see where the twin *is*, including behind, so the forced
    # refspec answers that question — and when git answers that the branch
    # is gone, the stale ref a past fetch left behind must never speak for
    # the remote again; the False return hands that fact to the caller.
    try:
        _run_git(["git", "fetch", "origin", f"+refs/heads/{branch_name}:refs/remotes/origin/{branch_name}"])
    except subprocess.CalledProcessError as failure:
        # ``_run_git`` decodes with ``text=True``, so the stderr is
        # text (or None) — never bytes.
        stderr = failure.stderr or ""
        if "couldn't find remote ref" in stderr:
            return False
        raise
    return True


def push_branch_with_lease(branch_name: str, expected_tip: str) -> None:
    """Push a branch whose history was rewritten, protected by a lease on the last-seen tip.

    Args:
        branch_name: The short name of the local branch.
        expected_tip: The commit the branch pointed at before the rewrite —
            the value the caller last saw on the remote.

    Algorithm:
        1. Ask git to push the branch with a lease naming ``expected_tip``
           as the remote's current value
        2. A remote standing anywhere else refuses — the failure propagates
           raw with git's reason

    Requirements:
        The push is a network operation of the topics domain.

        Exactly the named branch — no other branches or tags.

    Constraints:
        Do not refresh the lease with a fetch first — the lease is the
        protection: it names the tip the caller captured before the
        rewrite, so any concurrent remote movement must refuse.

        Do not retry — the caller owns the failure policy.

    Raises:
        subprocess.CalledProcessError: a git infrastructure failure of the
            push itself, a lease rejection included (propagated raw — the
            caller wraps it).
        OSError: unexpected OS-level failures of the git invocation (e.g. a
            missing git binary).
    """
    # The full-ref lease form is load-bearing: the short ``--force-with-lease``
    # protects against the remote-tracking ref's *current* value, which nobody
    # verified — only the explicit ``<ref>:<tip>`` form binds the protection to
    # the caller's captured tip. The full refspec can never start with a dash,
    # exactly as in ``push_branch``, so exactly the named branch goes.
    _run_git(
        [
            "git",
            "push",
            "--no-follow-tags",
            f"--force-with-lease=refs/heads/{branch_name}:{expected_tip}",
            "origin",
            f"refs/heads/{branch_name}:refs/heads/{branch_name}",
        ]
    )


def push_revision_to_branch(revision: str, branch_name: str) -> None:
    """Push one built revision onto a remote branch without any local branch.

    Args:
        revision: The commit hash of the built delivery.
        branch_name: The short name of the branch on origin.

    Algorithm:
        1. Ask git to push the revision onto the remote branch
        2. A non-fast-forward remote rejects — the failure propagates raw
           with git's reason

    Requirements:
        The push is a network operation of the topics domain.

        No local branch is created — the revision exists only as a hash
        until the remote accepts it.

        Exactly the named branch — no other branches or tags.

    Constraints:
        Do not force and do not bind an upstream — a rejection is a
        concurrent movement the caller owns.

    Raises:
        subprocess.CalledProcessError: a git infrastructure failure of the
            push itself (propagated raw — the caller wraps it).
        OSError: unexpected OS-level failures of the git invocation (e.g. a
            missing git binary).
    """
    # The ``<revision>:refs/heads/...`` refspec is load-bearing exactly as in
    # ``push_branch``: a bare branch name that starts with a dash (git accepts
    # ``refs/heads/--mirror``, and the plant creates names verbatim) would be
    # parsed as a push option — ``--mirror`` would sync and prune every remote
    # ref while ``--repo`` or ``--all`` would act at all. The refspec starts
    # with the revision, so exactly the named branch goes.
    _run_git(["git", "push", "--no-follow-tags", "origin", f"{revision}:refs/heads/{branch_name}"])


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
    # The output is display data — hashes and git messages — so a byte a
    # remote hook left outside UTF-8 decodes with the replacement character
    # instead of raising from inside ``subprocess.run``: a
    # ``UnicodeDecodeError`` is a ``ValueError``, it matches none of the
    # domain's handlers, so it would pierce the clean-error boundary and
    # skip the caller's rollback — mirroring ``read_ref_file``.
    #
    # The devnull stdin is load-bearing: without it every invocation
    # inherits the caller's stdin, and a git subcommand that falls back to
    # reading its operand from stdin would block on a descriptor that never
    # reaches EOF — a terminal, an open pipe under a harness. ``commit-tree
    # -m ""`` does exactly that (an empty ``-m`` counts as "no message
    # supplied"), so an explicit empty template hung the publish cycle
    # forever. No invocation of this module consumes the caller's stdin:
    # the two that need stdin (``hash-object --stdin``,
    # ``update-ref --stdin``) pass ``input`` explicitly, which routes them
    # through a pipe instead.
    #
    # ``LC_ALL=C`` is load-bearing for the callers that read git's own
    # wording: the absent-remote-ref fetch marker and the
    # concurrent-movement push markers are matched as English text, and a
    # localized git would translate its messages — the fetch would read as
    # a hard failure instead of the absent twin, the rejected push would
    # lose its retry cycle. The C locale keeps the parsed wording stable;
    # the C locale is also the one locale under which gettext ignores
    # ``LANGUAGE`` outright.
    return subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        input=input,
        stdin=subprocess.DEVNULL if input is None else None,
        env={
            **os.environ,
            "GIT_TERMINAL_PROMPT": "0",
            "LC_ALL": "C",
            **({"GIT_INDEX_FILE": str(index)} if index is not None else {}),
        },
    )
