"""The fresh-work creation of the topics domain.

The entities declared in the cell CODEMANIFEST with
``location: creation.py``: the three-oracle occupancy check of a fresh-work
name, the branch-tree slug oracle that reads the topic directory of a slug
across every branch tree of the inventory — without checkout, so a topic
hosted only on a branch (or only on ``origin``) is visible — and the
orchestrator that creates the branch — named exactly as entered
— together with its topic directory of the year and, when a title is given,
its topic title file. Topic identity and addressing belong to the history
facade; the bounded git mutation belongs to the nested git cell. Git
infrastructure failures surface as ``click.ClickException`` — the
clean-error boundary of the domain; the interactive moments follow the
``click`` practice. The status scale is never assembled here — creation is
not a status consumer.
"""

from __future__ import annotations

import subprocess
import sys

import click

from ..history import (
    current_year,
    ensure_topic_dir,
    normalize_topic_slug,
    resolve_current_branch_name,
    resolve_history_root,
    resolve_topic_file,
    topic_exists,
)
from .git import create_and_switch_branch, list_branch_refs, read_ref_tree_paths

# The board hint of an occupancy conflict — where the occupied names are
# visible to the user.
_BOARD_HINT = "run 'goga topics status' to see the board"


def check_branch_occupancy(
    branch_name: str, slug: str, year: str | None = None
) -> str | None:
    """Decide whether the entered branch name and the topic slug are free.

    Probes three oracles in order and returns the human-readable reason of
    the first occupied one; the remaining oracles are not probed:

    1. a local ``BranchRef`` of the inventory named exactly ``branch_name``;
    2. a remote-tracking ``BranchRef`` whose short name — the part after the
       first slash of its display name — equals ``branch_name`` (the local
       inventory only, no network);
    3. the topic directory of ``slug`` in the year via ``topic_exists`` —
       only a directory occupies a topic.

    The git oracles check the name as entered; the history oracle checks the
    slug — the two may deliberately differ (``Feature/Foo_Bar`` vs
    ``feature-foo-bar``).

    Args:
        branch_name: Branch name as entered (checked against the inventory).
        slug: Normalized topic slug (checked against the topic directory).
        year: Optional year as four digits; ``None`` means the current year.

    Returns:
        The human-readable reason of the first occupied oracle, or ``None``
        when everything is free.

    Constraints:
        Read-only — no ref or directory is created.
        Do not resolve remote state over the network — the local inventory
        only.

    Raises:
        click.ClickException: a git infrastructure failure (its stderr when
            git reports one, or a missing git binary).
    """
    try:
        return _occupancy_conflict(branch_name, slug, year)
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or "").strip() or str(exc)
        raise click.ClickException(f"git failed: {detail}") from exc
    except FileNotFoundError as exc:
        raise click.ClickException(f"git is not available: {exc}") from exc


def check_slug_occupancy(slug: str, year: str | None = None) -> str | None:
    """Decide whether any branch of the inventory already hosts the topic
    directory of the slug.

    Reads the branch trees through ``read_ref_tree_paths`` — the local
    branches and the remote-tracking refs as they exist locally, without
    checkout — one ref at a time; the first ref whose tree carries paths
    under the topic directory prefix of the slug is the conflict. A topic
    hosted only on ``origin`` blocks the slug the same way a local one
    does; a topic living only in the working copy does not — that is the
    file oracle's domain.

    Args:
        slug: Normalized topic slug (checked across every branch tree).
        year: Optional year as four digits; ``None`` means the current year.

    Returns:
        The human-readable reason naming the hosting branch, or ``None``
        when no branch hosts the slug.

    Constraints:
        Read-only — no ref or directory is created; no checkout, no
        worktree.
        Do not resolve remote state over the network — the local inventory
        only.
        Do not probe the working copy — a topic living only on disk is the
        file oracle's domain.

    Raises:
        click.ClickException: a git infrastructure failure (its stderr when
            git reports one, or a missing git binary).
    """
    try:
        return _slug_conflict(slug, year)
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or "").strip() or str(exc)
        raise click.ClickException(f"git failed: {detail}") from exc
    except FileNotFoundError as exc:
        raise click.ClickException(f"git is not available: {exc}") from exc


def create_topic(
    branch_name: str, year: str | None = None, title: str | None = None
) -> str:
    """Create fresh work — a branch with the name as entered, its topic
    directory of the year, and an optional topic title.

    Args:
        branch_name: Branch name as entered by the user.
        year: Optional year as four digits; ``None`` means the current year.
        title: Optional topic title; ``None`` writes no title file.

    Returns:
        One line describing the outcome — the created work, or the
        idempotent success when the current branch already hosts the topic.

    Algorithm:
        1. Normalize ``branch_name`` into a slug via ``normalize_topic_slug``
        2. Empty slug -> print the reason, prompt for a new name on an
           interactive terminal and restart, or fail with the reason
           otherwise
        3. The current branch — read via ``resolve_current_branch_name`` —
           hosts the same slug -> the idempotent path: a ``title`` given
           writes the topic title file ``title.txt`` of the ensured topic
           directory; no ``title`` is a success without mutation; no
           occupancy check, no switch
        4. ``check_branch_occupancy`` reports a conflict -> print the reason
           with a hint to the board, prompt for a new name on an interactive
           terminal and restart, or fail otherwise
        5. Free name -> create the branch named exactly as entered and
           switch to it via ``create_and_switch_branch``, create the topic
           directory via ``ensure_topic_dir`` of the year, and a ``title``
           given writes the title file ``title.txt`` of the topic directory
        6. Return the single result line

    Requirements:
        The branch keeps the name as entered; the topic directory takes the
        slug — the two may deliberately differ.
        The title file carries ``title`` as entered plus a single trailing
        newline, encoded UTF-8.
        The title file is written only when ``title`` is given — ``None``
        never creates and never overwrites it; an explicit ``title`` creates
        the file or overwrites it.
        The topic directory exists before the title file is written.
        An aborted re-ask leaves the repository untouched.
        The caller stays on the new branch.

    Constraints:
        Do not validate branch-name characters — git owns name validity.
        Do not auto-pick suffixed names on a conflict — the user re-asks or
        aborts.
        Do not write artifact files other than the topic title file inside
        the topic directory.

    Raises:
        click.ClickException: an unresolved empty slug or occupancy conflict
            without a terminal, a git infrastructure failure (its stderr
            when git reports one, or a missing git binary).
        click.Abort: Ctrl-C or EOF at the re-ask prompt — the repository is
            left untouched.
    """
    try:
        return _create_topic(branch_name, year, title)
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or "").strip() or str(exc)
        raise click.ClickException(f"git failed: {detail}") from exc
    except FileNotFoundError as exc:
        raise click.ClickException(f"git is not available: {exc}") from exc
    except OSError as exc:
        # ``ensure_topic_dir`` propagates the mkdir failures — a stray file
        # named like the slug occupies no topic for the oracle, so the
        # failure can only surface here, after the branch was created. The
        # title write shares the boundary: one clean error for both.
        raise click.ClickException(
            f"cannot create the topic directory or write the title file: {exc}"
        ) from exc


def _occupancy_conflict(
    branch_name: str, slug: str, year: str | None
) -> str | None:
    """Probe the three occupancy oracles — the traced algorithm, unwrapped.

    Args:
        branch_name: Branch name as entered (checked against the inventory).
        slug: Normalized topic slug (checked against the topic directory).
        year: Optional year as four digits; ``None`` means the current year.

    Returns:
        The reason of the first occupied oracle, or ``None``.
    """
    resolved_year = year or current_year()
    refs = list_branch_refs()
    if any(not ref.remote and ref.name == branch_name for ref in refs):
        return f"branch '{branch_name}' already exists"
    if any(
        ref.remote and ref.name.partition("/")[2] == branch_name for ref in refs
    ):
        return f"remote-tracking branch '{branch_name}' already exists"
    if topic_exists(slug, resolved_year):
        return f"history topic '{slug}' already exists for {resolved_year}"
    return None


def _slug_conflict(slug: str, year: str | None) -> str | None:
    """Probe the branch-tree slug oracle — the traced algorithm, unwrapped.

    Args:
        slug: Normalized topic slug (checked across every branch tree).
        year: Optional year as four digits; ``None`` means the current year.

    Returns:
        The reason naming the first hosting branch, or ``None``.
    """
    resolved_year = year or current_year()
    # The trailing slash is load-bearing: it keeps a sibling slug that only
    # shares the prefix text ("feature-foo-bar" of "feature-foo") free.
    prefix = f"{resolve_history_root().as_posix()}/{resolved_year}/{slug}/"
    for ref in list_branch_refs():
        if read_ref_tree_paths(ref.name, prefix):
            return (
                f"topic '{slug}' of {resolved_year} is already hosted by branch '{ref.name}'"
            )
    return None


def _create_topic(branch_name: str, year: str | None, title: str | None) -> str:
    """Run the traced creation procedure — the unwrapped orchestration.

    Args:
        branch_name: Branch name as entered by the user.
        year: Optional year as four digits; ``None`` means the current year.
        title: Optional topic title; ``None`` writes no title file.

    Returns:
        The single result line of the outcome.
    """
    resolved_year = year or current_year()
    while True:
        slug = normalize_topic_slug(branch_name)

        if slug == "":
            reason = f"branch name '{branch_name}' normalizes to an empty topic slug"
            branch_name = _reask(reason)
            continue

        current = resolve_current_branch_name()
        if current is not None and normalize_topic_slug(current) == slug:
            if title is not None:
                ensure_topic_dir(branch_name, resolved_year)
                _write_title(branch_name, resolved_year, title)
            return f"Branch {current} already hosts topic {resolved_year}/{slug}"

        conflict = check_branch_occupancy(branch_name, slug, resolved_year)
        if conflict is not None:
            branch_name = _reask(conflict, _BOARD_HINT)
            continue

        create_and_switch_branch(branch_name)
        ensure_topic_dir(branch_name, resolved_year)
        if title is not None:
            _write_title(branch_name, resolved_year, title)
        return f"Created branch {branch_name} and topic {resolved_year}/{slug}"


def _write_title(name: str, year: str, title: str) -> None:
    """Write the topic title file of a topic directory.

    The file carries the title as entered plus a single trailing newline,
    encoded UTF-8 — created when absent, overwritten when present. The topic
    directory must already exist; only directories are created here.

    Args:
        name: Topic input — a branch name or an already-normalized slug.
        year: Year as four digits.
        title: Topic title as entered by the user.
    """
    resolve_topic_file(name, "title.txt", year).write_text(
        f"{title}\n", encoding="utf-8"
    )


def _reask(reason: str, hint: str = "") -> str:
    """Handle an unusable name: re-ask on a terminal, abort otherwise.

    Args:
        reason: Human-readable reason the current name cannot be used.
        hint: Optional next step appended to the non-terminal error.

    Returns:
        The re-asked branch name — the caller restarts the procedure with it.

    Raises:
        click.ClickException: without a terminal — the reason (and the hint
            when given) go to the user as a non-terminal abort.
        click.Abort: Ctrl-C or EOF at the prompt.
    """
    if not sys.stdin.isatty():
        message = f"{reason} — {hint}" if hint else reason
        raise click.ClickException(message)
    click.echo(reason, err=True)
    return click.prompt("New branch name")
