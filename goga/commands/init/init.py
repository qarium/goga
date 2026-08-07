from __future__ import annotations

import click

from ...init import FileGenerator, InitLogic, Questionnaire


@click.command()
@click.pass_context
def init(ctx: click.Context) -> None:
    """Initialize a new goga project interactively."""
    questionnaire = Questionnaire()
    generator = FileGenerator()
    logic = InitLogic(questionnaire, generator)
    exit_code = logic.run()
    ctx.exit(exit_code)
