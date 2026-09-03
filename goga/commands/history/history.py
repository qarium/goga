"""The ``goga history`` command group — the CLI surface of the history domain.

The click group declared in the cell CODEMANIFEST with ``location:
history.py``: the ``list``/``status``/``path``/``ensure``/``prune``
subcommands over the ``.goga/history/`` tree. The group carries the year
scope every subcommand shares — the ``-y/--year`` option addressed before
the subcommand; the subcommands themselves carry no year surfaces of their
own. The group is a thin wrapper — it resolves the inputs, delegates every
computation to the domain routines of ``goga.history``, and renders the
results through the ``render`` module. No path building, no slug grammar,
no year validation, and no status resolution live here. Domain errors
surface as clean CLI errors: a ``ValueError`` from the domain and an
undetermined git branch become ``click.ClickException`` (stderr, exit 1,
no traceback) — no fallback topic names, no silent skips.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass

import click

from ...history import (
    assemble_status_scale,
    collect_history_tree,
    collect_topic_statuses,
    ensure_topic_dir,
    normalize_topic_slug,
    prune_topics,
    resolve_current_branch_name,
    resolve_topic_dir,
    resolve_topic_file,
)
from .render import render_history_tree, render_topic_statuses


@dataclass(kw_only=True)
class _HistoryScope:
    """The year scope shared by every subcommand of the group."""

    year: str | None = None


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
@click.option(
    "--year",
    "-y",
    default=None,
    help="Four-digit year shared by every subcommand (without it: "
    "list prints every year, the others take the current year)",
)
@click.pass_context
def history(ctx: click.Context, year: str | None = None) -> None:
    """Work with the .goga/history/ tree."""
    ctx.ensure_object(_HistoryScope)
    ctx.obj.year = year


@history.command("list")
@click.pass_obj
def list_topics(scope: _HistoryScope) -> None:
    """Print the inventory tree — every year with its topics, or the year given via -y/--year alone.

    The inventory view: one YYYY/ line per year, each topic indented under
    its year. An empty tree prints nothing. Read-only — nothing is created
    or written; statuses and artifact names never appear.
    """
    render_history_tree(collect_history_tree(scope.year))
    click.get_current_context().exit(0)


@history.command("status")
@click.option("-t", "--topic", default=None, help="Substring filter on the normalized topic slug.")
@click.option("-s", "--status", "statuses", multiple=True, help="Status filter, repeatable (e.g. -s planned).")
@click.pass_obj
def status(scope: _HistoryScope, topic: str | None = None, statuses: tuple[str, ...] = ()) -> None:
    """Print the topics of one year, one 'topic [status] [status] …' line each.

    A topic carries its maximal statuses in scale order — one bracketed
    segment per status, tool statuses included. The year comes from the
    group's -y/--year (default: the current year) and is never printed.
    -t/--topic keeps the topics whose slug contains the normalized filter
    as a substring; -s/--status keeps the topics carrying at least one of
    the requested statuses; both filters combine by AND. An empty result
    prints nothing and exits 0 — it is not an error. The topics come out
    alphabetically; the domain sorts, this command does not re-sort.
    """
    try:
        scale = assemble_status_scale()
    except (ValueError, ImportError) as exc:
        raise click.ClickException(str(exc)) from exc
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

    records = collect_topic_statuses(scope.year, scale)

    if topic is not None:
        records = [record for record in records if filter_slug in record.topic]
    if statuses:
        requested = set(statuses)
        records = [record for record in records if set(record.statuses) & requested]
    render_topic_statuses(records)
    click.get_current_context().exit(0)


@history.command("path")
@click.argument("topic", required=False)
@click.option(
    "-f",
    "--file",
    "filename",
    default=None,
    help="Print the artifact file path instead of the topic directory.",
)
@click.pass_obj
def path(scope: _HistoryScope, topic: str | None = None, filename: str | None = None) -> None:
    """Print one path of the history tree — and nothing else.

    TOPIC defaults to the current git branch (taken raw, as a branch name or
    a slug). With -f/--file the artifact file path is printed, otherwise the
    topic directory; the year comes from the group's -y/--year (default:
    the current one). The path and only the path — exactly one stdout line,
    for scripting: plan=$(goga history path -f plan.md). Nothing is created
    on disk.
    """
    resolved_topic = _resolve_topic_input(topic)

    try:
        if filename is not None:
            resolved_path = resolve_topic_file(resolved_topic, filename, scope.year)
        else:
            resolved_path = resolve_topic_dir(resolved_topic, scope.year)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(resolved_path)
    click.get_current_context().exit(0)


@history.command("ensure")
@click.argument("name", required=False)
@click.pass_obj
def ensure(scope: _HistoryScope, name: str | None = None) -> None:
    """Create the topic directory of the scoped year, idempotently.

    NAME defaults to the current git branch (taken raw, as a branch name or
    a slug); parent directories are created as needed and an existing topic
    directory is a success, not a conflict. The year comes from the group's
    -y/--year (default: the current one). Prints nothing on stdout — the
    exit code carries the result. Only directories: no artifact file is
    created, and occupancy is not reported (deciding whether a topic may be
    created belongs to the caller).
    """
    resolved_name = _resolve_topic_input(name)

    try:
        ensure_topic_dir(resolved_name, scope.year)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    click.get_current_context().exit(0)


@history.command("prune")
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="List the deletion candidates without deleting anything.",
)
@click.pass_obj
def prune(scope: _HistoryScope, dry_run: bool = False) -> None:
    """Delete the orphan topics of one year — the topics no branch hosts.

    A local branch or a remote-tracking ref whose short name normalizes to
    the topic slug protects it, in every year; every other topic of the
    year is an orphan and goes. The year comes from the group's -y/--year
    (default: the current year) — only that year is touched. Every removed
    topic is printed as one slug per line, and nothing else; an empty
    result prints nothing and exits 0. The deletion is filesystem-only (no
    branch, ref, or index of git is touched) and unconditional — no status
    protects a topic. It is also irreversible: the history tree is not in
    git, so a deleted topic directory cannot be recovered. Run the command
    with --dry-run first to preview the candidates.
    """
    try:
        removed = prune_topics(scope.year, dry_run)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or "").strip() or str(exc)
        raise click.ClickException(f"git failed: {detail}") from exc
    except FileNotFoundError as exc:
        raise click.ClickException(f"git is not available: {exc}") from exc
    except OSError as exc:
        # FileNotFoundError is matched above — the git-less binary never
        # lands here; this wraps the rmtree failures of the deletion.
        raise click.ClickException(f"cannot delete topic directory: {exc}") from exc
    for slug in removed:
        click.echo(slug)
    click.get_current_context().exit(0)
