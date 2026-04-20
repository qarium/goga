"""Contract tests for ImportUsageExists rule."""

from pathlib import Path

from goga.ast.errors import DocumentRuleError
from goga.ast.nodes import (
    DocumentNode,
    DocumentRoot,
    HeaderNode,
    ImportsNode,
    ImportTypeItemNode,
    ImportUsageItemNode,
)
from goga.ast.rules import ImportUsageExists


class TestImportUsageExistsName:
    def test_default_name(self):
        rule = ImportUsageExists()
        assert rule.name == "import_usage_exists"


class TestImportUsageExistsFound:
    def test_usage_file_exists_no_errors(self, tmp_path):
        """ImportUsageItemNode + .usages/{name}.md exists -> no errors."""
        # Create the usage file
        usages_dir = tmp_path / "some_cell" / ".usages"
        usages_dir.mkdir(parents=True)
        (usages_dir / "my_usage.md").write_text("# My Usage")

        root = DocumentRoot(
            header=HeaderNode(
                imports=ImportsNode(
                    items=[
                        ImportUsageItemNode(
                            usage_name={"my_usage"},
                            from_path=str(tmp_path / "some_cell"),
                        ),
                    ],
                ),
            ),
        )
        node = DocumentNode(root=root)
        rule = ImportUsageExists()
        errors = rule.check(node)
        assert errors == []

    def test_multiple_usage_files_exist(self, tmp_path):
        """Multiple usage files all exist -> no errors."""
        usages_dir = tmp_path / "cell" / ".usages"
        usages_dir.mkdir(parents=True)
        (usages_dir / "usage_a.md").write_text("a")
        (usages_dir / "usage_b.md").write_text("b")

        root = DocumentRoot(
            header=HeaderNode(
                imports=ImportsNode(
                    items=[
                        ImportUsageItemNode(
                            usage_name={"usage_a", "usage_b"},
                            from_path=str(tmp_path / "cell"),
                        ),
                    ],
                ),
            ),
        )
        node = DocumentNode(root=root)
        rule = ImportUsageExists()
        errors = rule.check(node)
        assert errors == []


class TestImportUsageExistsNotFound:
    def test_usage_file_not_found_produces_error(self, tmp_path):
        """ImportUsageItemNode + .usages/{name}.md missing -> error."""
        (tmp_path / "some_cell").mkdir()
        root = DocumentRoot(
            header=HeaderNode(
                imports=ImportsNode(
                    items=[
                        ImportUsageItemNode(
                            usage_name={"missing_usage"},
                            from_path=str(tmp_path / "some_cell"),
                        ),
                    ],
                ),
            ),
        )
        node = DocumentNode(root=root)
        rule = ImportUsageExists()
        errors = rule.check(node)
        assert len(errors) == 1
        assert isinstance(errors[0], DocumentRuleError)
        assert errors[0].rule == "import_usage_exists"
        assert "missing_usage" in errors[0].message
        assert "does not exists on filesystem by path" in errors[0].message

    def test_error_message_template(self, tmp_path):
        """Error message matches the contract template exactly."""
        (tmp_path / "some_cell").mkdir()
        expected_path = str(Path(tmp_path / "some_cell" / ".usages" / "missing.md"))
        root = DocumentRoot(
            header=HeaderNode(
                imports=ImportsNode(
                    items=[
                        ImportUsageItemNode(
                            usage_name={"missing"},
                            from_path=str(tmp_path / "some_cell"),
                        ),
                    ],
                ),
            ),
        )
        node = DocumentNode(root=root)
        rule = ImportUsageExists()
        errors = rule.check(node)
        assert len(errors) == 1
        assert errors[0].message == (
            f"Usage 'missing' does not exists on filesystem by path '{expected_path}'"
        )

    def test_one_missing_one_found(self, tmp_path):
        """One usage exists, one doesn't -> error only for the missing one."""
        usages_dir = tmp_path / "cell" / ".usages"
        usages_dir.mkdir(parents=True)
        (usages_dir / "found_usage.md").write_text("found")

        root = DocumentRoot(
            header=HeaderNode(
                imports=ImportsNode(
                    items=[
                        ImportUsageItemNode(
                            usage_name={"found_usage", "missing_usage"},
                            from_path=str(tmp_path / "cell"),
                        ),
                    ],
                ),
            ),
        )
        node = DocumentNode(root=root)
        rule = ImportUsageExists()
        errors = rule.check(node)
        assert len(errors) == 1
        assert "missing_usage" in errors[0].message


class TestImportUsageExistsSkipsTypeItems:
    def test_type_item_is_skipped(self):
        """ImportTypeItemNode -> rule does not check it."""
        root = DocumentRoot(
            header=HeaderNode(
                imports=ImportsNode(
                    items=[
                        ImportTypeItemNode(type_name={"SomeType"}, from_path="some/path"),
                    ],
                ),
            ),
        )
        node = DocumentNode(root=root)
        rule = ImportUsageExists()
        errors = rule.check(node)
        assert errors == []

    def test_mixed_items_type_skipped(self, tmp_path):
        """Mixed items: type item skipped, usage item checked."""
        (tmp_path / "nonexistent").mkdir()
        root = DocumentRoot(
            header=HeaderNode(
                imports=ImportsNode(
                    items=[
                        ImportTypeItemNode(type_name={"SomeType"}, from_path=str(tmp_path)),
                        ImportUsageItemNode(
                            usage_name={"some_usage"},
                            from_path=str(tmp_path / "nonexistent"),
                        ),
                    ],
                ),
            ),
        )
        node = DocumentNode(root=root)
        rule = ImportUsageExists()
        errors = rule.check(node)
        assert len(errors) == 1
        assert errors[0].rule == "import_usage_exists"


class TestImportUsageExistsSkipsNonExistentFromPath:
    def test_nonexistent_from_path_skipped(self, tmp_path):
        """Usage item with non-existent from_path -> skipped (ImportHasValidFromPath handles it)."""
        root = DocumentRoot(
            header=HeaderNode(
                imports=ImportsNode(
                    items=[
                        ImportUsageItemNode(
                            usage_name={"some_usage"},
                            from_path=str(tmp_path / "nonexistent_path"),
                        ),
                    ],
                ),
            ),
        )
        node = DocumentNode(root=root)
        rule = ImportUsageExists()
        errors = rule.check(node)
        assert errors == []

    def test_empty_from_path_skipped(self):
        """Usage item with empty from_path -> skipped."""
        root = DocumentRoot(
            header=HeaderNode(
                imports=ImportsNode(
                    items=[
                        ImportUsageItemNode(
                            usage_name={"some_usage"},
                            from_path="",
                        ),
                    ],
                ),
            ),
        )
        node = DocumentNode(root=root)
        rule = ImportUsageExists()
        errors = rule.check(node)
        assert errors == []
