from __future__ import annotations

from typing import TYPE_CHECKING

from ...errors import ASTRuleError

if TYPE_CHECKING:
    from ...nodes import DocumentRoot


class ASTRule:
    """Base class for AST-level rules."""

    def __init__(self, tree: list[DocumentRoot], name: str) -> None:
        self._name = name
        self._tree = tree

    @property
    def name(self) -> str:
        """Stable identifier of the rule used in error reports."""
        return self._name

    @property
    def tree(self) -> list[DocumentRoot]:
        """Document tree analyzed by this rule."""
        return self._tree

    def check(self, document: DocumentRoot) -> list[ASTRuleError]:
        """Run the rule against a single document and return collected errors.

        Args:
            document: Document root to validate.

        Returns:
            List of errors produced by this rule for the document.

        Raises:
            NotImplementedError: Subclasses must implement this method.
        """
        raise NotImplementedError
