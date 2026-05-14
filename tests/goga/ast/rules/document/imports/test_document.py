from __future__ import annotations

import inspect
import shutil
from typing import ClassVar

from goga.ast.nodes.body import BodyNode, EntityTypeNode, PropertyNode
from goga.ast.nodes.common import AnnotationsNode
from goga.ast.nodes.document import DocumentNode, DocumentRoot
from goga.ast.nodes.header import (
    HeaderNode,
    ImportsNode,
    ImportTypeItemNode,
    ImportUsageItemNode,
)
from goga.ast.rules.base.document import DocumentRule
from goga.ast.rules.document.imports.document import (
    ImportHasNotDuplicate,
    ImportHasValidFromPath,
    ImportIsUsed,
    ImportItemIsValid,
    ImportsCanNotBeEmpty,
    ImportsHasOnlyValidKeys,
    ImportUsageExists,
)


class TestContract:
    """Contract tests — verify all 7 classes exist, inherit DocumentRule, have correct check signature."""

    CLASSES: ClassVar[list[type]] = [
        ImportsCanNotBeEmpty,
        ImportsHasOnlyValidKeys,
        ImportItemIsValid,
        ImportUsageExists,
        ImportHasValidFromPath,
        ImportHasNotDuplicate,
        ImportIsUsed,
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
            # params[0] is 'self', params[1] is 'node'
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
            assert cls.__module__ == "goga.ast.rules.document.imports.document", (
                f"{cls.__name__} has wrong module: {cls.__module__}"
            )


class TestImportsCanNotBeEmpty:
    """ImportsCanNotBeEmpty: imports block must not be empty when declared."""

    def test_empty_imports_returns_error(self):
        root = DocumentRoot(
            path="test.md",
            header=_make_header(data={"Imports": {}}, imports=ImportsNode()),
        )
        node = DocumentNode(root=root)
        rule = ImportsCanNotBeEmpty()
        errors = rule.check(node)
        assert len(errors) == 1
        assert "empty" in errors[0].message.lower()

    def test_no_imports_block_returns_empty(self):
        root = DocumentRoot(path="test.md")
        node = DocumentNode(root=root)
        rule = ImportsCanNotBeEmpty()
        assert rule.check(node) == []

    def test_non_empty_imports_returns_empty(self):
        root = DocumentRoot(
            path="test.md",
            header=_make_header(
                data={"Imports": {}},
                imports=ImportsNode(
                    types=[ImportTypeItemNode(type_name={"Foo"}, from_path="bar")],
                ),
            ),
        )
        node = DocumentNode(root=root)
        rule = ImportsCanNotBeEmpty()
        assert rule.check(node) == []


class TestImportsHasOnlyValidKeys:
    """ImportsHasOnlyValidKeys: import items must only contain Types, Usages, From keys."""

    def test_unknown_key_returns_error(self):
        item = ImportTypeItemNode(
            type_name={"Foo"},
            from_path="bar",
            data={"Types": "Foo", "From": "bar", "Extra": "bad"},
        )
        root = DocumentRoot(
            path="test.md",
            header=_make_header(
                data={"Imports": {}},
                imports=ImportsNode(types=[item]),
            ),
        )
        node = DocumentNode(root=root)
        rule = ImportsHasOnlyValidKeys()
        errors = rule.check(node)
        assert len(errors) == 1
        assert "unknown keys" in errors[0].message.lower()

    def test_valid_keys_returns_empty(self):
        item = ImportTypeItemNode(
            type_name={"Foo"},
            from_path="bar",
            data={"Types": "Foo", "From": "bar"},
        )
        root = DocumentRoot(
            path="test.md",
            header=_make_header(
                data={"Imports": {}},
                imports=ImportsNode(types=[item]),
            ),
        )
        node = DocumentNode(root=root)
        rule = ImportsHasOnlyValidKeys()
        assert rule.check(node) == []


class TestImportItemIsValid:
    """ImportItemIsValid: every import item must have at least one type name or usage name."""

    def test_empty_type_name_returns_error(self):
        item = ImportTypeItemNode(type_name=set(), from_path="bar")
        root = DocumentRoot(
            path="test.md",
            header=_make_header(
                data={"Imports": {}},
                imports=ImportsNode(types=[item]),
            ),
        )
        node = DocumentNode(root=root)
        rule = ImportItemIsValid()
        errors = rule.check(node)
        assert len(errors) == 1
        assert "no types listed" in errors[0].message.lower() or "no usages listed" in errors[0].message.lower()

    def test_non_empty_type_name_returns_empty(self):
        item = ImportTypeItemNode(type_name={"Foo"}, from_path="bar")
        root = DocumentRoot(
            path="test.md",
            header=_make_header(
                data={"Imports": {}},
                imports=ImportsNode(types=[item]),
            ),
        )
        node = DocumentNode(root=root)
        rule = ImportItemIsValid()
        assert rule.check(node) == []

    def test_empty_usage_name_returns_error(self):
        item = ImportUsageItemNode(usage_name=set(), from_path="bar")
        root = DocumentRoot(
            path="test.md",
            header=_make_header(
                data={"Imports": {}},
                imports=ImportsNode(usages=[item]),
            ),
        )
        node = DocumentNode(root=root)
        rule = ImportItemIsValid()
        errors = rule.check(node)
        assert len(errors) == 1
        assert "no types listed" in errors[0].message.lower() or "no usages listed" in errors[0].message.lower()


class TestImportUsageExists:
    """ImportUsageExists: imported usage must exist as .md file in .usages/ directory."""

    def test_usage_file_not_found(self, tmp_path):
        cell_dir = tmp_path / "cell"
        cell_dir.mkdir()
        item = ImportUsageItemNode(
            usage_name={"MyUsage"},
            from_path=str(cell_dir),
        )
        root = DocumentRoot(
            path="test.md",
            header=_make_header(
                data={"Imports": {}},
                imports=ImportsNode(usages=[item]),
            ),
        )
        node = DocumentNode(root=root)
        rule = ImportUsageExists()
        errors = rule.check(node)
        assert len(errors) == 1
        assert "not_found" in errors[0].message.lower() or "does not exist" in errors[0].message.lower()

    def test_usage_file_exists(self, tmp_path):
        cell_dir = tmp_path / "cell"
        cell_dir.mkdir()
        usages_dir = cell_dir / ".usages"
        usages_dir.mkdir()
        (usages_dir / "MyUsage.md").write_text("content")
        item = ImportUsageItemNode(
            usage_name={"MyUsage"},
            from_path=str(cell_dir),
        )
        root = DocumentRoot(
            path="test.md",
            header=_make_header(
                data={"Imports": {}},
                imports=ImportsNode(usages=[item]),
            ),
        )
        node = DocumentNode(root=root)
        rule = ImportUsageExists()
        assert rule.check(node) == []

    def test_empty_from_path_skipped(self):
        item = ImportUsageItemNode(usage_name={"MyUsage"}, from_path="")
        root = DocumentRoot(
            path="test.md",
            header=_make_header(
                data={"Imports": {}},
                imports=ImportsNode(usages=[item]),
            ),
        )
        node = DocumentNode(root=root)
        rule = ImportUsageExists()
        assert rule.check(node) == []

    def test_nonexistent_from_path_skipped(self):
        item = ImportUsageItemNode(
            usage_name={"MyUsage"},
            from_path="/nonexistent/path",
        )
        root = DocumentRoot(
            path="test.md",
            header=_make_header(
                data={"Imports": {}},
                imports=ImportsNode(usages=[item]),
            ),
        )
        node = DocumentNode(root=root)
        rule = ImportUsageExists()
        assert rule.check(node) == []


class TestImportHasValidFromPath:
    """ImportHasValidFromPath: from_path must be non-empty, exist, and not escape CWD."""

    def test_empty_from_path(self):
        item = ImportTypeItemNode(type_name={"Foo"}, from_path="")
        root = DocumentRoot(
            path="test.md",
            header=_make_header(
                data={"Imports": {}},
                imports=ImportsNode(types=[item]),
            ),
        )
        node = DocumentNode(root=root)
        rule = ImportHasValidFromPath()
        errors = rule.check(node)
        assert len(errors) == 1
        assert "empty" in errors[0].message.lower()

    def test_from_path_not_found(self):
        item = ImportTypeItemNode(type_name={"Foo"}, from_path="/nonexistent/path")
        root = DocumentRoot(
            path="test.md",
            header=_make_header(
                data={"Imports": {}},
                imports=ImportsNode(types=[item]),
            ),
        )
        node = DocumentNode(root=root)
        rule = ImportHasValidFromPath()
        errors = rule.check(node)
        assert len(errors) == 1
        assert "not found" in errors[0].message.lower()

    def test_valid_from_path(self, tmp_path, monkeypatch):
        cell_dir = tmp_path / "test_cell_for_import"
        cell_dir.mkdir()
        monkeypatch.chdir(tmp_path)
        item = ImportTypeItemNode(type_name={"Foo"}, from_path=str(cell_dir))
        root = DocumentRoot(
            path="test.md",
            header=_make_header(
                data={"Imports": {}},
                imports=ImportsNode(types=[item]),
            ),
        )
        node = DocumentNode(root=root)
        rule = ImportHasValidFromPath()
        assert rule.check(node) == []


class TestImportHasNotDuplicate:
    """ImportHasNotDuplicate: type/usage names must be unique across imports."""

    def test_duplicate_returns_error(self):
        item1 = ImportTypeItemNode(type_name={"Foo"}, from_path="bar")
        item2 = ImportTypeItemNode(type_name={"Foo"}, from_path="baz")
        root = DocumentRoot(
            path="test.md",
            header=_make_header(
                data={"Imports": {}},
                imports=ImportsNode(types=[item1, item2]),
            ),
        )
        node = DocumentNode(root=root)
        rule = ImportHasNotDuplicate()
        errors = rule.check(node)
        assert len(errors) == 1
        assert "more than once" in errors[0].message.lower()

    def test_unique_returns_empty(self):
        item1 = ImportTypeItemNode(type_name={"Foo"}, from_path="bar")
        item2 = ImportTypeItemNode(type_name={"Bar"}, from_path="baz")
        root = DocumentRoot(
            path="test.md",
            header=_make_header(
                data={"Imports": {}},
                imports=ImportsNode(types=[item1, item2]),
            ),
        )
        node = DocumentNode(root=root)
        rule = ImportHasNotDuplicate()
        assert rule.check(node) == []


class TestImportIsUsed:
    """ImportIsUsed: imported types/usages must be used in annotations or signatures."""

    def test_unused_type_returns_error(self):
        item = ImportTypeItemNode(type_name={"UnusedType"}, from_path="bar")
        root = DocumentRoot(
            path="test.md",
            header=_make_header(
                data={"Imports": {}},
                imports=ImportsNode(types=[item]),
            ),
        )
        node = DocumentNode(root=root)
        rule = ImportIsUsed()
        errors = rule.check(node)
        assert len(errors) == 1
        assert "not used" in errors[0].message.lower()

    def test_type_used_in_annotation_returns_empty(self):
        item = ImportTypeItemNode(type_name={"UsedType"}, from_path="bar")
        root = DocumentRoot(
            path="test.md",
            header=_make_header(
                data={"Imports": {}},
                annotations=AnnotationsNode(links=["UsedType"]),
                imports=ImportsNode(types=[item]),
            ),
        )
        node = DocumentNode(root=root)
        rule = ImportIsUsed()
        assert rule.check(node) == []

    def test_embedded_considered_used(self):
        item = ImportTypeItemNode(type_name={"Foo"}, from_path="bar")
        root = DocumentRoot(
            path="test.md",
            embeddings=[("Foo", "other.md")],
            header=_make_header(
                data={"Imports": {}},
                imports=ImportsNode(types=[item]),
            ),
        )
        node = DocumentNode(root=root)
        rule = ImportIsUsed()
        assert rule.check(node) == []

    def test_usage_not_checked_in_signatures(self):
        item = ImportUsageItemNode(usage_name={"SomeUsage"}, from_path="bar")
        entity = EntityTypeNode(
            name="MyEntity",
            signature="(param: SomeUsage)",
            annotations=AnnotationsNode(),
        )
        root = DocumentRoot(
            path="test.md",
            header=_make_header(
                data={"Imports": {}},
                imports=ImportsNode(usages=[item]),
            ),
            body=_make_body(entities=[entity]),
        )
        node = DocumentNode(root=root)
        rule = ImportIsUsed()
        errors = rule.check(node)
        # usages are not matched in signatures, only in annotation links
        assert len(errors) == 1
        assert "not used" in errors[0].message.lower()

    def test_type_used_in_signature(self):
        item = ImportTypeItemNode(type_name={"MyType"}, from_path="bar")
        entity = EntityTypeNode(
            name="Entity",
            signature="(param: MyType)",
            annotations=AnnotationsNode(),
        )
        root = DocumentRoot(
            path="test.md",
            header=_make_header(
                data={"Imports": {}},
                imports=ImportsNode(types=[item]),
            ),
            body=_make_body(entities=[entity]),
        )
        node = DocumentNode(root=root)
        rule = ImportIsUsed()
        assert rule.check(node) == []

    def test_type_used_in_property_type(self):
        item = ImportTypeItemNode(type_name={"MyType"}, from_path="bar")
        entity = EntityTypeNode(
            name="Entity",
            signature="()",
            annotations=AnnotationsNode(),
            properties=[PropertyNode(name="prop", type="MyType")],
        )
        root = DocumentRoot(
            path="test.md",
            header=_make_header(
                data={"Imports": {}},
                imports=ImportsNode(types=[item]),
            ),
            body=_make_body(entities=[entity]),
        )
        node = DocumentNode(root=root)
        rule = ImportIsUsed()
        assert rule.check(node) == []

    def test_type_used_with_alias(self):
        item = ImportTypeItemNode(type_name={"OriginalName"}, from_path="bar", alias="Alias")
        root = DocumentRoot(
            path="test.md",
            header=_make_header(
                data={"Imports": {}},
                annotations=AnnotationsNode(links=["Alias"]),
                imports=ImportsNode(types=[item]),
            ),
        )
        node = DocumentNode(root=root)
        rule = ImportIsUsed()
        assert rule.check(node) == []


class TestImportItemIsValidExtra:
    """Extra cases from old test_import_item_is_valid.py."""

    def test_mixed_items_all_valid(self):
        item_t = ImportTypeItemNode(type_name={"Foo"}, from_path="bar")
        item_u = ImportUsageItemNode(usage_name={"my_usage"}, from_path="baz")
        root = DocumentRoot(
            path="test.md",
            header=_make_header(
                data={"Imports": {}},
                imports=ImportsNode(types=[item_t], usages=[item_u]),
            ),
        )
        node = DocumentNode(root=root)
        rule = ImportItemIsValid()
        assert rule.check(node) == []

    def test_empty_type_error_message_template(self):
        item = ImportTypeItemNode(type_name=set(), from_path="some/path")
        root = DocumentRoot(
            path="test.md",
            header=_make_header(
                data={"Imports": {}},
                imports=ImportsNode(types=[item]),
            ),
        )
        node = DocumentNode(root=root)
        rule = ImportItemIsValid()
        errors = rule.check(node)
        assert len(errors) == 1
        assert errors[0].message == (
            "Import from 'some/path' has no Types listed — specify at least one type to import"
        )

    def test_empty_usage_error_message_template(self):
        item = ImportUsageItemNode(usage_name=set(), from_path="some/path")
        root = DocumentRoot(
            path="test.md",
            header=_make_header(
                data={"Imports": {}},
                imports=ImportsNode(usages=[item]),
            ),
        )
        node = DocumentNode(root=root)
        rule = ImportItemIsValid()
        errors = rule.check(node)
        assert len(errors) == 1
        assert errors[0].message == (
            "Import from 'some/path' has no Usages listed — specify at least one usage to import"
        )

    def test_both_empty_type_and_empty_usage(self):
        item_t = ImportTypeItemNode(type_name=set(), from_path="a")
        item_u = ImportUsageItemNode(usage_name=set(), from_path="b")
        root = DocumentRoot(
            path="test.md",
            header=_make_header(
                data={"Imports": {}},
                imports=ImportsNode(types=[item_t], usages=[item_u]),
            ),
        )
        node = DocumentNode(root=root)
        rule = ImportItemIsValid()
        errors = rule.check(node)
        assert len(errors) == 2
        assert all(e.rule == "import_item_is_valid" for e in errors)


class TestImportUsageExistsExtra:
    """Extra cases from old test_import_usage_exists.py."""

    def test_multiple_usage_files_exist(self, tmp_path):
        usages_dir = tmp_path / "cell" / ".usages"
        usages_dir.mkdir(parents=True)
        (usages_dir / "usage_a.md").write_text("a")
        (usages_dir / "usage_b.md").write_text("b")

        item = ImportUsageItemNode(
            usage_name={"usage_a", "usage_b"},
            from_path=str(tmp_path / "cell"),
        )
        root = DocumentRoot(
            path="test.md",
            header=_make_header(
                data={"Imports": {}},
                imports=ImportsNode(usages=[item]),
            ),
        )
        node = DocumentNode(root=root)
        rule = ImportUsageExists()
        assert rule.check(node) == []

    def test_error_message_template(self, tmp_path):
        cell_dir = tmp_path / "some_cell"
        cell_dir.mkdir()
        expected_path = str(cell_dir / ".usages" / "missing.md")
        item = ImportUsageItemNode(
            usage_name={"missing"},
            from_path=str(cell_dir),
        )
        root = DocumentRoot(
            path="test.md",
            header=_make_header(
                data={"Imports": {}},
                imports=ImportsNode(usages=[item]),
            ),
        )
        node = DocumentNode(root=root)
        rule = ImportUsageExists()
        errors = rule.check(node)
        assert len(errors) == 1
        assert errors[0].message == (f"Usage 'missing' does not exist on filesystem by path '{expected_path}'")

    def test_one_missing_one_found(self, tmp_path):
        usages_dir = tmp_path / "cell" / ".usages"
        usages_dir.mkdir(parents=True)
        (usages_dir / "found_usage.md").write_text("found")

        item = ImportUsageItemNode(
            usage_name={"found_usage", "missing_usage"},
            from_path=str(tmp_path / "cell"),
        )
        root = DocumentRoot(
            path="test.md",
            header=_make_header(
                data={"Imports": {}},
                imports=ImportsNode(usages=[item]),
            ),
        )
        node = DocumentNode(root=root)
        rule = ImportUsageExists()
        errors = rule.check(node)
        assert len(errors) == 1
        assert "missing_usage" in errors[0].message

    def test_type_items_skipped(self):
        item = ImportTypeItemNode(type_name={"SomeType"}, from_path="some/path")
        root = DocumentRoot(
            path="test.md",
            header=_make_header(
                data={"Imports": {}},
                imports=ImportsNode(types=[item]),
            ),
        )
        node = DocumentNode(root=root)
        rule = ImportUsageExists()
        assert rule.check(node) == []

    def test_mixed_type_skipped_usage_checked(self, tmp_path):
        nonexistent = tmp_path / "nonexistent"
        nonexistent.mkdir()
        item_t = ImportTypeItemNode(type_name={"SomeType"}, from_path=str(tmp_path))
        item_u = ImportUsageItemNode(
            usage_name={"some_usage"},
            from_path=str(nonexistent),
        )
        root = DocumentRoot(
            path="test.md",
            header=_make_header(
                data={"Imports": {}},
                imports=ImportsNode(types=[item_t], usages=[item_u]),
            ),
        )
        node = DocumentNode(root=root)
        rule = ImportUsageExists()
        errors = rule.check(node)
        assert len(errors) == 1
        assert errors[0].rule == "import_usage_exists"


class TestImportHasValidFromPathExtra:
    """Extra cases from old test_document.py."""

    def test_from_deep_nested_path(self, tmp_path, monkeypatch):
        src = tmp_path / "some" / "deep" / "path"
        src.mkdir(parents=True)
        (src / "CODEMANIFEST").write_text("Types:\n  Foo:\n")

        item = ImportTypeItemNode(type_name={"Foo"}, from_path=str(src))
        root = DocumentRoot(
            path="test.md",
            header=_make_header(
                data={"Imports": {}},
                imports=ImportsNode(types=[item]),
            ),
        )
        root.path = str(tmp_path)
        node = DocumentNode(root=root)
        rule = ImportHasValidFromPath()
        monkeypatch.chdir(tmp_path)
        assert rule.check(node) == []

    def test_absolute_path_outside_project(self, tmp_path, monkeypatch):
        real_outside = tmp_path.parent / f"goga_test_outside_{id(tmp_path)}"
        real_outside.mkdir(parents=True, exist_ok=True)
        (real_outside / "CODEMANIFEST").write_text("Types:\n  Bar:\n")
        try:
            item = ImportTypeItemNode(type_name={"Bar"}, from_path=str(real_outside))
            root = DocumentRoot(
                path="test.md",
                header=_make_header(
                    data={"Imports": {}},
                    imports=ImportsNode(types=[item]),
                ),
            )
            root.path = str(tmp_path)
            node = DocumentNode(root=root)
            rule = ImportHasValidFromPath()
            monkeypatch.chdir(tmp_path)
            errors = rule.check(node)
            assert len(errors) == 1
            assert "outside the project root" in errors[0].message
        finally:
            shutil.rmtree(real_outside, ignore_errors=True)


# --- Helpers ---


def _make_header(data=None, imports=None, annotations=None):
    return HeaderNode(
        data=data or {},
        imports=imports or ImportsNode(),
        annotations=annotations or AnnotationsNode(root=None),
    )


def _make_body(entities=None, routines=None):
    return BodyNode(entities=entities or [], routines=routines or [])
