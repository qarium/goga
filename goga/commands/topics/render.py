"""Console rendering for the topics command group.

The entities declared in the cell CODEMANIFEST with ``location: render.py``:
the default board renderer — the aggregated entries as a four-column table
of topic, branch, hosts, and statuses, or a five-column table with the todo
column between hosts and statuses under ``info``; the audit renderer — the
per-host records as a three-column table of topic, branch, and statuses, or
a four-column table with the todo column between branch and statuses; and
the JSON projection — the machine-readable form of either view. Pure
output: the records and the entries print as given, never sorted,
filtered, or recomputed; the domain owns the collection and the ordering.
"""

from __future__ import annotations

import json

import click

from ...topics import BoardEntry, BoardRecord

# The fixed grid overhead per column — one pipe and two padding spaces; the
# leading pipe replaces the pipe of the first column, so a table of k text
# columns carries 3*k overhead columns in total.
# The minimum of every column before truncation applies.
_MIN_COLUMN = 8
# The current-row marker — a prefix inside the topic cell.
_CURRENT_MARKER = "* "
# The truncation marker — a single ellipsis character.
_ELLIPSIS = "…"


def render_topic_board(entries: list[BoardEntry], width: int, info: bool = False) -> None:
    """Render the default board as a table: topic, branch, hosts, and statuses.

    Under ``info``, the todo column sits between hosts and statuses.

    Args:
        entries: The aggregated board entries — already sorted by the domain.
        width: The measured terminal width in columns.
        info: ``True`` adds the todo column and switches to the
            five-column width rule.

    Algorithm:
        1. Compute the column widths from ``width`` alone per the width
           rule of the requirements — the four-column rule without
           ``info``, the five-column rule with it; the grid is fixed and
           independent of the entry content
        2. Print one header row and one separator row with column and row
           dividers — the column order is topic, branch, hosts, todo,
           statuses under ``info``; the hosts column header is the word
           Hosts
        3. Print each entry: every text column truncated with an ellipsis
           when it exceeds its column; every host name prints on its own
           grid line of the hosts column, and the statuses wrap whole
           onto continuation lines in brackets — neither affects the
           column widths
        4. Print one row divider after every entry — the same dash run as
           the header separator — the last entry included; the wrapped
           continuation lines of one entry stay undivided
        5. Mark the entry hosting the current branch with an asterisk; the
           remote prefix of a remote own branch stays visible in the
           branch column
        6. An empty ``entries`` prints nothing

    Requirements:
        The four-column rule gives topic, branch, and hosts an equal share
        first — each capped at one quarter of ``width`` minus the dividers
        — and statuses the non-negative remainder; the five-column rule
        under ``info`` gives topic, branch, hosts, and todo an equal share
        — each capped at one fifth of ``width`` minus the dividers — and
        statuses the non-negative remainder. Every column keeps a minimum
        of 8 columns before truncation applies. The hosts column header is
        the word Hosts. Every host name prints on its own grid line of
        the hosts column. A todo of ``None`` or an empty string renders an
        empty cell. The truncation marker is a single ellipsis character;
        an overlong host or status name is truncated like the other
        columns. A row divider — identical to the header separator row —
        closes every entry: it prints after the wrapped columns of each
        entry, the last entry included, and never between the continuation
        lines of one entry. The table never exceeds ``width``, with one
        documented exception: below the narrow threshold of the active
        column rule — 44 columns for the quarters, 55 for the fifths —
        every column keeps its minimum of 8 and the table may exceed
        ``width``; minimum readability wins over the width cap on
        ultra-narrow terminals.

    Constraints:
        Read-only on ``entries`` — do not mutate, do not re-sort, do not
        filter. Do not print the year or the artifacts.
    """
    if not entries:
        return

    columns_count = 5 if info else 4
    caps = _column_widths(width, columns_count)
    header = ("Topic", "Branch", "Hosts", "Todo", "Statuses") if info else ("Topic", "Branch", "Hosts", "Statuses")

    click.echo(_row_line(header, caps))
    click.echo(_separator(caps))

    for entry in entries:
        topic_text = f"{_CURRENT_MARKER}{entry.topic}" if entry.current else entry.topic
        leading = (topic_text, entry.branch)
        host_lines = _stack_segments(list(entry.hosts), caps[2])
        status_lines = _wrap_segments([f"[{status}]" for status in entry.statuses], caps[-1])

        for index in range(max(len(host_lines), len(status_lines), 1)):
            cells = [
                *(cell if index == 0 else "" for cell in leading),
                host_lines[index] if index < len(host_lines) else "",
            ]

            if info:
                cells.append((entry.todo or "") if index == 0 else "")

            cells.append(status_lines[index] if index < len(status_lines) else "")
            click.echo(_row_line(tuple(cells), caps))

        click.echo(_separator(caps))


def render_topic_host_rows(records: list[BoardRecord], width: int, info: bool = False) -> None:
    """Render the audit board as a table: topic, branch, and statuses.

    One row per topic and hosting branch — the per-host audit view of the
    collection. Under ``info``, the todo column sits between branch and
    statuses.

    Args:
        records: The collected board records — already sorted by the domain.
        width: The measured terminal width in columns.
        info: ``True`` adds the todo column and switches to the
            four-column width rule.

    Algorithm:
        1. Compute the column widths from ``width`` alone per the width
           rule of the requirements — the three-column rule without
           ``info``, the four-column rule with it; the grid is fixed and
           independent of the record content
        2. Print one header row and one separator row with column and row
           dividers — the column order is topic, branch, todo, statuses
           under ``info``
        3. Print each record: every text column truncated with an ellipsis
           when it exceeds its column, and the statuses wrapped onto
           continuation lines without affecting the column widths
        4. Print one row divider after every record — the same dash run as
           the header separator — the last record included; the wrapped
           continuation lines of one record stay undivided
        5. Mark the record hosting the current branch with an asterisk; the
           remote prefix of a remote host stays visible in the branch column
        6. An empty ``records`` prints nothing

    Requirements:
        The three-column rule gives topic and branch an equal share first —
        each capped at one third of ``width`` minus the dividers — and
        statuses the remainder; the four-column rule under ``info`` gives
        topic, branch, and todo an equal share — each capped at one quarter
        of ``width`` minus the dividers — and statuses the non-negative
        remainder. Every column keeps a minimum of 8 columns before
        truncation applies. The todo column header is the word Todo. A todo
        of ``None`` or an empty string renders an empty cell. The truncation
        marker is a single ellipsis character;
        an overlong status segment is truncated like the other columns. A
        row divider — identical to the header separator row — closes every
        record: it prints after the wrapped statuses of each record, the
        last record included, and never between the continuation lines of
        one record. The
        table never exceeds ``width``, with one documented exception: below
        the narrow threshold of the active column rule — 33 columns for the
        thirds, 44 for the quarters — every column keeps its minimum of 8
        and the table may exceed ``width``; minimum readability wins over
        the width cap on ultra-narrow terminals.

    Constraints:
        Read-only on ``records`` — do not mutate, do not re-sort, do not
        filter. Do not print the year or the artifacts.
    """
    if not records:
        return

    columns_count = 4 if info else 3
    caps = _column_widths(width, columns_count)
    header = ("Topic", "Branch", "Todo", "Statuses") if info else ("Topic", "Branch", "Statuses")

    click.echo(_row_line(header, caps))
    click.echo(_separator(caps))

    for record in records:
        topic_text = f"{_CURRENT_MARKER}{record.topic}" if record.current else record.topic
        leading = (topic_text, record.branch, record.todo or "") if info else (topic_text, record.branch)
        segments = [f"[{status}]" for status in record.statuses]

        for index, statuses_line in enumerate(_wrap_segments(segments, caps[-1])):
            cells = (*(cell if index == 0 else "" for cell in leading), statuses_line)
            click.echo(_row_line(cells, caps))

        click.echo(_separator(caps))


def render_board_json(board: list[BoardEntry] | list[BoardRecord]) -> None:
    """Render the board — either view — as pretty-printed JSON.

    Args:
        board: The board of one view — the aggregated entries of the
            default view, or the per-host records of the audit view; never
            mixed.

    Algorithm:
        1. Project every item into its plain shape — a ``BoardEntry``
           carries the ``hosts`` key beside topic, branch, statuses,
           current, remote, and todo; a ``BoardRecord`` the same keys
           without ``hosts``; the ``todo`` key is a string or ``null``,
           never omitted
        2. Echo the array pretty-printed — indent 4, sorted keys, UTF-8 —
           with one trailing newline; an empty board prints ``[]``

    Requirements:
        Read-only on ``board`` — the items project as given. The record
        shapes are a stable consumer contract; the key order is not.

    Constraints:
        Do not print anything outside the JSON array — no year, no
        artifacts, no heading.
    """
    items = [
        _entry_shape(item) if isinstance(item, BoardEntry) else _record_shape(item)
        for item in board
    ]

    click.echo(json.dumps(items, indent=4, sort_keys=True, ensure_ascii=False))


def _entry_shape(entry: BoardEntry) -> dict[str, object]:
    """Project one board entry into its JSON shape.

    Args:
        entry: The aggregated entry of the default view.

    Returns:
        The plain shape of the entry — the hosts key included, the todo
        key always present.
    """
    return {
        "topic": entry.topic,
        "branch": entry.branch,
        "hosts": entry.hosts,
        "statuses": entry.statuses,
        "current": entry.current,
        "remote": entry.remote,
        "todo": entry.todo,
    }


def _record_shape(record: BoardRecord) -> dict[str, object]:
    """Project one board record into its JSON shape.

    Args:
        record: The per-host record of the audit view.

    Returns:
        The plain shape of the record — no hosts key, the todo key always
        present.
    """
    return {
        "topic": record.topic,
        "branch": record.branch,
        "statuses": record.statuses,
        "current": record.current,
        "remote": record.remote,
        "todo": record.todo,
    }


def _column_widths(width: int, columns_count: int) -> tuple[int, ...]:
    """Resolve the column widths of the grid for one terminal width.

    Args:
        width: The measured terminal width in columns.
        columns_count: The number of text columns of the grid — 3, 4, or 5.

    Returns:
        The caps of every column in grid order. The text columns take an
        equal share of the usable width and statuses the non-negative
        remainder; when the minimums no longer fit, every column keeps its
        minimum of 8 and the table may exceed ``width``.
    """
    usable = width - 3 * columns_count

    if usable < columns_count * _MIN_COLUMN:
        return (_MIN_COLUMN,) * columns_count

    cap = usable // columns_count

    return (cap,) * (columns_count - 1) + (usable - (columns_count - 1) * cap,)


def _row_line(cells: tuple[str, ...], caps: tuple[int, ...]) -> str:
    """Build one grid row — every cell fitted to its column.

    The fixed overhead of the grid is one pipe and two padding spaces per
    column: the leading pipe, the column separators, and the right padding
    of the last cell — the table closes on the padded column, not on a
    trailing pipe.

    Args:
        cells: The cell texts of this grid line in grid order — the
            continuation lines pass the text columns empty.
        caps: The caps of every column.

    Returns:
        The grid line with the cells truncated, padded, and divided.
    """
    return f"| {' | '.join(_fit(text, cap) for text, cap in zip(cells, caps, strict=True))} "


def _separator(caps: tuple[int, ...]) -> str:
    """Build the row divider of the grid.

    Args:
        caps: The caps of every column.

    Returns:
        The separator row — one dash run per column under its padding,
        joined by the pipes of the grid.
    """
    return "|" + "|".join("-" * (cap + 2) for cap in caps)


def _fit(text: str, cap: int) -> str:
    """Fit one cell — truncate an overlong text, then pad to the column.

    Args:
        text: The cell text — already carrying the current-row marker when
            the row hosts the current branch.
        cap: The column cap in columns.

    Returns:
        The cell text of exactly ``cap`` columns.
    """
    return _truncate(text, cap).ljust(cap)


def _truncate(text: str, cap: int) -> str:
    """Truncate one text to its column — the single-character ellipsis marker.

    Args:
        text: The text to fit.
        cap: The column cap in columns.

    Returns:
        The text unchanged when it fits; ``text[: cap - 1]`` plus the
        ellipsis when it exceeds the cap.
    """
    if len(text) > cap:
        return f"{text[: cap - 1]}{_ELLIPSIS}"

    return text


def _stack_segments(segments: list[str], cap: int) -> list[str]:
    """Place every segment of the column on its own grid line.

    Args:
        segments: The whole segments of one cell — the plain host names.
        cap: The cap of the column.

    Returns:
        The cell content per grid line — one whole segment per line, an
        overlong one truncated with the ellipsis like the other columns;
        an empty ``segments`` renders one empty line. The grid lives on:
        the continuation lines carry empty text cells.
    """
    return [_truncate(segment, cap) for segment in segments] or [""]


def _wrap_segments(segments: list[str], statuses_w: int) -> list[str]:
    """Wrap the whole segments onto the continuation lines of the column.

    Args:
        segments: The whole segments of one cell — the bracketed status
            names.
        statuses_w: The cap of the wrapping column.

    Returns:
        The cell content per grid line — a greedy fill that keeps every
        segment whole; a single segment longer than the column is
        truncated with the ellipsis like the other columns. The grid lives
        on: the continuation lines carry empty text cells.
    """
    lines: list[str] = []
    current = ""

    for segment in segments:
        piece = _truncate(segment, statuses_w)
        if not current:
            current = piece
        elif len(current) + 1 + len(piece) <= statuses_w:
            current = f"{current} {piece}"
        else:
            lines.append(current)
            current = piece

    if current or not lines:
        lines.append(current)

    return lines
