from __future__ import annotations

from pathlib import Path

import click

from ...onboarding import FileGenerator, InitLogic, Questionnaire, ToolParticipation
from ...scaffold import Scaffold

# Execution modes owned by this integrator.
_UPGRADE = "UPGRADE"
_SCAFFOLD_THEN_ONBOARDING = "SCAFFOLD_THEN_ONBOARDING"
_BARE_ONBOARDING = "BARE_ONBOARDING"


@click.command()
@click.argument("tpl", required=False)
@click.option(
    "--upgrade",
    is_flag=True,
    default=False,
    help="Migrate a previously scaffolded project (copier run_update); no onboarding",
)
@click.option(
    "--ref",
    default=None,
    help="Override the git ref: with <tpl> the URL fragment, with --upgrade the migration target",
)
@click.option(
    "-t",
    "--tool",
    "tools",
    multiple=True,
    help="Invite a tool package into the onboarding session (repeatable)",
)
@click.pass_context
def init(
    ctx: click.Context,
    tpl: str | None,
    upgrade: bool,
    ref: str | None,
    tools: tuple[str, ...],
) -> None:
    """Initialize a new goga project interactively or from a copier template."""
    # 1. --ref placement validation: ref is meaningful only with a template source.
    if ref is not None and tpl is None and not upgrade:
        click.echo("--ref requires <tpl> or --upgrade", err=True)
        ctx.exit(1)
        return

    # 2. Determine mode (mutual-exclusion rejection happens here).
    mode = _resolve_mode(tpl, upgrade, ctx)
    if mode is None:
        return  # _resolve_mode already emitted an error and called ctx.exit(1).

    # 3. Invitation validation: an invitation needs an onboarding session.
    if not _validate_invitation(tools, mode, ctx):
        return  # _validate_invitation already emitted an error and called ctx.exit(1).

    # 4. Dedup the invitations preserving the flag order — one block per tool.
    #    The tuple→list conversion happens here: the domain receives a list.
    invited = list(dict.fromkeys(tools))

    # 5. Already-initialized guard — BARE_ONBOARDING only.
    if mode == _BARE_ONBOARDING and Path(".goga").is_dir():
        click.echo("Project already initialized", err=True)
        ctx.exit(1)
        return

    # 6. Dispatch.
    if mode == _UPGRADE:
        scaffold = Scaffold()
        ctx.exit(scaffold.upgrade(ref))
        return

    if mode == _SCAFFOLD_THEN_ONBOARDING:
        scaffold = Scaffold()
        sc = scaffold.generate(tpl, ref)
        if sc != 0:
            ctx.exit(sc)
            return

    # Both onboarding modes (BARE and template-given) carry the invitations.
    logic = InitLogic(Questionnaire(), FileGenerator(), ToolParticipation(invited=invited))
    ctx.exit(logic.run())


def _resolve_mode(
    tpl: str | None,
    upgrade: bool,
    ctx: click.Context,
) -> str | None:
    """Resolve the execution mode, rejecting the mutually-exclusive combination.

    The mode constant is ``_UPGRADE`` / ``_SCAFFOLD_THEN_ONBOARDING`` /
    ``_BARE_ONBOARDING``; ``None`` is returned when the combination is invalid
    (the error is emitted and ``ctx.exit(1)`` called before returning ``None``).

    Args:
        tpl: the optional copier template source argument, or ``None``.
        upgrade: whether ``--upgrade`` was passed.
        ctx: the click context, used to exit with code 1 on invalid input.

    Returns:
        The mode constant, or ``None`` for an invalid combination.
    """
    if upgrade and tpl is not None:
        click.echo(
            "<tpl> and --upgrade are mutually exclusive "
            "(--upgrade updates existing state tied to a specific repository)",
            err=True,
        )
        ctx.exit(1)
        return None

    if upgrade:
        return _UPGRADE

    if tpl is not None:
        return _SCAFFOLD_THEN_ONBOARDING

    return _BARE_ONBOARDING


def _validate_invitation(
    tools: tuple[str, ...],
    mode: str,
    ctx: click.Context,
) -> bool:
    """Validate the invitation flag against the resolved execution mode.

    An invitation acts in a session that runs onboarding — ``--upgrade``
    runs none, so the combination is rejected.

    Args:
        tools: the invited tool names from the repeated ``-t/--tool`` flag.
        mode: the resolved execution mode constant.
        ctx: the click context, used to exit with code 1 on invalid input.

    Returns:
        ``True`` when the combination is valid; ``False`` when it was
        rejected (the error is emitted and ``ctx.exit(1)`` called first).
    """
    if tools and mode == _UPGRADE:
        click.echo("-t/--tool requires an onboarding session and --upgrade runs none", err=True)
        ctx.exit(1)
        return False

    return True
