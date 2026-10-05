"""The session declaration surface of one tool."""

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
    """The moment-one surface of one tool — the declaration context delivered to the hook, with its buffer.

    Attributes:
        tool: The tool identity of the owning tool.
        invited: The invitation marker — False marks a subscribed tool the
            session did not invite.
        questions: The declared questions and groups, in declaration order — local names the
            engine later qualifies with the tool identity.
        skips: The declared skip paths, in declaration order.

    Requirements:
        only a ``Question`` record or a one-level ``QuestionGroup`` is
        buffered — any other object, and a group whose children contain a
        nested group, is refused with a warning naming the tool and the
        reason, never an exception, and the element is not buffered.
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
        if not isinstance(item, (Question, QuestionGroup)):
            logger.warning(
                "rejected the declared element",
                extra={
                    "tool": self.tool,
                    "reason": "only a Question record or a one-level QuestionGroup can be declared, "
                    f"got {type(item).__name__}",
                },
            )
            return

        if isinstance(item, QuestionGroup) and _has_nested_group(item):
            logger.warning(
                "rejected declared group",
                extra={
                    "group": item.id,
                    "tool": self.tool,
                    "reason": "a tool group is limited to one nesting level with simple children",
                },
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
