"""The ``goga history`` command group — the CLI surface of the history domain.

The click group declared in the cell CODEMANIFEST with ``location:
history.py``: the ``list``/``status``/``path``/``ensure`` subcommands over the
``.goga/history/`` tree. The group is a thin wrapper — it resolves the inputs,
delegates every computation to the domain routines of ``goga.history``, and
renders the results through the ``render`` module. No path building, no slug
grammar, and no status resolution live here. Domain errors surface as clean
CLI errors: a ``ValueError`` from the domain and an undetermined git branch
become ``click.ClickException`` (stderr, exit 1, no traceback) — no fallback
topic names, no silent skips.
"""

from __future__ import annotations

import click

from ...history import (
    assemble_status_scale,
    collect_history_tree,
    collect_topic_statuses,
    ensure_topic_dir,
    normalize_topic_slug,
    resolve_current_branch_name,
    resolve_topic_dir,
    resolve_topic_file,
)
from .render import render_history_tree, render_topic_statuses


def _resolve_topic_input(topic: str | None) -> str:
    """Resolve a topic input: the positional when given, the branch otherwise.

    Args:
        topic: The positional value — ``None`` when the user passed none.

    Returns:
        The topic input to hand to the domain (verbatim, unnormalized).

    Raises:
        click.ClickException: when the positional is absent and the current
            git branch cannot be determined (the three documented ``None``
            modes of the domain branch reader).
    """
    if topic is not None:
        return topic
    branch = resolve_current_branch_name()
    if branch is None:
        raise click.ClickException("cannot determine the current git branch — pass a topic explicitly")
    return branch


@click.group()
def history() -> None:
    """Work with the .goga/history/ tree."""


@history.command("list")
@click.pass_context
def list_topics(ctx: click.Context) -> None:
    """Print the tree of every history year with its topics.

    The inventory view: one YYYY/ line per year, each topic indented under
    its year. An empty tree prints nothing. Read-only — nothing is created
    or written; statuses and artifact names never appear.
    """
    render_history_tree(collect_history_tree())
    ctx.exit(0)


@history.command("status")
@click.argument("year", required=False)
@click.option("-t", "--topic", default=None, help="Substring filter on the normalized topic slug.")
@click.option("-s", "--status", "statuses", multiple=True, help="Status filter, repeatable (e.g. -s planned).")
@click.pass_context
def status(
    ctx: click.Context,
    year: str | None = None,
    topic: str | None = None,
    statuses: tuple[str, ...] = (),
) -> None:
    """Print the topics of one year, one 'topic [status]' line each.

    YEAR defaults to the current year and is never printed. -t/--topic keeps
    the topics whose slug contains the normalized filter as a substring;
    -s/--status keeps the given statuses; both filters combine by AND. An
    empty result prints nothing and exits 0 — it is not an error. The topics
    come out alphabetically; the domain sorts, this command does not re-sort.
    """
    scale = assemble_status_scale()
    for name in statuses:
        try:
            scale.resolve_status(name)
        except ValueError as exc:
            raise click.ClickException(f"unknown status name: {name!r}") from exc

    filter_slug: str | None = None
    if topic is not None:
        filter_slug = normalize_topic_slug(topic)
        if filter_slug == "":
            raise click.ClickException(f"topic filter {topic!r} normalizes to an empty topic slug")

    records = collect_topic_statuses(year, scale)
    if topic is not None:
        records = [record for record in records if filter_slug in record.topic]
    if statuses:
        requested = set(statuses)
        records = [record for record in records if set(record.statuses) & requested]
    render_topic_statuses(records)
    ctx.exit(0)


@history.command("path")
@click.argument("topic", required=False)
@click.option(
    "-f",
    "--file",
    "filename",
    default=None,
    help="Print the artifact file path instead of the topic directory.",
)
@click.option("-y", "--year", default=None, help="Four-digit year (default: the current year).")
@click.pass_context
def path(
    ctx: click.Context,
    topic: str | None = None,
    filename: str | None = None,
    year: str | None = None,
) -> None:
    """Print one path of the history tree — and nothing else.

    TOPIC defaults to the current git branch (taken raw, as a branch name or
    a slug). With -f/--file the artifact file path is printed, otherwise the
    topic directory; the year defaults to the current one. The path and only
    the path — exactly one stdout line, for scripting:
    plan=$(goga history path -f plan.md). Nothing is created on disk.
    """
    resolved_topic = _resolve_topic_input(topic)
    try:
        if filename is not None:
            resolved_path = resolve_topic_file(resolved_topic, filename, year)
        else:
            resolved_path = resolve_topic_dir(resolved_topic, year)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(resolved_path)
    ctx.exit(0)


@history.command("ensure")
@click.argument("name", required=False)
@click.pass_context
def ensure(ctx: click.Context, name: str | None = None) -> None:
    """Create the topic directory of the current year, idempotently.

    NAME defaults to the current git branch (taken raw, as a branch name or
    a slug); parent directories are created as needed and an existing topic
    directory is a success, not a conflict. Prints nothing on stdout — the
    exit code carries the result. Only directories: no artifact file is
    created, and occupancy is not reported (deciding whether a topic may be
    created belongs to the caller).
    """
    resolved_name = _resolve_topic_input(name)
    try:
        ensure_topic_dir(resolved_name)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    ctx.exit(0)
