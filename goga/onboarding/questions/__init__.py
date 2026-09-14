"""Questions cell — the declarative question-and-answer model of the session.

The owner of the question records of every kind, the nesting groups, and
the session answer space of the onboarding session. Data and pure answer
operations only — no interactivity, no filesystem, no tool delivery. The
question records are immutable; the answer space is the single mutable
accumulator of one run.
"""

from .questions import Question, QuestionGroup

__all__: list[str] = ["Question", "QuestionGroup"]
