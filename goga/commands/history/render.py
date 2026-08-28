"""Console rendering for the history command group.

The entities declared in the cell CODEMANIFEST with ``location: render.py``:
the list-view tree renderer and the flat status-view renderer. Both are pure
output — what the input carries is printed as given, never sorted, filtered,
or recomputed; the caller owns the collection and the filtering.
"""

from __future__ import annotations

import os

import click

from ...history import HistoryYear, TopicRecord


def render_history_tree(tree: list[HistoryYear]) -> None:
    """Render the history tree as the list-view output.

    One ``YYYY/`` line per year, each topic of the year on its own indented
    line under the tree marker. An empty tree renders nothing.

    Args:
        tree: The collected tree — years ascending, topics alphabetical.
    """
    for year_record in tree:
        click.echo(f"{year_record.year}/")
        for topic in year_record.topics:
            click.echo(f" └── {topic}")


def render_topic_statuses(records: list[TopicRecord]) -> None:
    """Render the status view — one flat ``topic [status]`` line per record.

    The topic prints plain with a trailing space and no newline; the bracketed
    status display name follows as the one colored segment (``cyan``). A
    non-empty ``NO_COLOR`` keeps the segment plain — click does not honor the
    variable, so it is checked explicitly. An empty input renders nothing.

    Args:
        records: The records to print — already filtered by the caller.
    """
    for record in records:
        click.echo(f"{record.topic} ", nl=False)
        status_segment = f"[{record.status.value}]"
        if os.environ.get("NO_COLOR"):
            click.echo(status_segment)
        else:
            click.secho(status_segment, fg="cyan")
