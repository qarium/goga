from __future__ import annotations

import os
import re
from pathlib import Path
from typing import TYPE_CHECKING

from ..errors import ManifestRuleError
from ..nodes.common import AnnotationsNode

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

    def check(self, node: DocumentNode) -> list[ManifestRuleError]:
        raise NotImplementedError


class ImportsCanNotBeEmpty(DocumentRule):
    """Rule: imports collection must not be empty."""

    def __init__(self) -> None:
        super().__init__(name="imports_can_not_be_empty")

    def check(self, node: DocumentNode) -> list[ManifestRuleError]:
        if "Imports" not in node.root.header.data:
            return []
        errors: list[ManifestRuleError] = []
        if not node.root.header.imports.items:
            errors.append(
                ManifestRuleError(
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


class ImportHasType(DocumentRule):
    """Rule: every import must have at least one type name."""

    def __init__(self) -> None:
        super().__init__(name="import_has_type")

    def check(self, node: DocumentNode) -> list[ManifestRuleError]:
        errors: list[ManifestRuleError] = []
        for item in node.root.header.imports.items:
            if not item.type_name:
                errors.append(
                    ManifestRuleError(
                        message=(
                            f"Import from '{item.from_path}' has no Types listed — specify at least one type to import"
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

    def check(self, node: DocumentNode) -> list[ManifestRuleError]:
        errors: list[ManifestRuleError] = []
        cwd = Path.cwd().resolve()

        for item in node.root.header.imports.items:
            if not item.from_path:
                errors.append(
                    ManifestRuleError(
                        message=f"Import in '{node.root.path}' has empty source path (From field)",
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
                        message=(
                            f"Source path '{item.from_path}' in import of types {item.type_name}"
                            f" not found on filesystem"
                        ),
                        rule=self.name,
                        document=node.root,
                        node=item,
                    )
                )
                continue

            if not str(resolved).startswith(str(cwd)):
                errors.append(
                    ManifestRuleError(
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
                    ManifestRuleError(
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

    def check(self, node: DocumentNode) -> list[ManifestRuleError]:
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

        errors: list[ManifestRuleError] = []
        for usage_name in usage_names:
            if usage_name not in all_links:
                errors.append(
                    ManifestRuleError(
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

    def check(self, node: DocumentNode) -> list[ManifestRuleError]:
        errors: list[ManifestRuleError] = []
        seen: dict[str, str] = {}  # type_name -> from_path where first seen

        for item in node.root.header.imports.items:
            for type_name in item.type_name:
                if type_name in seen:
                    errors.append(
                        ManifestRuleError(
                            message=(
                                f"Type '{type_name}' is imported more than once:"
                                f" from '{seen[type_name]}' and '{item.from_path}'"
                            ),
                            rule=self.name,
                            document=node.root,
                            node=item,
                        )
                    )
                else:
                    seen[type_name] = item.from_path

        return errors


class UsageLinksHasNotConflicts(DocumentRule):
    """Rule: usage names must not conflict with import type names (without alias) or entity/routine names."""

    def __init__(self) -> None:
        super().__init__(name="usage_links_has_not_conflicts")

    def check(self, node: DocumentNode) -> list[ManifestRuleError]:
        errors: list[ManifestRuleError] = []

        usage_names = [item.name for item in node.root.header.usages.items]
        if not usage_names:
            return []

        # Collect type names from imports that have no alias (alias resolves the conflict)
        # Map each type_name to itself so we can look it up per-usage
        type_names_without_alias: set[str] = set()
        for import_item in node.root.header.imports.items:
            if not import_item.alias:
                type_names_without_alias.update(import_item.type_name)

        # Collect entity and routine names from body, tracking kind
        entity_names: dict[str, str] = {}  # name -> kind
        for entity in node.root.body.entities:
            entity_names[entity.name] = "entity"
        for routine in node.root.body.routines:
            entity_names[routine.name] = "routine"

        # Check each usage name individually
        for name in usage_names:
            # Check conflict with imports
            if name in type_names_without_alias:
                errors.append(
                    ManifestRuleError(
                        message=(
                            f"Usage key '{name}' conflicts with imported type '{name}'"
                            f" — rename the usage or use an alias in Imports"
                        ),
                        rule=self.name,
                        document=node.root,
                        node=node,
                    )
                )

            # Check conflict with entity/routine
            if name in entity_names:
                kind = entity_names[name]
                errors.append(
                    ManifestRuleError(
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

    for import_item in header.imports.items:
        valid_names.update(import_item.type_name)
        if import_item.alias:
            valid_names.add(import_item.alias)
        if import_item.from_path:
            valid_names.add(import_item.from_path)

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

    def _check_header_links(self, node: DocumentNode, valid_names: set[str], errors: list[ManifestRuleError]) -> None:
        header = node.root.header
        for link in header.annotations.links:
            if link not in valid_names:
                errors.append(
                    ManifestRuleError(
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
                        ManifestRuleError(
                            message=(
                                f"Link `{link}` in UsageItemNode annotation does not match any import,"
                                f" usage, entity, routine, or signature parameter"
                            ),
                            rule=self.name,
                            document=node.root,
                            node=usage_item,
                        )
                    )

    def _check_body_links(self, node: DocumentNode, valid_names: set[str], errors: list[ManifestRuleError]) -> None:
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
        errors: list[ManifestRuleError],
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
        errors: list[ManifestRuleError],
    ) -> None:
        context = type(owner).__name__
        signature = getattr(owner, "signature", None)
        for link in annotations.links:
            if link in valid_names:
                continue
            if signature:
                pattern = r"(?<![\w-])" + re.escape(link) + r"(?![\w-])"
                if re.search(pattern, signature):
                    continue
            errors.append(
                ManifestRuleError(
                    message=(
                        f"Link `{link}` in {context} annotation does not match any import,"
                        f" usage, entity, routine, or signature parameter"
                    ),
                    rule=self.name,
                    document=node.root,
                    node=owner,
                )
            )

    def check(self, node: DocumentNode) -> list[ManifestRuleError]:
        valid_names = _collect_valid_names(node)
        errors: list[ManifestRuleError] = []
        self._check_header_links(node, valid_names, errors)
        self._check_body_links(node, valid_names, errors)
        return errors


class EntitiesAndRoutinesHasNotConflicts(DocumentRule):
    """Rule: entity and routine names must not conflict with imported type names (without alias)."""

    def __init__(self, name: str = "entities_and_routines_has_not_conflicts") -> None:
        super().__init__(name=name)

    def check(self, node: DocumentNode) -> list[ManifestRuleError]:
        # Collect type names from imports that have no alias (alias resolves the conflict)
        active_type_names: set[str] = set()
        for import_item in node.root.header.imports.items:
            if not import_item.alias:
                active_type_names.update(import_item.type_name)

        if not active_type_names:
            return []

        errors: list[ManifestRuleError] = []

        # Check entity names
        for entity in node.root.body.entities:
            if entity.embedded:
                continue
            if entity.name in active_type_names:
                errors.append(
                    ManifestRuleError(
                        message=(
                            f"Entity '{entity.name}' has the same name as imported type '{entity.name}'"
                            f" — use an alias in Imports to resolve"
                        ),
                        rule=self.name,
                        document=node.root,
                        node=entity,
                    )
                )

        # Check routine names
        for routine in node.root.body.routines:
            if routine.embedded:
                continue
            if routine.name in active_type_names:
                errors.append(
                    ManifestRuleError(
                        message=(
                            f"Routine '{routine.name}' has the same name as imported type '{routine.name}'"
                            f" — use an alias in Imports to resolve"
                        ),
                        rule=self.name,
                        document=node.root,
                        node=routine,
                    )
                )

        return errors


class MutationExists(DocumentRule):
    """Rule: every mutation name on an entity must exist among entity names, routine names, or imported type names."""

    def __init__(self, name: str = "mutation_exists") -> None:
        super().__init__(name=name)

    def check(self, node: DocumentNode) -> list[ManifestRuleError]:
        errors: list[ManifestRuleError] = []

        # Collect valid names: entity names, routine names, imported type names
        valid_names: set[str] = set()
        for entity in node.root.body.entities:
            valid_names.add(entity.name)
        for routine in node.root.body.routines:
            valid_names.add(routine.name)
        for import_item in node.root.header.imports.items:
            valid_names.update(import_item.type_name)

        # Check each entity's mutations
        for entity in node.root.body.entities:
            for mutation_name, _mutation_path in entity.mutations:
                if mutation_name not in valid_names:
                    errors.append(
                        ManifestRuleError(
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

    def check(self, node: DocumentNode) -> list[ManifestRuleError]:
        errors: list[ManifestRuleError] = []

        for entity in node.root.body.entities:
            for mutation_name, _mutation_path in entity.mutations:
                if mutation_name == entity.name:
                    errors.append(
                        ManifestRuleError(
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


class ReturnTypeHasLink(DocumentRule):
    """Rule: return type in signature must have a link label (-> link:Type, not -> Type)."""

    def __init__(self, name: str = "return_type_has_link") -> None:
        super().__init__(name=name)

    def check(self, node: DocumentNode) -> list[ManifestRuleError]:
        errors: list[ManifestRuleError] = []

        # Check entities and routines
        for entity in node.root.body.entities:
            self._check_signature(entity.signature, entity, node, errors)
            for method in entity.methods:
                self._check_signature(method.signature, method, node, errors)

        for routine in node.root.body.routines:
            self._check_signature(routine.signature, routine, node, errors)

        return errors

    def _check_signature(
        self,
        signature: str,
        owner_node: EntityTypeNode | MethodNode | RoutineTypeNode,
        node: DocumentNode,
        errors: list[ManifestRuleError],
    ) -> None:
        if "->" not in signature:
            return

        # Get the return part after the last ->
        return_part = signature.rsplit("->", 1)[1].strip()

        # If there's no ':' in the return part, the link label is missing
        if ":" not in return_part:
            errors.append(
                ManifestRuleError(
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

    def check(self, node: DocumentNode) -> list[ManifestRuleError]:
        errors: list[ManifestRuleError] = []

        for entity in node.root.body.entities:
            if entity.embedded and entity.mutations:
                errors.append(
                    ManifestRuleError(
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
    """Rule: import items must only contain 'Types' and 'From' keys."""

    def __init__(self) -> None:
        super().__init__(name="imports_has_only_valid_keys")

    def check(self, node: DocumentNode) -> list[ManifestRuleError]:
        errors: list[ManifestRuleError] = []
        valid_keys = {"Types", "From"}

        for item in node.root.header.imports.items:
            unknown_keys = set(item.data.keys()) - valid_keys
            if unknown_keys:
                errors.append(
                    ManifestRuleError(
                        message=(
                            f"Import from '{item.from_path}' contains unknown keys {sorted(unknown_keys)}"
                            f" — allowed: Types, From"
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

    def check(self, node: DocumentNode) -> list[ManifestRuleError]:
        errors: list[ManifestRuleError] = []
        valid_keys = {"location", "annotations", "properties", "methods"}

        for entity in node.root.body.entities:
            unknown_keys = set(entity.data.keys()) - valid_keys
            if unknown_keys:
                errors.append(
                    ManifestRuleError(
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

    def check(self, node: DocumentNode) -> list[ManifestRuleError]:
        errors: list[ManifestRuleError] = []
        valid_keys = {"location", "annotations"}

        for routine in node.root.body.routines:
            unknown_keys = set(routine.data.keys()) - valid_keys
            if unknown_keys:
                errors.append(
                    ManifestRuleError(
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
