from __future__ import annotations

from typing import TYPE_CHECKING

from ..errors import ASTRuleError

if TYPE_CHECKING:
    from ..nodes import DocumentRoot
    from ..rules import ASTRule


class Analyzer:
    """Analyzes a document tree against a set of AST-level rules."""

    def __init__(self, tree: list[DocumentRoot]) -> None:
        self._tree = tree

    @property
    def tree(self) -> list[DocumentRoot]:
        """Document tree being analyzed."""
        return self._tree

    def analyze(self, rules: list[ASTRule]) -> list[ASTRuleError]:
        errors: list[ASTRuleError] = []
        for rule in rules:
            for document in self._tree:
                errors.extend(rule.check(document))
        return errors
