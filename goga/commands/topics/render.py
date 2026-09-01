"""Console rendering for the topics command group.

The entity declared in the cell CODEMANIFEST with ``location: render.py``:
the board renderer — the collected board records as a three-column table of
topic, branch, and statuses, or as a four-column table with the todo
column between branch and statuses under ``info``. Pure output: the records
print as given, never sorted, filtered, or recomputed; the domain owns the
collection and the ordering.
"""

from __future__ import annotations

import click

from ...topics import BoardRecord

# The fixed grid overhead per column — one pipe and two padding spaces; the
# leading pipe replaces the pipe of the first column, so a table of k text
# columns carries 3*k overhead columns in total.
# The minimum of every column before truncation applies.
_MIN_COLUMN = 8
# The current-row marker — a prefix inside the topic cell.
_CURRENT_MARKER = "* "
# The truncation marker — a single ellipsis character.
_ELLIPSIS = "…"


def render_topic_board(records: list[BoardRecord], width: int, info: bool = False) -> None:
    """Render the board as a table: topic, branch, and statuses — under
    ``info`` the todo column sits between branch and statuses.

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
        4. Mark the record hosting the current branch with an asterisk; the
           remote prefix of a remote host stays visible in the branch column
        5. An empty ``records`` prints nothing

    Requirements:
        The three-column rule gives topic and branch an equal share first —
        each capped at one third of ``width`` minus the dividers — and
        statuses the remainder; the four-column rule under ``info`` gives
        topic, branch, and todo an equal share — each capped at one quarter
        of ``width`` minus the dividers — and statuses the non-negative
        remainder. Every column keeps a minimum of 8 columns before
        truncation applies. The todo column header is the word todo. A todo
        of ``None`` or an empty string renders an empty cell. The truncation
        marker is a single ellipsis character;
        an overlong status segment is truncated like the other columns. The
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
    header = ("Topic", "Branch", "todo", "Statuses") if info else ("Topic", "Branch", "Statuses")
    click.echo(_row_line(header, caps))
    click.echo(_separator(caps))
    for record in records:
        topic_text = f"{_CURRENT_MARKER}{record.topic}" if record.current else record.topic
        leading = (
            (topic_text, record.branch, record.todo or "") if info else (topic_text, record.branch)
        )
        segments = [f"[{status}]" for status in record.statuses]
        for index, statuses_line in enumerate(_wrap_segments(segments, caps[-1])):
            cells = (*(cell if index == 0 else "" for cell in leading), statuses_line)
            click.echo(_row_line(cells, caps))


def _column_widths(width: int, columns_count: int) -> tuple[int, ...]:
    """Resolve the column widths of the grid for one terminal width.

    Args:
        width: The measured terminal width in columns.
        columns_count: The number of text columns of the grid — 3 or 4.

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


def _wrap_segments(segments: list[str], statuses_w: int) -> list[str]:
    """Wrap the status segments onto the continuation lines of the column.

    Args:
        segments: The bracketed status names of one record.
        statuses_w: The cap of the statuses column.

    Returns:
        The statuses cell content per grid line — a greedy fill that keeps
        every segment whole; a single segment longer than the column is
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
