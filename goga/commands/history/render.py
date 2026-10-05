"""Console rendering for the history command group."""

from __future__ import annotations

import os

import click

from ...history import HistoryYear, TopicRecord


def render_history_tree(tree: list[HistoryYear]) -> None:
    """Render the history tree as the list view: ``YYYY/`` per year, topics indented; empty renders nothing.

    Args:
        tree: The collected tree — years ascending, topics alphabetical.
    """
    for year_record in tree:
        click.echo(f"{year_record.year}/")
        for topic in year_record.topics:
            click.echo(f" └── {topic}")


def render_topic_statuses(records: list[TopicRecord]) -> None:
    """Render the status view — one flat ``topic [status] …`` line per record.

    Args:
        records: The records to print — already filtered by the caller.

    Note:
        The topic prints plain with a trailing space and no newline; the
        bracketed status names follow, space-separated, as a ``cyan``
        segment. A non-empty ``NO_COLOR`` keeps the segments plain — click
        does not honor the variable, so it is checked explicitly. An empty
        input renders nothing.
    """
    for record in records:
        click.echo(f"{record.topic} ", nl=False)
        status_segments = " ".join(f"[{status_name}]" for status_name in record.statuses)
        if os.environ.get("NO_COLOR"):
            click.echo(status_segments)
        else:
            click.secho(status_segments, fg="cyan")
