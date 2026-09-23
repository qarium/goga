"""The topic board of the topics domain.

The entities declared in the cell CODEMANIFEST with ``location: board.py``:
one row of the board audit view — a topic hosted by one branch with its
todo summary —, the read-only collector that merges the branch inventory,
the ref trees of one year, and the working copy of the current branch into
the sorted inventory of statuses and todo summaries, and the aggregated
default view — one entry per topic that still has its own branch, with
every branch carrying its history. The per-host records are the single
source of the board's facts; the aggregation is a pure projection over
them — no git access happens there. Git access follows the
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


@dataclass(frozen=True, kw_only=True)
class BoardEntry:
    """One entry of the default board — one topic that still has its own branch.

    Attributes:
        topic: The topic slug — the directory name of the topic.
        branch: The display name of the topic's own branch — the hosting
            branch whose branch part (the whole name of a local branch, the
            short name of a remote-tracking ref) normalizes into the topic
            slug.
        hosts: The display names of every branch carrying the topic's
            history, the own branch included, alphabetical by display name.
        statuses: The qualified names of the maximal present statuses of
            the own branch, in scale order.
        current: ``True`` when the topic's own branch is the current
            working branch — a merged host carrying the topic's history
            never marks the entry.
        remote: ``True`` when the own branch is a remote-tracking ref.
        todo: The todo summary of the topic read from the own branch, or
            ``None`` when the topic has no todo.md; a todo.md whose every
            line reduces to emptiness yields the empty summary.
    """

    topic: str
    branch: str
    hosts: list[str]
    statuses: list[str]
    current: bool
    remote: bool
    todo: str | None = None


def collect_topic_board(
    year: str | None = None,
    remote: bool = False,
    hosts: tuple[str, ...] | None = None,
) -> list[BoardRecord]:
    """Collect the cross-branch topic inventory of one year with todo summaries.

    Args:
        year: Optional year as four digits; ``None`` means the current year.
        remote: ``True`` reads remote-tracking refs instead of local branches.
        hosts: Optional hosting-branch display names — ``None`` or empty
            keeps every record; when non-empty, only the records whose
            branch display name exactly equals one of them survive, union
            across values; an unknown name yields the empty list, never an
            error.

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
        9. A non-empty ``hosts`` keeps the records of the named hosting
           branches only — exact display-name equality, union across values;
           the sort order of the survivors stays
        10. Sort by scale order of the first maximal status, then
            alphabetically by topic, and return the records

    Requirements:
        The current branch is read from the working copy — uncommitted
        progress is visible; remote mode shows it through its remote twin.

        A multi-line todo.md yields its first qualifying line; a todo.md
        whose every line reduces to emptiness yields the empty summary. The
        todo summary never affects the sort order.

        An unknown ``hosts`` name yields the empty list — not an error.

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
        return _board_records(year, remote, hosts)
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or "").strip() or str(exc)
        raise click.ClickException(f"git failed: {detail}") from exc
    except FileNotFoundError as exc:
        raise click.ClickException(f"git is not available: {exc}") from exc
    except ImportError as exc:
        raise click.ClickException(str(exc)) from exc


def aggregate_topic_board(
    records: list[BoardRecord],
    hosts: tuple[str, ...] | None = None,
) -> list[BoardEntry]:
    """Project the per-host records into the default board of the year.

    Args:
        records: The collected per-host records — the source of facts.
        hosts: Optional hosting-branch display names — ``None`` or empty
            keeps every entry; when non-empty, only the entries whose hosts
            list contains one of them survive, union across values; the
            own-branch requirement stands first — the filter never
            resurrects a topic without an own branch; an unknown name yields
            the empty list, never an error.

    Returns:
        One ``BoardEntry`` per topic with an own branch, sorted by scale
        order of the first maximal status, then alphabetically by topic.
        Read-only over ``records`` — no mutation, no re-sort of the input;
        no git access happens here, every fact comes from the records; an
        empty ``records`` yields the empty list.

    Algorithm:
        1. Assemble the status scale via ``assemble_status_scale`` once —
           the sort axis of the entries
        2. Group the records by topic slug, first-encounter order
        3. Hosts list of a topic — the branch display names of its records,
           alphabetical; a local branch and its remote twin count as one
           host under the local name — the collapse belongs to the
           collection
        4. Own branch — the topic's records whose branch part — the whole
           display name of a local branch, the short name (the part after
           the first ``/``) of a remote-tracking ref — normalizes into the
           topic slug via ``normalize_topic_slug``; a remote-tracking ref
           qualifies; a topic without an own branch produces no entry — its
           history survives only in merged hosts
        5. Several own branches collide -> the deterministic winner: the
           record hosting the current branch, otherwise a non-remote record
           over a remote-tracking one, otherwise the first in the
           display-name alphabet; the entry carries the winner's statuses,
           remote marker, and todo summary, and the current marker is
           ``True`` when the winner hosts the current branch — a merged
           host carrying the topic's history never marks the entry
        6. Sort by scale order of the first maximal status, then
           alphabetically by topic
        7. A non-empty ``hosts`` keeps the entries whose hosts list contains
           any given name — union; ``None`` or empty keeps every entry

    Requirements:
        Both board views derive from one collection pass — this routine
        computes, it never reads the ref trees; a topic without an own
        branch produces no entry, whatever hosts carry it.

    Constraints:
        Do not render — output shaping belongs to the consumer.
        Do not cross the year boundary — the records already scope it.

    Raises:
        click.ClickException: the fatal ``ImportError`` of the scale
            assembly — the broken tool package is named in the message.
    """
    try:
        return _aggregate_board(records, hosts)
    except ImportError as exc:
        raise click.ClickException(str(exc)) from exc


def _board_records(year: str | None, remote: bool, hosts: tuple[str, ...] | None) -> list[BoardRecord]:
    """Build the board rows of one year — the traced algorithm, unwrapped.

    Args:
        year: Optional year as four digits; ``None`` means the current year.
        remote: ``True`` reads remote-tracking refs instead of local branches.
        hosts: The hosting-branch display-name record filter, or ``None``.

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

        if hosted is not None:
            slug, statuses, todo = hosted
            rows[(slug, ref.name)] = (False, statuses, todo)

        # The checked-out branch is a hosting branch like any other — its
        # merged-in topics keep their rows. Only the own slug is skipped: its
        # row above reads the working copy, so an uncommitted deletion stays
        # invisible. The merged rows read the working copy too.
        own_slug = normalize_topic_slug(current)

        for slug in topics_by_ref[ref.name]:
            if slug == own_slug:
                continue
            topic_dir = resolve_topic_dir(slug, resolved_year)
            rows[(slug, ref.name)] = (
                False,
                resolve_topic_status(topic_dir, scale),
                _todo_summary(_read_working(topic_dir / _TODO_FILE)),
            )

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

    if hosts:
        names = set(hosts)
        records = [record for record in records if record.branch in names]

    scale_order = {stage.name: index for index, stage in enumerate(scale.stages)}
    records.sort(key=lambda record: (scale_order[record.statuses[0]], record.topic))

    return records


def _aggregate_board(records: list[BoardRecord], hosts: tuple[str, ...] | None) -> list[BoardEntry]:
    """Project the per-host records into the default board — the traced algorithm, unwrapped.

    Args:
        records: The collected per-host records — the source of facts.
        hosts: The hosting-branch display-name entry filter, or ``None``.

    Returns:
        The sorted entries of the default board.
    """
    scale = assemble_status_scale()
    scale_order = {stage.name: index for index, stage in enumerate(scale.stages)}

    groups: dict[str, list[BoardRecord]] = {}
    for record in records:
        groups.setdefault(record.topic, []).append(record)

    entries: list[BoardEntry] = []
    for slug, group in groups.items():
        own = [record for record in group if normalize_topic_slug(_branch_part(record)) == slug]

        if not own:
            continue

        winner = min(own, key=lambda record: (not record.current, record.remote, record.branch))
        entries.append(
            BoardEntry(
                topic=slug,
                branch=winner.branch,
                hosts=_topic_hosts(group),
                statuses=winner.statuses,
                current=winner.current,
                remote=winner.remote,
                todo=winner.todo,
            )
        )

    entries.sort(key=lambda entry: (scale_order[entry.statuses[0]], entry.topic))

    if hosts:
        names = set(hosts)
        entries = [entry for entry in entries if any(host in names for host in entry.hosts)]

    return entries


def _branch_part(record: BoardRecord) -> str:
    """Return the branch part of a record's display name.

    The whole name of a local branch; the short name — the part after the
    first ``/`` — of a remote-tracking ref.
    """
    return record.branch if not record.remote else _short_name(record.branch)


def _topic_hosts(group: list[BoardRecord]) -> list[str]:
    """Take the hosts of one topic — every branch carrying its history.

    Args:
        group: The topic's records.

    Returns:
        The display names of every branch carrying the topic's history, the
        own branch included, alphabetical by display name; a local branch
        and its remote twin count once, under the local name.
    """
    local_names = {record.branch for record in group if not record.remote}

    return sorted(
        {record.branch for record in group if not (record.remote and _short_name(record.branch) in local_names)}
    )


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
