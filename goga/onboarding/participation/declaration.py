"""The session declaration surface of one tool.

The entity declared in the cell CODEMANIFEST with ``location: declaration.py``:
the moment-one surface ``ToolDeclaration``. The surface is delivered to one
tool's declare-session hook — the invitation marker and the buffer of the
declared questions and skip paths. A hook of a non-invited tool returns
immediately; the buffered data is read by the engine after the delivery of
the moment completes.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from ..questions import Question, QuestionGroup

logger = logging.getLogger(__name__)


def _has_nested_group(group: QuestionGroup) -> bool:
    """Report whether the children of the group contain a nested group.

    Args:
        group: The declared group to inspect.

    Returns:
        True when at least one child is itself a ``QuestionGroup`` — the
        violation of the one-level rule.
    """
    return group.children is not None and any(isinstance(child, QuestionGroup) for child in group.children)


@dataclass(kw_only=True)
class ToolDeclaration:
    """The moment-one surface of one tool — the declaration context and its buffer.

    The object a declare-session hook receives as ``context``: the invitation
    marker the hook checks first, the ``declare`` buffer of the tool's
    questions and one-level groups, and the ``skip`` buffer of the raw skip
    paths. The local names are the tool's own — the engine qualifies them
    with the tool identity once it reads the buffers after the delivery of
    the moment completes.

    Attributes:
        tool: The tool identity of the owning tool.
        invited: The invitation marker — False marks a subscribed tool the
            session did not invite.
        questions: The declared questions and groups, in declaration order.
        skips: The declared skip paths, in declaration order.

    Requirements:
        a group of a tool is limited to one nesting level with simple
        children — a violation is refused with a warning naming the tool and
        the reason, never an exception, and the element is not buffered.
    """

    tool: str
    invited: bool
    questions: list[Question | QuestionGroup] = field(init=False, default_factory=list)
    skips: list[str] = field(init=False, default_factory=list)

    def declare(self, item: Question | QuestionGroup) -> None:
        """Declare one question or one group of the tool's block.

        Args:
            item: The question record or the one-level group.
        """
        if isinstance(item, QuestionGroup) and _has_nested_group(item):
            logger.warning(
                "rejected declared group %s of tool %s: %s",
                item.id,
                self.tool,
                "a tool group is limited to one nesting level with simple children",
            )
            return

        self.questions.append(item)

    def skip(self, path: str) -> None:
        """Declare one skip request.

        Args:
            path: The raw path — unprefixed for the core tree or the tool's
                own block, prefixed with a tool identity for another tool's
                block.
        """
        self.skips.append(path)
