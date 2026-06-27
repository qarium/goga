from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from .base import BaseASTError

if TYPE_CHECKING:
    from ..nodes.document import DocumentNode, DocumentRoot


class ASTRuleError(BaseASTError):
    """Raised when an AST violates a rule."""

    def __init__(
        self,
        message: str,
        rule: str,
        document: DocumentRoot | None,
        node: DocumentNode | None,
    ) -> None:
        """Initialize the AST rule error.

        Args:
            message: Description of the violation.
            rule: Name of the rule that produced the error.
            document: Document root where the violation was detected, or None when unknown.
            node: Document node that triggered the violation, or None when unknown.
        """
        super().__init__(message)
        self._rule = rule
        self._document = document
        self._node = node

    @property
    def rule(self) -> str:
        """Name of the rule that produced the error."""
        return self._rule

    @property
    def document(self) -> DocumentRoot | None:
        """Document root where the violation was detected, or None when unknown."""
        return self._document

    @property
    def node(self) -> DocumentNode | None:
        """Document node that triggered the violation, or None when unknown."""
        return self._node

    def __str__(self) -> str:
        lines = [f"Error: {self.message}", f"Rule: {self._rule}"]

        if self._document is not None:
            path = str(Path(self._document.path).parent)
            lines.append(f"Path: {path}")

        if self._node is not None:
            lines.append("Node:")
            lines.append(f"  {self._node.data!s}")

        return "\n".join(lines)
