from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from .base import BaseASTError

if TYPE_CHECKING:
    from ..nodes.document import DocumentNode, DocumentRoot


class DocumentNotFoundError(BaseASTError):
    """Raised when a document cannot be found by path."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class DocumentParseError(BaseASTError):
    """Raised when a document cannot be parsed."""

    def __init__(self, message: str, filepath: str) -> None:
        super().__init__(message)
        self._filepath = filepath

    @property
    def filepath(self) -> str:
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
        super().__init__(message)
        self._rule = rule
        self._document = document
        self._node = node

    @property
    def rule(self) -> str:
        return self._rule

    @property
    def document(self) -> DocumentRoot:
        return self._document

    @property
    def node(self) -> DocumentNode:
        return self._node

    def __str__(self) -> str:
        path = Path(self._document.path).parent
        return f"Error: {self.message}\nRule: {self._rule}\nPath: {path}\nNode:\n  {self._node.data!s}"
