"""The ``goga topics`` command group — the CLI surface of the topics domain.

The click group declared in the cell CODEMANIFEST with ``location:
topics.py``: the ``board``/``create``/``switch`` subcommands over the
topics domain. The group carries the year scope every subcommand shares and
is a thin wrapper — it resolves the inputs, delegates every computation to
the domain routines of ``goga.topics``, and renders the board through the
``render`` module. The todo of the fresh work is resolved at this layer:
the ``--todo/-t`` value acts as given, a bare flag starts the interactive
multi-line entry. The fast creation-and-publication mode of ``create``
resolves its own inputs at this layer: a flag beats the ``topics`` section
of the project configuration, which beats the built-in default. No
inventory walking, no switch resolution, and no git access live here;
domain errors surface as clean CLI errors.
"""

from __future__ import annotations

import shutil
import sys
from dataclasses import dataclass

import click
import yaml
from click import termui

from ...config import TopicsConfig, load_project_config
from ...topics import collect_topic_board, create_topic, publish_topic, switch_topic
from .render import render_topic_board

# The built-in template of the publish path — the lowest row of the
# flag > topics section > default resolution matrix.
_DEFAULT_PUBLISH_COMMIT = "goga: create topic {slug}"


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


def _prompt_multiline(label: str) -> str | None:
    """Collect a multi-line text interactively — one input per line.

    The prompt states the rule itself: a lone ``.`` line or Ctrl+D (EOF)
    finishes the entry, every entered line continues the text, and an empty
    line is an allowed text line — paragraphs survive. No line entered
    cancels the entry and returns None — an empty text is never produced;
    the emptiness check runs on the joined text, so a single blank line
    cancels the entry the same way. A non-interactive terminal is a clean
    error raised before the first prompt; a Ctrl+C aborts the command —
    it is not a terminator.

    Args:
        label: the human name of the collected value — used in the prompt
            and in the non-interactive error.

    Returns:
        The joined text — paragraphs separated by single newlines — or None
        when the entry was cancelled.
    """
    if not sys.stdin.isatty():
        raise click.ClickException(f"{label} entry needs an interactive terminal")

    click.echo(f"Enter the {label}. Finish with a lone '.' line or Ctrl+D.")
    lines: list[str] = []

    while True:
        try:
            # Resolved through the module attribute at call time — a
            # from-imported binding would never see the CliRunner patch.
            line = termui.visible_prompt_func("")
        except EOFError:
            break
        except KeyboardInterrupt:
            raise click.Abort() from None

        if line == ".":
            break

        lines.append(line)

    text = "\n".join(lines)
    return text if text else None


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
    is_flag=False,
    flag_value="",
    metavar="[TEXT]",
    help="Todo of the fresh work; without a value — interactive entry",
)
@click.option(
    "--publish",
    "-p",
    is_flag=True,
    default=False,
    help="Create the work off an explicit base and publish it to origin without switching.",
)
@click.option(
    "--base-ref",
    default=None,
    help="Base revision of the published branch; beats topics.base_ref of .goga/config.yml.",
)
@click.option(
    "--commit",
    "-c",
    "commit_message",
    default=None,
    help="Commit message template; beats topics.publish_commit — {slug} takes the topic slug.",
)
@click.pass_obj
def create(  # noqa: PLR0913, PLR0917 — the CODEMANIFEST-declared CLI surface
    scope: _TopicsScope,
    branch_name: str,
    todo: str | None = None,
    publish: bool = False,
    base_ref: str | None = None,
    commit_message: str | None = None,
) -> None:
    """Create fresh work — a branch with the name as entered and its topic directory.

    The branch name is taken verbatim; the topic directory of the scoped
    year is created from its slug. An explicit --todo/-t also writes the
    topic todo file todo.md — the multi-line text as entered plus one
    trailing newline; the flag given without a value starts the
    interactive multi-line entry on a terminal (a lone '.' line or Ctrl+D
    finishes, nothing entered cancels). Without a todo no todo file is
    written. The current branch already hosting the same slug is an
    idempotent success. Occupied names and empty slugs re-ask on an
    interactive terminal and fail with a clean error otherwise. One
    result line on stdout.

    --publish/-p is the fast mode: the branch is created off an explicit
    base — --base-ref, otherwise topics.base_ref of .goga/config.yml —
    carrying one commit with the topic todo file — the message template
    from --commit/-c, otherwise topics.publish_commit, otherwise the
    built-in default — and is pushed to origin without switching. The
    todo is required in this mode — the board reads the topic through
    todo.md — and a failed publication rolls back fully: the planted
    branch is deleted and one clean error names the reason.
    """
    if not publish and (base_ref is not None or commit_message is not None):
        raise click.ClickException("--base-ref and --commit act only together with --publish")

    # The empty string is the entry marker of the bare flag, never a
    # written value; a cancelled entry continues as without the flag.
    if todo == "":
        todo = _prompt_multiline("todo")

    if publish and todo is None:
        raise click.ClickException(
            "--publish needs a todo — pass --todo/-t; the board reads the topic through todo.md"
        )

    if not publish:
        # Interim delegation (superseded by the full CLI rework): the
        # domain owns the todo resolution now, and "HEAD" reproduces the
        # old behavior — a branch from the current HEAD.
        line = create_topic(branch_name, "HEAD", todo, year=scope.year)
        click.echo(line)
        click.get_current_context().exit(0)

    # The configuration is read lazily — only when a value no flag
    # provided has to come from it; both flags given means zero reads.
    section = _topics_section() if base_ref is None or commit_message is None else None

    base = base_ref if base_ref is not None else (section.base_ref if section is not None else None)
    if base is None:
        raise click.ClickException(
            "no base for the published branch — set topics.base_ref in .goga/config.yml or pass --base-ref:\n"
            "topics:\n  base_ref: origin/main"
        )

    template = (
        commit_message
        if commit_message is not None
        else (
            section.publish_commit
            if section is not None and section.publish_commit is not None
            else _DEFAULT_PUBLISH_COMMIT
        )
    )

    line = publish_topic(branch_name, todo, base, template, scope.year)
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
    line = switch_topic(identifier, year=scope.year)
    click.echo(line)
    click.get_current_context().exit(0)
