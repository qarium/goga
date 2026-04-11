from __future__ import annotations

from typing import TYPE_CHECKING

from goga.codemanifest.errors import ProjectRuleError

if TYPE_CHECKING:
    from goga.codemanifest.nodes import DocumentRoot
    from goga.codemanifest.rules import ProjectRule


class Analyzer:
    """Analyzes a document tree against a set of project-level rules."""

    def __init__(self, tree: list[DocumentRoot]) -> None:
        self._tree = tree

    @property
    def tree(self) -> list[DocumentRoot]:
        return self._tree

    def analyze(self, rules: list[ProjectRule]) -> list[ProjectRuleError]:
        errors: list[ProjectRuleError] = []
        for rule in rules:
            for document in self._tree:
                errors.extend(rule.check(document))
        return errors
