"""The topic board of the topics domain.

The entities declared in the cell CODEMANIFEST with ``location: board.py``:
one row of the board audit view — a topic hosted by one branch with its
todo summary —, the read-only collector that merges the branch inventory,
the ref trees of one year, and the working copy of the current branch into
the sorted inventory of statuses and todo summaries of the topics that
still have their own branch, and the aggregated default view — one entry
per topic that still has its own branch, with every branch carrying its
history. The board lives under the pointer model: a topic exists exactly
as long as its own branch exists — some ref of the full inventory whose
branch part normalizes into the topic slug, local or remote-tracking; a
topic without its own branch is history and appears in no view. The
per-host records are the single source of the board's facts; the
aggregation is a pure projection over them — no git access happens there.
The divergence marker of a configured base — base, up-to-date,
propagated, or need-update — is computed from local refs in the
collection pass, without network and without ever failing the board. Git access follows the
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
from .git import (
    BranchRef,
    is_ancestor,
    list_branch_refs,
    read_ref_file,
    read_ref_tree_paths,
    resolve_ref_commit,
)

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
        divergence: The topic's own-branch divergence marker (base /
            up-to-date / propagated / need-update), ``None`` when
            unconfigured or unresolvable.
    """

    topic: str
    branch: str
    statuses: list[str]
    current: bool
    remote: bool
    todo: str | None = None
    divergence: str | None = None


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
        divergence: The topic's own-branch divergence marker (base /
            up-to-date / propagated / need-update), ``None`` when
            unconfigured or unresolvable — projected from the winning
            own-branch record.
    """

    topic: str
    branch: str
    hosts: list[str]
    statuses: list[str]
    current: bool
    remote: bool
    todo: str | None = None
    divergence: str | None = None


def collect_topic_board(
    year: str | None = None,
    remote: bool = False,
    hosts: tuple[str, ...] | None = None,
    topics: tuple[str, ...] | None = None,
    base_ref: str | None = None,
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
        topics: Optional topic slugs — ``None`` or empty keeps every record;
            when non-empty, only the records of the named topics survive,
            exact slug equality, union across values, composed with
            ``hosts``; an unknown slug yields the empty list, never an
            error.
        base_ref: The configured base revision string of the topic
            exchange; ``None`` computes no divergence marker.

    Returns:
        One ``BoardRecord`` per topic and hosting branch of the topics that
        still have their own branch, sorted by scale order of the first
        maximal status, then alphabetically by topic. Read-only — no
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
        8. Primary filter: a topic keeps its records only when it has its
           own branch — some ref of the full inventory of
           ``list_branch_refs``, both local and remote-tracking entries,
           whatever ``remote`` mode enumerates, whose branch part (the
           whole name of a local branch, the short name of a
           remote-tracking ref) normalizes into the topic slug; a topic
           without an own branch is history and passes no records
        9. Mark the row hosting the current branch
        10. The divergence marker of every own-branched topic is computed
            in this single collection pass via ``resolve_divergence`` from
            its own-branch tip — a ``base_ref`` given, ``None`` markers
            otherwise; the marker is topic-scoped, every record of the
            topic carries the same value
        11. A non-empty ``hosts`` keeps the records of the named hosting
            branches, a non-empty ``topics`` keeps the records of the named
            topics — both exact, union across values, composed together;
            the sort order of the survivors stays
        12. Sort by scale order of the first maximal status, then
            alphabetically by topic, and return the records

    Requirements:
        The current branch is read from the working copy — uncommitted
        progress is visible; remote mode shows it through its remote twin.

        The collection never fetches and never fails on an unconfigured or
        unresolvable base — the marker stays ``None``.

        A multi-line todo.md yields its first qualifying line; a todo.md
        whose every line reduces to emptiness yields the empty summary. The
        todo summary never affects the sort order.

        A topic without its own branch appears in no record, whatever hosts
        carry it — the primary filter owns this, the display filters never
        see its rows.

        An unknown ``hosts`` name or ``topics`` slug yields the empty list —
        not an error.

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
        return _board_records(year, remote, hosts, topics, base_ref)
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
    topics: tuple[str, ...] | None = None,
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
        topics: Optional topic slugs — ``None`` or empty keeps every entry;
            when non-empty, only the entries of the named topics survive,
            exact slug equality, union across values, composed with
            ``hosts``; the own-branch requirement stands first — a filter
            never resurrects a topic without an own branch; an unknown slug
            yields the empty list, never an error.

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
           remote marker, todo summary, and divergence marker, and the
           current marker is ``True`` when the winner hosts the current
           branch — a merged host carrying the topic's history never marks
           the entry
        6. Sort by scale order of the first maximal status, then
           alphabetically by topic
        7. A non-empty ``hosts`` keeps the entries whose hosts list contains
           any given name, a non-empty ``topics`` keeps the entries of the
           named topics — both exact, union across values, composed
           together; ``None`` or empty keeps every entry

    Requirements:
        Both board views derive from one collection pass — this routine
        computes, it never reads the ref trees; a topic without an own
        branch produces no entry, whatever hosts carry it.

        The divergence of the winning own-branch record projects into the
        entry.

        A filter never resurrects a hidden topic — the own-branch
        requirement precedes both.

    Constraints:
        Do not render — output shaping belongs to the consumer.
        Do not cross the year boundary — the records already scope it.

    Raises:
        click.ClickException: the fatal ``ImportError`` of the scale
            assembly — the broken tool package is named in the message.
    """
    try:
        return _aggregate_board(records, hosts, topics)
    except ImportError as exc:
        raise click.ClickException(str(exc)) from exc


def resolve_divergence(own_tip: str, base_ref: str | None) -> str | None:
    """Compute the board's directional divergence marker — read-only, from local refs, without network.

    Args:
        own_tip: The own-branch tip commit of the topic.
        base_ref: The configured base revision string; ``None`` renders no
            marker.

    Returns:
        ``base`` when the own tip equals every projection the base offers
        locally — the topic sits exactly on the base, ``up-to-date`` when
        the own tip strictly contains every projection — the topic carries
        the base with no lag, ``propagated`` when every projection contains
        the own tip — the base carries the whole topic, ``need-update``
        when the pair diverged, and ``None`` when the base is unconfigured
        or unresolvable — never an error.

    Algorithm:
        1. ``base_ref`` ``None`` -> ``None``
        2. The available projections of the base — the local branch tip
           and the twin tip, each as it exists locally, no fetch; a tag
           or hash base resolves to its commit; an unresolvable side is
           skipped, every side unresolvable -> ``None``
        3. ``own_tip`` equal to every projection -> ``base`` — the topic
           branch is the base, nothing of its own and nothing delivered
        4. every projection an ancestor of ``own_tip`` via
           ``is_ancestor`` -> ``up-to-date`` — the topic strictly carries
           the base, the exchange's already-carried rule
        5. ``own_tip`` an ancestor of every projection -> ``propagated``
           — the containment of the tip carries every commit of the
           topic, so a partially delivered topic fails the probe
        6. otherwise ``need-update`` — the pair diverged

    Requirements:
        Read-only — no fetch, no mutation, never a failure.

        ``base`` names the identity of the pair — equal tips; the
        equality probe runs before the containment probes, which both
        hold under it. ``up-to-date`` and ``propagated`` are the two
        delivery directions — the topic ahead of the base, the base
        carrying the whole topic; ``propagated`` is the state the clear
        scope addresses.

    Constraints:
        Do not reconcile — divergence of the base pair reads as
        need-update until an update converges it.

        Do not probe content — a delivery without ancestry, a squash,
        reads as need-update.
    """
    if base_ref is None:
        return None

    local, twin = _base_name_pair(base_ref)
    projections = [tip for tip in (_projection(local), _projection(twin)) if tip is not None]

    if not projections:
        return None

    if all(tip == own_tip for tip in projections):
        return "base"

    if all(is_ancestor(tip, own_tip) for tip in projections):
        return "up-to-date"

    return "propagated" if all(is_ancestor(own_tip, tip) for tip in projections) else "need-update"


def _board_records(
    year: str | None,
    remote: bool,
    hosts: tuple[str, ...] | None,
    topics: tuple[str, ...] | None,
    base_ref: str | None,
) -> list[BoardRecord]:
    """Build the board rows of one year — the traced algorithm, unwrapped.

    Args:
        year: Optional year as four digits; ``None`` means the current year.
        remote: ``True`` reads remote-tracking refs instead of local branches.
        hosts: The hosting-branch display-name record filter, or ``None``.
        topics: The topic-slug record filter, or ``None``.
        base_ref: The configured base revision string, or ``None`` for no
            divergence markers.

    Returns:
        The sorted board records of the resolved year — the topics that
        still have their own branch only.
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

    # The primary filter — the pointer model: a topic keeps its records only
    # when some ref of the FULL inventory — never the mode-sliced ``refs`` —
    # has a branch part that normalizes into its slug; a topic without its
    # own branch is history and passes no records.
    own = {normalize_topic_slug(_branch_part(ref.name, ref.remote)) for ref in inventory} - {""}

    collapsed = _collapse_remote_twins(rows)

    # The divergence markers — topic-scoped: the own-branch tip of every
    # surviving topic decides, and every record of the topic carries the
    # same value; no configured base resolves nothing at all.
    markers = _divergence_markers({slug for slug, _branch in collapsed if slug in own}, inventory, base_ref)

    records = [
        BoardRecord(
            topic=slug,
            branch=branch,
            statuses=statuses,
            current=_marks_current(branch, current, remote),
            remote=is_remote,
            todo=todo,
            divergence=markers.get(slug),
        )
        for (slug, branch), (is_remote, statuses, todo) in collapsed.items()
        if slug in own
    ]

    if hosts:
        names = set(hosts)
        records = [record for record in records if record.branch in names]
    if topics:
        slugs = set(topics)
        records = [record for record in records if record.topic in slugs]

    scale_order = {stage.name: index for index, stage in enumerate(scale.stages)}
    records.sort(key=lambda record: (scale_order[record.statuses[0]], record.topic))

    return records


def _aggregate_board(
    records: list[BoardRecord],
    hosts: tuple[str, ...] | None,
    topics: tuple[str, ...] | None,
) -> list[BoardEntry]:
    """Project the per-host records into the default board — the traced algorithm, unwrapped.

    Args:
        records: The collected per-host records — the source of facts.
        hosts: The hosting-branch display-name entry filter, or ``None``.
        topics: The topic-slug entry filter, or ``None``.

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
        own = [
            record
            for record in group
            if normalize_topic_slug(_branch_part(record.branch, record.remote)) == slug
        ]

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
                divergence=winner.divergence,
            )
        )

    entries.sort(key=lambda entry: (scale_order[entry.statuses[0]], entry.topic))

    if hosts:
        names = set(hosts)
        entries = [entry for entry in entries if any(host in names for host in entry.hosts)]
    if topics:
        slugs = set(topics)
        entries = [entry for entry in entries if entry.topic in slugs]

    return entries


def _branch_part(branch: str, remote: bool) -> str:
    """Return the branch part of a display name.

    The whole name of a local branch; the short name — the part after the
    first ``/`` — of a remote-tracking ref. The rule of the board's
    own-branch tests: the primary filter of the collection and the
    own-branch gate of the projection share it.

    Args:
        branch: The branch display name.
        remote: Whether the name is a remote-tracking ref.
    """
    return branch if not remote else _short_name(branch)


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


def _divergence_markers(slugs: set[str], inventory: list[BranchRef], base_ref: str | None) -> dict[str, str | None]:
    """Compute the divergence marker of every own-branched topic of the pass.

    The marker is topic-scoped — the own-branch tip decides, every record
    of the topic carries the same value. A topic whose own tip resolves to
    nothing carries ``None`` — an unresolvable side is a fact of the local
    state, never a failure of the board.

    Args:
        slugs: The topic slugs that survived the primary filter.
        inventory: The branch inventory — the own-branch lookup.
        base_ref: The configured base revision string, or ``None`` for no
            markers at all.

    Returns:
        The marker per slug — a ``base_ref`` of ``None`` yields the empty
        mapping, and every record's defaulted marker stays ``None``.
    """
    if base_ref is None:
        return {}

    markers: dict[str, str | None] = {}
    for slug in slugs:
        markers[slug] = _topic_divergence(slug, inventory, base_ref)

    return markers


def _topic_divergence(slug: str, inventory: list[BranchRef], base_ref: str) -> str | None:
    """Compute one topic's divergence marker from its own-branch tip.

    Args:
        slug: The topic slug.
        inventory: The branch inventory — the own-branch lookup.
        base_ref: The configured base revision string.

    Returns:
        The marker of the topic's own-branch tip, or ``None`` when the own
        tip resolves to nothing.
    """
    own_tip = _own_branch_tip(slug, inventory)

    return None if own_tip is None else resolve_divergence(own_tip, base_ref)


def _own_branch_tip(slug: str, inventory: list[BranchRef]) -> str | None:
    """Resolve the own-branch tip commit of one topic.

    The local branch the inventory carries wins — the twin resolves only
    for a remote-only own branch; colliding own branches pick the first in
    the display-name alphabet, the deterministic spelling of the
    projection's winner rule.

    Args:
        slug: The topic slug.
        inventory: The branch inventory.

    Returns:
        The commit the own branch resolves to, or ``None`` when no ref of
        the inventory is the topic's own branch or the ref resolves to
        nothing — display data degrades, never fails.
    """
    own = [ref for ref in inventory if normalize_topic_slug(_branch_part(ref.name, ref.remote)) == slug]

    if not own:
        return None

    local = [ref for ref in own if not ref.remote]
    chosen = min(local or own, key=lambda ref: ref.name)

    try:
        return resolve_ref_commit(chosen.name)
    except subprocess.CalledProcessError:
        # An unresolvable own ref is a fact of the local state — the
        # marker stays None, the board lives.
        return None


def _base_name_pair(base_ref: str) -> tuple[str, str]:
    """Split a base revision string into its local-branch and twin spellings.

    The board's marker reads the base as it stands locally — no inventory,
    no fetch: an ``origin/``-prefixed base contributes its short form as
    the local spelling and itself as the twin; every other base keeps its
    name locally and spells its twin under ``origin/``, where a tag or a
    hash resolves to nothing and drops out of the projections.

    Args:
        base_ref: The base revision string as configured.

    Returns:
        The ``(local, twin)`` name pair — the local branch spelling and
        its origin remote-tracking twin, existing or not.
    """
    if base_ref.startswith("origin/"):
        return _short_name(base_ref), base_ref

    return base_ref, f"origin/{base_ref}"


def _projection(ref_name: str) -> str | None:
    """Resolve one base side as it exists locally.

    Args:
        ref_name: The local branch or twin name to resolve.

    Returns:
        The commit the name resolves to, or ``None`` when it resolves to
        nothing — an absent side is a fact of the projection, never a
        failure.
    """
    try:
        return resolve_ref_commit(ref_name)
    except subprocess.CalledProcessError:
        return None
