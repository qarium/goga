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
        return self._name

    def check(self, node: DocumentNode) -> list[DocumentRuleError]:
        raise NotImplementedError
