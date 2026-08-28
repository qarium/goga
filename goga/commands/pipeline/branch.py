"""Host-side branch routines for the ``-b/--branch`` procedure of ``goga pipeline``.

The four branch routines declared in the cell CODEMANIFEST with ``location:
branch.py``: the pure slug transformer, the git current-branch reader, the
three-oracle occupancy check, and the orchestrator of the whole branch
procedure. Every git invocation follows the ``git`` practice —
``subprocess.run`` with ``check=True``, captured output, and
``GIT_TERMINAL_PROMPT=0`` in the environment. The oracles are read-only; the
single host-side mutation (create-and-switch) is owned by
``ensure_pipeline_branch``.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import click

_GIT_REQUIRED_MESSAGE = "git is required for -b/--branch: git binary not found"
_REASK_HINT = "Pass another branch name via -b."


def _reask_branch_name(reason: str) -> str:
    """Handle an unusable branch name: re-ask on a terminal, abort otherwise.

    Args:
        reason: Human-readable reason the current name cannot be used.

    Returns:
        The re-asked branch name (the caller restarts the procedure with it).

    Raises:
        click.ClickException: without a terminal — the reason plus the ``-b``
            hint go to the user as a non-terminal abort.
        click.Abort: Ctrl-C or EOF at the prompt.
    """
    if not sys.stdin.isatty():
        raise click.ClickException(f"{reason} {_REASK_HINT}")
    click.echo(reason, err=True)
    return click.prompt("New branch name")


def normalize_topic_slug(name: str) -> str:
    """Normalize a branch name into the history topic slug.

    Deterministic pure string transformation: lowercase the name, drop every
    non-ASCII character (no transliteration), replace each remaining character
    outside ``[a-z0-9]`` with a hyphen, collapse repeat hyphens into one, and
    trim leading and trailing hyphens. Lowercasing happens BEFORE the ASCII
    filter, so a name like ``"aБb"`` yields ``"ab"`` and the Turkish dotted
    capital ``"İ"`` lowercases to ``"i"`` plus a combining dot that the filter
    drops.

    A fully non-ASCII or all-separator name yields the empty string — a valid
    output. No fallback is returned for an empty result; the caller owns the
    empty-slug decision.

    Args:
        name: Branch name as entered by the user.

    Returns:
        The history topic slug (possibly empty). No git, no filesystem, no
        side effects.
    """
    lowered = name.lower()
    ascii_only = "".join(character for character in lowered if character.isascii())
    hyphened = re.sub(r"[^a-z0-9]", "-", ascii_only)
    collapsed = re.sub(r"-{2,}", "-", hyphened)
    return collapsed.strip("-")


def resolve_current_branch_name() -> str | None:
    """Read the current git branch name exactly as git reports it.

    Asks git via ``git branch --show-current`` (per the ``git`` practice) and
    returns the stripped answer unmodified — no slugification, no fallback
    value; both belong to the caller. ``None`` covers only the three documented
    failure modes: detached HEAD (an empty git answer), a missing git binary
    (``FileNotFoundError``), and a non-repository (a non-zero git exit).
    Read-only; the result is not cached — each call asks git anew.

    Returns:
        The raw current branch name (stripped, unmodified), or ``None`` when it
        cannot be determined.

    Raises:
        OSError: unexpected OS-level failures of the git invocation (e.g. a
            ``PermissionError``); the ``None`` result covers only the
            documented failure modes.
    """
    try:
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            check=True,
            capture_output=True,
            text=True,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None
    value = result.stdout.strip()
    if value == "":
        return None
    return value


def check_branch_occupancy(branch_name: str, slug: str, history_year: str) -> str | None:
    """Decide whether the entered branch name and the topic slug are free.

    Probes three oracles in order and returns the human-readable reason of the
    first occupied one; remaining oracles are not probed:

    1. a local branch ref for ``branch_name`` (exact full-ref verification via
       ``git show-ref --verify`` — no glob ambiguity for names containing
       ``/``);
    2. a remote-tracking ref for ``branch_name`` (local
       ``git for-each-ref refs/remotes`` output only — no network call);
    3. the history topic folder ``.goga/history/<history_year>/<slug>`` — only
       a DIRECTORY occupies a topic (a stray file named ``<slug>`` does not).

    The git oracles check the name as entered; the history oracle checks the
    slug — the two may deliberately differ (``release/1.3.0`` vs
    ``release-1-3-0``). Read-only — no ref or folder is created. Occupancy
    answers are not error paths: git infrastructure failures beyond the
    occupancy semantics propagate.

    Args:
        branch_name: Branch name as entered (checked against git refs).
        slug: Normalized topic slug (checked against the history folder).
        history_year: Current year as ``YYYY`` (the caller owns the clock).

    Returns:
        The human-readable reason of the first occupied oracle, or ``None``
        when everything is free.

    Raises:
        subprocess.CalledProcessError: when the remote-tracking-ref listing
            itself fails (an infrastructure failure, not an occupancy answer).
        OSError: unexpected OS-level failures of the git invocations (e.g. a
            missing git binary).
    """
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}

    # Oracle 1 — local branch ref. A non-zero exit of the quiet --verify means
    # "no such ref": free, not an error.
    try:
        subprocess.run(
            ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch_name}"],
            check=True,
            capture_output=True,
            text=True,
            env=env,
        )
    except subprocess.CalledProcessError:
        pass
    else:
        return f"branch '{branch_name}' already exists"

    # Oracle 2 — remote-tracking refs, local refs only (no network). A ref
    # refs/remotes/<remote>/<branch> matches when its branch part equals the
    # entered name exactly (feat/x must not match feat/xy).
    result = subprocess.run(
        ["git", "for-each-ref", "--format=%(refname)", "refs/remotes"],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    for line in result.stdout.splitlines():
        rest = line.removeprefix("refs/remotes/")
        _remote, separator, branch = rest.partition("/")
        if separator and branch == branch_name:
            return f"remote-tracking branch '{branch_name}' already exists"

    # Oracle 3 — history topic folder. Only a directory occupies a topic.
    topic_dir = Path.cwd() / ".goga" / "history" / history_year / slug
    if topic_dir.is_dir():
        return f"history topic '.goga/history/{history_year}/{slug}' already exists"
    return None


def ensure_pipeline_branch(branch_name: str) -> str:
    """Bring the project onto a fresh branch with a fresh history topic.

    Composes the three primitives above: normalize the entered name into the
    topic slug, read the current branch, and check occupancy against the three
    oracles. A free name is created and switched to on the host exactly as
    entered (``git switch -c`` — the single mutation; git owns name validity).
    An unusable name (an empty slug or an occupancy conflict) re-asks on a
    terminal — the cycle restarts from the top and validates the NEW name
    fully — and aborts cleanly without one. The already-on-branch case (the
    current branch's slug equals the entered slug) touches nothing and returns
    the CURRENT branch name.

    Args:
        branch_name: Branch name as entered by the user via ``-b/--branch``.

    Returns:
        The final branch name — the entered one or the re-asked one after a
        create-and-switch; the current branch name for the already-on-branch
        case.

    Raises:
        click.ClickException: an empty topic slug or an unresolved occupancy
            conflict without a terminal, a failed create-and-switch (carrying
            git's stderr), a git infrastructure failure of the occupancy
            oracles (carrying git's stderr), or a missing git binary.
        click.Abort: Ctrl-C or EOF at the re-ask prompt — the repository is
            left untouched.
    """
    while True:
        slug = normalize_topic_slug(branch_name)
        current = resolve_current_branch_name()

        if slug == "":
            reason = f"branch name '{branch_name}' normalizes to an empty topic slug"
            branch_name = _reask_branch_name(reason)
            continue

        if current is not None and normalize_topic_slug(current) == slug:
            return current

        try:
            # Local-timezone year — the history tree is organized by the host's
            # calendar year; the bare now() shape is the mandated test mock target.
            conflict = check_branch_occupancy(
                branch_name,
                slug,
                f"{datetime.now().year:04d}",  # noqa: DTZ005
            )
        except FileNotFoundError as exc:
            raise click.ClickException(_GIT_REQUIRED_MESSAGE) from exc
        except subprocess.CalledProcessError as exc:
            # A git infrastructure failure of the oracles themselves (e.g. the
            # ref listing exiting 128 outside a repository) — not an occupancy
            # answer; surfaced as a clean failure, never a traceback.
            stderr = exc.stderr if isinstance(exc.stderr, str) else ""
            raise click.ClickException(
                f"git failed to check branch occupancy for {branch_name!r}: {stderr.strip()}"
            ) from exc
        if conflict is not None:
            branch_name = _reask_branch_name(conflict)
            continue

        try:
            subprocess.run(
                ["git", "switch", "-c", branch_name],
                check=True,
                capture_output=True,
                text=True,
                env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
            )
        except FileNotFoundError as exc:
            raise click.ClickException(_GIT_REQUIRED_MESSAGE) from exc
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr if isinstance(exc.stderr, str) else ""
            raise click.ClickException(f"git failed to create branch {branch_name!r}: {stderr.strip()}") from exc
        return branch_name
