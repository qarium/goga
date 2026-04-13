from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from .base import BaseCodemanifestError

if TYPE_CHECKING:
    from ..nodes.document import DocumentNode, DocumentRoot


class ManifestParseError(BaseCodemanifestError):
    """Raised when a manifest file cannot be parsed."""

    def __init__(self, message: str, filepath: str) -> None:
        super().__init__(message)
        self._filepath = filepath

    @property
    def filepath(self) -> str:
        return self._filepath


class ManifestRuleError(BaseCodemanifestError):
    """Raised when a manifest document violates a rule."""

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
