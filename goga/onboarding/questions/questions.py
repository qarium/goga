"""The question records of the onboarding session.

The entities declared in the cell CODEMANIFEST with ``location: questions.py``:
the question record ``Question`` and the nesting node ``QuestionGroup``. The
records are immutable declarative data of the survey — rendering the question
and validating the answer value belong to the survey engine. The kind fixes
the parameterization; the tree path of a node — the ids from the root to the
node joined by dots — addresses the node in skip requests and answer paths.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class Question:
    """One declarative question record — the survey unit of the session.

    The record carries data only: rendering the question and validating the
    answer value belong to the survey engine. The kind fixes the
    parameterization — ``choices`` for the choice kind, ``default`` for the
    input and confirm kinds, ``keys`` for the pairs kind.

    Attributes:
        id: The local name of the question within its parent — unique among
            the siblings of its tree position.
        kind: The question kind — choice, input, confirm, or pairs.
        prompt: The user-facing prompt text.
        choices: The offered values of the choice kind.
        default: The preselected value or the input default; a bool for the
            confirm kind.
        keys: The proposed keys of the repeated key-value collection of the
            pairs kind.

    Requirements:
        no validation runs at construction — the kinds are checked at ask
        time, not here; the answer value of each kind is a string for choice
        and input, a boolean for confirm, a mapping of strings for pairs.
    """

    id: str
    kind: str
    prompt: str
    choices: list[str] | None = None
    default: str | bool | None = None
    keys: list[str] | None = None


@dataclass(frozen=True, kw_only=True)
class QuestionGroup:
    """One nesting node of the question tree — a section.

    A section whose answer is the mapping of its children's answers. A group
    with ``children`` of ``None`` is a purely structural node carrying no
    prompt.

    Attributes:
        id: The local name of the group within its parent — unique among the
            siblings of its tree position.
        prompt: The optional section heading; a purely structural node
            carries none.
        children: The nested questions and groups, in survey order.

    Requirements:
        the answer value of a group is a nested mapping keyed by child ids —
        never a flat dotted key; a group declared by a tool is limited to one
        nesting level with simple children.
    """

    id: str
    prompt: str | None = None
    children: list[Question | QuestionGroup] | None = None
