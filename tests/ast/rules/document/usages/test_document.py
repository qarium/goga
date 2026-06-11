from __future__ import annotations

import inspect
from typing import ClassVar
from unittest.mock import MagicMock, patch

import requests.exceptions
from goga.ast.nodes.body import BodyNode, EntityTypeNode, MethodNode, PropertyNode, RoutineTypeNode
from goga.ast.nodes.common import AnnotationsNode
from goga.ast.nodes.document import DocumentNode, DocumentRoot
from goga.ast.nodes.header import (
    HeaderNode,
    ImportsNode,
    ImportTypeItemNode,
    UsageItemNode,
    UsagesNode,
)
from goga.ast.rules.base.document import DocumentRule
from goga.ast.rules.document.usages.rules import (
    AllUsagesIsUsed,
    UsageFilepathExists,
    UsageLinksHasNotConflicts,
    UsageUrlIsAccessible,
)


def _mock_response(status_code: int = 200):
    """Create a mock HTTP response for requests library."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.raise_for_status = MagicMock()
    return resp


class TestContract:
    """Contract tests — verify all 4 classes exist, inherit DocumentRule, have correct check signature."""

    CLASSES: ClassVar[list[type]] = [
        AllUsagesIsUsed,
        UsageFilepathExists,
        UsageUrlIsAccessible,
        UsageLinksHasNotConflicts,
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
            assert cls.__module__ == "goga.ast.rules.document.usages.rules", (
                f"{cls.__name__} has wrong module: {cls.__module__}"
            )


class TestAllUsagesIsUsed:
    """AllUsagesIsUsed: every declared usage must appear in at least one AnnotationsNode."""

    def test_unused_usage_returns_error(self):
        usage_item = UsageItemNode(name="conventions", annotations=AnnotationsNode(root=None))
        root = DocumentRoot(
            path="test.md",
            header=_make_header(
                usages=UsagesNode(items=[usage_item]),
            ),
        )
        node = DocumentNode(root=root)
        rule = AllUsagesIsUsed()
        errors = rule.check(node)
        assert len(errors) == 1
        assert "not referenced" in errors[0].message.lower()

    def test_used_in_header_annotations_returns_empty(self):
        usage_item = UsageItemNode(
            name="conventions",
            annotations=AnnotationsNode(root=None, links=["other"]),
        )
        root = DocumentRoot(
            path="test.md",
            header=_make_header(
                usages=UsagesNode(items=[usage_item]),
                annotations=AnnotationsNode(root=None, links=["conventions"]),
            ),
        )
        node = DocumentNode(root=root)
        rule = AllUsagesIsUsed()
        assert rule.check(node) == []

    def test_used_in_entity_annotations_returns_empty(self):
        usage_item = UsageItemNode(name="conventions", annotations=AnnotationsNode(root=None))
        entity = EntityTypeNode(
            name="Foo",
            annotations=AnnotationsNode(root=None, links=["conventions"]),
        )
        root = DocumentRoot(
            path="test.md",
            header=_make_header(usages=UsagesNode(items=[usage_item])),
            body=BodyNode(entities=[entity]),
        )
        node = DocumentNode(root=root)
        rule = AllUsagesIsUsed()
        assert rule.check(node) == []

    def test_used_in_routine_annotations_returns_empty(self):
        usage_item = UsageItemNode(name="conventions", annotations=AnnotationsNode(root=None))
        routine = RoutineTypeNode(
            name="Bar",
            annotations=AnnotationsNode(root=None, links=["conventions"]),
        )
        root = DocumentRoot(
            path="test.md",
            header=_make_header(usages=UsagesNode(items=[usage_item])),
            body=BodyNode(routines=[routine]),
        )
        node = DocumentNode(root=root)
        rule = AllUsagesIsUsed()
        assert rule.check(node) == []

    def test_no_usages_returns_empty(self):
        root = DocumentRoot(path="test.md")
        node = DocumentNode(root=root)
        rule = AllUsagesIsUsed()
        assert rule.check(node) == []


class TestUsageFilepathExists:
    """UsageFilepathExists: filepath usages must have correct prefix, stay within root, and exist."""

    def test_incorrect_path_returns_error(self):
        usage_item = UsageItemNode(
            name="bad",
            annotations=AnnotationsNode(root=None, filepath="some/other/path.md"),
        )
        root = DocumentRoot(
            path="test.md",
            header=_make_header(usages=UsagesNode(items=[usage_item])),
        )
        node = DocumentNode(root=root)
        rule = UsageFilepathExists()
        errors = rule.check(node)
        assert len(errors) == 1
        assert "incorrect_path" in errors[0].message.lower() or "not built from" in errors[0].message.lower()

    def test_outside_usages_returns_error(self, tmp_path):
        outside_path = str(tmp_path / ".." / ".." / ".." / ".." / ".." / ".goga" / "usages" / "evil.md")
        usage_item = UsageItemNode(
            name="evil",
            annotations=AnnotationsNode(root=None, filepath=outside_path),
        )
        root = DocumentRoot(
            path="test.md",
            header=_make_header(usages=UsagesNode(items=[usage_item])),
        )
        node = DocumentNode(root=root)
        rule = UsageFilepathExists()
        errors = rule.check(node)
        assert len(errors) >= 1
        assert any("outside" in e.message.lower() or "root" in e.message.lower() for e in errors)

    def test_not_found_returns_error(self):
        usage_item = UsageItemNode(
            name="missing",
            annotations=AnnotationsNode(root=None, filepath=".goga/usages/missing.md"),
        )
        root = DocumentRoot(
            path="test.md",
            header=_make_header(usages=UsagesNode(items=[usage_item])),
        )
        node = DocumentNode(root=root)
        rule = UsageFilepathExists()
        errors = rule.check(node)
        assert len(errors) == 1
        assert "not_found" in errors[0].message.lower() or "does not exist" in errors[0].message.lower()

    def test_existing_file_returns_empty(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        usage_dir = tmp_path / ".goga" / "usages"
        usage_dir.mkdir(parents=True)
        (usage_dir / "conventions.md").write_text("content")

        usage_item = UsageItemNode(
            name="conventions",
            annotations=AnnotationsNode(root=None, filepath=".goga/usages/conventions.md"),
        )
        root = DocumentRoot(
            path="test.md",
            header=_make_header(usages=UsagesNode(items=[usage_item])),
        )
        node = DocumentNode(root=root)
        rule = UsageFilepathExists()
        errors = rule.check(node)
        assert errors == []

    def test_inline_usage_skipped(self):
        usage_item = UsageItemNode(
            name="inline",
            annotations=AnnotationsNode(root=None, text="inline content"),
        )
        root = DocumentRoot(
            path="test.md",
            header=_make_header(usages=UsagesNode(items=[usage_item])),
        )
        node = DocumentNode(root=root)
        rule = UsageFilepathExists()
        assert rule.check(node) == []

    def test_url_usage_skipped(self):
        usage_item = UsageItemNode(
            name="remote",
            annotations=AnnotationsNode(root=None, url="https://example.com"),
        )
        root = DocumentRoot(
            path="test.md",
            header=_make_header(usages=UsagesNode(items=[usage_item])),
        )
        node = DocumentNode(root=root)
        rule = UsageFilepathExists()
        assert rule.check(node) == []


class TestUsageUrlIsAccessible:
    """UsageUrlIsAccessible: URL usages must be accessible via HTTP 200."""

    @patch("goga.ast.rules.document.usages.rules.requests.head")
    def test_accessible_url_returns_empty(self, mock_head):
        mock_response = _mock_response(200)
        mock_head.return_value = mock_response

        usage_item = UsageItemNode(
            name="remote",
            annotations=AnnotationsNode(root=None, url="https://example.com"),
        )
        root = DocumentRoot(
            path="test.md",
            header=_make_header(usages=UsagesNode(items=[usage_item])),
        )
        node = DocumentNode(root=root)
        rule = UsageUrlIsAccessible()
        assert rule.check(node) == []

    @patch("goga.ast.rules.document.usages.rules.requests.head")
    def test_not_accessible_returns_error(self, mock_head):
        mock_response = _mock_response(404)
        mock_head.return_value = mock_response

        usage_item = UsageItemNode(
            name="remote",
            annotations=AnnotationsNode(root=None, url="https://example.com"),
        )
        root = DocumentRoot(
            path="test.md",
            header=_make_header(usages=UsagesNode(items=[usage_item])),
        )
        node = DocumentNode(root=root)
        rule = UsageUrlIsAccessible()
        errors = rule.check(node)
        assert len(errors) == 1
        assert "not_accessible" in errors[0].message.lower() or "404" in errors[0].message

    @patch("goga.ast.rules.document.usages.rules.requests.head")
    def test_request_failed_returns_error(self, mock_head):

        mock_head.side_effect = requests.exceptions.ConnectionError("Connection refused")

        usage_item = UsageItemNode(
            name="remote",
            annotations=AnnotationsNode(root=None, url="https://example.com"),
        )
        root = DocumentRoot(
            path="test.md",
            header=_make_header(usages=UsagesNode(items=[usage_item])),
        )
        node = DocumentNode(root=root)
        rule = UsageUrlIsAccessible()
        errors = rule.check(node)
        assert len(errors) == 1
        assert "request_failed" in errors[0].message.lower() or "failed" in errors[0].message.lower()

    def test_inline_usage_skipped(self):
        usage_item = UsageItemNode(
            name="inline",
            annotations=AnnotationsNode(root=None, text="inline content"),
        )
        root = DocumentRoot(
            path="test.md",
            header=_make_header(usages=UsagesNode(items=[usage_item])),
        )
        node = DocumentNode(root=root)
        rule = UsageUrlIsAccessible()
        assert rule.check(node) == []

    def test_filepath_usage_skipped(self):
        usage_item = UsageItemNode(
            name="local",
            annotations=AnnotationsNode(root=None, filepath=".goga/usages/local.md"),
        )
        root = DocumentRoot(
            path="test.md",
            header=_make_header(usages=UsagesNode(items=[usage_item])),
        )
        node = DocumentNode(root=root)
        rule = UsageUrlIsAccessible()
        assert rule.check(node) == []

    @patch("goga.ast.rules.document.usages.rules.requests.get")
    @patch("goga.ast.rules.document.usages.rules.requests.head")
    def test_head_405_fallback_get_ok(self, mock_head, mock_get):
        head_response = _mock_response(405)
        get_response = _mock_response(200)
        mock_head.return_value = head_response
        mock_get.return_value = get_response

        usage_item = UsageItemNode(
            name="remote",
            annotations=AnnotationsNode(root=None, url="https://example.com"),
        )
        root = DocumentRoot(
            path="test.md",
            header=_make_header(usages=UsagesNode(items=[usage_item])),
        )
        node = DocumentNode(root=root)
        rule = UsageUrlIsAccessible()
        assert rule.check(node) == []


class TestUsageLinksHasNotConflicts:
    """UsageLinksHasNotConflicts: usage names must not conflict with imports or entity/routine names."""

    def test_import_conflict_returns_error(self):
        usage_item = UsageItemNode(name="Foo", annotations=AnnotationsNode(root=None))
        import_item = ImportTypeItemNode(type_name={"Foo"}, from_path="bar")
        root = DocumentRoot(
            path="test.md",
            header=_make_header(
                usages=UsagesNode(items=[usage_item]),
                imports=ImportsNode(types=[import_item]),
            ),
        )
        node = DocumentNode(root=root)
        rule = UsageLinksHasNotConflicts()
        errors = rule.check(node)
        assert len(errors) == 1
        assert "import_conflict" in errors[0].message.lower() or "conflicts with imported" in errors[0].message.lower()

    def test_entity_conflict_returns_error(self):
        usage_item = UsageItemNode(name="MyEntity", annotations=AnnotationsNode(root=None))
        entity = EntityTypeNode(name="MyEntity")
        root = DocumentRoot(
            path="test.md",
            header=_make_header(usages=UsagesNode(items=[usage_item])),
            body=BodyNode(entities=[entity]),
        )
        node = DocumentNode(root=root)
        rule = UsageLinksHasNotConflicts()
        errors = rule.check(node)
        assert len(errors) == 1
        assert "entity_conflict" in errors[0].message.lower() or "conflicts with entity" in errors[0].message.lower()

    def test_routine_conflict_returns_error(self):
        usage_item = UsageItemNode(name="MyRoutine", annotations=AnnotationsNode(root=None))
        routine = RoutineTypeNode(name="MyRoutine")
        root = DocumentRoot(
            path="test.md",
            header=_make_header(usages=UsagesNode(items=[usage_item])),
            body=BodyNode(routines=[routine]),
        )
        node = DocumentNode(root=root)
        rule = UsageLinksHasNotConflicts()
        errors = rule.check(node)
        assert len(errors) == 1
        assert "entity_conflict" in errors[0].message.lower() or "conflicts with routine" in errors[0].message.lower()

    def test_no_conflicts_returns_empty(self):
        usage_item = UsageItemNode(name="conventions", annotations=AnnotationsNode(root=None))
        import_item = ImportTypeItemNode(type_name={"OtherType"}, from_path="bar")
        entity = EntityTypeNode(name="OtherEntity")
        root = DocumentRoot(
            path="test.md",
            header=_make_header(
                usages=UsagesNode(items=[usage_item]),
                imports=ImportsNode(types=[import_item]),
            ),
            body=BodyNode(entities=[entity]),
        )
        node = DocumentNode(root=root)
        rule = UsageLinksHasNotConflicts()
        assert rule.check(node) == []

    def test_no_usages_returns_empty(self):
        root = DocumentRoot(path="test.md")
        node = DocumentNode(root=root)
        rule = UsageLinksHasNotConflicts()
        assert rule.check(node) == []

    def test_import_with_alias_no_conflict(self):
        usage_item = UsageItemNode(name="Foo", annotations=AnnotationsNode(root=None))
        import_item = ImportTypeItemNode(type_name={"Foo"}, from_path="bar", alias="BarFoo")
        root = DocumentRoot(
            path="test.md",
            header=_make_header(
                usages=UsagesNode(items=[usage_item]),
                imports=ImportsNode(types=[import_item]),
            ),
        )
        node = DocumentNode(root=root)
        rule = UsageLinksHasNotConflicts()
        assert rule.check(node) == []


class TestAllUsagesIsUsedExtra:
    """Extra edge cases for AllUsagesIsUsed."""

    def test_used_in_method_annotations_returns_empty(self):
        usage_item = UsageItemNode(name="conventions", annotations=AnnotationsNode(root=None))
        method = MethodNode(
            name="do_stuff",
            annotations=AnnotationsNode(root=None, links=["conventions"]),
        )
        entity = EntityTypeNode(
            name="Foo",
            annotations=AnnotationsNode(root=None),
            methods=[method],
        )
        root = DocumentRoot(
            path="test.md",
            header=_make_header(usages=UsagesNode(items=[usage_item])),
            body=BodyNode(entities=[entity]),
        )
        node = DocumentNode(root=root)
        rule = AllUsagesIsUsed()
        assert rule.check(node) == []

    def test_used_in_property_annotations_returns_empty(self):
        usage_item = UsageItemNode(name="conventions", annotations=AnnotationsNode(root=None))
        prop = PropertyNode(
            name="value",
            type="str",
            annotations=AnnotationsNode(root=None, links=["conventions"]),
        )
        entity = EntityTypeNode(
            name="Foo",
            annotations=AnnotationsNode(root=None),
            properties=[prop],
        )
        root = DocumentRoot(
            path="test.md",
            header=_make_header(usages=UsagesNode(items=[usage_item])),
            body=BodyNode(entities=[entity]),
        )
        node = DocumentNode(root=root)
        rule = AllUsagesIsUsed()
        assert rule.check(node) == []

    def test_used_in_usage_item_annotations_returns_empty(self):
        usage_item = UsageItemNode(
            name="conventions",
            annotations=AnnotationsNode(root=None, links=["conventions"]),
        )
        root = DocumentRoot(
            path="test.md",
            header=_make_header(usages=UsagesNode(items=[usage_item])),
        )
        node = DocumentNode(root=root)
        rule = AllUsagesIsUsed()
        assert rule.check(node) == []

    def test_multiple_unused_usages_returns_multiple_errors(self):
        usage_a = UsageItemNode(name="alpha", annotations=AnnotationsNode(root=None))
        usage_b = UsageItemNode(name="beta", annotations=AnnotationsNode(root=None))
        root = DocumentRoot(
            path="test.md",
            header=_make_header(usages=UsagesNode(items=[usage_a, usage_b])),
        )
        node = DocumentNode(root=root)
        rule = AllUsagesIsUsed()
        errors = rule.check(node)
        assert len(errors) == 2


class TestUsageUrlIsAccessibleExtra:
    """Extra edge cases for UsageUrlIsAccessible."""

    @patch("goga.ast.rules.document.usages.rules.requests.get")
    @patch("goga.ast.rules.document.usages.rules.requests.head")
    def test_head_405_fallback_get_fails(self, mock_head, mock_get):
        head_response = _mock_response(405)
        mock_head.return_value = head_response
        mock_get.side_effect = requests.exceptions.ConnectionError("Connection refused")

        usage_item = UsageItemNode(
            name="remote",
            annotations=AnnotationsNode(root=None, url="https://example.com"),
        )
        root = DocumentRoot(
            path="test.md",
            header=_make_header(usages=UsagesNode(items=[usage_item])),
        )
        node = DocumentNode(root=root)
        rule = UsageUrlIsAccessible()
        errors = rule.check(node)
        assert len(errors) == 1
        assert "failed" in errors[0].message.lower()

    @patch("goga.ast.rules.document.usages.rules.requests.get")
    @patch("goga.ast.rules.document.usages.rules.requests.head")
    def test_head_405_fallback_get_non_200(self, mock_head, mock_get):
        head_response = _mock_response(405)
        get_response = _mock_response(503)
        mock_head.return_value = head_response
        mock_get.return_value = get_response

        usage_item = UsageItemNode(
            name="remote",
            annotations=AnnotationsNode(root=None, url="https://example.com"),
        )
        root = DocumentRoot(
            path="test.md",
            header=_make_header(usages=UsagesNode(items=[usage_item])),
        )
        node = DocumentNode(root=root)
        rule = UsageUrlIsAccessible()
        errors = rule.check(node)
        assert len(errors) == 1
        assert "503" in errors[0].message


    @patch("goga.ast.rules.document.usages.rules.requests.head")
    def test_cache_hit_returns_cached_result(self, mock_head):
        mock_response = _mock_response(200)
        mock_head.return_value = mock_response

        usage_item = UsageItemNode(
            name="remote",
            annotations=AnnotationsNode(root=None, url="https://example.com"),
        )
        root = DocumentRoot(
            path="test.md",
            header=_make_header(usages=UsagesNode(items=[usage_item])),
        )
        node = DocumentNode(root=root)
        rule = UsageUrlIsAccessible()
        rule.check(node)
        mock_head.assert_called_once()

        mock_head.reset_mock()
        errors = rule.check(node)
        assert errors == []
        mock_head.assert_not_called()

    @patch("goga.ast.rules.document.usages.rules.requests.head")
    def test_cache_stores_error_result(self, mock_head):
        mock_head.return_value = _mock_response(404)

        usage_item = UsageItemNode(
            name="remote",
            annotations=AnnotationsNode(root=None, url="https://example.com"),
        )
        root = DocumentRoot(
            path="test.md",
            header=_make_header(usages=UsagesNode(items=[usage_item])),
        )
        node = DocumentNode(root=root)
        rule = UsageUrlIsAccessible()
        errors1 = rule.check(node)
        assert len(errors1) == 1

        mock_head.reset_mock()
        errors2 = rule.check(node)
        assert len(errors2) == 1
        assert errors1[0].message == errors2[0].message
        mock_head.assert_not_called()

    @patch("goga.ast.rules.document.usages.rules.requests.head")
    def test_different_urls_both_checked(self, mock_head):
        mock_response = _mock_response(200)
        mock_head.return_value = mock_response

        usage_a = UsageItemNode(
            name="alpha",
            annotations=AnnotationsNode(root=None, url="https://alpha.com"),
        )
        usage_b = UsageItemNode(
            name="beta",
            annotations=AnnotationsNode(root=None, url="https://beta.com"),
        )
        root = DocumentRoot(
            path="test.md",
            header=_make_header(usages=UsagesNode(items=[usage_a, usage_b])),
        )
        node = DocumentNode(root=root)
        rule = UsageUrlIsAccessible()
        assert rule.check(node) == []
        assert mock_head.call_count == 2

    @patch("goga.ast.rules.document.usages.rules.requests.head")
    def test_cache_persists_across_documents(self, mock_head):
        mock_response = _mock_response(200)
        mock_head.return_value = mock_response

        usage_item = UsageItemNode(
            name="remote",
            annotations=AnnotationsNode(root=None, url="https://example.com"),
        )
        root1 = DocumentRoot(
            path="doc1.md",
            header=_make_header(usages=UsagesNode(items=[usage_item])),
        )
        root2 = DocumentRoot(
            path="doc2.md",
            header=_make_header(usages=UsagesNode(items=[usage_item])),
        )
        node1 = DocumentNode(root=root1)
        node2 = DocumentNode(root=root2)
        rule = UsageUrlIsAccessible()

        rule.check(node1)
        assert mock_head.call_count == 1

        rule.check(node2)
        assert mock_head.call_count == 1

    @patch("goga.ast.rules.document.usages.rules.requests.head")
    def test_cache_hit_with_network_error_returns_cached_error(self, mock_head):
        mock_head.side_effect = requests.exceptions.ConnectionError("Connection refused")

        usage_item = UsageItemNode(
            name="remote",
            annotations=AnnotationsNode(root=None, url="https://example.com"),
        )
        root = DocumentRoot(
            path="test.md",
            header=_make_header(usages=UsagesNode(items=[usage_item])),
        )
        node = DocumentNode(root=root)
        rule = UsageUrlIsAccessible()
        errors1 = rule.check(node)
        assert len(errors1) == 1
        assert "failed" in errors1[0].message.lower()

        mock_head.reset_mock()
        mock_head.return_value = _mock_response(200)
        errors2 = rule.check(node)
        assert len(errors2) == 1
        assert errors1[0].message == errors2[0].message
        mock_head.assert_not_called()

    @patch("goga.ast.rules.document.usages.rules.requests.head")
    def test_cache_empty_for_new_rule_instance(self, mock_head):
        mock_response = _mock_response(200)
        mock_head.return_value = mock_response

        usage_item = UsageItemNode(
            name="remote",
            annotations=AnnotationsNode(root=None, url="https://example.com"),
        )
        root = DocumentRoot(
            path="test.md",
            header=_make_header(usages=UsagesNode(items=[usage_item])),
        )
        node = DocumentNode(root=root)
        rule1 = UsageUrlIsAccessible()
        rule1.check(node)
        assert mock_head.call_count == 1

        rule2 = UsageUrlIsAccessible()
        rule2.check(node)
        assert mock_head.call_count == 2

    @patch("goga.ast.rules.document.usages.rules.requests.get")
    @patch("goga.ast.rules.document.usages.rules.requests.head")
    def test_cache_with_head_fallback_get(self, mock_head, mock_get):
        head_response = _mock_response(405)
        get_response = _mock_response(200)
        mock_head.return_value = head_response
        mock_get.return_value = get_response

        usage_item = UsageItemNode(
            name="remote",
            annotations=AnnotationsNode(root=None, url="https://example.com"),
        )
        root = DocumentRoot(
            path="test.md",
            header=_make_header(usages=UsagesNode(items=[usage_item])),
        )
        node = DocumentNode(root=root)
        rule = UsageUrlIsAccessible()
        assert rule.check(node) == []
        assert mock_head.call_count == 1
        assert mock_get.call_count == 1

        mock_head.reset_mock()
        mock_get.reset_mock()
        assert rule.check(node) == []
        mock_head.assert_not_called()
        mock_get.assert_not_called()

    @patch("goga.ast.rules.document.usages.rules.requests.get")
    @patch("goga.ast.rules.document.usages.rules.requests.head")
    def test_cache_with_head_fallback_get_failure(self, mock_head, mock_get):
        head_response = _mock_response(405)
        mock_head.return_value = head_response
        mock_get.side_effect = requests.exceptions.ConnectionError("Connection refused")

        usage_item = UsageItemNode(
            name="remote",
            annotations=AnnotationsNode(root=None, url="https://example.com"),
        )
        root = DocumentRoot(
            path="test.md",
            header=_make_header(usages=UsagesNode(items=[usage_item])),
        )
        node = DocumentNode(root=root)
        rule = UsageUrlIsAccessible()
        errors1 = rule.check(node)
        assert len(errors1) == 1
        assert "failed" in errors1[0].message.lower()

        mock_head.reset_mock()
        mock_get.reset_mock()
        errors2 = rule.check(node)
        assert len(errors2) == 1
        assert errors1[0].message == errors2[0].message
        mock_head.assert_not_called()
        mock_get.assert_not_called()

    @patch("goga.ast.rules.document.usages.rules.requests.head")
    def test_cache_generic_exception(self, mock_head):
        mock_head.side_effect = ValueError("unexpected error")

        usage_item = UsageItemNode(
            name="remote",
            annotations=AnnotationsNode(root=None, url="https://example.com"),
        )
        root = DocumentRoot(
            path="test.md",
            header=_make_header(usages=UsagesNode(items=[usage_item])),
        )
        node = DocumentNode(root=root)
        rule = UsageUrlIsAccessible()
        errors1 = rule.check(node)
        assert len(errors1) == 1
        assert "unexpected error" in errors1[0].message

        mock_head.reset_mock()
        errors2 = rule.check(node)
        assert len(errors2) == 1
        assert errors1[0].message == errors2[0].message
        mock_head.assert_not_called()

    @patch("goga.ast.rules.document.usages.rules.requests.head")
    def test_cache_rebuilds_errors_with_current_context(self, mock_head):
        mock_head.return_value = _mock_response(404)

        usage_a = UsageItemNode(
            name="alpha",
            annotations=AnnotationsNode(root=None, url="https://example.com"),
        )
        usage_b = UsageItemNode(
            name="beta",
            annotations=AnnotationsNode(root=None, url="https://example.com"),
        )
        root1 = DocumentRoot(
            path="doc_a.md",
            header=_make_header(usages=UsagesNode(items=[usage_a])),
        )
        root2 = DocumentRoot(
            path="doc_b.md",
            header=_make_header(usages=UsagesNode(items=[usage_b])),
        )
        node1 = DocumentNode(root=root1)
        node2 = DocumentNode(root=root2)
        rule = UsageUrlIsAccessible()

        errors1 = rule.check(node1)
        assert len(errors1) == 1
        assert "alpha" in errors1[0].message
        assert errors1[0].document.path == "doc_a.md"

        errors2 = rule.check(node2)
        assert len(errors2) == 1
        assert "beta" in errors2[0].message
        assert errors2[0].document.path == "doc_b.md"
        mock_head.assert_called_once()


class TestUsageLinksHasNotConflictsExtra:
    """Extra edge cases for UsageLinksHasNotConflicts."""

    def test_embedded_entity_no_conflict(self):
        usage_item = UsageItemNode(name="MyEntity", annotations=AnnotationsNode(root=None))
        entity = EntityTypeNode(name="MyEntity", embedded=True)
        root = DocumentRoot(
            path="test.md",
            header=_make_header(usages=UsagesNode(items=[usage_item])),
            body=BodyNode(entities=[entity]),
        )
        node = DocumentNode(root=root)
        rule = UsageLinksHasNotConflicts()
        assert rule.check(node) == []

    def test_embedded_routine_no_conflict(self):
        usage_item = UsageItemNode(name="MyRoutine", annotations=AnnotationsNode(root=None))
        routine = RoutineTypeNode(name="MyRoutine", embedded=True)
        root = DocumentRoot(
            path="test.md",
            header=_make_header(usages=UsagesNode(items=[usage_item])),
            body=BodyNode(routines=[routine]),
        )
        node = DocumentNode(root=root)
        rule = UsageLinksHasNotConflicts()
        assert rule.check(node) == []


class TestUsageFilepathExistsExtra:
    """Extra cases from old test_document.py."""

    def test_filepath_and_url_both_set_skipped(self, tmp_path, monkeypatch):
        usage_item = UsageItemNode(
            name="both",
            annotations=AnnotationsNode(root=None, filepath=".usages/old.md", url="https://example.com"),
        )
        root = DocumentRoot(
            path="test.md",
            header=_make_header(usages=UsagesNode(items=[usage_item])),
        )
        root.path = str(tmp_path)
        node = DocumentNode(root=root)
        rule = UsageFilepathExists()
        monkeypatch.chdir(tmp_path)
        assert rule.check(node) == []

    def test_empty_filepath_skipped(self, tmp_path, monkeypatch):
        usage_item = UsageItemNode(
            name="empty",
            annotations=AnnotationsNode(root=None, filepath=""),
        )
        root = DocumentRoot(
            path="test.md",
            header=_make_header(usages=UsagesNode(items=[usage_item])),
        )
        root.path = str(tmp_path)
        node = DocumentNode(root=root)
        rule = UsageFilepathExists()
        monkeypatch.chdir(tmp_path)
        assert rule.check(node) == []

    def test_none_filepath_skipped(self, tmp_path, monkeypatch):
        usage_item = UsageItemNode(name="none", annotations=AnnotationsNode(root=None))
        root = DocumentRoot(
            path="test.md",
            header=_make_header(usages=UsagesNode(items=[usage_item])),
        )
        root.path = str(tmp_path)
        node = DocumentNode(root=root)
        rule = UsageFilepathExists()
        monkeypatch.chdir(tmp_path)
        assert rule.check(node) == []


def _make_header(data=None, imports=None, annotations=None, usages=None):
    return HeaderNode(
        data=data or {},
        imports=imports or ImportsNode(),
        annotations=annotations or AnnotationsNode(root=None),
        usages=usages or UsagesNode(),
    )
