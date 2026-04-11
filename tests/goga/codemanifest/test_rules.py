"""Contract tests for the goga.codemanifest.rules package."""

import os
from pathlib import Path

import pytest
from goga.codemanifest.errors import ManifestRuleError, ProjectRuleError
from goga.codemanifest.nodes import (
    AnnotationsNode,
    DocumentNode,
    DocumentRoot,
    HeaderNode,
    ImportItemNode,
    ImportsNode,
    UsageItemNode,
    UsagesNode,
)
from goga.codemanifest.rules import (
    AllUsagesIsUsed,
    DocumentRule,
    ImportHasTypeRule,
    ImportHasValidFromPathRule,
    ImportsCanNotBeEmptyRule,
    ImportsHasNotCyclicalDepsRule,
    ProjectRule,
)

# ---------------------------------------------------------------------------
# 1. Facade: all 7 rule classes are importable
# ---------------------------------------------------------------------------

EXPECTED_RULE_CLASSES = [
    DocumentRule,
    ImportsCanNotBeEmptyRule,
    ImportHasTypeRule,
    ImportHasValidFromPathRule,
    ProjectRule,
    ImportsHasNotCyclicalDepsRule,
    AllUsagesIsUsed,
]


def test_all_rule_classes_importable():
    """All 7 rule classes must be importable from the rules facade."""
    for cls in EXPECTED_RULE_CLASSES:
        assert isinstance(cls, type), f"{cls.__name__} is not a class"


# ---------------------------------------------------------------------------
# 2. DocumentRule base class
# ---------------------------------------------------------------------------


class TestDocumentRule:
    def test_name_property_stores_name(self):
        rule = DocumentRule(name="my_rule")
        assert rule.name == "my_rule"

    def test_check_raises_not_implemented_error(self):
        rule = DocumentRule(name="base")
        node = DocumentNode(root=DocumentRoot())
        with pytest.raises(NotImplementedError):
            rule.check(node)


# ---------------------------------------------------------------------------
# 3. ImportsCanNotBeEmptyRule
# ---------------------------------------------------------------------------


class TestImportsCanNotBeEmptyRule:
    def test_default_name(self):
        rule = ImportsCanNotBeEmptyRule()
        assert rule.name == "imports_can_not_be_empty"

    def test_positive_non_empty_imports_returns_empty_errors(self):
        root = DocumentRoot(
            header=HeaderNode(imports=ImportsNode(items=[ImportItemNode(type_name={"Foo"}, from_path="bar")]))
        )
        node = DocumentNode(root=root)
        rule = ImportsCanNotBeEmptyRule()
        errors = rule.check(node)
        assert errors == []

    def test_negative_empty_imports_returns_error(self):
        root = DocumentRoot(header=HeaderNode(data={"Imports": []}, imports=ImportsNode(items=[])))
        node = DocumentNode(root=root)
        rule = ImportsCanNotBeEmptyRule()
        errors = rule.check(node)
        assert len(errors) == 1
        assert isinstance(errors[0], ManifestRuleError)
        assert errors[0].rule == "imports_can_not_be_empty"


# ---------------------------------------------------------------------------
# 3b. ImportsCanNotBeEmptyRule — conditional behavior
# ---------------------------------------------------------------------------


class TestImportsCanNotBeEmptyRuleConditional:
    """Tests for conditional check: rule only applies when Imports is declared in data."""

    def test_positive_declared_imports_with_non_empty_items_no_errors(self):
        """Manifest with declared Imports and non-empty items produces no errors."""
        root = DocumentRoot(
            header=HeaderNode(
                data={"Imports": [{"Foo": {"from": "bar"}}]},
                imports=ImportsNode(items=[ImportItemNode(type_name={"Foo"}, from_path="bar")]),
            )
        )
        node = DocumentNode(root=root)
        rule = ImportsCanNotBeEmptyRule()
        errors = rule.check(node)
        assert errors == []

    def test_negative_declared_imports_with_empty_items_returns_error(self):
        """Manifest with declared Imports but empty items returns an error."""
        root = DocumentRoot(
            header=HeaderNode(
                data={"Imports": []},
                imports=ImportsNode(items=[]),
            )
        )
        node = DocumentNode(root=root)
        rule = ImportsCanNotBeEmptyRule()
        errors = rule.check(node)
        assert len(errors) == 1
        assert isinstance(errors[0], ManifestRuleError)
        assert errors[0].rule == "imports_can_not_be_empty"

    def test_positive_no_imports_key_in_data_no_errors(self):
        """Manifest without Imports key in data — rule is skipped, no errors."""
        root = DocumentRoot(
            header=HeaderNode(
                data={},
                imports=ImportsNode(items=[]),
            )
        )
        node = DocumentNode(root=root)
        rule = ImportsCanNotBeEmptyRule()
        errors = rule.check(node)
        assert errors == []

    def test_positive_only_usages_and_annotations_no_errors(self):
        """Manifest with only Usages and Annotations but no Imports — no errors."""
        root = DocumentRoot(
            header=HeaderNode(
                data={"Usages": {"nodes": {}}, "Annotations": "some annotation"},
                usages=UsagesNode(items=[UsageItemNode(name="nodes")]),
                annotations=AnnotationsNode(root=None),
            )
        )
        node = DocumentNode(root=root)
        rule = ImportsCanNotBeEmptyRule()
        errors = rule.check(node)
        assert errors == []


# ---------------------------------------------------------------------------
# 4. ImportHasTypeRule
# ---------------------------------------------------------------------------


class TestImportHasTypeRule:
    def test_default_name(self):
        rule = ImportHasTypeRule()
        assert rule.name == "import_has_type"

    def test_positive_import_with_non_empty_type(self):
        root = DocumentRoot(
            header=HeaderNode(imports=ImportsNode(items=[ImportItemNode(type_name={"MyType"}, from_path="foo")]))
        )
        node = DocumentNode(root=root)
        rule = ImportHasTypeRule()
        errors = rule.check(node)
        assert errors == []

    def test_negative_import_with_empty_type(self):
        root = DocumentRoot(
            header=HeaderNode(imports=ImportsNode(items=[ImportItemNode(type_name=set(), from_path="foo")]))
        )
        node = DocumentNode(root=root)
        rule = ImportHasTypeRule()
        errors = rule.check(node)
        assert len(errors) == 1
        assert isinstance(errors[0], ManifestRuleError)
        assert errors[0].rule == "import_has_type"


# ---------------------------------------------------------------------------
# 5. ImportHasValidFromPathRule
# ---------------------------------------------------------------------------


class TestImportHasValidFromPathRule:
    def test_default_name(self):
        rule = ImportHasValidFromPathRule()
        assert rule.name == "import_has_valid_from_path"

    def test_positive_valid_existing_path(self, tmp_path: Path):
        existing_file = Path(os.getcwd()) / "_test_rules_tmp_module.py"
        existing_file.write_text("# module")
        try:
            root = DocumentRoot(
                header=HeaderNode(
                    imports=ImportsNode(
                        items=[
                            ImportItemNode(
                                type_name={"Foo"},
                                from_path=str(existing_file),
                            )
                        ]
                    )
                )
            )
            node = DocumentNode(root=root)
            rule = ImportHasValidFromPathRule()
            errors = rule.check(node)
            assert errors == []
        finally:
            existing_file.unlink(missing_ok=True)

    def test_negative_empty_path(self):
        root = DocumentRoot(
            header=HeaderNode(imports=ImportsNode(items=[ImportItemNode(type_name={"Foo"}, from_path="")]))
        )
        node = DocumentNode(root=root)
        rule = ImportHasValidFromPathRule()
        errors = rule.check(node)
        assert len(errors) == 1
        assert isinstance(errors[0], ManifestRuleError)

    def test_negative_non_existing_path(self, tmp_path: Path):
        missing = tmp_path / "does_not_exist.py"
        root = DocumentRoot(
            header=HeaderNode(imports=ImportsNode(items=[ImportItemNode(type_name={"Foo"}, from_path=str(missing))]))
        )
        node = DocumentNode(root=root)
        rule = ImportHasValidFromPathRule()
        errors = rule.check(node)
        assert len(errors) == 1
        assert isinstance(errors[0], ManifestRuleError)

    def test_negative_path_escaping_cwd(self, tmp_path: Path):
        escaping_path = str(Path(os.getcwd()).resolve().parent / "outside")
        root = DocumentRoot(
            header=HeaderNode(imports=ImportsNode(items=[ImportItemNode(type_name={"Foo"}, from_path=escaping_path)]))
        )
        node = DocumentNode(root=root)
        rule = ImportHasValidFromPathRule()
        errors = rule.check(node)
        assert len(errors) >= 1
        assert isinstance(errors[0], ManifestRuleError)


# ---------------------------------------------------------------------------
# 6. ProjectRule base class
# ---------------------------------------------------------------------------


class TestProjectRule:
    def test_name_and_tree_properties(self):
        tree = [DocumentRoot(), DocumentRoot()]
        rule = ProjectRule(tree=tree, name="my_project_rule")
        assert rule.name == "my_project_rule"
        assert rule.tree is tree

    def test_check_raises_not_implemented_error(self):
        rule = ProjectRule(tree=[], name="base")
        doc = DocumentRoot()
        with pytest.raises(NotImplementedError):
            rule.check(doc)


# ---------------------------------------------------------------------------
# 7. ImportsHasNotCyclicalDepsRule
# ---------------------------------------------------------------------------


class TestImportsHasNotCyclicalDepsRule:
    def test_default_name(self):
        rule = ImportsHasNotCyclicalDepsRule(tree=[])
        assert rule.name == "imports_has_not_cyclical_deps"

    def test_positive_no_cycles(self):
        doc1 = DocumentRoot(
            path="/project/a.cm",
            header=HeaderNode(imports=ImportsNode(items=[ImportItemNode(type_name={"X"}, from_path="/project/b.cm")])),
        )
        doc2 = DocumentRoot(
            path="/project/b.cm",
            header=HeaderNode(imports=ImportsNode(items=[])),
        )
        rule = ImportsHasNotCyclicalDepsRule(tree=[doc1, doc2])
        errors = rule.check(doc1)
        assert errors == []

    def test_negative_circular_imports(self):
        doc1 = DocumentRoot(
            path="/project/a.cm",
            header=HeaderNode(imports=ImportsNode(items=[ImportItemNode(type_name={"X"}, from_path="/project/b.cm")])),
        )
        doc2 = DocumentRoot(
            path="/project/b.cm",
            header=HeaderNode(imports=ImportsNode(items=[ImportItemNode(type_name={"Y"}, from_path="/project/a.cm")])),
        )
        rule = ImportsHasNotCyclicalDepsRule(tree=[doc1, doc2])
        errors = rule.check(doc1)
        assert len(errors) == 1
        assert isinstance(errors[0], ProjectRuleError)
        assert errors[0].rule == "imports_has_not_cyclical_deps"


# ---------------------------------------------------------------------------
# 8. AllUsagesIsUsed
# ---------------------------------------------------------------------------


class TestAllUsagesIsUsed:
    def test_default_name(self):
        rule = AllUsagesIsUsed(tree=[])
        assert rule.name == "all_usages_is_used"

    def test_positive_usage_referenced_in_header_annotations(self):
        root = DocumentRoot(
            path="/project/doc.cm",
            header=HeaderNode(
                annotations=AnnotationsNode(text="uses nodes for something"),
                usages=UsagesNode(items=[UsageItemNode(name="nodes")]),
            ),
        )
        rule = AllUsagesIsUsed(tree=[root])
        errors = rule.check(root)
        assert errors == []

    def test_negative_unused_usage_name(self):
        root = DocumentRoot(
            path="/project/doc.cm",
            header=HeaderNode(
                annotations=AnnotationsNode(text="unrelated text"),
                usages=UsagesNode(items=[UsageItemNode(name="nodes")]),
            ),
        )
        rule = AllUsagesIsUsed(tree=[root])
        errors = rule.check(root)
        assert len(errors) == 1
        assert isinstance(errors[0], ProjectRuleError)
        assert errors[0].rule == "all_usages_is_used"


# ---------------------------------------------------------------------------
# 9. AllUsagesIsUsed — usage found in various annotation locations
# ---------------------------------------------------------------------------


class TestAllUsagesIsUsedLocations:
    def test_usage_found_in_entity_annotation(self):
        from goga.codemanifest.nodes import BodyNode, EntityTypeNode

        entity = EntityTypeNode(
            name="MyEntity",
            annotations=AnnotationsNode(text="uses mypract for something"),
        )
        root = DocumentRoot(
            path="/project/doc.cm",
            header=HeaderNode(
                annotations=AnnotationsNode(text="unrelated"),
                usages=UsagesNode(items=[UsageItemNode(name="mypract")]),
            ),
            body=BodyNode(entities=[entity]),
        )
        rule = AllUsagesIsUsed(tree=[root])
        errors = rule.check(root)
        assert errors == []

    def test_usage_found_in_method_annotation(self):
        from goga.codemanifest.nodes import BodyNode, EntityTypeNode, MethodNode

        method = MethodNode(
            name="do_work",
            annotations=AnnotationsNode(text="uses mypract for logic"),
        )
        entity = EntityTypeNode(name="MyEntity", methods=[method])
        root = DocumentRoot(
            path="/project/doc.cm",
            header=HeaderNode(
                annotations=AnnotationsNode(text="unrelated"),
                usages=UsagesNode(items=[UsageItemNode(name="mypract")]),
            ),
            body=BodyNode(entities=[entity]),
        )
        rule = AllUsagesIsUsed(tree=[root])
        errors = rule.check(root)
        assert errors == []

    def test_usage_found_in_property_annotation(self):
        from goga.codemanifest.nodes import BodyNode, EntityTypeNode, PropertyNode

        prop = PropertyNode(
            name="value",
            type="str",
            annotations=AnnotationsNode(text="uses mypract for formatting"),
        )
        entity = EntityTypeNode(name="MyEntity", properties=[prop])
        root = DocumentRoot(
            path="/project/doc.cm",
            header=HeaderNode(
                annotations=AnnotationsNode(text="unrelated"),
                usages=UsagesNode(items=[UsageItemNode(name="mypract")]),
            ),
            body=BodyNode(entities=[entity]),
        )
        rule = AllUsagesIsUsed(tree=[root])
        errors = rule.check(root)
        assert errors == []

    def test_usage_found_in_routine_annotation(self):
        from goga.codemanifest.nodes import BodyNode, RoutineTypeNode

        routine = RoutineTypeNode(
            name="my_func",
            annotations=AnnotationsNode(text="uses mypract for data"),
        )
        root = DocumentRoot(
            path="/project/doc.cm",
            header=HeaderNode(
                annotations=AnnotationsNode(text="unrelated"),
                usages=UsagesNode(items=[UsageItemNode(name="mypract")]),
            ),
            body=BodyNode(routines=[routine]),
        )
        rule = AllUsagesIsUsed(tree=[root])
        errors = rule.check(root)
        assert errors == []


# ---------------------------------------------------------------------------
# 10. ImportHasValidFromPathRule — existing path outside CWD
# ---------------------------------------------------------------------------


class TestImportHasValidFromPathEdgeCases:
    def test_existing_path_outside_cwd(self, tmp_path: Path):
        """A path that exists on filesystem but is outside CWD triggers an error."""
        # Create a real file outside CWD
        outside_dir = tmp_path / "outside_project"
        outside_dir.mkdir()
        outside_file = outside_dir / "module.py"
        outside_file.write_text("# module")

        # Resolve the path — it exists but is not under CWD
        resolved_outside = str(outside_file.resolve())

        root = DocumentRoot(
            header=HeaderNode(
                imports=ImportsNode(
                    items=[
                        ImportItemNode(
                            type_name={"Foo"},
                            from_path=resolved_outside,
                        )
                    ]
                )
            )
        )
        node = DocumentNode(root=root)
        rule = ImportHasValidFromPathRule()
        errors = rule.check(node)
        # Should find error about escaping CWD
        assert len(errors) >= 1
        assert any("escapes CWD" in e.message for e in errors)
