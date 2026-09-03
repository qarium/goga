"""The topic board of the topics domain.

The entities declared in the cell CODEMANIFEST with ``location: board.py``:
one row of the board — a topic hosted by one branch with its todo summary —
and the read-only collector that merges the branch inventory, the ref trees
of one year, and the working copy of the current branch into the sorted
inventory of statuses and todo summaries. Git access follows the
``refs-and-switching`` patterns of the nested git cell; topic identity,
addressing, and statuses belong to the history facade. Git infrastructure
failures and the fatal scale-assembly import failure surface as
``click.ClickException`` — the clean-error boundary of the domain.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

import click

from ..history import (
    StatusScale,
    assemble_status_scale,
    current_year,
    normalize_topic_slug,
    resolve_current_branch_name,
    resolve_history_root,
    resolve_topic_dir,
    resolve_topic_status,
    topic_exists,
)
from .git import BranchRef, list_branch_refs, read_ref_file, read_ref_tree_paths

# One board row under construction — whether the hosting ref is
# remote-tracking, the row's maximal statuses, and the row's todo summary.
_Row = tuple[bool, list[str], str | None]

# The topic todo file — the artifact of the ``todo`` status entry.
_TODO_FILE = "todo.md"

# The minimum part count of a topic path — ``.goga/history/<year>/<slug>/<artifact>``.
_TOPIC_PATH_PARTS = 5


@dataclass(frozen=True, kw_only=True)
class BoardRecord:
    """One row of the topic board — a topic hosted by one branch.

    Attributes:
        topic: The topic slug — the directory name of the topic.
        branch: The display name of the hosting branch.
        statuses: The qualified names of the maximal present statuses, in
            scale order.
        current: ``True`` when the row hosts the current working branch.
        remote: ``True`` when the hosting ref is remote-tracking.
        todo: The todo summary of the topic — the first line of todo.md
            that yields a non-empty result after leading # markers are
            stripped and the edges trimmed — or ``None`` when the topic has
            no todo.md.
    """

    topic: str
    branch: str
    statuses: list[str]
    current: bool
    remote: bool
    todo: str | None = None


def collect_topic_board(year: str | None = None, remote: bool = False) -> list[BoardRecord]:
    """Collect the cross-branch topic inventory of one year with todo summaries.

    Args:
        year: Optional year as four digits; ``None`` means the current year.
        remote: ``True`` reads remote-tracking refs instead of local branches.

    Returns:
        One ``BoardRecord`` per hosted topic, sorted by scale order of the
        first maximal status, then alphabetically by topic. Read-only — no
        checkout, no worktree, no mutation of any kind; the working copy is
        read but never changed. A year without topics yields an empty list —
        not an error.

    Algorithm:
        1. Resolve the year — ``year`` when given, otherwise the current year
        2. Assemble the status scale via ``assemble_status_scale`` once
        3. Local mode enumerates local branches via ``list_branch_refs`` and
           reads the current branch from the working copy via
           ``resolve_current_branch_name``; remote mode enumerates the
           remote-tracking ``BranchRef`` entries of the same inventory only.
           Local mode takes the full inventory of ``list_branch_refs`` — a
           topic hosted only by a remote-tracking ref keeps its row with the
           remote marker
        4. Read the topic tree of every ref under the root resolved via
           ``resolve_history_root`` with ``read_ref_tree_paths``, without
           checkout
        5. For every ref, take the topics of the resolved year with their
           artifact paths and compute the maximal statuses — the working copy
           via ``resolve_topic_status``, every other ref via the
           ``StatusScale``
        6. Read the todo summary of every hosted topic — the working copy
           from the todo file ``todo.md`` of its directory, every other ref
           from the todo.md of its ref tree via ``read_ref_file``; the
           summary is the first line that yields a non-empty result after
           leading # markers are stripped and the edges trimmed — the
           normalization decides the choice, a line of # markers alone never
           qualifies; ``None`` when the file is absent, the empty string
           when no line qualifies; the file is never modified
        7. Collapse a local branch and its remote twin into one row — the
           local branch wins; different branches hosting one slug stay
           separate rows
        8. Mark the row hosting the current branch
        9. Sort by scale order of the first maximal status, then
           alphabetically by topic, and return the records

    Requirements:
        The current branch is read from the working copy — uncommitted
        progress is visible; remote mode shows it through its remote twin.

        A multi-line todo.md yields its first qualifying line; a todo.md
        whose every line reduces to emptiness yields the empty summary. The
        todo summary never affects the sort order.

    Constraints:
        Do not render — output shaping belongs to the consumer.
        Do not cross the year boundary — other years are invisible here.

    Raises:
        click.ClickException: a git infrastructure failure (its stderr when
            git reports one, or a missing git binary), or the fatal
            ``ImportError`` of the scale assembly — the broken tool package
            is named in the message.
    """
    try:
        return _board_records(year, remote)
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or "").strip() or str(exc)
        raise click.ClickException(f"git failed: {detail}") from exc
    except FileNotFoundError as exc:
        raise click.ClickException(f"git is not available: {exc}") from exc
    except ImportError as exc:
        raise click.ClickException(str(exc)) from exc


def _board_records(year: str | None, remote: bool) -> list[BoardRecord]:
    """Build the board rows of one year — the traced algorithm, unwrapped.

    Args:
        year: Optional year as four digits; ``None`` means the current year.
        remote: ``True`` reads remote-tracking refs instead of local branches.

    Returns:
        The sorted board records of the resolved year.
    """
    resolved_year = year or current_year()
    scale = assemble_status_scale()
    inventory = list_branch_refs()
    current = resolve_current_branch_name()
    refs = [ref for ref in inventory if ref.remote] if remote else inventory
    prefix = _history_prefix()
    topics_by_ref = _year_topics_by_ref(refs, resolved_year)

    rows: dict[tuple[str, str], _Row] = {}
    for ref in refs:
        if remote or current is None or ref.name != current:
            for slug, artifacts in topics_by_ref[ref.name].items():
                todo_path = f"{prefix}{resolved_year}/{slug}/{_TODO_FILE}"
                rows[(slug, ref.name)] = (
                    ref.remote,
                    scale.maximal_present(artifacts),
                    _todo_summary(read_ref_file(ref.name, todo_path)),
                )
            continue

        hosted = _current_branch_topic(current, resolved_year, scale)

        if hosted is None:
            continue

        slug, statuses, todo = hosted
        rows[(slug, ref.name)] = (False, statuses, todo)

    records = [
        BoardRecord(
            topic=slug,
            branch=branch,
            statuses=statuses,
            current=_marks_current(branch, current, remote),
            remote=is_remote,
            todo=todo,
        )
        for (slug, branch), (is_remote, statuses, todo) in _collapse_remote_twins(rows).items()
    ]

    scale_order = {stage.name: index for index, stage in enumerate(scale.stages)}
    records.sort(key=lambda record: (scale_order[record.statuses[0]], record.topic))

    return records


def _history_prefix() -> str:
    """Return the history root as a git path prefix.

    The prefix carries the trailing slash and is always posix — git
    pathspecs, ``ls-tree`` output, and ``show`` paths are forward-slashed on
    Windows too; a native-separator path would match nothing and silently
    empty the board.
    """
    return f"{resolve_history_root().as_posix()}/"


def _year_topics_by_ref(refs: list[BranchRef], year: str) -> dict[str, dict[str, list[str]]]:
    """Read the topics of one year hosted by every given ref.

    One ``read_ref_tree_paths`` invocation per ref under the history root;
    the shared entry point of the board and the switch resolution — both
    walk the same ref trees without checkout.

    Args:
        refs: The refs whose trees are read.
        year: The resolved year as four digits.

    Returns:
        The topics of the year per ref display name — ``{slug: [artifact,
        ...]}`` with the artifact paths relative to the topic directory,
        ready for ``StatusScale.maximal_present``.
    """
    prefix = _history_prefix()
    return {ref.name: _year_topics(read_ref_tree_paths(ref.name, prefix), year) for ref in refs}


def _year_topics(paths: list[str], year: str) -> dict[str, list[str]]:
    """Split the ref-tree paths of one year into its topics.

    Args:
        paths: The file paths of one ref tree, relative to the repository
            root.
        year: The resolved year as four digits.

    Returns:
        The topics of the year — ``{slug: [artifact, ...]}`` with the
        artifact paths relative to the topic directory.
    """
    topics: dict[str, list[str]] = {}

    for path in paths:
        parts = path.split("/")
        if len(parts) < _TOPIC_PATH_PARTS or parts[2] != year:
            continue

        topics.setdefault(parts[3], []).append("/".join(parts[4:]))

    return topics


def _current_branch_topic(current: str, year: str, scale: StatusScale) -> tuple[str, list[str], str | None] | None:
    """Read the current branch's own topic from the working copy.

    The slug guard runs first: ``resolve_topic_dir`` and ``topic_exists``
    raise ``ValueError`` on an empty slug before their existence check, and
    a fully non-ASCII branch name is a legal input that simply hosts no
    topic.

    Args:
        current: The current branch name as git reports it.
        year: The resolved year as four digits.
        scale: The assembled status scale.

    Returns:
        The current branch's slug with its maximal statuses and its todo
        summary, or ``None`` when the branch hosts no topic of the year.
    """
    slug = normalize_topic_slug(current)

    if slug == "":
        return None
    if not topic_exists(current, year):
        return None

    topic_dir = resolve_topic_dir(current, year)
    todo = _todo_summary(_read_working(topic_dir / _TODO_FILE))

    return slug, resolve_topic_status(topic_dir, scale), todo


def _todo_summary(content: str | None) -> str | None:
    """Take the todo summary of a todo file's content.

    Args:
        content: The todo file content, or ``None`` when the file is
            absent.

    Returns:
        The first line that yields a non-empty result after the leading #
        markers are stripped and the edges trimmed, ``""`` when no line
        qualifies, ``None`` for an absent file — presence differs from
        absence.
    """
    if content is None:
        return None
    return next(
        (line.lstrip("#").strip() for line in content.splitlines() if line.lstrip("#").strip()),
        "",
    )


def _read_working(path: Path) -> str | None:
    """Read one file of the working copy.

    Args:
        path: The file path to read.

    Returns:
        The UTF-8 file content, or ``None`` when the file is absent —
        uncommitted progress is visible, a missing file is not an error.
        A file a hand edit left outside UTF-8 decodes with the replacement
        character instead of raising — the todo summary is display data,
        never a reason to fail the board.
    """
    return path.read_text(encoding="utf-8", errors="replace") if path.is_file() else None


def _collapse_remote_twins(rows: dict[tuple[str, str], _Row]) -> dict[tuple[str, str], _Row]:
    """Drop every remote row whose local twin hosts the same topic.

    Args:
        rows: The board rows keyed by ``(slug, branch display name)``.

    Returns:
        The rows without the collapsed remote twins — the local branch wins.
    """
    local_keys = {key for key, row in rows.items() if not row[0]}

    return {key: row for key, row in rows.items() if row[0] is False or (key[0], _short_name(key[1])) not in local_keys}


def _marks_current(branch: str, current: str | None, remote: bool) -> bool:
    """Decide whether a row's branch hosts the current work in this mode.

    Args:
        branch: The row's branch display name.
        current: The current branch name, or ``None`` when there is none.
        remote: Whether the board runs in remote mode.

    Returns:
        ``True`` when the row hosts the current branch — by display name in
        local mode, through the remote twin's short name in remote mode.
    """
    if current is None:
        return False
    return _short_name(branch) == current if remote else branch == current


def _short_name(branch: str) -> str:
    """Return the branch part of a display name — after the first ``/``."""
    return branch.partition("/")[2]
