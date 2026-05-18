from __future__ import annotations

import inspect
from typing import ClassVar

from goga.ast.nodes.body import BodyNode, EntityTypeNode, RoutineTypeNode
from goga.ast.nodes.common import AnnotationsNode
from goga.ast.nodes.document import DocumentRoot
from goga.ast.nodes.header import (
    HeaderNode,
    ImportsNode,
    ImportTypeItemNode,
    ImportUsageItemNode,
)
from goga.ast.rules.ast.rules import (
    EmbeddedTypeHasLowLevel,
    ImportsHasNotCyclicalDeps,
    ImportTypeExists,
)
from goga.ast.rules.base.ast import ASTRule


def _make_header(imports=None):
    return HeaderNode(
        imports=imports or ImportsNode(),
        annotations=AnnotationsNode(root=None),
    )


class TestFacadeAccessibility:
    """All 3 AST rules must be importable from the facade and sub-cell."""

    RULE_NAMES: ClassVar[list[str]] = [
        "ImportsHasNotCyclicalDeps",
        "ImportTypeExists",
        "EmbeddedTypeHasLowLevel",
    ]

    def test_facade_imports(self):
        import goga.ast.rules  # noqa: PLC0415

        facade = goga.ast.rules
        for name in self.RULE_NAMES:
            assert hasattr(facade, name), f"{name} not in facade"
            assert callable(getattr(facade, name))

    def test_subcell_imports(self):
        import goga.ast.rules.ast  # noqa: PLC0415

        subcell = goga.ast.rules.ast
        for name in self.RULE_NAMES:
            assert hasattr(subcell, name), f"{name} not in sub-cell"
            assert callable(getattr(subcell, name))


class TestContract:
    """Contract tests — verify all 3 classes exist, inherit ASTRule, have correct check signature."""

    CLASSES: ClassVar[list[type]] = [
        ImportsHasNotCyclicalDeps,
        ImportTypeExists,
        EmbeddedTypeHasLowLevel,
    ]

    def test_all_classes_importable(self):
        for cls in self.CLASSES:
            assert callable(cls), f"{cls.__name__} is not callable"

    def test_all_inherit_ast_rule(self):
        for cls in self.CLASSES:
            assert issubclass(cls, ASTRule), f"{cls.__name__} does not inherit ASTRule"

    def test_check_signature(self):
        for cls in self.CLASSES:
            sig = inspect.signature(cls.check)
            params = list(sig.parameters)
            assert params == ["self", "document"], f"{cls.__name__}.check signature mismatch"
            assert sig.return_annotation == "list[ASTRuleError]"

    def test_module_location(self):
        for cls in self.CLASSES:
            assert cls.__module__ == "goga.ast.rules.ast.rules", f"{cls.__name__} has wrong module: {cls.__module__}"


class TestImportsHasNotCyclicalDeps:
    """ImportsHasNotCyclicalDeps: detect mutual imports forming a cycle."""

    def test_no_cycle(self):
        doc_a = DocumentRoot(
            path="a",
            header=_make_header(imports=ImportsNode(types=[ImportTypeItemNode(type_name={"X"}, from_path="b")])),
        )
        doc_b = DocumentRoot(
            path="b",
            header=_make_header(),
        )
        tree = [doc_a, doc_b]
        rule = ImportsHasNotCyclicalDeps(tree=tree)
        errors = rule.check(doc_a)
        assert errors == []

    def test_cycle_detected(self):
        doc_a = DocumentRoot(
            path="a",
            header=_make_header(imports=ImportsNode(types=[ImportTypeItemNode(type_name={"X"}, from_path="b")])),
        )
        doc_b = DocumentRoot(
            path="b",
            header=_make_header(imports=ImportsNode(types=[ImportTypeItemNode(type_name={"Y"}, from_path="a")])),
        )
        tree = [doc_a, doc_b]
        rule = ImportsHasNotCyclicalDeps(tree=tree)
        errors = rule.check(doc_a)
        assert len(errors) >= 1
        assert any("cyclical" in e.rule for e in errors) or any("cyclical" in e.message.lower() for e in errors)

    def test_cycle_via_usages(self):
        doc_a = DocumentRoot(
            path="a",
            header=_make_header(imports=ImportsNode(usages=[ImportUsageItemNode(usage_name={"U"}, from_path="b")])),
        )
        doc_b = DocumentRoot(
            path="b",
            header=_make_header(imports=ImportsNode(usages=[ImportUsageItemNode(usage_name={"V"}, from_path="a")])),
        )
        tree = [doc_a, doc_b]
        rule = ImportsHasNotCyclicalDeps(tree=tree)
        errors = rule.check(doc_a)
        assert len(errors) >= 1

    def test_no_imports_no_errors(self):
        doc = DocumentRoot(path="a", header=_make_header())
        rule = ImportsHasNotCyclicalDeps(tree=[doc])
        errors = rule.check(doc)
        assert errors == []


class TestImportTypeExists:
    """ImportTypeExists: imported type must exist in target document."""

    def test_type_found_in_entity(self):
        doc_b = DocumentRoot(
            path="b",
            header=_make_header(),
            body=BodyNode(entities=[EntityTypeNode(name="MyType")]),
        )
        doc_a = DocumentRoot(
            path="a",
            header=_make_header(imports=ImportsNode(types=[ImportTypeItemNode(type_name={"MyType"}, from_path="b")])),
        )
        tree = [doc_a, doc_b]
        rule = ImportTypeExists(tree=tree)
        errors = rule.check(doc_a)
        assert errors == []

    def test_type_found_in_routine(self):
        doc_b = DocumentRoot(
            path="b",
            header=_make_header(),
            body=BodyNode(routines=[RoutineTypeNode(name="MyRoutine")]),
        )
        doc_a = DocumentRoot(
            path="a",
            header=_make_header(
                imports=ImportsNode(types=[ImportTypeItemNode(type_name={"MyRoutine"}, from_path="b")])
            ),
        )
        tree = [doc_a, doc_b]
        rule = ImportTypeExists(tree=tree)
        errors = rule.check(doc_a)
        assert errors == []

    def test_type_not_found(self, tmp_path):
        from_path = str(tmp_path / "b")
        tmp_path.joinpath("b").mkdir()
        doc_b = DocumentRoot(path=from_path, header=_make_header(), body=BodyNode())
        doc_a = DocumentRoot(
            path="a",
            header=_make_header(
                imports=ImportsNode(types=[ImportTypeItemNode(type_name={"MissingType"}, from_path=from_path)])
            ),
        )
        tree = [doc_a, doc_b]
        rule = ImportTypeExists(tree=tree)
        errors = rule.check(doc_a)
        assert len(errors) >= 1
        assert any(
            "not_found" in e.rule or "not found" in e.message.lower() or "not defined" in e.message.lower()
            for e in errors
        )

    def test_path_not_exists_skipped(self):
        doc_a = DocumentRoot(
            path="a",
            header=_make_header(
                imports=ImportsNode(types=[ImportTypeItemNode(type_name={"X"}, from_path="/nonexistent/path")])
            ),
        )
        rule = ImportTypeExists(tree=[doc_a])
        errors = rule.check(doc_a)
        assert errors == []

    def test_type_found_in_header_types(self):
        doc_b = DocumentRoot(
            path="b",
            header=_make_header(),
        )
        doc_b.header.types = ["HeaderType"]
        doc_a = DocumentRoot(
            path="a",
            header=_make_header(
                imports=ImportsNode(types=[ImportTypeItemNode(type_name={"HeaderType"}, from_path="b")])
            ),
        )
        tree = [doc_a, doc_b]
        rule = ImportTypeExists(tree=tree)
        errors = rule.check(doc_a)
        assert errors == []


class TestEmbeddedTypeHasLowLevel:
    """EmbeddedTypeHasLowLevel: embedded types must be from documents lower in hierarchy."""

    def test_lower_level_ok(self):
        parent_doc = DocumentRoot(
            path="project/pkg",
            header=_make_header(),
            body=BodyNode(entities=[EntityTypeNode(name="SubType", embedded=True)]),
        )
        child_doc = DocumentRoot(
            path="project/pkg/sub",
            header=_make_header(),
            body=BodyNode(entities=[EntityTypeNode(name="SubType", embedded=False)]),
        )
        tree = [parent_doc, child_doc]
        rule = EmbeddedTypeHasLowLevel(tree=tree)
        errors = rule.check(parent_doc)
        assert errors == []

    def test_higher_level_error(self):
        parent_doc = DocumentRoot(
            path="project/pkg",
            header=_make_header(),
            body=BodyNode(entities=[EntityTypeNode(name="OtherType", embedded=True)]),
        )
        other_doc = DocumentRoot(
            path="project/other",
            header=_make_header(),
            body=BodyNode(entities=[EntityTypeNode(name="OtherType", embedded=False)]),
        )
        tree = [parent_doc, other_doc]
        rule = EmbeddedTypeHasLowLevel(tree=tree)
        errors = rule.check(parent_doc)
        assert len(errors) >= 1
        assert any("embedded" in e.message.lower() for e in errors)

    def test_embedded_routine_lower_level(self):
        parent_doc = DocumentRoot(
            path="project/pkg",
            header=_make_header(),
            body=BodyNode(routines=[RoutineTypeNode(name="SubRoutine", embedded=True)]),
        )
        child_doc = DocumentRoot(
            path="project/pkg/sub",
            header=_make_header(),
            body=BodyNode(routines=[RoutineTypeNode(name="SubRoutine", embedded=False)]),
        )
        tree = [parent_doc, child_doc]
        rule = EmbeddedTypeHasLowLevel(tree=tree)
        errors = rule.check(parent_doc)
        assert errors == []

    def test_no_embedded_no_errors(self):
        doc = DocumentRoot(
            path="project/pkg",
            header=_make_header(),
            body=BodyNode(entities=[EntityTypeNode(name="NormalType", embedded=False)]),
        )
        rule = EmbeddedTypeHasLowLevel(tree=[doc])
        errors = rule.check(doc)
        assert errors == []

    def test_normpath_normalization(self):
        parent_doc = DocumentRoot(
            path="project/./pkg",
            header=_make_header(),
            body=BodyNode(entities=[EntityTypeNode(name="SubType", embedded=True)]),
        )
        child_doc = DocumentRoot(
            path="project/pkg/sub",
            header=_make_header(),
            body=BodyNode(entities=[EntityTypeNode(name="SubType", embedded=False)]),
        )
        tree = [parent_doc, child_doc]
        rule = EmbeddedTypeHasLowLevel(tree=tree)
        errors = rule.check(parent_doc)
        assert errors == []
