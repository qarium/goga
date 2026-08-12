from __future__ import annotations

import logging

import click

from .generator import FileGenerator
from .questionnaire import Questionnaire

logger = logging.getLogger(__name__)


class InitLogic:
    """Orchestrator for project initialization.

    Wires together Questionnaire and FileGenerator via dependency injection.
    """

    def __init__(self, questionnaire: Questionnaire, generator: FileGenerator) -> None:
        self._questionnaire = questionnaire
        self._generator = generator

    def run(self) -> int:
        """Run the full init flow: ask → generate.

        Returns:
            0 on success, 1 on any error.
        """
        try:
            answers = self._questionnaire.ask()
            self._generator.generate(answers)
            return 0
        except click.Abort:
            return 1
        except Exception as exc:
            logger.error("init flow failed", extra={"error": str(exc)})
            click.echo(f"Error: {exc}", err=True)
            return 1
