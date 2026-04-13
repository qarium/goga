from __future__ import annotations

import os
import re
from pathlib import Path
from typing import TYPE_CHECKING

from ..errors import ManifestRuleError
from ..nodes.common import AnnotationsNode

if TYPE_CHECKING:
    from ..nodes import DocumentNode


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
        if "Imports" not in node.root.header.data:
            return []
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
        cwd = Path.cwd().resolve()

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
                            f"Import from_path '{item.from_path}' is not at the same level "
                            f"or below the document directory"
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
                        message=f"Usage '{usage_name}' is declared but not used in any annotation",
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
                                f"Duplicate type name '{type_name}' found in imports"
                                f" from '{item.from_path}' and '{seen[type_name]}'"
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

        usage_names = {item.name for item in node.root.header.usages.items}
        if not usage_names:
            return []

        # Collect type names from imports that have no alias (alias resolves the conflict)
        type_names_without_alias: set[str] = set()
        for import_item in node.root.header.imports.items:
            if not import_item.alias:
                type_names_without_alias.update(import_item.type_name)

        # Collect entity and routine names from body
        entity_routine_names: set[str] = set()
        for entity in node.root.body.entities:
            entity_routine_names.add(entity.name)
        for routine in node.root.body.routines:
            entity_routine_names.add(routine.name)

        # Check conflicts with type names
        type_conflicts = usage_names & type_names_without_alias
        for name in sorted(type_conflicts):
            errors.append(
                ManifestRuleError(
                    message=f"Usage '{name}' conflicts with imported type name (use alias to resolve)",
                    rule=self.name,
                    document=node.root,
                    node=node,
                )
            )

        # Check conflicts with entity/routine names
        entity_conflicts = usage_names & entity_routine_names
        for name in sorted(entity_conflicts):
            errors.append(
                ManifestRuleError(
                    message=f"Usage '{name}' conflicts with entity or routine name",
                    rule=self.name,
                    document=node.root,
                    node=node,
                )
            )

        return errors


class AnnotationLinksExists(DocumentRule):
    """Rule: every link in AnnotationsNode must resolve to a known name or appear in a signature."""

    def __init__(self) -> None:
        super().__init__(name="annotation_links_exists")

    def check(self, node: DocumentNode) -> list[ManifestRuleError]:  # noqa: C901
        header = node.root.header
        body = node.root.body

        # 1. Collect all valid names from imports, usages, entities, routines
        valid_names: set[str] = set()

        # Import type_names (flatten all), aliases, and from_paths
        for import_item in header.imports.items:
            valid_names.update(import_item.type_name)
            if import_item.alias:
                valid_names.add(import_item.alias)
            if import_item.from_path:
                valid_names.add(import_item.from_path)

        # Usage names
        for usage_item in header.usages.items:
            valid_names.add(usage_item.name)

        # Entity and routine names from body
        for entity in body.entities:
            valid_names.add(entity.name)
        for routine in body.routines:
            valid_names.add(routine.name)

        errors: list[ManifestRuleError] = []

        # Helper: check links for a given node with optional signature
        def _check_links(
            owner_node: object,
            annotations: AnnotationsNode,
            signature: str | None = None,
        ) -> None:
            for link in annotations.links:
                if link in valid_names:
                    continue
                if signature is not None and signature:
                    pattern = r"(?<![\w-])" + re.escape(link) + r"(?![\w-])"
                    if re.search(pattern, signature):
                        continue
                errors.append(
                    ManifestRuleError(
                        message=f"Annotation link '{link}' does not exist",
                        rule=self.name,
                        document=node.root,
                        node=owner_node,
                    )
                )

        # 2. Check annotations for each node type

        # Header annotations
        _check_links(header, header.annotations)

        # Usage items annotations
        for usage_item in header.usages.items:
            _check_links(usage_item, usage_item.annotations)

        # Entity annotations, methods, properties (skip embedded — checked in their own document)
        for entity in body.entities:
            if entity.embedded:
                continue
            _check_links(entity, entity.annotations, signature=entity.signature)
            for method in entity.methods:
                _check_links(method, method.annotations, signature=method.signature)
            for prop in entity.properties:
                _check_links(prop, prop.annotations)

        # Routine annotations (skip embedded — checked in their own document)
        for routine in body.routines:
            if routine.embedded:
                continue
            _check_links(routine, routine.annotations, signature=routine.signature)

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
                        message=f"Entity '{entity.name}' conflicts with imported type name (use alias to resolve)",
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
                        message=f"Routine '{routine.name}' conflicts with imported type name (use alias to resolve)",
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
            for mutation in entity.mutations:
                if mutation not in valid_names:
                    errors.append(
                        ManifestRuleError(
                            message=f"Mutation '{mutation}' on entity '{entity.name}' does not exist",
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
            for mutation in entity.mutations:
                if mutation == entity.name:
                    errors.append(
                        ManifestRuleError(
                            message=f"Mutation '{mutation}' on entity '{entity.name}' matches entity name",
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
        owner_node: object,
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
                        f"Return type '{return_part}' in signature"
                        f" '{signature}' has no link label (expected '-> link:Type')"
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
                        message=f"Embedded entity '{entity.name}' cannot have mutations",
                        rule=self.name,
                        document=node.root,
                        node=entity,
                    )
                )

        return errors


class ImportsHasOnlyValidKeys(DocumentRule):
    """Rule: import items must only contain 'Types' and 'From' keys."""

    def __init__(self) -> None:
        super().__init__(name="Imports_has_only_valid_keys")

    def check(self, node: DocumentNode) -> list[ManifestRuleError]:
        errors: list[ManifestRuleError] = []
        valid_keys = {"Types", "From"}

        for item in node.root.header.imports.items:
            unknown_keys = set(item.data.keys()) - valid_keys
            if unknown_keys:
                errors.append(
                    ManifestRuleError(
                        message=f"Import item has unknown keys: {sorted(unknown_keys)}",
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
                        message=f"Entity '{entity.name}' has unknown keys: {sorted(unknown_keys)}",
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
                        message=f"Routine '{routine.name}' has unknown keys: {sorted(unknown_keys)}",
                        rule=self.name,
                        document=node.root,
                        node=routine,
                    )
                )

        return errors
