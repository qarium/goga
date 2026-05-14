"""Integration tests for the rules package refactoring.

Verifies: facade re-export of all 27 entities, backward compatibility,
cross-cell interaction (AnnotationLinksExists -> signature_contains_type_name),
and edge-case instantiation with valid/invalid data.
"""

from __future__ import annotations

import goga.ast.rules as facade
import pytest
from goga.ast.errors import ASTRuleError, DocumentRuleError
from goga.ast.nodes import (
    AnnotationsNode,
    BodyNode,
    DocumentNode,
    DocumentRoot,
    EntityTypeNode,
    HeaderNode,
    ImportsNode,
    ImportTypeItemNode,
    RoutineTypeNode,
    UsagesNode,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_doc(  # noqa: PLR0913
    *,
    imports: ImportsNode | None = None,
    usages: UsagesNode | None = None,
    header_annotations: AnnotationsNode | None = None,
    entities: list[EntityTypeNode] | None = None,
    routines: list[RoutineTypeNode] | None = None,
    path: str = "test.goga",
) -> DocumentNode:
    header = HeaderNode(
        imports=imports or ImportsNode(),
        usages=usages or UsagesNode(),
        annotations=header_annotations or AnnotationsNode(),
    )
    body = BodyNode(
        entities=entities or [],
        routines=routines or [],
    )
    root = DocumentRoot(header=header, body=body, path=path)
    return DocumentNode(root=root)


ALL_27_NAMES = [
    "ASTRule",
    "AllUsagesIsUsed",
    "AnnotationLinksExists",
    "DocumentRule",
    "EmbeddedEntityCanNotHasMutations",
    "EmbeddedTypeHasLowLevel",
    "EntitiesAndRoutinesHasNotConflicts",
    "EntityHasOnlyValidKeys",
    "ImportHasNotDuplicate",
    "ImportHasValidFromPath",
    "ImportIsUsed",
    "ImportItemIsValid",
    "ImportTypeExists",
    "ImportUsageExists",
    "ImportsCanNotBeEmpty",
    "ImportsHasNotCyclicalDeps",
    "ImportsHasOnlyValidKeys",
    "LocationIsRequired",
    "MutationExists",
    "MutationIsValid",
    "ReturnTypeHasLink",
    "RoutineHasOnlyValidKeys",
    "SignatureIsValid",
    "UsageFilepathExists",
    "UsageLinksHasNotConflicts",
    "UsageUrlIsAccessible",
    "signature_contains_type_name",
]


# ---------------------------------------------------------------------------
# 1. Facade: all 27 entities importable in one import
# ---------------------------------------------------------------------------


class TestFacadeImport:
    """All 27 entities must be importable from the top-level facade."""

    @pytest.mark.parametrize("name", ALL_27_NAMES)
    def test_entity_is_available(self, name: str) -> None:
        assert hasattr(facade, name), f"{name} missing from facade"

    def test_all_27_count(self) -> None:
        assert len(ALL_27_NAMES) == 27

    def test_facade_all_matches(self) -> None:
        for name in ALL_27_NAMES:
            assert name in facade.__all__


# ---------------------------------------------------------------------------
# 2. Backward compatibility: old import paths return same objects
# ---------------------------------------------------------------------------


class TestBackwardCompatibility:
    """Old import paths must still work and return identical objects."""

    def test_document_rules_from_old_path(self) -> None:
        from goga.ast.rules.document import (  # noqa: PLC0415
            ImportsCanNotBeEmpty,
        )

        assert ImportsCanNotBeEmpty is facade.ImportsCanNotBeEmpty

    def test_ast_rules_from_old_path(self) -> None:
        from goga.ast.rules.ast import (  # noqa: PLC0415
            ImportsHasNotCyclicalDeps,
        )

        assert ImportsHasNotCyclicalDeps is facade.ImportsHasNotCyclicalDeps

    def test_tools_from_old_path(self) -> None:
        from goga.ast.rules.tools import (  # noqa: PLC0415
            signature_contains_type_name,
        )

        assert signature_contains_type_name is facade.signature_contains_type_name

    def test_base_classes_from_old_path(self) -> None:
        from goga.ast.rules.base import ASTRule, DocumentRule  # noqa: PLC0415

        assert DocumentRule is facade.DocumentRule
        assert ASTRule is facade.ASTRule

    def test_subcell_direct_imports(self) -> None:
        from goga.ast.rules.document.imports import (  # noqa: PLC0415
            ImportHasNotDuplicate,
            ImportsCanNotBeEmpty,
            signature_contains_type_name,
        )
        from goga.ast.rules.document.mutation import (  # noqa: PLC0415
            MutationExists,
        )
        from goga.ast.rules.document.structure import (  # noqa: PLC0415
            LocationIsRequired,
        )
        from goga.ast.rules.document.usages import (  # noqa: PLC0415
            AllUsagesIsUsed,
        )

        assert ImportHasNotDuplicate is facade.ImportHasNotDuplicate
        assert ImportsCanNotBeEmpty is facade.ImportsCanNotBeEmpty
        assert signature_contains_type_name is facade.signature_contains_type_name
        assert MutationExists is facade.MutationExists
        assert LocationIsRequired is facade.LocationIsRequired
        assert AllUsagesIsUsed is facade.AllUsagesIsUsed


# ---------------------------------------------------------------------------
# 3. Cross-cell interaction: AnnotationLinksExists -> signature_contains_type_name
# ---------------------------------------------------------------------------


class TestCrossCellInteraction:
    """AnnotationLinksExists must call signature_contains_type_name across cell boundary."""

    def test_annotation_link_resolved_by_signature(self) -> None:
        """A type referenced in annotations but not in imports/usages/body
        should be resolved via signature_contains_type_name."""
        rule = facade.AnnotationLinksExists()

        entity = EntityTypeNode(
            name="MyEntity",
            location="my_entity.goga",
            signature="(param: LinkedType) -> rv:LinkedType",
            annotations=AnnotationsNode(links=["LinkedType"]),
        )
        doc = _make_doc(entities=[entity])
        errors = rule.check(doc)
        assert errors == []

    def test_annotation_link_not_found(self) -> None:
        """A link not resolvable by any mechanism must produce an error."""
        rule = facade.AnnotationLinksExists()

        entity = EntityTypeNode(
            name="MyEntity",
            location="my_entity.goga",
            annotations=AnnotationsNode(links=["MissingType"]),
        )
        doc = _make_doc(entities=[entity])
        errors = rule.check(doc)
        assert len(errors) > 0
        assert any("not_found" not in e.rule and "MissingType" in e.message for e in errors)

    def test_annotation_link_resolved_by_import(self) -> None:
        """A link matching an imported type name must be valid."""
        rule = facade.AnnotationLinksExists()

        imports = ImportsNode(
            types=[
                ImportTypeItemNode(
                    type_name={"ImportedType"},
                    from_path="other.goga",
                ),
            ],
        )
        entity = EntityTypeNode(
            name="MyEntity",
            location="my_entity.goga",
            annotations=AnnotationsNode(links=["ImportedType"]),
        )
        doc = _make_doc(imports=imports, entities=[entity])
        errors = rule.check(doc)
        assert errors == []


# ---------------------------------------------------------------------------
# 4. Edge cases: instantiate all classes and call check
# ---------------------------------------------------------------------------


class TestInstantiationAndCheck:
    """All rule classes must be instantiable and callable with valid/invalid data."""

    # -- DocumentRule subclasses (no tree required) --

    @pytest.mark.parametrize(
        "cls_name",
        [
            "ImportsCanNotBeEmpty",
            "ImportsHasOnlyValidKeys",
            "ImportItemIsValid",
            "ImportUsageExists",
            "ImportHasValidFromPath",
            "ImportHasNotDuplicate",
            "ImportIsUsed",
            "AllUsagesIsUsed",
            "UsageFilepathExists",
            "UsageUrlIsAccessible",
            "UsageLinksHasNotConflicts",
            "EntitiesAndRoutinesHasNotConflicts",
            "EntityHasOnlyValidKeys",
            "RoutineHasOnlyValidKeys",
            "SignatureIsValid",
            "ReturnTypeHasLink",
            "LocationIsRequired",
            "MutationExists",
            "MutationIsValid",
            "EmbeddedEntityCanNotHasMutations",
            "AnnotationLinksExists",
        ],
    )
    def test_document_rule_instantiation_and_check(self, cls_name: str) -> None:
        cls = getattr(facade, cls_name)
        instance = cls()
        assert hasattr(instance, "name")
        assert hasattr(instance, "check")

        doc = _make_doc()
        result = instance.check(doc)
        assert isinstance(result, list)

    # -- ASTRule subclasses (tree required) --

    @pytest.mark.parametrize(
        "cls_name",
        [
            "ImportsHasNotCyclicalDeps",
            "ImportTypeExists",
            "EmbeddedTypeHasLowLevel",
        ],
    )
    def test_ast_rule_instantiation_and_check(self, cls_name: str) -> None:
        cls = getattr(facade, cls_name)
        root = DocumentRoot(path="test.goga")
        instance = cls(tree=[root])
        assert hasattr(instance, "name")
        assert hasattr(instance, "tree")
        assert hasattr(instance, "check")

        result = instance.check(root)
        assert isinstance(result, list)

    # -- signature_contains_type_name --

    def test_signature_contains_type_name_callable(self) -> None:
        func = facade.signature_contains_type_name
        assert callable(func)
        assert func("(param: TypeName)", "TypeName") is True
        assert func("(param: Other)", "TypeName") is False

    # -- base classes raise NotImplementedError --

    def test_document_rule_base_raises(self) -> None:
        rule = facade.DocumentRule(name="test")
        doc = _make_doc()
        with pytest.raises(NotImplementedError):
            rule.check(doc)

    def test_ast_rule_base_raises(self) -> None:
        root = DocumentRoot(path="test.goga")
        rule = facade.ASTRule(tree=[root], name="test")
        with pytest.raises(NotImplementedError):
            rule.check(root)

    # -- concrete rules produce correct error types --

    def test_document_rule_error_type(self) -> None:
        rule = facade.ImportsCanNotBeEmpty()
        imports = ImportsNode(data={"Types": [], "Usages": []})
        doc = _make_doc(imports=imports)
        errors = rule.check(doc)
        for e in errors:
            assert isinstance(e, DocumentRuleError)

    def test_ast_rule_error_type(self) -> None:
        rule = facade.EmbeddedTypeHasLowLevel(tree=[])
        root = DocumentRoot(path="test.goga")
        errors = rule.check(root)
        for e in errors:
            assert isinstance(e, ASTRuleError)
