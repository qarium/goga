"""The orchestrator of one initialization session.

The entity declared in the domain CODEMANIFEST with ``location: logic.py``:
the orchestrator ``InitLogic`` — the eight-step run that guards on the
existing config, derives the image tag from the installed version, delivers
both tool participation moments, assembles the session plan, runs the
survey, generates the artifacts, and renders the file report with
attribution. The collaborators are injected; the error tiers are the
session's own: tool failures stay soft inside the collaborators, session
errors are one clean message, a user abort is quiet.
"""

from __future__ import annotations

import logging
from pathlib import Path

import click

from ..config import resolve_project_name
from ..version import host_goga_version, minor_version
from .generator import FileGenerator
from .participation import ToolParticipation
from .questions import SessionAnswers
from .survey import Questionnaire, apply_skips, assemble_session_plan, core_questions

logger = logging.getLogger(__name__)

_CONFIG_PATH = Path(".goga") / "config.yml"
_CONVENTIONS_PATH = Path(".goga") / "usages" / "conventions.md"


class InitLogic:
    """The orchestrator of one initialization session.

    Wires together the three injected collaborators — the survey engine, the
    artifact generator, and the tool participation mediator — and runs the
    whole session: guard, tag derivation, declaration moment, plan assembly
    with the declared skips, survey, amendment moment, generation with the
    attributed file report.

    Requirements:
        - A tool failure never changes the exit code — the softness of the
          tool moments is theirs
        - A session error is one clean message — a broken package import,
          an unreadable version, an empty required field at generation —
          never a traceback
    """

    def __init__(
        self,
        questionnaire: Questionnaire,
        generator: FileGenerator,
        participation: ToolParticipation,
    ) -> None:
        """Create the orchestrator of one session.

        Args:
            questionnaire: The survey engine asking the plan.
            generator: The artifact generator writing the run's files.
            participation: The tool participation mediator delivering both
                tool moments.
        """
        self._questionnaire = questionnaire
        self._generator = generator
        self._participation = participation

    def run(self) -> int:
        """Run the whole session.

        Algorithm:
            1. An existing .goga/config.yml ends the session — no question
               is asked, no tool event is delivered, no artifact is written
            2. Read the installed goga version and derive its minor line
               for the image hints
            3. Deliver the declaration moment via the participation mediator
            4. Build the core tree, assemble the plan with the collected
               declarations, and apply the declared skips
            5. Run the survey into the answer space
            6. Deliver the amendment moment and commit the surviving tool
               contributions
            7. Generate the artifacts and render the file report with the
               tool attribution
            8. Return 0

        Returns:
            ``0`` on success; ``1`` on a session error or a user abort.

        Raises:
            Nothing — every failure is translated into the exit code; a
            session error additionally emits one clean message to stderr.
        """
        try:
            return self._run_session()
        except click.Abort:
            return 1  # a user abort is quiet — no message, no traceback
        except Exception as exc:
            logger.error("the init session failed", extra={"error": str(exc)})
            click.echo(f"Error: {exc}", err=True)
            return 1

    def _run_session(self) -> int:
        """Run the eight session steps — every exception is the caller's tier.

        Returns:
            ``0`` — the session completed.

        Raises:
            click.Abort: A user interrupt of the survey — the quiet tier.
            Exception: A session error — the clean-message tier; the single
                fatal participation case (a broken package import) arrives
                here as the platform-wrapped ImportError naming the package.
        """
        # 1. Whoever created .goga/config.yml first wins — the session ends.
        if _CONFIG_PATH.is_file():
            return 0

        # 2. The image hints carry the minor line of the installed version.
        tag = minor_version(host_goga_version())

        # 3. Moment one — the tool declarations of the run.
        declarations = self._participation.collect_declarations()

        # 4. The plan: the core tree, the tool blocks, the declared skips.
        project_name = resolve_project_name()
        convention_exists = _CONVENTIONS_PATH.is_file()
        core = core_questions(tag, project_name, convention_exists)
        plan = assemble_session_plan(core, declarations)
        skips = [(declaration.tool, path) for declaration in declarations for path in declaration.skips]
        plan = apply_skips(plan, skips)

        # 5. The survey fills the answer space at the plan paths.
        answers = SessionAnswers(tools=plan.tools)
        self._questionnaire.run(plan, answers)

        # 6. Moment two — the committed tool contributions.
        contributions = self._participation.collect_contributions(answers)

        # 7. The artifacts and the attributed report.
        for entry in self._generator.generate(answers, contributions):
            if entry.tool is None:
                click.echo(f"created {entry.path}")
            else:
                click.echo(f"created {entry.path} (tool: {entry.tool})")

        # 8. Tool failures never change the exit code.
        return 0
