from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from .base import BaseASTError

if TYPE_CHECKING:
    from ..nodes.document import DocumentNode, DocumentRoot


class DocumentNotFoundError(BaseASTError):
    """Raised when a document cannot be found by path."""

    def __init__(self, message: str) -> None:
        """Initialize the error with a human-readable message.

        Args:
            message: Description of why the document was not found.
        """
        super().__init__(message)


class DocumentParseError(BaseASTError):
    """Raised when a document cannot be parsed."""

    def __init__(self, message: str, filepath: str) -> None:
        """Initialize the parse error.

        Args:
            message: Description of the parse failure.
            filepath: Path of the file that failed to parse.
        """
        super().__init__(message)
        self._filepath = filepath

    @property
    def filepath(self) -> str:
        """Path of the file that failed to parse."""
        return self._filepath


class DocumentRuleError(BaseASTError):
    """Raised when a document violates a rule."""

    def __init__(
        self,
        message: str,
        rule: str,
        document: DocumentRoot,
        node: DocumentNode,
    ) -> None:
        """Initialize the document rule error.

        Args:
            message: Description of the violation.
            rule: Name of the rule that produced the error.
            document: Document root where the violation was detected.
            node: Document node that triggered the violation.
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
    def document(self) -> DocumentRoot:
        """Document root where the violation was detected."""
        return self._document

    @property
    def node(self) -> DocumentNode:
        """Document node that triggered the violation."""
        return self._node

    def __str__(self) -> str:
        path = Path(self._document.path).parent
        return f"Error: {self.message}\nRule: {self._rule}\nPath: {path}\nNode:\n  {self._node.data!s}"
