"""Facade of the onboarding domain — the initialization session orchestration.

The owner of the session orchestration and the re-export point of the
public session API of the leaf cells: the question-and-answer model, the
survey, the tool participation, and the artifact generation. Consumers
address the domain through this facade only.
"""

from .generator import CreatedFile, FileGenerator
from .logic import InitLogic
from .participation import ToolContribution, ToolDeclaration, ToolParticipation
from .questions import Question, QuestionGroup, SessionAnswers
from .survey import Questionnaire, SessionPlan, apply_skips, assemble_session_plan, core_questions

# The order is the embedding order of the domain CODEMANIFEST (the 13
# re-exported entities followed by the orchestrator) — a contract order,
# deliberately not the isort-style sort.
__all__: list[str] = [  # noqa: RUF022
    "Question",
    "QuestionGroup",
    "SessionAnswers",
    "SessionPlan",
    "Questionnaire",
    "core_questions",
    "assemble_session_plan",
    "apply_skips",
    "ToolParticipation",
    "ToolDeclaration",
    "ToolContribution",
    "FileGenerator",
    "CreatedFile",
    "InitLogic",
]
