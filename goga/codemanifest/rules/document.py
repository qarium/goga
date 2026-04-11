from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from goga.codemanifest.errors import ManifestRuleError

if TYPE_CHECKING:
    from goga.codemanifest.nodes import DocumentNode


class DocumentRule:
    """Base class for document-level rules."""

    def __init__(self, name: str) -> None:
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    def check(self, node: DocumentNode) -> list[ManifestRuleError]:
        raise NotImplementedError


class ImportsCanNotBeEmptyRule(DocumentRule):
    """Rule: imports collection must not be empty."""

    def __init__(self) -> None:
        super().__init__(name="imports_can_not_be_empty")

    def check(self, node: DocumentNode) -> list[ManifestRuleError]:
        errors: list[ManifestRuleError] = []
        if not node.root.header.imports.items:
            errors.append(
                ManifestRuleError(
                    message="Imports cannot be empty",
                    rule=self.name,
                    document=node.root,
                    node=node,
                )
            )
        return errors


class ImportHasTypeRule(DocumentRule):
    """Rule: every import must have at least one type name."""

    def __init__(self) -> None:
        super().__init__(name="import_has_type")

    def check(self, node: DocumentNode) -> list[ManifestRuleError]:
        errors: list[ManifestRuleError] = []
        for item in node.root.header.imports.items:
            if not item.type_name:
                errors.append(
                    ManifestRuleError(
                        message=f"Import from '{item.from_path}' has no type specified",
                        rule=self.name,
                        document=node.root,
                        node=item,
                    )
                )
        return errors


class ImportHasValidFromPathRule(DocumentRule):
    """Rule: every import must have a valid, existing from_path that does not escape CWD."""

    def __init__(self) -> None:
        super().__init__(name="import_has_valid_from_path")

    def check(self, node: DocumentNode) -> list[ManifestRuleError]:
        errors: list[ManifestRuleError] = []
        cwd = Path(os.getcwd()).resolve()

        for item in node.root.header.imports.items:
            if not item.from_path:
                errors.append(
                    ManifestRuleError(
                        message="Import has empty from_path",
                        rule=self.name,
                        document=node.root,
                        node=item,
                    )
                )
                continue

            resolved = Path(item.from_path).resolve()

            if not resolved.exists():
                errors.append(
                    ManifestRuleError(
                        message=f"Import from_path '{item.from_path}' does not exist on filesystem",
                        rule=self.name,
                        document=node.root,
                        node=item,
                    )
                )
                continue

            if not str(resolved).startswith(str(cwd)):
                errors.append(
                    ManifestRuleError(
                        message=f"Import from_path '{item.from_path}' escapes CWD",
                        rule=self.name,
                        document=node.root,
                        node=item,
                    )
                )

        return errors
