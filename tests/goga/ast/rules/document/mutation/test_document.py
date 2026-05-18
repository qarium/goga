from __future__ import annotations

import inspect
from typing import ClassVar

from goga.ast.nodes.body import BodyNode, EntityTypeNode, RoutineTypeNode
from goga.ast.nodes.common import AnnotationsNode
from goga.ast.nodes.document import DocumentNode, DocumentRoot
from goga.ast.nodes.header import HeaderNode, ImportsNode, ImportTypeItemNode
from goga.ast.rules.base.document import DocumentRule
from goga.ast.rules.document.mutation.rules import (
    EmbeddedEntityCanNotHasMutations,
    MutationExists,
    MutationIsValid,
)


class TestContract:
    """Contract tests — verify all 3 classes exist, inherit DocumentRule, have correct check signature."""

    CLASSES: ClassVar[list[type]] = [
        MutationExists,
        MutationIsValid,
        EmbeddedEntityCanNotHasMutations,
    ]

    def test_all_classes_importable(self):
        for cls in self.CLASSES:
            assert callable(cls), f"{cls.__name__} is not callable"

    def test_all_inherit_document_rule(self):
        for cls in self.CLASSES:
            assert issubclass(cls, DocumentRule), f"{cls.__name__} does not inherit DocumentRule"

    def test_check_signature(self):
        for cls in self.CLASSES:
            sig = inspect.signature(cls.check)
            params = list(sig.parameters)
            assert params == ["self", "node"], f"{cls.__name__}.check signature mismatch"
            assert sig.return_annotation == "list[DocumentRuleError]"

    def test_check_returns_list(self):
        root = DocumentRoot(path="test.md")
        node = DocumentNode(root=root)
        for cls in self.CLASSES:
            instance = cls()
            result = instance.check(node)
            assert isinstance(result, list), f"{cls.__name__}.check must return list"

    def test_module_location(self):
        for cls in self.CLASSES:
            assert cls.__module__ == "goga.ast.rules.document.mutation.rules", (
                f"{cls.__name__} has wrong module: {cls.__module__}"
            )

    def test_accessible_from_facade(self):
        import goga.ast.rules as facade  # noqa: PLC0415

        assert facade.MutationExists is MutationExists
        assert facade.MutationIsValid is MutationIsValid
        assert facade.EmbeddedEntityCanNotHasMutations is EmbeddedEntityCanNotHasMutations

    def test_accessible_from_submodule(self):
        import goga.ast.rules.document.mutation as submod  # noqa: PLC0415

        assert submod.MutationExists is MutationExists
        assert submod.MutationIsValid is MutationIsValid
        assert submod.EmbeddedEntityCanNotHasMutations is EmbeddedEntityCanNotHasMutations


def _make_header(data=None, imports=None):
    return HeaderNode(
        data=data or {},
        imports=imports or ImportsNode(),
        annotations=AnnotationsNode(root=None),
    )


class TestMutationExists:
    """MutationExists: base type for mutation must exist in imports, entities, or routines."""

    def test_type_not_found(self):
        entity = EntityTypeNode(name="MyEntity", mutations=[("UnknownType", "path")])
        root = DocumentRoot(
            path="test.md",
            header=_make_header(),
            body=BodyNode(entities=[entity]),
        )
        node = DocumentNode(root=root)
        rule = MutationExists()
        errors = rule.check(node)
        assert len(errors) == 1
        assert "not_found" in errors[0].message.lower() or "not found" in errors[0].message.lower()

    def test_found_in_entities(self):
        base = EntityTypeNode(name="BaseEntity")
        entity = EntityTypeNode(name="MyEntity", mutations=[("BaseEntity", "path")])
        root = DocumentRoot(
            path="test.md",
            header=_make_header(),
            body=BodyNode(entities=[base, entity]),
        )
        node = DocumentNode(root=root)
        rule = MutationExists()
        errors = rule.check(node)
        assert errors == []

    def test_found_in_routines(self):
        routine = RoutineTypeNode(name="MyRoutine")
        entity = EntityTypeNode(name="MyEntity", mutations=[("MyRoutine", "path")])
        root = DocumentRoot(
            path="test.md",
            header=_make_header(),
            body=BodyNode(entities=[entity], routines=[routine]),
        )
        node = DocumentNode(root=root)
        rule = MutationExists()
        errors = rule.check(node)
        assert errors == []

    def test_found_in_imports(self):
        import_item = ImportTypeItemNode(type_name={"ImportedType"}, from_path="pkg")
        entity = EntityTypeNode(name="MyEntity", mutations=[("ImportedType", "path")])
        root = DocumentRoot(
            path="test.md",
            header=_make_header(imports=ImportsNode(types=[import_item])),
            body=BodyNode(entities=[entity]),
        )
        node = DocumentNode(root=root)
        rule = MutationExists()
        errors = rule.check(node)
        assert errors == []

    def test_no_mutations(self):
        entity = EntityTypeNode(name="MyEntity")
        root = DocumentRoot(
            path="test.md",
            header=_make_header(),
            body=BodyNode(entities=[entity]),
        )
        node = DocumentNode(root=root)
        rule = MutationExists()
        errors = rule.check(node)
        assert errors == []

    def test_multiple_mutations_some_not_found(self):
        base = EntityTypeNode(name="BaseEntity")
        entity = EntityTypeNode(
            name="MyEntity",
            mutations=[("BaseEntity", "path"), ("UnknownType", "path")],
        )
        root = DocumentRoot(
            path="test.md",
            header=_make_header(),
            body=BodyNode(entities=[base, entity]),
        )
        node = DocumentNode(root=root)
        rule = MutationExists()
        errors = rule.check(node)
        assert len(errors) == 1
        assert "UnknownType" in errors[0].message

    def test_empty_document(self):
        root = DocumentRoot(
            path="test.md",
            header=_make_header(),
            body=BodyNode(),
        )
        node = DocumentNode(root=root)
        rule = MutationExists()
        errors = rule.check(node)
        assert errors == []


class TestMutationIsValid:
    """MutationIsValid: mutation must not reference itself."""

    def test_self_mutation(self):
        entity = EntityTypeNode(name="MyEntity", mutations=[("MyEntity", "path")])
        root = DocumentRoot(
            path="test.md",
            header=_make_header(),
            body=BodyNode(entities=[entity]),
        )
        node = DocumentNode(root=root)
        rule = MutationIsValid()
        errors = rule.check(node)
        assert len(errors) == 1
        assert (
            "self_mutation" in errors[0].message.lower()
            or "itself" in errors[0].message.lower()
            or "self" in errors[0].message.lower()
        )

    def test_mutation_references_other(self):
        entity = EntityTypeNode(name="MyEntity", mutations=[("OtherType", "path")])
        root = DocumentRoot(
            path="test.md",
            header=_make_header(),
            body=BodyNode(entities=[entity]),
        )
        node = DocumentNode(root=root)
        rule = MutationIsValid()
        errors = rule.check(node)
        assert errors == []

    def test_no_mutations(self):
        entity = EntityTypeNode(name="MyEntity")
        root = DocumentRoot(
            path="test.md",
            header=_make_header(),
            body=BodyNode(entities=[entity]),
        )
        node = DocumentNode(root=root)
        rule = MutationIsValid()
        errors = rule.check(node)
        assert errors == []

    def test_multiple_mutations_one_self(self):
        entity = EntityTypeNode(
            name="MyEntity",
            mutations=[("OtherType", "path"), ("MyEntity", "path")],
        )
        root = DocumentRoot(
            path="test.md",
            header=_make_header(),
            body=BodyNode(entities=[entity]),
        )
        node = DocumentNode(root=root)
        rule = MutationIsValid()
        errors = rule.check(node)
        assert len(errors) == 1
        assert "MyEntity" in errors[0].message


class TestEmbeddedEntityCanNotHasMutations:
    """EmbeddedEntityCanNotHasMutations: embedded entities must not define mutations."""

    def test_embedded_with_mutations(self):
        entity = EntityTypeNode(name="MyEntity", embedded=True, mutations=[("Base", "path")])
        root = DocumentRoot(
            path="test.md",
            header=_make_header(),
            body=BodyNode(entities=[entity]),
        )
        node = DocumentNode(root=root)
        rule = EmbeddedEntityCanNotHasMutations()
        errors = rule.check(node)
        assert len(errors) == 1
        assert "has_mutations" in errors[0].message.lower() or "mutations" in errors[0].message.lower()

    def test_embedded_without_mutations(self):
        entity = EntityTypeNode(name="MyEntity", embedded=True)
        root = DocumentRoot(
            path="test.md",
            header=_make_header(),
            body=BodyNode(entities=[entity]),
        )
        node = DocumentNode(root=root)
        rule = EmbeddedEntityCanNotHasMutations()
        errors = rule.check(node)
        assert errors == []

    def test_non_embedded_with_mutations(self):
        entity = EntityTypeNode(name="MyEntity", embedded=False, mutations=[("Base", "path")])
        root = DocumentRoot(
            path="test.md",
            header=_make_header(),
            body=BodyNode(entities=[entity]),
        )
        node = DocumentNode(root=root)
        rule = EmbeddedEntityCanNotHasMutations()
        errors = rule.check(node)
        assert errors == []

    def test_multiple_embedded_with_mutations(self):
        e1 = EntityTypeNode(name="Embed1", embedded=True, mutations=[("Base", "path")])
        e2 = EntityTypeNode(name="Embed2", embedded=True, mutations=[("Base", "path")])
        root = DocumentRoot(
            path="test.md",
            header=_make_header(),
            body=BodyNode(entities=[e1, e2]),
        )
        node = DocumentNode(root=root)
        rule = EmbeddedEntityCanNotHasMutations()
        errors = rule.check(node)
        assert len(errors) == 2
