from __future__ import annotations

from typing import TYPE_CHECKING

from ..errors import DocumentRuleError
from ..nodes import DocumentNode

if TYPE_CHECKING:
    from ..nodes import DocumentRoot
    from ..rules import DocumentRule


class Visitor:
    """Visits a document root and runs document-level rules against it."""

    def __init__(self, document: DocumentRoot) -> None:
        self._document = document

    @property
    def document(self) -> DocumentRoot:
        """Document root being visited."""
        return self._document

    def analyze(self, rules: list[DocumentRule]) -> list[DocumentRuleError]:
        """Run document-level rules against the wrapped document and collect errors.

        Args:
            rules: Document-level rules to evaluate.

        Returns:
            All errors collected from every rule.
        """
        wrapper = DocumentNode(root=self._document)
        errors: list[DocumentRuleError] = []
        for rule in rules:
            errors.extend(rule.check(wrapper))

        return errors
