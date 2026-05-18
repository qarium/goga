from __future__ import annotations

from typing import TYPE_CHECKING

from ....errors import DocumentRuleError
from ...base.document import DocumentRule

if TYPE_CHECKING:
    from ....nodes import DocumentNode


class MutationExists(DocumentRule):
    """Rule: every mutation name on an entity must exist among entity names, routine names, or imported type names."""

    def __init__(self, name: str = "mutation_exists") -> None:
        super().__init__(name=name)

    def check(self, node: DocumentNode) -> list[DocumentRuleError]:
        errors: list[DocumentRuleError] = []

        valid_names: set[str] = set()
        for entity in node.root.body.entities:
            valid_names.add(entity.name)
        for routine in node.root.body.routines:
            valid_names.add(routine.name)
        for import_item in node.root.header.imports.types:
            valid_names.update(import_item.type_name)

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
            if entity.embedded:
                continue
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
