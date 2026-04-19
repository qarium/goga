"""Contract tests for ImportItemIsValid rule."""

from goga.ast.errors import DocumentRuleError
from goga.ast.nodes import (
    DocumentNode,
    DocumentRoot,
    HeaderNode,
    ImportTypeItemNode,
    ImportUsageItemNode,
    ImportsNode,
)
from goga.ast.rules import ImportItemIsValid


class TestImportItemIsValidName:
    def test_default_name(self):
        rule = ImportItemIsValid()
        assert rule.name == "import_item_is_valid"


class TestImportItemIsValidHappyPath:
    def test_type_item_with_types_no_errors(self):
        root = DocumentRoot(
            header=HeaderNode(
                imports=ImportsNode(
                    items=[ImportTypeItemNode(type_name={"Foo"}, from_path="bar")],
                ),
            ),
        )
        node = DocumentNode(root=root)
        rule = ImportItemIsValid()
        errors = rule.check(node)
        assert errors == []

    def test_usage_item_with_usages_no_errors(self):
        root = DocumentRoot(
            header=HeaderNode(
                imports=ImportsNode(
                    items=[ImportUsageItemNode(usage_name={"my_usage"}, from_path="baz")],
                ),
            ),
        )
        node = DocumentNode(root=root)
        rule = ImportItemIsValid()
        errors = rule.check(node)
        assert errors == []

    def test_mixed_items_all_valid(self):
        root = DocumentRoot(
            header=HeaderNode(
                imports=ImportsNode(
                    items=[
                        ImportTypeItemNode(type_name={"Foo"}, from_path="bar"),
                        ImportUsageItemNode(usage_name={"my_usage"}, from_path="baz"),
                    ],
                ),
            ),
        )
        node = DocumentNode(root=root)
        rule = ImportItemIsValid()
        errors = rule.check(node)
        assert errors == []


class TestImportItemIsValidEmptyType:
    def test_empty_type_name_produces_error(self):
        root = DocumentRoot(
            header=HeaderNode(
                imports=ImportsNode(
                    items=[ImportTypeItemNode(type_name=set(), from_path="bar")],
                ),
            ),
        )
        node = DocumentNode(root=root)
        rule = ImportItemIsValid()
        errors = rule.check(node)
        assert len(errors) == 1
        assert isinstance(errors[0], DocumentRuleError)
        assert errors[0].rule == "import_item_is_valid"
        assert "has no Types listed" in errors[0].message
        assert "bar" in errors[0].message

    def test_error_message_template(self):
        root = DocumentRoot(
            header=HeaderNode(
                imports=ImportsNode(
                    items=[ImportTypeItemNode(type_name=set(), from_path="some/path")],
                ),
            ),
        )
        node = DocumentNode(root=root)
        rule = ImportItemIsValid()
        errors = rule.check(node)
        assert len(errors) == 1
        assert errors[0].message == (
            "Import from 'some/path' has no Types listed — specify at least one type to import"
        )


class TestImportItemIsValidEmptyUsage:
    def test_empty_usage_name_produces_error(self):
        root = DocumentRoot(
            header=HeaderNode(
                imports=ImportsNode(
                    items=[ImportUsageItemNode(usage_name=set(), from_path="baz")],
                ),
            ),
        )
        node = DocumentNode(root=root)
        rule = ImportItemIsValid()
        errors = rule.check(node)
        assert len(errors) == 1
        assert isinstance(errors[0], DocumentRuleError)
        assert errors[0].rule == "import_item_is_valid"
        assert "has no Usages listed" in errors[0].message
        assert "baz" in errors[0].message

    def test_error_message_template(self):
        root = DocumentRoot(
            header=HeaderNode(
                imports=ImportsNode(
                    items=[ImportUsageItemNode(usage_name=set(), from_path="some/path")],
                ),
            ),
        )
        node = DocumentNode(root=root)
        rule = ImportItemIsValid()
        errors = rule.check(node)
        assert len(errors) == 1
        assert errors[0].message == (
            "Import from 'some/path' has no Usages listed — specify at least one type to import"
        )


class TestImportItemIsValidMultipleErrors:
    def test_both_empty_type_and_empty_usage(self):
        root = DocumentRoot(
            header=HeaderNode(
                imports=ImportsNode(
                    items=[
                        ImportTypeItemNode(type_name=set(), from_path="a"),
                        ImportUsageItemNode(usage_name=set(), from_path="b"),
                    ],
                ),
            ),
        )
        node = DocumentNode(root=root)
        rule = ImportItemIsValid()
        errors = rule.check(node)
        assert len(errors) == 2
        assert errors[0].rule == "import_item_is_valid"
        assert errors[1].rule == "import_item_is_valid"
