from __future__ import annotations

from typing import TYPE_CHECKING

from goga.codemanifest.errors import ManifestRuleError
from goga.codemanifest.nodes import DocumentNode

if TYPE_CHECKING:
    from goga.codemanifest.nodes import DocumentRoot
    from goga.codemanifest.rules import DocumentRule


class Visitor:
    """Visits a document root and runs document-level rules against it."""

    def __init__(self, document: DocumentRoot) -> None:
        self._document = document

    @property
    def document(self) -> DocumentRoot:
        return self._document

    def analyze(self, rules: list[DocumentRule]) -> list[ManifestRuleError]:
        wrapper = DocumentNode(root=self._document)
        errors: list[ManifestRuleError] = []
        for rule in rules:
            errors.extend(rule.check(wrapper))
        return errors
