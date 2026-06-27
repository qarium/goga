from __future__ import annotations

import re
from typing import TYPE_CHECKING

from ....errors import DocumentRuleError
from ....nodes.header import ImportTypeItemNode, ImportUsageItemNode
from ...base.document import DocumentRule

if TYPE_CHECKING:
    from ....nodes import (
        DocumentNode,
        EntityTypeNode,
        MethodNode,
        RoutineTypeNode,
    )


class EntitiesAndRoutinesHasNotConflicts(DocumentRule):
    """Rule: entity and routine names must not conflict with imported type names (without alias)."""

    def __init__(self, name: str = "entities_and_routines_has_not_conflicts") -> None:
        super().__init__(name=name)

    def check(self, node: DocumentNode) -> list[DocumentRuleError]:
        """Validate that entity and routine names do not shadow imported names without aliases.

        Args:
            node: Document node wrapping the root to validate.

        Returns:
            Errors for names colliding with imported names.
        """
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
        """Collect imported names that have no alias."""
        names: set[str] = set()

        for import_item in node.root.header.imports.types + node.root.header.imports.usages:
            if import_item.alias:
                continue
            if isinstance(import_item, ImportTypeItemNode):
                names.update(import_item.type_name)
            elif isinstance(import_item, ImportUsageItemNode):
                names.update(import_item.usage_name)
        return names


class EntityHasOnlyValidKeys(DocumentRule):
    """Rule: entity entries must only contain 'location', 'annotations', 'properties', 'methods' keys."""

    def __init__(self) -> None:
        super().__init__(name="entity_has_only_valid_keys")

    def check(self, node: DocumentNode) -> list[DocumentRuleError]:
        """Validate that entity entries contain only allowed keys.

        Args:
            node: Document node wrapping the root to validate.

        Returns:
            Errors for entity entries with unknown keys.
        """
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
        """Validate that routine entries contain only allowed keys.

        Args:
            node: Document node wrapping the root to validate.

        Returns:
            Errors for routine entries with unknown keys.
        """
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


class SignatureIsValid(DocumentRule):
    """Rule: entity, routine, and method signatures must match '(...)' or '(...) -> ...' format."""

    def __init__(self) -> None:
        super().__init__(name="signature_is_valid")

    _PATTERN = re.compile(r"^\([^)]*\)(\s*->.*)?$")

    def check(self, node: DocumentNode) -> list[DocumentRuleError]:
        """Validate that entity, method, and routine signatures match the expected format.

        Args:
            node: Document node wrapping the root to validate.

        Returns:
            Errors for malformed or empty signatures.
        """
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
        """Validate a single signature and append errors for malformed values."""
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
        """Validate that return types in signatures carry a semantic label.

        Args:
            node: Document node wrapping the root to validate.

        Returns:
            Errors for return types without a label.
        """
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
        """Validate the return type part of a single signature carries a semantic label."""
        if not signature or "->" not in signature:
            return

        return_part = signature.rsplit("->", 1)[1].strip()

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


class LocationIsRequired(DocumentRule):
    """Rule: every non-embedded entity and routine must have a non-empty location."""

    def __init__(self) -> None:
        super().__init__(name="location_is_required")

    def check(self, node: DocumentNode) -> list[DocumentRuleError]:
        """Validate that non-embedded entities and routines declare a valid location.

        Args:
            node: Document node wrapping the root to validate.

        Returns:
            Errors for missing or malformed location values.
        """
        errors: list[DocumentRuleError] = []

        for entity in node.root.body.entities:
            if entity.embedded:
                continue
            if "location" not in entity.data or not entity.data.get("location"):
                errors.append(
                    DocumentRuleError(
                        message=(
                            f"Type '{entity.name}' in '{node.root.path}'"
                            " is missing required 'location'"
                            " — specify the source file"
                        ),
                        rule=self.name,
                        document=node.root,
                        node=entity,
                    )
                )
            else:
                self._check_location_format(
                    str(entity.data["location"]),
                    entity.name,
                    node.root.path,
                    entity,
                    errors,
                )

        for routine in node.root.body.routines:
            if routine.embedded:
                continue
            if "location" not in routine.data or not routine.data.get("location"):
                errors.append(
                    DocumentRuleError(
                        message=(
                            f"Type '{routine.name}' in '{node.root.path}'"
                            " is missing required 'location'"
                            " — specify the source file"
                        ),
                        rule=self.name,
                        document=node.root,
                        node=routine,
                    )
                )
            else:
                self._check_location_format(
                    str(routine.data["location"]),
                    routine.name,
                    node.root.path,
                    routine,
                    errors,
                )

        return errors

    def _check_location_format(
        self,
        location_value: str,
        type_name: str,
        doc_path: str,
        node: EntityTypeNode | RoutineTypeNode,
        errors: list[DocumentRuleError],
    ) -> None:
        """Validate the location format and append errors for malformed values."""
        if "/" in location_value:
            errors.append(
                DocumentRuleError(
                    message=(
                        f"Type '{type_name}' in '{doc_path}'"
                        f" has location '{location_value}' containing"
                        " directory path"
                        " — use a plain filename without directories"
                    ),
                    rule=self.name,
                    document=node.root,
                    node=node,
                )
            )
        if "." not in location_value or not location_value.rsplit(".", 1)[-1]:
            errors.append(
                DocumentRuleError(
                    message=(
                        f"Type '{type_name}' in '{doc_path}'"
                        f" has location '{location_value}' without"
                        " file extension"
                        " — use format 'filename.ext'"
                    ),
                    rule=self.name,
                    document=node.root,
                    node=node,
                )
            )
