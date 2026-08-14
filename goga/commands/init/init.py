from __future__ import annotations

from pathlib import Path

import click

from ...onboarding import FileGenerator, InitLogic, Questionnaire
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
@click.pass_context
def init(ctx: click.Context, tpl: str | None, upgrade: bool, ref: str | None) -> None:
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

    # 3. Already-initialized guard — BARE_ONBOARDING only.
    if mode == _BARE_ONBOARDING and Path(".goga").is_dir():
        click.echo("Project already initialized", err=True)
        ctx.exit(1)
        return

    # 4. Dispatch.
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
        logic = InitLogic(Questionnaire(), FileGenerator())
        ctx.exit(logic.run())
        return

    # BARE_ONBOARDING
    logic = InitLogic(Questionnaire(), FileGenerator())
    ctx.exit(logic.run())


def _resolve_mode(
    tpl: str | None,
    upgrade: bool,
    ctx: click.Context,
) -> str | None:
    """Resolve the execution mode, rejecting the mutually-exclusive combination.

    Returns the mode constant (``_UPGRADE`` / ``_SCAFFOLD_THEN_ONBOARDING`` /
    ``_BARE_ONBOARDING``), or ``None`` when the combination is invalid (the
    error is emitted and ``ctx.exit(1)`` called before returning ``None``).
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
