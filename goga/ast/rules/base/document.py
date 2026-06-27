from __future__ import annotations

from typing import TYPE_CHECKING

from ...errors import DocumentRuleError

if TYPE_CHECKING:
    from ...nodes import DocumentNode


class DocumentRule:
    """Base class for document-level rules."""

    def __init__(self, name: str) -> None:
        self._name = name

    @property
    def name(self) -> str:
        """Stable identifier of the rule used in error reports."""
        return self._name

    def check(self, node: DocumentNode) -> list[DocumentRuleError]:
        """Run the rule against a document node and return collected errors.

        Args:
            node: Document node to validate.

        Returns:
            List of errors produced by this rule for the node.

        Raises:
            NotImplementedError: Subclasses must implement this method.
        """
        raise NotImplementedError
