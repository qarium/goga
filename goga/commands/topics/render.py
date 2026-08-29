"""Console rendering for the topics command group.

The entity declared in the cell CODEMANIFEST with ``location: render.py``:
the board renderer — the collected board records as a three-column table of
topic, branch, and statuses. Pure output: the records print as given, never
sorted, filtered, or recomputed; the domain owns the collection and the
ordering.
"""

from __future__ import annotations

from typing import NamedTuple

import click

from ...topics import BoardRecord

# The fixed grid overhead — three pipe characters and six padding spaces.
_GRID_OVERHEAD = 9
# The minimum of every column before truncation applies.
_MIN_COLUMN = 8
# The usable-content floor of the thirds layout — below it the degenerate
# minimum-width layout wins over the width cap.
_USABLE_FLOOR = 3 * _MIN_COLUMN
# The current-row marker — a prefix inside the topic cell.
_CURRENT_MARKER = "* "
# The truncation marker — a single ellipsis character.
_ELLIPSIS = "…"


class _Columns(NamedTuple):
    """The caps of the three board columns, in grid order."""

    topic: int
    branch: int
    statuses: int


def render_topic_board(records: list[BoardRecord], width: int) -> None:
    """Render the board as a three-column table: topic, branch, statuses.

    Args:
        records: The collected board records — already sorted by the domain.
        width: The measured terminal width in columns.

    Algorithm:
        1. Compute the column widths from ``width`` — the width rule of the
           requirements
        2. Print one header row and one separator row with column and row
           dividers
        3. Print each record: the topic truncated with an ellipsis when it
           exceeds its column, the branch truncated the same way, and the
           statuses wrapped onto continuation lines without affecting the
           column widths
        4. Mark the record hosting the current branch with an asterisk; the
           remote prefix of a remote host stays visible in the branch column
        5. An empty ``records`` prints nothing

    Requirements:
        Topic and branch get an equal share first — each capped at one third
        of ``width`` minus the dividers — and statuses take the remainder;
        every column keeps a minimum of 8 columns before truncation applies.
        The truncation marker is a single ellipsis character; an overlong
        status segment is truncated like the other columns. The table never
        exceeds ``width``, with one documented exception: when ``width`` is
        below 33, every column keeps its minimum of 8 and the table may
        exceed ``width`` — minimum readability wins over the width cap on
        ultra-narrow terminals.

    Constraints:
        Read-only on ``records`` — do not mutate, do not re-sort, do not
        filter. Do not print the year or the artifacts.
    """
    if not records:
        return
    columns = _column_widths(width)
    click.echo(_row_line(("Topic", "Branch", "Statuses"), columns))
    click.echo(_separator(columns))
    for record in records:
        topic_text = f"{_CURRENT_MARKER}{record.topic}" if record.current else record.topic
        segments = [f"[{status}]" for status in record.statuses]
        for index, statuses_line in enumerate(_wrap_segments(segments, columns.statuses)):
            cells = (
                topic_text if index == 0 else "",
                record.branch if index == 0 else "",
                statuses_line,
            )
            click.echo(_row_line(cells, columns))


def _column_widths(width: int) -> _Columns:
    """Resolve the column widths of the grid for one terminal width.

    Args:
        width: The measured terminal width in columns.

    Returns:
        The caps of the topic, branch, and statuses columns. With at least
        24 usable columns topic and branch take an equal third each and
        statuses the remainder; below that every column keeps its minimum
        of 8 and the table may exceed ``width``.
    """
    usable = width - _GRID_OVERHEAD
    if usable < _USABLE_FLOOR:
        return _Columns(_MIN_COLUMN, _MIN_COLUMN, _MIN_COLUMN)
    topic_cap = usable // 3
    return _Columns(topic_cap, topic_cap, usable - 2 * topic_cap)


def _row_line(cells: tuple[str, str, str], columns: _Columns) -> str:
    """Build one grid row — every cell fitted to its column.

    The fixed overhead of the grid is three pipes and six padding spaces:
    the leading pipe, the two column separators, and the right padding of
    the statuses cell — the table closes on the padded column, not on a
    trailing pipe.

    Args:
        cells: The topic, branch, and statuses cell texts of this grid
            line — the continuation lines pass the first two empty.
        columns: The caps of the three columns.

    Returns:
        The grid line with the cells truncated, padded, and divided.
    """
    topic, branch, statuses = cells
    return f"| {_fit(topic, columns.topic)} | {_fit(branch, columns.branch)} | {_fit(statuses, columns.statuses)} "


def _separator(columns: _Columns) -> str:
    """Build the row divider of the grid.

    Args:
        columns: The caps of the three columns.

    Returns:
        The separator row — one dash run per column under its padding,
        joined by the pipes of the grid.
    """
    return f"|{'-' * (columns.topic + 2)}|{'-' * (columns.branch + 2)}|{'-' * (columns.statuses + 2)}"


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
        on: the continuation lines carry empty topic and branch cells.
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
