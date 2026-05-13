"""Contract and behavioral tests for UsageFilepathExists and ImportHasValidFromPath rules."""

from __future__ import annotations

import shutil
from pathlib import Path

from goga.ast.errors import DocumentRuleError
from goga.ast.nodes import (
    AnnotationsNode,
    DocumentNode,
    DocumentRoot,
    HeaderNode,
    ImportsNode,
    ImportTypeItemNode,
    UsageItemNode,
    UsagesNode,
)
from goga.ast.rules import ImportHasValidFromPath, UsageFilepathExists
from goga.ast.rules.document import DocumentRule

# ---------------------------------------------------------------------------
# Contract tests
# ---------------------------------------------------------------------------


class TestUsageFilepathExistsContract:
    def test_class_exists(self):
        assert UsageFilepathExists is not None

    def test_default_name(self):
        rule = UsageFilepathExists()
        assert rule.name == "usage_filepath_exists"

    def test_inherits_document_rule(self):
        assert issubclass(UsageFilepathExists, DocumentRule)

    def test_check_accepts_document_node(self):
        rule = UsageFilepathExists()
        root = DocumentRoot()
        node = DocumentNode(root=root)
        result = rule.check(node)
        assert isinstance(result, list)

    def test_check_returns_list_of_document_rule_error(self):
        rule = UsageFilepathExists()
        root = DocumentRoot()
        node = DocumentNode(root=root)
        result = rule.check(node)
        for item in result:
            assert isinstance(item, DocumentRuleError)


class TestImportHasValidFromPathContract:
    def test_class_exists(self):
        assert ImportHasValidFromPath is not None

    def test_default_name(self):
        rule = ImportHasValidFromPath()
        assert rule.name == "import_has_valid_from_path"

    def test_inherits_document_rule(self):
        assert issubclass(ImportHasValidFromPath, DocumentRule)

    def test_check_accepts_document_node(self):
        rule = ImportHasValidFromPath()
        root = DocumentRoot()
        node = DocumentNode(root=root)
        result = rule.check(node)
        assert isinstance(result, list)

    def test_check_returns_list_of_document_rule_error(self):
        rule = ImportHasValidFromPath()
        root = DocumentRoot()
        node = DocumentNode(root=root)
        result = rule.check(node)
        for item in result:
            assert isinstance(item, DocumentRuleError)


# ---------------------------------------------------------------------------
# UsageFilepathExists behavioral tests
# ---------------------------------------------------------------------------


def _make_usage_root(*usages: tuple[str, str | None, str | None]) -> DocumentRoot:
    """Build a DocumentRoot with the given usages.

    Each tuple is (name, filepath, url).
    """
    usage_items: list[UsageItemNode] = []
    for name, filepath, url in usages:
        annotations = AnnotationsNode(root=None)
        if filepath is not None:
            annotations.filepath = filepath
        if url is not None:
            annotations.url = url
        usage_items.append(UsageItemNode(name=name, annotations=annotations))
    return DocumentRoot(header=HeaderNode(usages=UsagesNode(items=usage_items)))


class TestUsageFilepathExistsPrefix:
    def test_valid_prefix_with_existing_file_no_errors(self, tmp_path: Path, monkeypatch):
        goga_usages = tmp_path / ".goga" / "usages"
        goga_usages.mkdir(parents=True)
        (goga_usages / "existing.md").write_text("hello")

        root = _make_usage_root(("existing", ".goga/usages/existing.md", None))
        root.path = str(tmp_path)

        rule = UsageFilepathExists()
        monkeypatch.chdir(tmp_path)
        errors = rule.check(DocumentNode(root=root))
        assert errors == []

    def test_missing_prefix_produces_incorrect_path_error(self, tmp_path: Path, monkeypatch):
        root = _make_usage_root(("old_style", ".usages/old_style.md", None))
        root.path = str(tmp_path)

        rule = UsageFilepathExists()
        monkeypatch.chdir(tmp_path)
        errors = rule.check(DocumentNode(root=root))
        assert len(errors) == 1
        assert errors[0].rule == "usage_filepath_exists"
        assert "is not built from '.goga/usages/'" in errors[0].message
        assert "old_style" in errors[0].message

    def test_prefix_correct_but_file_not_found(self, tmp_path: Path, monkeypatch):
        root = _make_usage_root(("missing", ".goga/usages/nonexistent.md", None))
        root.path = str(tmp_path)

        rule = UsageFilepathExists()
        monkeypatch.chdir(tmp_path)
        errors = rule.check(DocumentNode(root=root))
        assert len(errors) == 1
        assert errors[0].rule == "usage_filepath_exists"
        assert "does not exist on filesystem" in errors[0].message

    def test_filepath_and_url_both_set_skipped(self, tmp_path: Path, monkeypatch):
        root = _make_usage_root(("both", ".usages/old.md", "https://example.com"))
        root.path = str(tmp_path)

        rule = UsageFilepathExists()
        monkeypatch.chdir(tmp_path)
        errors = rule.check(DocumentNode(root=root))
        assert errors == []

    def test_empty_filepath_skipped(self, tmp_path: Path, monkeypatch):
        root = _make_usage_root(("empty", "", None))
        root.path = str(tmp_path)

        rule = UsageFilepathExists()
        monkeypatch.chdir(tmp_path)
        errors = rule.check(DocumentNode(root=root))
        assert errors == []

    def test_none_filepath_skipped(self, tmp_path: Path, monkeypatch):
        usage = UsageItemNode(name="none", annotations=AnnotationsNode(root=None))
        root = DocumentRoot(header=HeaderNode(usages=UsagesNode(items=[usage])))
        root.path = str(tmp_path)

        rule = UsageFilepathExists()
        monkeypatch.chdir(tmp_path)
        errors = rule.check(DocumentNode(root=root))
        assert errors == []

    def test_outside_project_prefix_ok_but_resolves_outside(self, tmp_path: Path, monkeypatch):
        outside = tmp_path.parent / "goga_escape_outside"
        outside.mkdir(parents=True, exist_ok=True)
        (outside / "outside.md").write_text("data")
        try:
            # Three levels up from .goga/usages/ escapes the project root
            root = _make_usage_root(("escape", ".goga/usages/../../../goga_escape_outside/outside.md", None))
            root.path = str(tmp_path)

            rule = UsageFilepathExists()
            monkeypatch.chdir(tmp_path)
            errors = rule.check(DocumentNode(root=root))
            assert len(errors) == 1
            assert "not built from the root of the project" in errors[0].message
        finally:
            shutil.rmtree(outside, ignore_errors=True)


# ---------------------------------------------------------------------------
# ImportHasValidFromPath behavioral tests (regression — no level constraint)
# ---------------------------------------------------------------------------


class TestImportHasValidFromPathRegression:
    def test_import_from_any_level_no_level_constraint(self, tmp_path: Path, monkeypatch):
        src = tmp_path / "some" / "deep" / "path"
        src.mkdir(parents=True)
        (src / "CODEMANIFEST").write_text("Types:\n  Foo:\n")

        root = DocumentRoot(
            header=HeaderNode(
                imports=ImportsNode(
                    types=[ImportTypeItemNode(type_name={"Foo"}, from_path=str(src))],
                ),
            ),
        )
        root.path = str(tmp_path)

        rule = ImportHasValidFromPath()
        monkeypatch.chdir(tmp_path)
        errors = rule.check(DocumentNode(root=root))
        assert errors == []

    def test_empty_from_path_produces_error(self, tmp_path: Path, monkeypatch):
        root = DocumentRoot(
            header=HeaderNode(
                imports=ImportsNode(
                    types=[ImportTypeItemNode(type_name={"Foo"}, from_path="")],
                ),
            ),
        )
        root.path = str(tmp_path)

        rule = ImportHasValidFromPath()
        monkeypatch.chdir(tmp_path)
        errors = rule.check(DocumentNode(root=root))
        assert len(errors) == 1
        assert errors[0].rule == "import_has_valid_from_path"
        assert "empty source path" in errors[0].message

    def test_nonexistent_path_produces_error(self, tmp_path: Path, monkeypatch):
        root = DocumentRoot(
            header=HeaderNode(
                imports=ImportsNode(
                    types=[ImportTypeItemNode(type_name={"Foo"}, from_path=str(tmp_path / "nope"))],
                ),
            ),
        )
        root.path = str(tmp_path)

        rule = ImportHasValidFromPath()
        monkeypatch.chdir(tmp_path)
        errors = rule.check(DocumentNode(root=root))
        assert len(errors) == 1
        assert errors[0].rule == "import_has_valid_from_path"
        assert "not found on filesystem" in errors[0].message

    def test_absolute_path_outside_project(self, tmp_path: Path, monkeypatch):
        real_outside = Path("/tmp") / f"goga_test_outside_{id(tmp_path)}"
        real_outside.mkdir(parents=True, exist_ok=True)
        (real_outside / "CODEMANIFEST").write_text("Types:\n  Bar:\n")
        try:
            root = DocumentRoot(
                header=HeaderNode(
                    imports=ImportsNode(
                        types=[ImportTypeItemNode(type_name={"Bar"}, from_path=str(real_outside))],
                    ),
                ),
            )
            root.path = str(tmp_path)

            rule = ImportHasValidFromPath()
            monkeypatch.chdir(tmp_path)
            errors = rule.check(DocumentNode(root=root))
            assert len(errors) == 1
            assert errors[0].rule == "import_has_valid_from_path"
            assert "outside the project root" in errors[0].message
        finally:
            shutil.rmtree(real_outside, ignore_errors=True)
