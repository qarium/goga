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
        return self._name

    @property
    def tree(self) -> list[DocumentRoot]:
        return self._tree

    def check(self, document: DocumentRoot) -> list[ASTRuleError]:
        raise NotImplementedError
