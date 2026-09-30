"""The ``goga topics`` command group — the CLI surface of the topics domain.

The click group declared in the cell CODEMANIFEST with ``location:
topics.py``: the ``board``/``create``/``switch``/``delete``/``clear``/
``update``/``publish``/``propagate`` subcommands over the topics
domain. The group
carries the year scope every subcommand shares and is a thin wrapper —
it resolves the inputs, delegates every computation to the domain
routines of ``goga.topics``, and renders the board through the
``render`` module in its two views
and its JSON form: the default view aggregates the collected records
into one entry per topic that still has its own branch, ``--per-host``
keeps the per-host audit records, and ``--json`` prints the
machine-readable projection of either view; ``--host`` filters by exact
hosting-branch display name and ``--topic`` by exact topic slug — both
repeatable, the union across values, composed with each other; the
board loads the project configuration the ``clear`` way and hands the
configured ``topics.base_ref`` into both collection views — the
divergence marker of the info view and the JSON projection. The
creation inputs resolve their
values at this layer: the base — ``--base-ref``, the ``topics`` section
of the project configuration, the current HEAD under ``--from-current``
— and the commit message template — ``--commit/-c``,
``topics.create.commit``, the built-in default of the domain; the
configuration is read
lazily, only for values no flag provided. The optional-value
``--todo/-t`` option is mapped into the domain's source declaration at
this layer — a value passes through as the todo, the value-less form
declares the piped stdin as the source, and absent or empty declares
nothing; no todo resolution happens here. The deletion and the
merged-topic clear are confirmed at this layer — one confirmation for
the whole resolved list; the clear resolves its base the same lazy way
— ``--base-ref``, the ``topics`` section — minus the current-HEAD rung,
and its scope belongs to the domain. The exchange pair follows the
same base resolution — ``--base-ref``, then ``topics.base_ref``, no
current-HEAD rung — and reads the strategy and the message template
verbatim from ``topics.update.*`` / ``topics.propagate.*`` with no
validation here: ``update`` delegates to the domain with the optional
``--publish/-p`` push flag and asks no confirmation, while
``propagate`` resolves the read-only plan first and asks exactly one
confirmation — naming the topic, the base, and the inherent push —
between the plan and its execution, with ``--yes/-y`` as the escape.
The publication delivery is an operation of its own: ``publish``
delegates to the domain with the identifier and the scoped year alone —
no confirmation, no configuration keys — and echoes the single result
line naming the outcome kind.
No inventory
walking, no switch resolution, no git access, no stdin read, and no
editor session live here — the ``--switch/-s`` flag passes through and
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
from ...config.hooks import ConfigHooks
from ...topics import (
    aggregate_topic_board,
    collect_topic_board,
    create_topic,
    delete_topics,
    execute_propagation,
    publish_existing_topic,
    resolve_clear_targets,
    resolve_delete_targets,
    resolve_propagation,
    switch_topic,
    update_topic,
)
from .render import render_board_json, render_topic_board, render_topic_host_rows

# The reserved sentinel of the optional-value --todo option (the click
# practice's rule): a marker no plausible todo value carries, delivered
# by the value-less form and mapped in the callback into the stdin
# source declaration.
_TODO_DECLARED = "__declared__"


@dataclass(kw_only=True)
class _TopicsScope:
    """The year scope shared by every subcommand of the group."""

    year: str | None = None


def _topics_section() -> TopicsConfig | None:
    """Read the topics section of .goga/config.yml — None when unset or unconfigured.

    The successful load delivers the config-amendment checkpoint; the
    returned section is the effective one and its summary lines print to
    stderr. A missing file counts as unset — nothing was loaded, so no
    checkpoint is offered.
    """
    try:
        authored = load_project_config()
        # The checkpoint joins the load inside the try: its ValueError (a
        # hard failure) or ImportError (a broken tool package) folds into
        # the same clean-error wrapper as a failed load.
        overlay = ConfigHooks().amend_config(config=authored)
    except FileNotFoundError:
        return None
    except OSError as exc:
        # A present-but-unreadable file (a directory in its place, a
        # permission failure) surfaces as its own clean error — the loader
        # documents OSError on its Raises surface. FileNotFoundError, an
        # OSError subclass, is already handled above as "unset".
        raise click.ClickException(str(exc)) from exc
    except (KeyError, ValueError, ImportError, yaml.YAMLError) as exc:
        # ImportError — a broken tool package facade during the registry
        # build — is the same clean error, never a raw traceback.
        raise click.ClickException(str(exc)) from exc

    # The summary lines print here — the caller's stdout stays the data
    # surface of the command (nothing prints when nothing applied).
    for line in overlay.summary_lines:
        click.echo(line, err=True)

    return overlay.config.topics


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
    help="Add the todo and delivery columns to the table.",
)
@click.option(
    "--host",
    multiple=True,
    default=(),
    help="Hosting branch to keep — an exact display-name match; repeatable, the union across values.",
)
@click.option(
    "--per-host",
    is_flag=True,
    default=False,
    help="Print the audit view — one row per topic and hosting branch.",
)
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    default=False,
    help="Print the machine-readable projection of either view instead of the table.",
)
@click.option(
    "--topic",
    multiple=True,
    default=(),
    help="Topic slug to keep — an exact match; repeatable, the union across values.",
)
@click.pass_obj
def board(  # noqa: PLR0913, PLR0917 — the CODEMANIFEST-declared CLI surface
    scope: _TopicsScope,
    remote: bool = False,
    info: bool = False,
    host: tuple[str, ...] = (),
    per_host: bool = False,
    json_output: bool = False,
    topic: tuple[str, ...] = (),
) -> None:
    """Print the board — the cross-branch topic inventory of the scoped year.

    The default view is one four-column row per topic that still has its
    own branch: topic, branch, hosts, statuses — every branch carrying
    the topic's history sits in the hosts column, wrapped whole onto
    continuation lines, and the row of the current branch carries an
    asterisk. --info/-i adds the todo and delivery columns between hosts
    and statuses — the delivery column carries the topic's divergence
    marker against the configured base (base / up-to-date / propagated /
    need-update — the topic sits on the base, carries it with no lag, is
    carried by it whole, or diverged from it; empty when no base is
    configured or it does not resolve).
    --per-host switches to the audit view — one three-column row per
    topic and hosting branch: topic, branch, statuses, with the todo
    and delivery columns between branch and statuses under --info.
    --host NAME keeps
    only the named hosting branches — an exact display-name match,
    repeatable, the union across values; it filters the topics of the
    default view and the records of the audit view, and an unknown name
    is the empty board, never an error. --topic SLUG keeps only the
    named topics — an exact slug match, repeatable, the union across
    values, composed with --host; an unknown slug is the empty board,
    never an error. --json prints the
    machine-readable projection of either view instead of the table —
    pretty-printed with sorted keys; it cannot combine with --info, the
    todo is always present in the JSON. --remote/-r reads
    remote-tracking refs instead of local branches. An empty board
    prints nothing as a table, [] as JSON, and exits 0 — it is not an
    error. The year defaults to the current one and is never printed.
    """
    if json_output and info:
        raise click.ClickException("--json cannot combine with --info — the todo is always present in the JSON records")

    # The configuration is read once, the clear way — the divergence
    # marker needs the configured base; a missing file counts as unset.
    section = _topics_section()
    base = section.base_ref if section is not None else None

    if not per_host:
        # The default view collects the full inventory — the hosts lists
        # need every hosting branch — and hands both display filters to
        # the pure aggregate projection alone.
        records = collect_topic_board(scope.year, remote, base_ref=base)
        entries = aggregate_topic_board(records, host, topic)
    else:
        records = collect_topic_board(scope.year, remote, hosts=host, topics=topic, base_ref=base)

    if json_output:
        render_board_json(entries if not per_host else records)
    else:
        width = shutil.get_terminal_size().columns

        if not per_host:
            render_topic_board(entries, width, info)
        else:
            render_topic_host_rows(records, width, info)

    click.get_current_context().exit(0)


@topics.command("create")
@click.argument("branch_name")
@click.option(
    "--todo",
    "-t",
    "todo",
    is_flag=False,
    flag_value=_TODO_DECLARED,
    default=None,
    metavar="[TEXT]",
    help="Todo of the fresh work — a value is the todo itself, the value-less form takes it "
    "from the piped stdin, and an empty value counts as absent; the literal __declared__ is "
    "the reserved marker of the stdin declaration.",
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
    help="Commit message template, publication-only; beats topics.create.commit — "
    "{slug} takes the topic slug, {base} the base name.",
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
    todo_from_stdin: bool = False,
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
    --todo/-t carries three states: a value is the todo itself; the
    value-less form declares the piped stdin as the todo source — the
    pipe is read fully once, decoded strictly as UTF-8 (anything else is
    a clean error naming the option), and its content becomes the todo
    verbatim; absent or an empty value declares nothing. Content on the
    pipe without the declaration is never silently ignored — it is a
    clean error naming the option. With nothing declared a terminal
    opens the external editor for the todo; without a terminal the
    default path is a clean error naming the todo sources, while a
    headless --switch/-s creation succeeds with no todo at all.
    By default the branch is planted at one commit carrying the topic's
    todo.md and you stay on your branch — the todo is required on this
    path. --switch/-s checks out the fresh branch instead — the topic
    directory and todo.md land in the working copy uncommitted and the
    todo is optional. On a terminal without --publish the publication ask
    appears once a todo is resolved — never when the todo came from the
    pipe; declining takes the local path. --publish/-p publishes to
    origin without switching and without the ask; a failed publication
    rolls back fully. --commit/-c — the message template;
    topics.create.commit — is publication-only. One result line on stdout.
    """
    if commit_message is not None and not publish:
        raise click.ClickException("--commit is publication-only — it acts only together with --publish")

    if switch and publish:
        raise click.ClickException("--switch acts only without --publish — the publication never switches")

    # The three states of the optional-value --todo option map into the
    # domain declaration: the reserved sentinel declares the piped stdin
    # as the source, an empty real value counts as an absent option, and
    # everything else is the value; the stdin read and the editor entry
    # belong to the domain.
    if todo == _TODO_DECLARED:
        todo = None
        todo_from_stdin = True
    elif todo == "":
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
    if template is None and section is not None and section.create is not None:
        template = section.create.commit

    line = create_topic(branch_name, base, todo, todo_from_stdin, publish, template, scope.year, switch)
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


@topics.command("clear")
@click.option(
    "--base-ref",
    default=None,
    help="Base whose tree defines the clear scope; beats topics.base_ref of .goga/config.yml.",
)
@click.option(
    "--yes",
    "-y",
    is_flag=True,
    default=False,
    help="Skip the confirmation; sits after the subcommand token, unlike the group -y year.",
)
@click.pass_obj
def clear(scope: _TopicsScope, base_ref: str | None = None, yes: bool = False) -> None:
    """Clear the merged topics of the scoped year.

    The base resolves as --base-ref, then topics.base_ref of
    .goga/config.yml — there is no current-HEAD rung, unlike create; no
    base at all is a clean error naming the flag and the configuration
    line. The scope is every topic of the year that still has its own
    branch and whose history the base ref's tree carries — the merged
    work; a branchless topic is out of scope silently. An empty scope
    is one line and exit 0 — not an error. The resolved list prints one
    line per target — the topic, then its branch, its remote twin, or
    (directory only) — and one confirmation covers the whole list; a
    declined answer exits 0 with nothing deleted. --yes/-y skips the
    confirmation; without it a non-interactive terminal is a clean
    error. One result line on stdout.
    """
    # The configuration is read lazily — only when the flag is absent;
    # a missing file counts as unset.
    base = base_ref

    if base is None:
        section = _topics_section()
        base = section.base_ref if section is not None else None
    if base is None:
        raise click.ClickException(
            "no base for the clear — pass --base-ref or set topics.base_ref in .goga/config.yml:\n"
            "topics:\n  base_ref: origin/release/2.0.0"
        )

    targets = resolve_clear_targets(base, scope.year)

    if not targets:
        click.echo("No merged topics to clear.")
        click.get_current_context().exit(0)

    if not yes:
        if not sys.stdin.isatty():
            raise click.ClickException(
                "the clear confirmation needs an interactive terminal — pass --yes/-y to skip it"
            )

        for target in targets:
            click.echo(f"{target.topic} -> {target.branch or target.remote or '(directory only)'}")

        if not click.confirm(f"Clear {len(targets)} topic(s)?"):
            click.get_current_context().exit(0)

    line = delete_topics(targets, scope.year)
    click.echo(line)
    click.get_current_context().exit(0)


@topics.command("update")
@click.argument("identifier", required=False)
@click.option(
    "--base-ref",
    default=None,
    help="Base to bring the topic up to; beats topics.base_ref of .goga/config.yml.",
)
@click.option(
    "--publish",
    "-p",
    is_flag=True,
    default=False,
    help="Push the refreshed branch to origin after the update.",
)
@click.pass_obj
def update(
    scope: _TopicsScope,
    identifier: str | None = None,
    base_ref: str | None = None,
    publish: bool = False,
) -> None:
    """Bring a topic up to its base — merged, rebased, or fast-forwarded.

    An omitted IDENTIFIER addresses the current topic; a given one is a
    branch name, a topic slug, or their prefix. The base resolves as
    --base-ref, then topics.base_ref of .goga/config.yml — there is no
    current-HEAD rung; no base at all is a clean error naming the flag
    and the configuration line. The strategy and the commit message
    template come verbatim from topics.update.strategy /
    topics.update.commit — no validation happens here; an invalid
    strategy is the domain's clean configuration error. A topic other
    than the current one is updated checkout-free; the current one is
    updated in place behind a read-only pre-flight, so a dirty working
    tree or a conflicting update is a clean error naming manual git.
    An already-current topic is an idempotent success. --publish/-p
    pushes the refreshed branch after the update — a rebase-based one
    with a lease against the pre-rebase tip; a failed push leaves the
    local update standing. No confirmation — the operation touches the
    topic branch alone. One result line on stdout.
    """
    # The configuration is read once — the strategy and the template
    # always come from it (no flags exist for them), and the base joins
    # the same read when the flag is absent.
    section = _topics_section()

    base = base_ref

    if base is None and section is not None:
        base = section.base_ref
    if base is None:
        raise click.ClickException(
            "no base for the update — pass --base-ref or set topics.base_ref in .goga/config.yml:\n"
            "topics:\n  base_ref: origin/main"
        )

    strategy = None
    template = None
    if section is not None and section.update is not None:
        strategy = section.update.strategy
        template = section.update.commit

    line = update_topic(identifier, base, strategy, template, publish, scope.year)
    click.echo(line)
    click.get_current_context().exit(0)


@topics.command("publish")
@click.argument("identifier", required=False)
@click.pass_obj
def publish(scope: _TopicsScope, identifier: str | None = None) -> None:
    """Deliver an existing topic branch to origin.

    An omitted IDENTIFIER addresses the current topic; a given one is a
    branch name, a topic slug, or their prefix. The delivery resolves
    one of three success kinds — pushed, up-to-date, remote-ahead — and
    a diverged origin twin is a clean error naming both tips. No
    confirmation, no force, no configuration keys. One result line on
    stdout.
    """
    line = publish_existing_topic(identifier, scope.year)
    click.echo(line)
    click.get_current_context().exit(0)


@topics.command("propagate")
@click.argument("identifier", required=False)
@click.option(
    "--base-ref",
    default=None,
    help="Base the topic is delivered into; beats topics.base_ref of .goga/config.yml.",
)
@click.option(
    "--yes",
    "-y",
    is_flag=True,
    default=False,
    help="Skip the confirmation; sits after the subcommand token, unlike the group -y year.",
)
@click.pass_obj
def propagate(
    scope: _TopicsScope,
    identifier: str | None = None,
    base_ref: str | None = None,
    yes: bool = False,
) -> None:
    """Deliver a topic into its base — merged, fast-forwarded, or squashed.

    An omitted IDENTIFIER addresses the current topic; a given one is a
    branch name, a topic slug, or their prefix. The base resolves as
    --base-ref, then topics.base_ref of .goga/config.yml — there is no
    current-HEAD rung; no base at all is a clean error naming the flag
    and the configuration line. The strategy and the commit message
    template come verbatim from topics.propagate.strategy /
    topics.propagate.commit — no validation happens here. The plan is
    resolved read-only first, then exactly one confirmation covers the
    delivery — it names the topic, the target base, and the push to
    origin that every propagation performs; a declined answer exits 0
    with nothing done. --yes/-y skips the confirmation; without it a
    non-interactive terminal is a clean error. The delivery itself is
    checkout-free and pushes the base's branch inherently; a base that
    moved concurrently is retried once, and every failure rolls back to
    the pre-resolution state. A nothing-to-do delivery — the base
    already carries the topic's commits or its content — is an
    idempotent success. The topic's branch and directory are untouched.
    One result line on stdout.
    """
    # The configuration is read once — the strategy and the template
    # always come from it (no flags exist for them), and the base joins
    # the same read when the flag is absent.
    section = _topics_section()

    base = base_ref

    if base is None and section is not None:
        base = section.base_ref
    if base is None:
        raise click.ClickException(
            "no base for the propagation — pass --base-ref or set topics.base_ref in .goga/config.yml:\n"
            "topics:\n  base_ref: origin/main"
        )

    strategy = None
    template = None
    if section is not None and section.propagate is not None:
        strategy = section.propagate.strategy
        template = section.propagate.commit

    plan = resolve_propagation(identifier, base, strategy, template, scope.year)

    if not yes:
        if not sys.stdin.isatty():
            raise click.ClickException(
                "the propagation confirmation needs an interactive terminal — pass --yes/-y to skip it"
            )

        if not click.confirm(f"Propagate topic {plan.target.topic} into '{base}' (pushes to origin)?"):
            click.get_current_context().exit(0)

    line = execute_propagation(plan)
    click.echo(line)
    click.get_current_context().exit(0)
