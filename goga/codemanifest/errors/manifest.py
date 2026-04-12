from __future__ import annotations

import os
from typing import TYPE_CHECKING

from goga.codemanifest.errors.base import BaseCodemanifestError

if TYPE_CHECKING:
    from goga.codemanifest.nodes.document import DocumentNode, DocumentRoot


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
        path = os.path.dirname(self._document.path)
        return (
            f"Error: {self.message}\n"
            f"Rule: {self._rule}\n"
            f"Path: {path}\n"
            f"Node:\n"
            f"  {str(self._node.data)}"
        )
