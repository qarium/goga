"""The ``goga topics`` command group — the CLI surface of the topics domain.

The click group declared in the cell CODEMANIFEST with ``location:
topics.py``: the ``board``/``create``/``switch``/``delete`` subcommands
over the topics domain. The group carries the year scope every subcommand
shares and is a thin wrapper — it resolves the inputs, delegates every
computation to the domain routines of ``goga.topics``, and renders the
board through the ``render`` module. The creation inputs resolve their
values at this layer: the base — ``--base-ref``, the ``topics`` section
of the project configuration, the current HEAD under ``--from-current``
— and the commit message template — ``--commit/-c``, the ``topics``
section, the built-in default of the domain; the configuration is read
lazily, only for values no flag provided. The deletion is confirmed at
this layer — one confirmation for the whole resolved list. No inventory
walking, no switch resolution, no git access, and no editor session
live here — the todo value and the ``--switch/-s`` flag pass through and
the entry belongs to the domain. Domain errors surface as clean CLI
errors.
"""

from __future__ import annotations

import shutil
import sys
from dataclasses import dataclass

import click
import yaml

from ...config import TopicsConfig, load_project_config
from ...topics import (
    collect_topic_board,
    create_topic,
    delete_topics,
    resolve_delete_targets,
    switch_topic,
)
from .render import render_topic_board


@dataclass(kw_only=True)
class _TopicsScope:
    """The year scope shared by every subcommand of the group."""

    year: str | None = None


def _topics_section() -> TopicsConfig | None:
    """Read the topics section of .goga/config.yml — None when unset or unconfigured."""
    try:
        return load_project_config().topics
    except FileNotFoundError:
        return None
    except OSError as exc:
        # A present-but-unreadable file (a directory in its place, a
        # permission failure) surfaces as its own clean error — the loader
        # documents OSError on its Raises surface. FileNotFoundError, an
        # OSError subclass, is already handled above as "unset".
        raise click.ClickException(str(exc)) from exc
    except (KeyError, ValueError, yaml.YAMLError) as exc:
        raise click.ClickException(str(exc)) from exc


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


@topics.command("board")
@click.option(
    "--remote",
    "-r",
    is_flag=True,
    default=False,
    help="Read remote-tracking refs instead of local branches.",
)
@click.option(
    "--info",
    "-i",
    is_flag=True,
    default=False,
    help="Add the todo column to the table.",
)
@click.pass_obj
def board(scope: _TopicsScope, remote: bool = False, info: bool = False) -> None:
    """Print the board — the cross-branch topic inventory of the scoped year.

    One three-column table row per topic: topic, branch, statuses — the row
    of the current branch carries an asterisk and the statuses wrap onto
    continuation lines when they overflow. --info/-i adds the todo column
    — the todo summary of the topic — between branch and statuses.
    --remote/-r reads remote-tracking refs instead of local branches. An
    empty board prints nothing and exits 0 — it is not an error. The year
    defaults to the current one and is never printed.
    """
    records = collect_topic_board(scope.year, remote)
    render_topic_board(records, shutil.get_terminal_size().columns, info)
    click.get_current_context().exit(0)


@topics.command("create")
@click.argument("branch_name")
@click.option(
    "--todo",
    "-t",
    "todo",
    default=None,
    metavar="[TEXT]",
    help="Todo of the fresh work; an empty value counts as absent; with no todo given a terminal opens the editor.",
)
@click.option(
    "--publish",
    "-p",
    is_flag=True,
    default=False,
    help="Create the work off the base and publish it to origin without switching and without the ask.",
)
@click.option(
    "--base-ref",
    default=None,
    help="Base of the branch; beats topics.base_ref of .goga/config.yml, which beats --from-current.",
)
@click.option(
    "--from-current",
    is_flag=True,
    default=False,
    help="Base the branch on the current HEAD.",
)
@click.option(
    "--commit",
    "-c",
    "commit_message",
    default=None,
    help="Commit message template, publication-only; beats topics.publish_commit — {slug} takes the topic slug.",
)
@click.option(
    "--switch",
    "-s",
    is_flag=True,
    default=False,
    help="Switch to the created branch after the creation; without the flag you stay on your branch.",
)
@click.pass_obj
def create(  # noqa: PLR0913, PLR0917 — the CODEMANIFEST-declared CLI surface
    scope: _TopicsScope,
    branch_name: str,
    todo: str | None = None,
    publish: bool = False,
    base_ref: str | None = None,
    from_current: bool = False,
    commit_message: str | None = None,
    switch: bool = False,
) -> None:
    """Create fresh work — a branch off the resolved base with its topic.

    The branch name is taken verbatim; the topic of the scoped year takes
    its slug. The base resolves as --base-ref, then topics.base_ref of
    .goga/config.yml, then the current HEAD under --from-current; no base
    at all is a clean error naming the flag and the configuration line.
    By default the branch is planted at one commit carrying the topic's
    todo.md and you stay on your branch — the todo is required on this
    path. An explicit --todo/-t value is the todo — the value form only,
    a value-less --todo is click's own usage error; an empty value counts
    as absent; with no todo given a terminal opens the external editor
    and without a terminal the command is a clean error naming the
    option. --switch/-s checks out the fresh branch instead — the topic
    directory and todo.md land in the working copy uncommitted and the
    todo is optional. On a terminal without --publish the publication ask
    appears once a todo is resolved; declining takes the local path.
    --publish/-p publishes to origin without switching and without the
    ask; a failed publication rolls back fully. --commit/-c — the
    message template; topics.publish_commit; the built-in default lives
    in the domain — is publication-only. One result line on stdout.
    """
    if commit_message is not None and not publish:
        raise click.ClickException("--commit is publication-only — it acts only together with --publish")

    if switch and publish:
        raise click.ClickException("--switch acts only without --publish — the publication never switches")

    # The empty --todo value counts as an absent option; the entry and
    # the write belong to the domain.
    if todo == "":
        todo = None

    # The configuration is read lazily — only when a value no flag
    # provided has to come from it; both values given means zero reads.
    section = _topics_section() if base_ref is None or commit_message is None else None

    base = base_ref
    if base is None and section is not None:
        base = section.base_ref
    if base is None and from_current:
        base = "HEAD"
    if base is None:
        raise click.ClickException(
            "no base for the branch — pass --base-ref or --from-current, or set "
            "topics.base_ref in .goga/config.yml:\ntopics:\n  base_ref: origin/main"
        )

    template = commit_message
    if template is None and section is not None:
        template = section.publish_commit

    line = create_topic(branch_name, base, todo, publish, template, scope.year, switch)
    click.echo(line)
    click.get_current_context().exit(0)


@topics.command("switch")
@click.argument("identifier")
@click.option(
    "--todo",
    is_flag=True,
    default=False,
    help="Open the editor with the switched topic's todo.md after the switch.",
)
@click.pass_obj
def switch(scope: _TopicsScope, identifier: str, todo: bool = False) -> None:
    """Bring the repository onto the branch hosting the requested work.

    IDENTIFIER is a branch name, a topic slug, or their prefix — resolved in
    that order. Several candidates offer a numbered list and a prompt on an
    interactive terminal; already being on the host is an idempotent
    success, and a dirty working tree is a clean error when a mutation is
    needed. With --todo the external editor opens with the switched
    topic's todo.md after the switch — saving overwrites the file without
    a commit, cancelling leaves it untouched; the flag needs an
    interactive terminal and a topic on the host branch. One result line
    on stdout; no pipeline is launched — continuation is a separate
    command.
    """
    line = switch_topic(identifier, todo, scope.year)
    click.echo(line)
    click.get_current_context().exit(0)


@topics.command("delete")
@click.argument("identifiers", nargs=-1, required=True)
@click.option(
    "--yes",
    "-y",
    is_flag=True,
    default=False,
    help="Skip the confirmation; sits after the subcommand token, unlike the group -y year.",
)
@click.pass_obj
def delete(scope: _TopicsScope, identifiers: tuple[str, ...], yes: bool = False) -> None:
    """Delete identified topics — the branch, its origin twin, and the directory.

    Every IDENTIFIER resolves first — a branch name, a topic slug, or
    their prefix; an unknown or ambiguous identifier is a clean error and
    nothing is deleted. The resolved list prints one line per target —
    the topic, then its branch, its remote twin, or (directory only) —
    and one confirmation covers the whole list; a declined answer exits
    0 with nothing deleted. --yes/-y skips the confirmation; without it a
    non-interactive terminal is a clean error. The deletion removes each
    topic's local branch, its origin twin, and its topic directory; the
    current branch hosting a target is a clean error — switch away
    first. One result line on stdout.
    """
    targets = resolve_delete_targets(list(identifiers), scope.year)

    if not yes:
        if not sys.stdin.isatty():
            raise click.ClickException(
                "the deletion confirmation needs an interactive terminal — pass --yes/-y to skip it"
            )

        for target in targets:
            click.echo(f"{target.topic} -> {target.branch or target.remote or '(directory only)'}")

        if not click.confirm(f"Delete {len(targets)} topic(s)?"):
            click.get_current_context().exit(0)

    line = delete_topics(targets, scope.year)
    click.echo(line)
    click.get_current_context().exit(0)
