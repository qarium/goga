"""The ``goga topics`` command group — the CLI surface of the topics domain.

The click group declared in the cell CODEMANIFEST with ``location:
topics.py``: the ``status``/``create``/``switch`` subcommands over the
topics domain. The group carries the year scope every subcommand shares and
is a thin wrapper — it resolves the inputs, delegates every computation to
the domain routines of ``goga.topics``, and renders the board through the
``render`` module. No inventory walking, no switch resolution, and no git
access live here; domain errors surface as clean CLI errors.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass

import click

from ...topics import collect_topic_board, create_topic, switch_topic
from .render import render_topic_board


@dataclass(kw_only=True)
class _TopicsScope:
    """The year scope shared by every subcommand of the group."""

    year: str | None = None


@click.group()
@click.option(
    "--year",
    "-y",
    default=None,
    help="Four-digit year scope shared by every subcommand (default: the current year)",
)
@click.pass_context
def topics(ctx: click.Context, year: str | None = None) -> None:
    """Work with the topics of one year."""
    ctx.ensure_object(_TopicsScope)
    ctx.obj.year = year


@topics.command("status")
@click.option(
    "--remote",
    "-r",
    is_flag=True,
    default=False,
    help="Read remote-tracking refs instead of local branches.",
)
@click.pass_obj
def status(scope: _TopicsScope, remote: bool = False) -> None:
    """Print the board — the cross-branch topic inventory of the scoped year.

    One three-column table row per topic: topic, branch, statuses — the row
    of the current branch carries an asterisk and the statuses wrap onto
    continuation lines when they overflow. --remote/-r reads remote-tracking
    refs instead of local branches. An empty board prints nothing and exits
    0 — it is not an error. The year defaults to the current one and is
    never printed.
    """
    records = collect_topic_board(scope.year, remote)
    render_topic_board(records, shutil.get_terminal_size().columns)
    click.get_current_context().exit(0)


@topics.command("create")
@click.argument("branch_name")
@click.pass_obj
def create(scope: _TopicsScope, branch_name: str) -> None:
    """Create fresh work — a branch with the name as entered and its topic directory.

    The branch name is taken verbatim; the topic directory of the scoped
    year is created from its slug. The current branch already hosting the
    same slug is an idempotent success. Occupied names and empty slugs
    re-ask on an interactive terminal and fail with a clean error
    otherwise. One result line on stdout.
    """
    line = create_topic(branch_name, scope.year)
    click.echo(line)
    click.get_current_context().exit(0)


@topics.command("switch")
@click.argument("identifier")
@click.pass_obj
def switch(scope: _TopicsScope, identifier: str) -> None:
    """Bring the repository onto the branch hosting the requested work.

    IDENTIFIER is a branch name, a topic slug, or their prefix — resolved in
    that order. Several candidates offer a numbered list and a prompt on an
    interactive terminal; already being on the host is an idempotent
    success, and a dirty working tree is a clean error when a mutation is
    needed. One result line on stdout; no pipeline is launched —
    continuation is a separate command.
    """
    line = switch_topic(identifier, scope.year)
    click.echo(line)
    click.get_current_context().exit(0)
