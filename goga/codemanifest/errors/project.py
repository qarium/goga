from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Optional

from goga.codemanifest.errors.base import BaseCodemanifestError

if TYPE_CHECKING:
    from goga.codemanifest.nodes.document import DocumentNode, DocumentRoot


class ProjectRuleError(BaseCodemanifestError):
    """Raised when a project violates a rule."""

    def __init__(
        self,
        message: str,
        rule: str,
        document: Optional[DocumentRoot],
        node: Optional[DocumentNode],
    ) -> None:
        super().__init__(message)
        self._rule = rule
        self._document = document
        self._node = node

    @property
    def rule(self) -> str:
        return self._rule

    @property
    def document(self) -> Optional[DocumentRoot]:
        return self._document

    @property
    def node(self) -> Optional[DocumentNode]:
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
