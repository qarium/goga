from __future__ import annotations

import os
import re
from pathlib import Path
from typing import TYPE_CHECKING

from ..errors import DocumentRuleError
from ..nodes.common import AnnotationsNode
from ..nodes.header import ImportTypeItemNode, ImportUsageItemNode
from .tools import signature_contains_type_name

if TYPE_CHECKING:
    from ..nodes import (
        DocumentNode,
        EntityTypeNode,
        MethodNode,
        PropertyNode,
        RoutineTypeNode,
    )


class DocumentRule:
    """Base class for document-level rules."""

    def __init__(self, name: str) -> None:
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    def check(self, node: DocumentNode) -> list[DocumentRuleError]:
        raise NotImplementedError


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
                            f"Import from '{item.from_path}' has no Types listed"
                            f" — specify at least one type to import"
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
    """Rule: every imported usage must exist as a .md file in the .usages/ directory of the referenced cell."""

    def __init__(self) -> None:
        super().__init__(name="import_usage_exists")

    def check(self, node: DocumentNode) -> list[DocumentRuleError]:
        errors: list[DocumentRuleError] = []

        for item in node.root.header.imports.usages:
            if not item.from_path:
                continue
            if not Path(item.from_path).exists():
                continue  # ImportHasValidFromPath will report the missing path
            for name in item.usage_name:
                usage_path = Path(item.from_path) / ".usages" / f"{name}.md"
                if not usage_path.exists():
                    errors.append(
                        DocumentRuleError(
                            message=(
                                f"Usage '{name}' does not exists on filesystem"
                                f" by path '{usage_path}'"
                            ),
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
                        message=(
                            f"Source path '{item.from_path}' in import of {kind} {names}"
                            f" not found on filesystem"
                        ),
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

            # Hierarchy check: from_path must be at the same level as the document or below
            doc_parent = Path(node.root.path).resolve().parent
            from_resolved = Path(item.from_path).resolve()
            from_parent = from_resolved.parent
            is_same_level = from_parent == doc_parent
            is_below = str(from_resolved).startswith(str(doc_parent) + os.sep)
            if not is_same_level and not is_below:
                errors.append(
                    DocumentRuleError(
                        message=(
                            f"Source path '{item.from_path}' must be at the same level"
                            f" or inside the current package directory"
                        ),
                        rule=self.name,
                        document=node.root,
                        node=item,
                    )
                )

        return errors


class AllUsagesIsUsed(DocumentRule):
    """Rule: every usage declared in the header must appear in links of at least one AnnotationsNode."""

    def __init__(self) -> None:
        super().__init__(name="all_usages_is_used")

    def check(self, node: DocumentNode) -> list[DocumentRuleError]:
        usage_names = [item.name for item in node.root.header.usages.items]
        if not usage_names:
            return []

        # Collect all links from all AnnotationsNode in the document
        all_links: set[str] = set()

        # Header annotations
        all_links.update(node.root.header.annotations.links)

        # Usage item annotations
        for usage_item in node.root.header.usages.items:
            all_links.update(usage_item.annotations.links)

        # Body entity annotations + property + method
        for entity in node.root.body.entities:
            all_links.update(entity.annotations.links)
            for method in entity.methods:
                all_links.update(method.annotations.links)
            for prop in entity.properties:
                all_links.update(prop.annotations.links)

        # Body routine annotations
        for routine in node.root.body.routines:
            all_links.update(routine.annotations.links)

        errors: list[DocumentRuleError] = []
        for usage_name in usage_names:
            if usage_name not in all_links:
                errors.append(
                    DocumentRuleError(
                        message=(
                            f"Usage '{usage_name}' is declared but not referenced in any annotation"
                            f" — either use it or remove the declaration"
                        ),
                        rule=self.name,
                        document=node.root,
                        node=node,
                    )
                )

        return errors


class ImportHasNotDuplicate(DocumentRule):
    """Rule: all type names across import items must be unique (no duplicates)."""

    def __init__(self) -> None:
        super().__init__(name="import_has_not_duplicate")

    def check(self, node: DocumentNode) -> list[DocumentRuleError]:
        errors: list[DocumentRuleError] = []
        seen_types: dict[str, str] = {}  # type name -> from_path where first seen
        seen_usages: dict[str, str] = {}  # usage name -> from_path where first seen

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
    """Rule: every imported type must be used in at least one annotation link or signature."""

    def __init__(self) -> None:
        super().__init__(name="import_is_used")

    def check(self, node: DocumentNode) -> list[DocumentRuleError]:
        all_links = self._collect_links(node)
        all_signatures = self._collect_signatures(node)
        property_types = self._collect_property_types(node)
        embedded_names = {name for name, _ in node.root.embeddings}
        usage_links = self._collect_links(node, include_embedded=True)
        doc_path = node.root.path

        errors: list[DocumentRuleError] = []
        for item in node.root.header.imports.types + node.root.header.imports.usages:
            if isinstance(item, ImportTypeItemNode):
                errors.extend(
                    self._check_type_item(item, doc_path, all_links, embedded_names, all_signatures, property_types),
                )
            elif isinstance(item, ImportUsageItemNode):
                errors.extend(self._check_usage_item(item, doc_path, usage_links))

        return errors

    def _check_type_item(  # noqa: PLR0913
        self,
        item: ImportTypeItemNode,
        doc_path: str,
        all_links: set[str],
        embedded_names: set[str],
        all_signatures: list[str],
        property_types: set[str] | None = None,
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
            errors.append(
                DocumentRuleError(
                    message=f"Type '{name}' was imported, but not used in '{doc_path}'",
                    rule=self.name,
                    document=item.root,
                    node=item,
                )
            )
        return errors

    def _check_usage_item(
        self,
        item: ImportUsageItemNode,
        doc_path: str,
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
                    document=item.root,
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
            if entity.embedded:
                continue
            for prop in entity.properties:
                if prop.type:
                    types.add(prop.type)
        return types

    def _collect_signatures(self, node: DocumentNode) -> list[str]:
        signatures: list[str] = []
        for entity in node.root.body.entities:
            if entity.embedded:
                continue
            signatures.append(entity.signature)
            for method in entity.methods:
                signatures.append(method.signature)
        for routine in node.root.body.routines:
            if routine.embedded:
                continue
            signatures.append(routine.signature)
        return signatures


class UsageLinksHasNotConflicts(DocumentRule):
    """Rule: usage names must not conflict with import type names (without alias) or entity/routine names."""

    def __init__(self) -> None:
        super().__init__(name="usage_links_has_not_conflicts")

    def check(self, node: DocumentNode) -> list[DocumentRuleError]:
        usage_names = [item.name for item in node.root.header.usages.items]
        if not usage_names:
            return []

        type_names_without_alias = self._collect_import_type_names(node)
        entity_names = self._collect_entity_routine_names(node)
        return self._check_conflicts(node, usage_names, type_names_without_alias, entity_names)

    def _collect_import_type_names(self, node: DocumentNode) -> set[str]:
        names: set[str] = set()
        for import_item in node.root.header.imports.types + node.root.header.imports.usages:
            if import_item.alias:
                continue
            if isinstance(import_item, ImportTypeItemNode):
                names.update(import_item.type_name)
            elif isinstance(import_item, ImportUsageItemNode):
                names.update(import_item.usage_name)
        return names

    def _collect_entity_routine_names(self, node: DocumentNode) -> dict[str, str]:
        names: dict[str, str] = {}
        for entity in node.root.body.entities:
            if not entity.embedded:
                names[entity.name] = "entity"
        for routine in node.root.body.routines:
            if not routine.embedded:
                names[routine.name] = "routine"
        return names

    def _check_conflicts(
        self,
        node: DocumentNode,
        usage_names: list[str],
        type_names_without_alias: set[str],
        entity_names: dict[str, str],
    ) -> list[DocumentRuleError]:
        errors: list[DocumentRuleError] = []
        for name in usage_names:
            if name in type_names_without_alias:
                errors.append(
                    DocumentRuleError(
                        message=(
                            f"Usage key '{name}' conflicts with imported name '{name}'"
                            f" — rename the usage or use an alias in Imports"
                        ),
                        rule=self.name,
                        document=node.root,
                        node=node,
                    )
                )
            if name in entity_names:
                kind = entity_names[name]
                errors.append(
                    DocumentRuleError(
                        message=(
                            f"Usage key '{name}' conflicts with {kind} '{name}' — rename the usage to avoid ambiguity"
                        ),
                        rule=self.name,
                        document=node.root,
                        node=node,
                    )
                )

        return errors


def _collect_valid_names(node: DocumentNode) -> set[str]:
    """Collect all valid link targets from imports, usages, entities, routines."""
    header = node.root.header
    body = node.root.body
    valid_names: set[str] = set()

    for import_item in header.imports.types:
        valid_names.update(import_item.type_name)
        if import_item.alias:
            valid_names.add(import_item.alias)
    for import_item in header.imports.usages:
        valid_names.update(import_item.usage_name)
        if import_item.alias:
            valid_names.add(import_item.alias)

    for usage_item in header.usages.items:
        valid_names.add(usage_item.name)

    for entity in body.entities:
        valid_names.add(entity.name)
    for routine in body.routines:
        valid_names.add(routine.name)

    return valid_names


class AnnotationLinksExists(DocumentRule):
    """Rule: every link in AnnotationsNode must resolve to a known name or appear in a signature."""

    def __init__(self) -> None:
        super().__init__(name="annotation_links_exists")

    def _check_header_links(self, node: DocumentNode, valid_names: set[str], errors: list[DocumentRuleError]) -> None:
        header = node.root.header
        for link in header.annotations.links:
            if link not in valid_names:
                errors.append(
                    DocumentRuleError(
                        message=(
                            f"Link `{link}` in HeaderNode annotation does not match any import,"
                            f" usage, entity, routine, or signature parameter"
                        ),
                        rule=self.name,
                        document=node.root,
                        node=header,
                    )
                )

        for usage_item in header.usages.items:
            for link in usage_item.annotations.links:
                if link not in valid_names:
                    errors.append(
                        DocumentRuleError(
                            message=(
                                f"Link `{link}` in UsageItemNode annotation does not match any import,"
                                f" usage, entity, routine, or signature parameter"
                            ),
                            rule=self.name,
                            document=node.root,
                            node=usage_item,
                        )
                    )

    def _check_body_links(self, node: DocumentNode, valid_names: set[str], errors: list[DocumentRuleError]) -> None:
        for entity in node.root.body.entities:
            if entity.embedded:
                continue
            self._check_entity_links(entity, node, valid_names, errors)

        for routine in node.root.body.routines:
            if routine.embedded:
                continue
            self._check_node_links(routine, routine.annotations, node, valid_names, errors)

    def _check_entity_links(
        self,
        entity: EntityTypeNode,
        node: DocumentNode,
        valid_names: set[str],
        errors: list[DocumentRuleError],
    ) -> None:
        self._check_node_links(entity, entity.annotations, node, valid_names, errors)
        for method in entity.methods:
            self._check_node_links(method, method.annotations, node, valid_names, errors)
        for prop in entity.properties:
            self._check_node_links(prop, prop.annotations, node, valid_names, errors)

    def _check_node_links(
        self,
        owner: EntityTypeNode | MethodNode | PropertyNode | RoutineTypeNode,
        annotations: AnnotationsNode,
        node: DocumentNode,
        valid_names: set[str],
        errors: list[DocumentRuleError],
    ) -> None:
        context = type(owner).__name__
        signature = getattr(owner, "signature", None)
        for link in annotations.links:
            if link in valid_names:
                continue
            if signature and signature_contains_type_name(signature, link):
                continue
            errors.append(
                DocumentRuleError(
                    message=(
                        f"Link `{link}` in {context} annotation does not match any import,"
                        f" usage, entity, routine, or signature parameter"
                    ),
                    rule=self.name,
                    document=node.root,
                    node=owner,
                )
            )

    def check(self, node: DocumentNode) -> list[DocumentRuleError]:
        valid_names = _collect_valid_names(node)
        errors: list[DocumentRuleError] = []
        self._check_header_links(node, valid_names, errors)
        self._check_body_links(node, valid_names, errors)
        return errors


class EntitiesAndRoutinesHasNotConflicts(DocumentRule):
    """Rule: entity and routine names must not conflict with imported type names (without alias)."""

    def __init__(self, name: str = "entities_and_routines_has_not_conflicts") -> None:
        super().__init__(name=name)

    def check(self, node: DocumentNode) -> list[DocumentRuleError]:
        active_type_names = self._collect_active_import_names(node)
        if not active_type_names:
            return []

        errors: list[DocumentRuleError] = []

        for entity in node.root.body.entities:
            if entity.embedded:
                continue
            if entity.name in active_type_names:
                errors.append(
                    DocumentRuleError(
                        message=(
                            f"Entity '{entity.name}' has the same name as imported name '{entity.name}'"
                            f" — use an alias in Imports to resolve"
                        ),
                        rule=self.name,
                        document=node.root,
                        node=entity,
                    )
                )

        for routine in node.root.body.routines:
            if routine.embedded:
                continue
            if routine.name in active_type_names:
                errors.append(
                    DocumentRuleError(
                        message=(
                            f"Routine '{routine.name}' has the same name as imported name '{routine.name}'"
                            f" — use an alias in Imports to resolve"
                        ),
                        rule=self.name,
                        document=node.root,
                        node=routine,
                    )
                )

        return errors

    @staticmethod
    def _collect_active_import_names(node: DocumentNode) -> set[str]:
        """Collect import names that have no alias (alias resolves conflicts)."""
        names: set[str] = set()
        for import_item in node.root.header.imports.types + node.root.header.imports.usages:
            if import_item.alias:
                continue
            if isinstance(import_item, ImportTypeItemNode):
                names.update(import_item.type_name)
            elif isinstance(import_item, ImportUsageItemNode):
                names.update(import_item.usage_name)
        return names


class MutationExists(DocumentRule):
    """Rule: every mutation name on an entity must exist among entity names, routine names, or imported type names."""

    def __init__(self, name: str = "mutation_exists") -> None:
        super().__init__(name=name)

    def check(self, node: DocumentNode) -> list[DocumentRuleError]:
        errors: list[DocumentRuleError] = []

        # Collect valid names: entity names, routine names, imported type names
        valid_names: set[str] = set()
        for entity in node.root.body.entities:
            valid_names.add(entity.name)
        for routine in node.root.body.routines:
            valid_names.add(routine.name)
        for import_item in node.root.header.imports.types:
            valid_names.update(import_item.type_name)

        # Check each entity's mutations
        for entity in node.root.body.entities:
            for mutation_name, _mutation_path in entity.mutations:
                if mutation_name not in valid_names:
                    errors.append(
                        DocumentRuleError(
                            message=(
                                f"Base type '{mutation_name}' for mutation of '{entity.name}'"
                                f" not found in imports, entities, or routines of this package"
                            ),
                            rule=self.name,
                            document=node.root,
                            node=entity,
                        )
                    )

        return errors


class MutationIsValid(DocumentRule):
    """Rule: mutation names on an entity must not match the entity's own name."""

    def __init__(self, name: str = "mutation_is_valid") -> None:
        super().__init__(name=name)

    def check(self, node: DocumentNode) -> list[DocumentRuleError]:
        errors: list[DocumentRuleError] = []

        for entity in node.root.body.entities:
            for mutation_name, _mutation_path in entity.mutations:
                if mutation_name == entity.name:
                    errors.append(
                        DocumentRuleError(
                            message=(
                                f"Mutation '{mutation_name}' on '{entity.name}' references itself"
                                f" — a type cannot mutate from its own signature"
                            ),
                            rule=self.name,
                            document=node.root,
                            node=entity,
                        )
                    )

        return errors


class SignatureIsValid(DocumentRule):
    """Rule: entity, routine, and method signatures must match '(...)' or '(...) -> ...' format."""

    def __init__(self) -> None:
        super().__init__(name="signature_is_valid")

    _PATTERN = re.compile(r"^\([^)]*\)(\s*->.*)?$")

    def check(self, node: DocumentNode) -> list[DocumentRuleError]:
        errors: list[DocumentRuleError] = []

        for entity in node.root.body.entities:
            if entity.embedded:
                continue
            self._check_signature(entity.signature, entity, node, errors)
            for method in entity.methods:
                self._check_signature(method.signature, method, node, errors)

        for routine in node.root.body.routines:
            if routine.embedded:
                continue
            self._check_signature(routine.signature, routine, node, errors)

        return errors

    def _check_signature(
        self,
        signature: str,
        owner_node: EntityTypeNode | MethodNode | RoutineTypeNode,
        node: DocumentNode,
        errors: list[DocumentRuleError],
    ) -> None:
        if not signature:
            errors.append(
                DocumentRuleError(
                    message="signature is empty, use '(...) -> ...' or '(...)'",
                    rule=self.name,
                    document=node.root,
                    node=owner_node,
                )
            )
            return
        if not self._PATTERN.match(signature):
            errors.append(
                DocumentRuleError(
                    message=(f"signature '{signature}' has invalid format, use '(...) -> ...' or '(...)'"),
                    rule=self.name,
                    document=node.root,
                    node=owner_node,
                )
            )


class ReturnTypeHasLink(DocumentRule):
    """Rule: return type in signature must have a link label (-> link:Type, not -> Type)."""

    def __init__(self, name: str = "return_type_has_link") -> None:
        super().__init__(name=name)

    def check(self, node: DocumentNode) -> list[DocumentRuleError]:
        errors: list[DocumentRuleError] = []

        # Check entities and routines (skip embedded — they inherit from originals)
        for entity in node.root.body.entities:
            if entity.embedded:
                continue
            self._check_signature(entity.signature, entity, node, errors)
            for method in entity.methods:
                self._check_signature(method.signature, method, node, errors)

        for routine in node.root.body.routines:
            if routine.embedded:
                continue
            self._check_signature(routine.signature, routine, node, errors)

        return errors

    def _check_signature(
        self,
        signature: str,
        owner_node: EntityTypeNode | MethodNode | RoutineTypeNode,
        node: DocumentNode,
        errors: list[DocumentRuleError],
    ) -> None:
        if "->" not in signature:
            return

        # Get the return part after the last ->
        return_part = signature.rsplit("->", 1)[1].strip()

        # If there's no ':' in the return part, the link label is missing
        if ":" not in return_part:
            errors.append(
                DocumentRuleError(
                    message=(
                        f"Return type '{return_part}' in '{signature}'"
                        f" is missing a semantic label — use format '-> label:Type'"
                    ),
                    rule=self.name,
                    document=node.root,
                    node=owner_node,
                )
            )


class EmbeddedEntityCanNotHasMutations(DocumentRule):
    """Rule: embedded entities must not have mutations."""

    def __init__(self, name: str = "embedded_entity_can_not_has_mutations") -> None:
        super().__init__(name=name)

    def check(self, node: DocumentNode) -> list[DocumentRuleError]:
        errors: list[DocumentRuleError] = []

        for entity in node.root.body.entities:
            if entity.embedded and entity.mutations:
                errors.append(
                    DocumentRuleError(
                        message=(
                            f"Embedded entity '{entity.name}' (->Entity) cannot define mutations"
                            f" — embedded types are included as-is from their source package"
                        ),
                        rule=self.name,
                        document=node.root,
                        node=entity,
                    )
                )

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


class EntityHasOnlyValidKeys(DocumentRule):
    """Rule: entity entries must only contain 'location', 'annotations', 'properties', 'methods' keys."""

    def __init__(self) -> None:
        super().__init__(name="entity_has_only_valid_keys")

    def check(self, node: DocumentNode) -> list[DocumentRuleError]:
        errors: list[DocumentRuleError] = []
        valid_keys = {"location", "annotations", "properties", "methods"}

        for entity in node.root.body.entities:
            unknown_keys = set(entity.data.keys()) - valid_keys
            if unknown_keys:
                errors.append(
                    DocumentRuleError(
                        message=(
                            f"Entity '{entity.name}' contains unknown keys {sorted(unknown_keys)}"
                            f" — allowed: location, annotations, methods, properties"
                        ),
                        rule=self.name,
                        document=node.root,
                        node=entity,
                    )
                )

        return errors


class RoutineHasOnlyValidKeys(DocumentRule):
    """Rule: routine entries must only contain 'location' and 'annotations' keys."""

    def __init__(self) -> None:
        super().__init__(name="routine_has_only_valid_keys")

    def check(self, node: DocumentNode) -> list[DocumentRuleError]:
        errors: list[DocumentRuleError] = []
        valid_keys = {"location", "annotations"}

        for routine in node.root.body.routines:
            unknown_keys = set(routine.data.keys()) - valid_keys
            if unknown_keys:
                errors.append(
                    DocumentRuleError(
                        message=(
                            f"Routine '{routine.name}' contains unknown keys {sorted(unknown_keys)}"
                            f" — allowed: location, annotations"
                        ),
                        rule=self.name,
                        document=node.root,
                        node=routine,
                    )
                )

        return errors
