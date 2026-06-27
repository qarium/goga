from __future__ import annotations

from typing import TYPE_CHECKING

from ....errors import DocumentRuleError
from ....nodes.common import AnnotationsNode
from ...base.document import DocumentRule
from ..imports.tools import signature_contains_type_name

if TYPE_CHECKING:
    from ....nodes import DocumentNode
    from ....nodes.body import EntityTypeNode, MethodNode, PropertyNode, RoutineTypeNode


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

    def _check_header_links(
        self,
        node: DocumentNode,
        valid_names: set[str],
        errors: list[DocumentRuleError],
    ) -> None:
        """Validate annotation links in the header and usage items."""
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

    def _check_body_links(
        self,
        node: DocumentNode,
        valid_names: set[str],
        errors: list[DocumentRuleError],
    ) -> None:
        """Validate annotation links across entities, methods, properties, and routines."""
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
        """Validate annotation links of an entity and its methods and properties."""
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
        """Validate links of a single annotations node against valid names and signature."""
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
        """Validate that every annotation link resolves to a known name or signature token.

        Args:
            node: Document node wrapping the root to validate.

        Returns:
            Errors for annotation links with no matching target.
        """
        valid_names = _collect_valid_names(node)
        errors: list[DocumentRuleError] = []
        self._check_header_links(node, valid_names, errors)
        self._check_body_links(node, valid_names, errors)
        return errors
