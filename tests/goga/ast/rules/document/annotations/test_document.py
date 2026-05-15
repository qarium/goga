from __future__ import annotations

import inspect
from typing import ClassVar

from goga.ast.nodes.body import BodyNode, EntityTypeNode, MethodNode, PropertyNode, RoutineTypeNode
from goga.ast.nodes.common import AnnotationsNode
from goga.ast.nodes.document import DocumentNode, DocumentRoot
from goga.ast.nodes.header import (
    HeaderNode,
    ImportsNode,
    ImportTypeItemNode,
    ImportUsageItemNode,
    UsageItemNode,
    UsagesNode,
)
from goga.ast.rules.base.document import DocumentRule
from goga.ast.rules.document.annotations.rules import AnnotationLinksExists


class TestContract:
    """Contract tests — verify AnnotationLinksExists exists, inherits DocumentRule, has correct check signature."""

    CLASSES: ClassVar[list[type]] = [AnnotationLinksExists]

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
            assert cls.__module__ == "goga.ast.rules.document.annotations.rules", (
                f"{cls.__name__} has wrong module: {cls.__module__}"
            )


def _make_header(data=None, imports=None, annotations=None, usages=None):
    return HeaderNode(
        data=data or {},
        imports=imports or ImportsNode(),
        annotations=annotations or AnnotationsNode(root=None),
        usages=usages or UsagesNode(),
    )


class TestAnnotationLinksExists:
    """AnnotationLinksExists: all links in annotations must resolve to known names."""

    def test_link_found_in_imports_type(self):
        import_item = ImportTypeItemNode(type_name={"MyType"}, from_path="pkg")
        header = _make_header(
            imports=ImportsNode(types=[import_item]),
            annotations=AnnotationsNode(root=None, links=["MyType"]),
        )
        root = DocumentRoot(path="test.md", header=header)
        node = DocumentNode(root=root)
        rule = AnnotationLinksExists()
        errors = rule.check(node)
        assert errors == []

    def test_link_found_in_imports_alias(self):
        import_item = ImportTypeItemNode(type_name={"OriginalType"}, from_path="pkg", alias="MyAlias")
        header = _make_header(
            imports=ImportsNode(types=[import_item]),
            annotations=AnnotationsNode(root=None, links=["MyAlias"]),
        )
        root = DocumentRoot(path="test.md", header=header)
        node = DocumentNode(root=root)
        rule = AnnotationLinksExists()
        errors = rule.check(node)
        assert errors == []

    def test_link_found_in_usages(self):
        usage_item = UsageItemNode(name="MyUsage")
        header = _make_header(
            usages=UsagesNode(items=[usage_item]),
            annotations=AnnotationsNode(root=None, links=["MyUsage"]),
        )
        root = DocumentRoot(path="test.md", header=header)
        node = DocumentNode(root=root)
        rule = AnnotationLinksExists()
        errors = rule.check(node)
        assert errors == []

    def test_link_found_in_entity_name(self):
        entity = EntityTypeNode(name="OtherEntity")
        entity2 = EntityTypeNode(
            name="MyEntity",
            annotations=AnnotationsNode(root=None, links=["OtherEntity"]),
        )
        header = _make_header()
        root = DocumentRoot(
            path="test.md",
            header=header,
            body=BodyNode(entities=[entity, entity2]),
        )
        node = DocumentNode(root=root)
        rule = AnnotationLinksExists()
        errors = rule.check(node)
        assert errors == []

    def test_link_found_in_routine_name(self):
        routine = RoutineTypeNode(name="MyRoutine")
        entity = EntityTypeNode(
            name="MyEntity",
            annotations=AnnotationsNode(root=None, links=["MyRoutine"]),
        )
        header = _make_header()
        root = DocumentRoot(
            path="test.md",
            header=header,
            body=BodyNode(entities=[entity], routines=[routine]),
        )
        node = DocumentNode(root=root)
        rule = AnnotationLinksExists()
        errors = rule.check(node)
        assert errors == []

    def test_link_found_in_signature(self):
        entity = EntityTypeNode(
            name="MyEntity",
            signature="(param: MyType) -> rv:Result",
            annotations=AnnotationsNode(root=None, links=["MyType"]),
        )
        header = _make_header()
        root = DocumentRoot(
            path="test.md",
            header=header,
            body=BodyNode(entities=[entity]),
        )
        node = DocumentNode(root=root)
        rule = AnnotationLinksExists()
        errors = rule.check(node)
        assert errors == []

    def test_link_not_found(self):
        header = _make_header(
            annotations=AnnotationsNode(root=None, links=["UnknownLink"]),
        )
        root = DocumentRoot(path="test.md", header=header)
        node = DocumentNode(root=root)
        rule = AnnotationLinksExists()
        errors = rule.check(node)
        assert len(errors) == 1
        assert "does not match" in errors[0].message

    def test_separator_underscore_not_valid(self):
        entity = EntityTypeNode(
            name="MyEntity",
            signature="(param: param_MyType) -> rv:Result",
            annotations=AnnotationsNode(root=None, links=["MyType"]),
        )
        header = _make_header()
        root = DocumentRoot(
            path="test.md",
            header=header,
            body=BodyNode(entities=[entity]),
        )
        node = DocumentNode(root=root)
        rule = AnnotationLinksExists()
        errors = rule.check(node)
        assert len(errors) == 1

    def test_separator_hyphen_not_valid(self):
        entity = EntityTypeNode(
            name="MyEntity",
            signature="(param: param-MyType) -> rv:Result",
            annotations=AnnotationsNode(root=None, links=["MyType"]),
        )
        header = _make_header()
        root = DocumentRoot(
            path="test.md",
            header=header,
            body=BodyNode(entities=[entity]),
        )
        node = DocumentNode(root=root)
        rule = AnnotationLinksExists()
        errors = rule.check(node)
        assert len(errors) == 1

    def test_separator_colon_is_valid(self):
        entity = EntityTypeNode(
            name="MyEntity",
            signature="(x: param:MyType) -> rv:Result",
            annotations=AnnotationsNode(root=None, links=["MyType"]),
        )
        header = _make_header()
        root = DocumentRoot(
            path="test.md",
            header=header,
            body=BodyNode(entities=[entity]),
        )
        node = DocumentNode(root=root)
        rule = AnnotationLinksExists()
        errors = rule.check(node)
        assert errors == []

    def test_embedded_entity_skipped(self):
        entity = EntityTypeNode(
            name="EmbeddedEntity",
            embedded=True,
            annotations=AnnotationsNode(root=None, links=["UnknownLink"]),
        )
        header = _make_header()
        root = DocumentRoot(
            path="test.md",
            header=header,
            body=BodyNode(entities=[entity]),
        )
        node = DocumentNode(root=root)
        rule = AnnotationLinksExists()
        errors = rule.check(node)
        assert errors == []

    def test_embedded_routine_skipped(self):
        routine = RoutineTypeNode(
            name="EmbeddedRoutine",
            embedded=True,
            annotations=AnnotationsNode(root=None, links=["UnknownLink"]),
        )
        header = _make_header()
        root = DocumentRoot(
            path="test.md",
            header=header,
            body=BodyNode(routines=[routine]),
        )
        node = DocumentNode(root=root)
        rule = AnnotationLinksExists()
        errors = rule.check(node)
        assert errors == []

    def test_method_link_found_in_signature(self):
        method = MethodNode(
            name="my_method",
            signature="(param: MyType) -> rv:Result",
            annotations=AnnotationsNode(root=None, links=["MyType"]),
        )
        entity = EntityTypeNode(name="MyEntity", methods=[method])
        header = _make_header()
        root = DocumentRoot(
            path="test.md",
            header=header,
            body=BodyNode(entities=[entity]),
        )
        node = DocumentNode(root=root)
        rule = AnnotationLinksExists()
        errors = rule.check(node)
        assert errors == []

    def test_method_link_not_found(self):
        method = MethodNode(
            name="my_method",
            signature="(param: str) -> rv:Result",
            annotations=AnnotationsNode(root=None, links=["UnknownType"]),
        )
        entity = EntityTypeNode(name="MyEntity", methods=[method])
        header = _make_header()
        root = DocumentRoot(
            path="test.md",
            header=header,
            body=BodyNode(entities=[entity]),
        )
        node = DocumentNode(root=root)
        rule = AnnotationLinksExists()
        errors = rule.check(node)
        assert len(errors) == 1

    def test_property_link_found_in_import(self):
        prop = PropertyNode(
            name="my_prop",
            type="str",
            annotations=AnnotationsNode(root=None, links=["MyType"]),
        )
        import_item = ImportTypeItemNode(type_name={"MyType"}, from_path="pkg")
        entity = EntityTypeNode(name="MyEntity", properties=[prop])
        header = _make_header(imports=ImportsNode(types=[import_item]))
        root = DocumentRoot(
            path="test.md",
            header=header,
            body=BodyNode(entities=[entity]),
        )
        node = DocumentNode(root=root)
        rule = AnnotationLinksExists()
        errors = rule.check(node)
        assert errors == []

    def test_property_link_not_found(self):
        prop = PropertyNode(
            name="my_prop",
            type="str",
            annotations=AnnotationsNode(root=None, links=["UnknownType"]),
        )
        entity = EntityTypeNode(name="MyEntity", properties=[prop])
        header = _make_header()
        root = DocumentRoot(
            path="test.md",
            header=header,
            body=BodyNode(entities=[entity]),
        )
        node = DocumentNode(root=root)
        rule = AnnotationLinksExists()
        errors = rule.check(node)
        assert len(errors) == 1

    def test_usage_item_link_not_found(self):
        usage_item = UsageItemNode(
            name="DevUsage",
            annotations=AnnotationsNode(root=None, links=["UnknownLink"]),
        )
        header = _make_header(usages=UsagesNode(items=[usage_item]))
        root = DocumentRoot(path="test.md", header=header)
        node = DocumentNode(root=root)
        rule = AnnotationLinksExists()
        errors = rule.check(node)
        assert len(errors) == 1

    def test_import_usage_name_resolves_link(self):
        import_usage = ImportUsageItemNode(usage_name={"MyUsage"}, from_path="pkg")
        header = _make_header(
            imports=ImportsNode(usages=[import_usage]),
            annotations=AnnotationsNode(root=None, links=["MyUsage"]),
        )
        root = DocumentRoot(path="test.md", header=header)
        node = DocumentNode(root=root)
        rule = AnnotationLinksExists()
        errors = rule.check(node)
        assert errors == []

    def test_import_usage_alias_resolves_link(self):
        import_usage = ImportUsageItemNode(usage_name={"OriginalUsage"}, from_path="pkg", alias="UsageAlias")
        header = _make_header(
            imports=ImportsNode(usages=[import_usage]),
            annotations=AnnotationsNode(root=None, links=["UsageAlias"]),
        )
        root = DocumentRoot(path="test.md", header=header)
        node = DocumentNode(root=root)
        rule = AnnotationLinksExists()
        errors = rule.check(node)
        assert errors == []

    def test_no_links(self):
        header = _make_header(annotations=AnnotationsNode(root=None, links=[]))
        root = DocumentRoot(path="test.md", header=header)
        node = DocumentNode(root=root)
        rule = AnnotationLinksExists()
        errors = rule.check(node)
        assert errors == []

    def test_multiple_errors(self):
        header = _make_header(
            annotations=AnnotationsNode(root=None, links=["Unknown1", "Unknown2"]),
        )
        root = DocumentRoot(path="test.md", header=header)
        node = DocumentNode(root=root)
        rule = AnnotationLinksExists()
        errors = rule.check(node)
        assert len(errors) == 2
