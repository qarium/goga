from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from ....errors import DocumentRuleError
from ....nodes.header import ImportTypeItemNode, ImportUsageItemNode
from ...base.document import DocumentRule
from .tools import signature_contains_type_name

if TYPE_CHECKING:
    from ....nodes import DocumentNode


class ImportsCanNotBeEmpty(DocumentRule):
    """Rule: imports collection must not be empty."""

    def __init__(self) -> None:
        super().__init__(name="imports_can_not_be_empty")

    def check(self, node: DocumentNode) -> list[DocumentRuleError]:
        if "Imports" not in node.root.header.data:
            return []
        errors: list[DocumentRuleError] = []
        if not node.root.header.imports.types and not node.root.header.imports.usages:
            errors.append(
                DocumentRuleError(
                    message=(
                        f"Imports block in '{node.root.path}' is empty"
                        f" — each import must specify at least Types and From"
                    ),
                    rule=self.name,
                    document=node.root,
                    node=node,
                )
            )
        return errors


class ImportItemIsValid(DocumentRule):
    """Rule: every import item must have at least one type name or usage name."""

    def __init__(self) -> None:
        super().__init__(name="import_item_is_valid")

    def check(self, node: DocumentNode) -> list[DocumentRuleError]:
        errors: list[DocumentRuleError] = []
        for item in node.root.header.imports.types:
            if not item.type_name:
                errors.append(
                    DocumentRuleError(
                        message=(
                            f"Import from '{item.from_path}' has no Types listed — specify at least one type to import"
                        ),
                        rule=self.name,
                        document=node.root,
                        node=item,
                    )
                )
        for item in node.root.header.imports.usages:
            if not item.usage_name:
                errors.append(
                    DocumentRuleError(
                        message=(
                            f"Import from '{item.from_path}' has no Usages listed"
                            f" — specify at least one usage to import"
                        ),
                        rule=self.name,
                        document=node.root,
                        node=item,
                    )
                )
        return errors


class ImportUsageExists(DocumentRule):
    """Rule: every imported usage must exist as a .md file in the .usages/ directory."""

    def __init__(self) -> None:
        super().__init__(name="import_usage_exists")

    def check(self, node: DocumentNode) -> list[DocumentRuleError]:
        errors: list[DocumentRuleError] = []

        for item in node.root.header.imports.usages:
            if not item.from_path:
                continue
            if not Path(item.from_path).exists():
                continue
            for name in item.usage_name:
                usage_path = Path(item.from_path) / ".usages" / f"{name}.md"
                if not usage_path.exists():
                    errors.append(
                        DocumentRuleError(
                            message=(f"Usage '{name}' does not exist on filesystem by path '{usage_path}'"),
                            rule=self.name,
                            document=node.root,
                            node=item,
                        )
                    )

        return errors


class ImportHasValidFromPath(DocumentRule):
    """Rule: every import must have a valid, existing from_path that does not escape CWD."""

    def __init__(self) -> None:
        super().__init__(name="import_has_valid_from_path")

    def check(self, node: DocumentNode) -> list[DocumentRuleError]:
        errors: list[DocumentRuleError] = []
        cwd = Path.cwd().resolve()

        for item in node.root.header.imports.types + node.root.header.imports.usages:
            if not item.from_path:
                errors.append(
                    DocumentRuleError(
                        message=f"Import in '{node.root.path}' has empty source path (From field)",
                        rule=self.name,
                        document=node.root,
                        node=item,
                    )
                )
                continue

            resolved = Path(item.from_path).resolve()

            if not resolved.exists():
                if isinstance(item, ImportTypeItemNode):
                    kind = "types"
                    names = item.type_name
                else:
                    kind = "usages"
                    names = item.usage_name
                errors.append(
                    DocumentRuleError(
                        message=(f"Source path '{item.from_path}' in import of {kind} {names} not found on filesystem"),
                        rule=self.name,
                        document=node.root,
                        node=item,
                    )
                )
                continue

            if not resolved.is_relative_to(cwd):
                errors.append(
                    DocumentRuleError(
                        message=f"Source path '{item.from_path}' in import points outside the project root",
                        rule=self.name,
                        document=node.root,
                        node=item,
                    )
                )
                continue

        return errors


class ImportsHasOnlyValidKeys(DocumentRule):
    """Rule: import items must only contain 'Types', 'Usages', and 'From' keys."""

    def __init__(self) -> None:
        super().__init__(name="imports_has_only_valid_keys")

    def check(self, node: DocumentNode) -> list[DocumentRuleError]:
        errors: list[DocumentRuleError] = []
        valid_keys = {"Types", "Usages", "From"}

        for item in node.root.header.imports.types + node.root.header.imports.usages:
            unknown_keys = set(item.data.keys()) - valid_keys
            if unknown_keys:
                errors.append(
                    DocumentRuleError(
                        message=(
                            f"Import from '{item.from_path}' contains unknown keys {sorted(unknown_keys)}"
                            f" — allowed: Types, Usages, From"
                        ),
                        rule=self.name,
                        document=node.root,
                        node=item,
                    )
                )

        return errors


class ImportHasNotDuplicate(DocumentRule):
    """Rule: all type names across import items must be unique (no duplicates)."""

    def __init__(self) -> None:
        super().__init__(name="import_has_not_duplicate")

    def check(self, node: DocumentNode) -> list[DocumentRuleError]:
        errors: list[DocumentRuleError] = []
        seen_types: dict[str, str] = {}
        seen_usages: dict[str, str] = {}

        for item in node.root.header.imports.types + node.root.header.imports.usages:
            if isinstance(item, ImportTypeItemNode):
                names, kind, seen = item.type_name, "Type", seen_types
            elif isinstance(item, ImportUsageItemNode):
                names, kind, seen = item.usage_name, "Usage", seen_usages
            else:
                continue
            for name in names:
                if name in seen:
                    errors.append(
                        DocumentRuleError(
                            message=(
                                f"{kind} '{name}' is imported more than once:"
                                f" from '{seen[name]}' and '{item.from_path}'"
                            ),
                            rule=self.name,
                            document=node.root,
                            node=item,
                        )
                    )
                else:
                    seen[name] = item.from_path

        return errors


class ImportIsUsed(DocumentRule):
    """Rule: every imported type must be used in at least one annotation link, signature, or entity mutation."""

    def __init__(self) -> None:
        super().__init__(name="import_is_used")

    def check(self, node: DocumentNode) -> list[DocumentRuleError]:
        all_links = self._collect_links(node, include_embedded=True)
        all_signatures = self._collect_signatures(node)
        property_types = self._collect_property_types(node)
        mutation_names = self._collect_mutation_names(node)
        embedded_names = {name for name, _ in node.root.embeddings}
        doc_path = node.root.path
        document = node.root

        errors: list[DocumentRuleError] = []
        for item in node.root.header.imports.types + node.root.header.imports.usages:
            if isinstance(item, ImportTypeItemNode):
                errors.extend(
                    self._check_type_item(
                        item, doc_path, document, all_links, embedded_names,
                        all_signatures, property_types, mutation_names,
                    ),
                )
            elif isinstance(item, ImportUsageItemNode):
                errors.extend(self._check_usage_item(item, doc_path, document, all_links))

        return errors

    def _check_type_item(  # noqa: PLR0913
        self,
        item: ImportTypeItemNode,
        doc_path: str,
        document,
        all_links: set[str],
        embedded_names: set[str],
        all_signatures: list[str],
        property_types: set[str] | None = None,
        mutation_names: set[str] | None = None,
    ) -> list[DocumentRuleError]:
        names = [item.alias] if item.alias else list(item.type_name)
        errors: list[DocumentRuleError] = []
        for name in names:
            if name in all_links:
                continue
            if name in embedded_names:
                continue
            if any(signature_contains_type_name(sig, name) for sig in all_signatures):
                continue
            if property_types and any(signature_contains_type_name(pt, name) for pt in property_types):
                continue
            if mutation_names and name in mutation_names:
                continue
            errors.append(
                DocumentRuleError(
                    message=f"Type '{name}' was imported, but not used in '{doc_path}'",
                    rule=self.name,
                    document=document,
                    node=item,
                )
            )
        return errors

    def _check_usage_item(
        self,
        item: ImportUsageItemNode,
        doc_path: str,
        document,
        usage_links: set[str],
    ) -> list[DocumentRuleError]:
        names = [item.alias] if item.alias else list(item.usage_name)
        errors: list[DocumentRuleError] = []
        for name in names:
            if name in usage_links:
                continue
            errors.append(
                DocumentRuleError(
                    message=f"Usage '{name}' was imported, but not used in '{doc_path}'",
                    rule=self.name,
                    document=document,
                    node=item,
                )
            )
        return errors

    def _collect_links(self, node: DocumentNode, include_embedded: bool = False) -> set[str]:
        links: set[str] = set()
        header = node.root.header

        links.update(header.annotations.links)

        for usage_item in header.usages.items:
            links.update(usage_item.annotations.links)

        for entity in node.root.body.entities:
            if entity.embedded and not include_embedded:
                continue
            links.update(entity.annotations.links)
            for method in entity.methods:
                links.update(method.annotations.links)
            for prop in entity.properties:
                links.update(prop.annotations.links)

        for routine in node.root.body.routines:
            if routine.embedded and not include_embedded:
                continue
            links.update(routine.annotations.links)

        return links

    def _collect_property_types(self, node: DocumentNode) -> set[str]:
        types: set[str] = set()
        for entity in node.root.body.entities:
            for prop in entity.properties:
                if prop.type:
                    types.add(prop.type)
        return types

    def _collect_signatures(self, node: DocumentNode) -> list[str]:
        signatures: list[str] = []
        for entity in node.root.body.entities:
            signatures.append(entity.signature)
            for method in entity.methods:
                signatures.append(method.signature)
        for routine in node.root.body.routines:
            signatures.append(routine.signature)
        return signatures

    def _collect_mutation_names(self, node: DocumentNode) -> set[str]:
        types: set[str] = set()
        for entity in node.root.body.entities:
            for mutation_name, _ in entity.mutations:
                types.add(mutation_name)
        return types
