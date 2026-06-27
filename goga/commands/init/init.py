from __future__ import annotations

import click

from ...init import FileGenerator, InitLogic, Questionnaire


@click.command()
@click.pass_context
def init(ctx: click.Context) -> None:
    """Initialize a new goga project interactively.

    Args:
        ctx: Click execution context used to control process exit codes.
    """
    questionnaire = Questionnaire()
    generator = FileGenerator()
    logic = InitLogic(questionnaire, generator)
    exit_code = logic.run()
    ctx.exit(exit_code)
