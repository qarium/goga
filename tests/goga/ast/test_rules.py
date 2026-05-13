"""Contract tests for the goga.ast.rules package."""

import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch

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
    ImportUsageItemNode,
    MethodNode,
    PropertyNode,
    RoutineTypeNode,
    UsageItemNode,
    UsagesNode,
)
from goga.ast.rules import (
    AllUsagesIsUsed,
    AnnotationLinksExists,
    ASTRule,
    DocumentRule,
    EmbeddedEntityCanNotHasMutations,
    EmbeddedTypeHasLowLevel,
    EntitiesAndRoutinesHasNotConflicts,
    EntityHasOnlyValidKeys,
    ImportHasNotDuplicate,
    ImportHasValidFromPath,
    ImportIsUsed,
    ImportItemIsValid,
    ImportsCanNotBeEmpty,
    ImportsHasNotCyclicalDeps,
    ImportsHasOnlyValidKeys,
    ImportTypeExists,
    ImportUsageExists,
    MutationExists,
    MutationIsValid,
    ReturnTypeHasLink,
    RoutineHasOnlyValidKeys,
    SignatureIsValid,
    UsageFilepathExists,
    UsageLinksHasNotConflicts,
    UsageUrlIsAccessible,
    signature_contains_type_name,
)

# ---------------------------------------------------------------------------
# 1. Facade: all 22 rule classes are importable
# ---------------------------------------------------------------------------

EXPECTED_RULE_CLASSES = [
    DocumentRule,
    ImportsCanNotBeEmpty,
    ImportsHasOnlyValidKeys,
    ImportHasValidFromPath,
    ImportHasNotDuplicate,
    ImportItemIsValid,
    AllUsagesIsUsed,
    AnnotationLinksExists,
    UsageLinksHasNotConflicts,
    EntitiesAndRoutinesHasNotConflicts,
    MutationExists,
    MutationIsValid,
    ReturnTypeHasLink,
    EmbeddedEntityCanNotHasMutations,
    EntityHasOnlyValidKeys,
    RoutineHasOnlyValidKeys,
    ASTRule,
    ImportsHasNotCyclicalDeps,
    ImportTypeExists,
    EmbeddedTypeHasLowLevel,
    SignatureIsValid,
    ImportIsUsed,
    ImportUsageExists,
    UsageFilepathExists,
    UsageUrlIsAccessible,
]


def test_all_rule_classes_importable():
    """All 25 rule classes must be importable from the rules facade."""
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
# 3. ImportsCanNotBeEmpty
# ---------------------------------------------------------------------------


class TestImportsCanNotBeEmpty:
    def test_default_name(self):
        rule = ImportsCanNotBeEmpty()
        assert rule.name == "imports_can_not_be_empty"

    def test_positive_non_empty_imports_returns_empty_errors(self):
        root = DocumentRoot(
            header=HeaderNode(imports=ImportsNode(types=[ImportTypeItemNode(type_name={"Foo"}, from_path="bar")]))
        )
        node = DocumentNode(root=root)
        rule = ImportsCanNotBeEmpty()
        errors = rule.check(node)
        assert errors == []

    def test_positive_non_empty_usages_returns_empty_errors(self):
        usage_item = ImportUsageItemNode(usage_name={"my_usage"}, from_path="bar")
        root = DocumentRoot(
            header=HeaderNode(imports=ImportsNode(usages=[usage_item])),
        )
        node = DocumentNode(root=root)
        rule = ImportsCanNotBeEmpty()
        errors = rule.check(node)
        assert errors == []

    def test_negative_empty_imports_returns_error(self):
        root = DocumentRoot(header=HeaderNode(data={"Imports": []}, imports=ImportsNode()))
        node = DocumentNode(root=root)
        rule = ImportsCanNotBeEmpty()
        errors = rule.check(node)
        assert len(errors) == 1
        assert isinstance(errors[0], DocumentRuleError)
        assert errors[0].rule == "imports_can_not_be_empty"
        assert "Imports block in" in errors[0].message
        assert "is empty — each import must specify at least Types and From" in errors[0].message


# ---------------------------------------------------------------------------
# 3b. ImportsCanNotBeEmpty — conditional behavior
# ---------------------------------------------------------------------------


class TestImportsCanNotBeEmptyConditional:
    """Tests for conditional check: rule only applies when Imports is declared in data."""

    def test_positive_declared_imports_with_non_empty_items_no_errors(self):
        """Manifest with declared Imports and non-empty items produces no errors."""
        root = DocumentRoot(
            header=HeaderNode(
                data={"Imports": [{"Foo": {"from": "bar"}}]},
                imports=ImportsNode(types=[ImportTypeItemNode(type_name={"Foo"}, from_path="bar")]),
            )
        )
        node = DocumentNode(root=root)
        rule = ImportsCanNotBeEmpty()
        errors = rule.check(node)
        assert errors == []

    def test_negative_declared_imports_with_empty_items_returns_error(self):
        """Manifest with declared Imports but empty items returns an error."""
        root = DocumentRoot(
            header=HeaderNode(
                data={"Imports": []},
                imports=ImportsNode(),
            )
        )
        node = DocumentNode(root=root)
        rule = ImportsCanNotBeEmpty()
        errors = rule.check(node)
        assert len(errors) == 1
        assert isinstance(errors[0], DocumentRuleError)
        assert errors[0].rule == "imports_can_not_be_empty"
        assert "Imports block in" in errors[0].message
        assert "is empty — each import must specify at least Types and From" in errors[0].message

    def test_positive_no_imports_key_in_data_no_errors(self):
        """Manifest without Imports key in data — rule is skipped, no errors."""
        root = DocumentRoot(
            header=HeaderNode(
                data={},
                imports=ImportsNode(),
            )
        )
        node = DocumentNode(root=root)
        rule = ImportsCanNotBeEmpty()
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
        rule = ImportsCanNotBeEmpty()
        errors = rule.check(node)
        assert errors == []


# ---------------------------------------------------------------------------
# 5. ImportHasValidFromPath
# ---------------------------------------------------------------------------


class TestImportHasValidFromPath:
    def test_default_name(self):
        rule = ImportHasValidFromPath()
        assert rule.name == "import_has_valid_from_path"

    def test_positive_valid_existing_path(self, tmp_path: Path):
        # The rule uses CWD as project root, so create files inside CWD
        test_dir = Path.cwd() / "_test_rules_valid_path"
        test_dir.mkdir(exist_ok=True)
        try:
            existing_file = test_dir / "manifest.py"
            existing_file.write_text("# module")
            doc_path = test_dir / "CODEMANIFEST"
            root = DocumentRoot(
                path=str(doc_path),
                header=HeaderNode(
                    imports=ImportsNode(
                        types=[
                            ImportTypeItemNode(
                                type_name={"Foo"},
                                from_path=str(existing_file),
                            )
                        ]
                    )
                ),
            )
            node = DocumentNode(root=root)
            rule = ImportHasValidFromPath()
            errors = rule.check(node)
            assert errors == []
        finally:
            existing_file.unlink(missing_ok=True)
            test_dir.rmdir()

    def test_negative_empty_path(self):
        root = DocumentRoot(
            header=HeaderNode(imports=ImportsNode(types=[ImportTypeItemNode(type_name={"Foo"}, from_path="")]))
        )
        node = DocumentNode(root=root)
        rule = ImportHasValidFromPath()
        errors = rule.check(node)
        assert len(errors) == 1
        assert isinstance(errors[0], DocumentRuleError)
        assert "has empty source path (From field)" in errors[0].message

    def test_negative_non_existing_path(self, tmp_path: Path):
        missing = tmp_path / "does_not_exist.py"
        imp = ImportTypeItemNode(type_name={"Foo"}, from_path=str(missing))
        root = DocumentRoot(header=HeaderNode(imports=ImportsNode(types=[imp])))
        node = DocumentNode(root=root)
        rule = ImportHasValidFromPath()
        errors = rule.check(node)
        assert len(errors) == 1
        assert isinstance(errors[0], DocumentRuleError)
        assert "not found on filesystem" in errors[0].message

    def test_negative_path_escaping_cwd(self, tmp_path: Path):
        escaping_path = str(Path.cwd().resolve().parent / "outside")
        imp = ImportTypeItemNode(type_name={"Foo"}, from_path=escaping_path)
        root = DocumentRoot(header=HeaderNode(imports=ImportsNode(types=[imp])))
        node = DocumentNode(root=root)
        rule = ImportHasValidFromPath()
        errors = rule.check(node)
        assert len(errors) >= 1
        assert isinstance(errors[0], DocumentRuleError)
        assert any(
            "not found on filesystem" in e.message or "points outside the project root" in e.message for e in errors
        )


# ---------------------------------------------------------------------------
# 6. ASTRule base class
# ---------------------------------------------------------------------------


class TestASTRule:
    def test_name_and_tree_properties(self):
        tree = [DocumentRoot(), DocumentRoot()]
        rule = ASTRule(tree=tree, name="my_project_rule")
        assert rule.name == "my_project_rule"
        assert rule.tree is tree

    def test_check_raises_not_implemented_error(self):
        rule = ASTRule(tree=[], name="base")
        doc = DocumentRoot()
        with pytest.raises(NotImplementedError):
            rule.check(doc)


# ---------------------------------------------------------------------------
# 7. ImportsHasNotCyclicalDeps
# ---------------------------------------------------------------------------


class TestImportsHasNotCyclicalDeps:
    def test_default_name(self):
        rule = ImportsHasNotCyclicalDeps(tree=[])
        assert rule.name == "imports_has_not_cyclical_deps"

    def test_positive_no_cycles(self):
        imp_x = ImportTypeItemNode(type_name={"X"}, from_path="/project/b.cm")
        doc1 = DocumentRoot(
            path="/project/a.cm",
            header=HeaderNode(imports=ImportsNode(types=[imp_x])),
        )
        doc2 = DocumentRoot(
            path="/project/b.cm",
            header=HeaderNode(imports=ImportsNode()),
        )
        rule = ImportsHasNotCyclicalDeps(tree=[doc1, doc2])
        errors = rule.check(doc1)
        assert errors == []

    def test_negative_circular_imports(self):
        imp_x = ImportTypeItemNode(type_name={"X"}, from_path="/project/b.cm")
        imp_y = ImportTypeItemNode(type_name={"Y"}, from_path="/project/a.cm")
        doc1 = DocumentRoot(
            path="/project/a.cm",
            header=HeaderNode(imports=ImportsNode(types=[imp_x])),
        )
        doc2 = DocumentRoot(
            path="/project/b.cm",
            header=HeaderNode(imports=ImportsNode(types=[imp_y])),
        )
        rule = ImportsHasNotCyclicalDeps(tree=[doc1, doc2])
        errors = rule.check(doc1)
        assert len(errors) == 1
        assert isinstance(errors[0], ASTRuleError)
        assert errors[0].rule == "imports_has_not_cyclical_deps"


# ---------------------------------------------------------------------------
# 8. AllUsagesIsUsed
# ---------------------------------------------------------------------------


class TestAllUsagesIsUsed:
    def test_default_name(self):
        rule = AllUsagesIsUsed()
        assert rule.name == "all_usages_is_used"

    def test_positive_usage_referenced_in_header_annotations_links(self):
        root = DocumentRoot(
            path="/project/doc.cm",
            header=HeaderNode(
                annotations=AnnotationsNode(text="uses `nodes` for something", links=["nodes"]),
                usages=UsagesNode(items=[UsageItemNode(name="nodes")]),
            ),
        )
        node = DocumentNode(root=root)
        rule = AllUsagesIsUsed()
        errors = rule.check(node)
        assert errors == []

    def test_negative_unused_usage_name(self):
        root = DocumentRoot(
            path="/project/doc.cm",
            header=HeaderNode(
                annotations=AnnotationsNode(text="unrelated text"),
                usages=UsagesNode(items=[UsageItemNode(name="nodes")]),
            ),
        )
        node = DocumentNode(root=root)
        rule = AllUsagesIsUsed()
        errors = rule.check(node)
        assert len(errors) == 1
        assert isinstance(errors[0], DocumentRuleError)
        assert errors[0].rule == "all_usages_is_used"
        assert "not referenced in any annotation — either use it or remove" in errors[0].message


# ---------------------------------------------------------------------------
# 9. AllUsagesIsUsed — usage found in various annotation locations
# ---------------------------------------------------------------------------


class TestAllUsagesIsUsedLocations:
    def test_usage_found_in_entity_annotation(self):
        entity = EntityTypeNode(
            name="MyEntity",
            annotations=AnnotationsNode(text="uses `mypract` for something", links=["mypract"]),
        )
        root = DocumentRoot(
            path="/project/doc.cm",
            header=HeaderNode(
                annotations=AnnotationsNode(text="unrelated"),
                usages=UsagesNode(items=[UsageItemNode(name="mypract")]),
            ),
            body=BodyNode(entities=[entity]),
        )
        node = DocumentNode(root=root)
        rule = AllUsagesIsUsed()
        errors = rule.check(node)
        assert errors == []

    def test_usage_found_in_method_annotation(self):
        method = MethodNode(
            name="do_work",
            annotations=AnnotationsNode(text="uses `mypract` for logic", links=["mypract"]),
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
        node = DocumentNode(root=root)
        rule = AllUsagesIsUsed()
        errors = rule.check(node)
        assert errors == []

    def test_usage_found_in_property_annotation(self):
        prop = PropertyNode(
            name="value",
            type="str",
            annotations=AnnotationsNode(text="uses `mypract` for formatting", links=["mypract"]),
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
        node = DocumentNode(root=root)
        rule = AllUsagesIsUsed()
        errors = rule.check(node)
        assert errors == []

    def test_usage_found_in_routine_annotation(self):
        routine = RoutineTypeNode(
            name="my_func",
            annotations=AnnotationsNode(text="uses `mypract` for data", links=["mypract"]),
        )
        root = DocumentRoot(
            path="/project/doc.cm",
            header=HeaderNode(
                annotations=AnnotationsNode(text="unrelated"),
                usages=UsagesNode(items=[UsageItemNode(name="mypract")]),
            ),
            body=BodyNode(routines=[routine]),
        )
        node = DocumentNode(root=root)
        rule = AllUsagesIsUsed()
        errors = rule.check(node)
        assert errors == []


# ---------------------------------------------------------------------------
# 10. ImportHasValidFromPath — existing path outside CWD
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
                    types=[
                        ImportTypeItemNode(
                            type_name={"Foo"},
                            from_path=resolved_outside,
                        )
                    ]
                )
            )
        )
        node = DocumentNode(root=root)
        rule = ImportHasValidFromPath()
        errors = rule.check(node)
        # Should find error about pointing outside the project root
        assert len(errors) >= 1
        assert any("points outside the project root" in e.message for e in errors)


# ---------------------------------------------------------------------------
# 11. ImportHasNotDuplicate
# ---------------------------------------------------------------------------


class TestImportHasNotDuplicate:
    def test_default_name(self):
        rule = ImportHasNotDuplicate()
        assert rule.name == "import_has_not_duplicate"

    def test_positive_all_type_names_unique(self):
        root = DocumentRoot(
            header=HeaderNode(
                imports=ImportsNode(
                    types=[
                        ImportTypeItemNode(type_name={"Foo"}, from_path="a"),
                        ImportTypeItemNode(type_name={"Bar"}, from_path="b"),
                    ]
                )
            )
        )
        node = DocumentNode(root=root)
        rule = ImportHasNotDuplicate()
        errors = rule.check(node)
        assert errors == []

    def test_negative_duplicate_type_name(self):
        root = DocumentRoot(
            header=HeaderNode(
                imports=ImportsNode(
                    types=[
                        ImportTypeItemNode(type_name={"Foo"}, from_path="a"),
                        ImportTypeItemNode(type_name={"Foo"}, from_path="b"),
                    ]
                )
            )
        )
        node = DocumentNode(root=root)
        rule = ImportHasNotDuplicate()
        errors = rule.check(node)
        assert len(errors) == 1
        assert isinstance(errors[0], DocumentRuleError)
        assert errors[0].rule == "import_has_not_duplicate"
        assert "is imported more than once: from" in errors[0].message
        assert "Foo" in errors[0].message


# ---------------------------------------------------------------------------
# 12. AnnotationLinksExists
# ---------------------------------------------------------------------------


class TestAnnotationLinksExists:
    def test_default_name(self):
        rule = AnnotationLinksExists()
        assert rule.name == "annotation_links_exists"

    def test_positive_link_found_in_imports(self):
        root = DocumentRoot(
            header=HeaderNode(
                imports=ImportsNode(types=[ImportTypeItemNode(type_name={"MyType"}, from_path="a")]),
                annotations=AnnotationsNode(text="uses `MyType`", links=["MyType"]),
            )
        )
        node = DocumentNode(root=root)
        rule = AnnotationLinksExists()
        errors = rule.check(node)
        assert errors == []

    def test_positive_link_found_in_usages(self):
        root = DocumentRoot(
            header=HeaderNode(
                usages=UsagesNode(items=[UsageItemNode(name="mypract")]),
                annotations=AnnotationsNode(text="uses `mypract`", links=["mypract"]),
            )
        )
        node = DocumentNode(root=root)
        rule = AnnotationLinksExists()
        errors = rule.check(node)
        assert errors == []

    def test_positive_link_found_in_entities(self):
        root = DocumentRoot(
            header=HeaderNode(
                annotations=AnnotationsNode(text="uses `MyEntity`", links=["MyEntity"]),
            ),
            body=BodyNode(entities=[EntityTypeNode(name="MyEntity")]),
        )
        node = DocumentNode(root=root)
        rule = AnnotationLinksExists()
        errors = rule.check(node)
        assert errors == []

    def test_positive_link_found_in_routines(self):
        root = DocumentRoot(
            header=HeaderNode(
                annotations=AnnotationsNode(text="uses `my_func`", links=["my_func"]),
            ),
            body=BodyNode(routines=[RoutineTypeNode(name="my_func")]),
        )
        node = DocumentNode(root=root)
        rule = AnnotationLinksExists()
        errors = rule.check(node)
        assert errors == []

    def test_negative_link_not_found_anywhere(self):
        root = DocumentRoot(
            header=HeaderNode(
                imports=ImportsNode(types=[ImportTypeItemNode(type_name={"OtherType"}, from_path="a")]),
                annotations=AnnotationsNode(text="uses `Missing`", links=["Missing"]),
            )
        )
        node = DocumentNode(root=root)
        rule = AnnotationLinksExists()
        errors = rule.check(node)
        assert len(errors) == 1
        assert isinstance(errors[0], DocumentRuleError)
        assert errors[0].rule == "annotation_links_exists"
        assert "does not match any import, usage, entity, routine, or signature parameter" in errors[0].message

    def test_positive_link_found_in_signature_as_whole_word(self):
        """Link found in entity signature as a whole word (word boundary match)."""
        entity = EntityTypeNode(
            name="MyClass",
            signature="do_work(param: MyParam)",
            annotations=AnnotationsNode(text="uses `MyParam`", links=["MyParam"]),
        )
        root = DocumentRoot(
            header=HeaderNode(),
            body=BodyNode(entities=[entity]),
        )
        node = DocumentNode(root=root)
        rule = AnnotationLinksExists()
        errors = rule.check(node)
        assert errors == []

    def test_negative_link_in_signature_not_whole_word(self):
        """Link in signature that is not a whole word match does not resolve."""
        entity = EntityTypeNode(
            name="MyClass",
            signature="do_work(param_name: str)",
            annotations=AnnotationsNode(text="uses `param`", links=["param"]),
        )
        root = DocumentRoot(
            header=HeaderNode(),
            body=BodyNode(entities=[entity]),
        )
        node = DocumentNode(root=root)
        rule = AnnotationLinksExists()
        errors = rule.check(node)
        assert len(errors) == 1
        assert errors[0].rule == "annotation_links_exists"
        assert "does not match any import, usage, entity, routine, or signature parameter" in errors[0].message

    def test_positive_link_found_in_method_signature(self):
        """Link found in method signature as a whole word."""
        method = MethodNode(
            name="do_work",
            signature="execute(value: MyType)",
            annotations=AnnotationsNode(text="uses `MyType`", links=["MyType"]),
        )
        entity = EntityTypeNode(name="MyClass", methods=[method])
        root = DocumentRoot(
            header=HeaderNode(
                imports=ImportsNode(types=[ImportTypeItemNode(type_name={"MyType"}, from_path="a")]),
            ),
            body=BodyNode(entities=[entity]),
        )
        node = DocumentNode(root=root)
        rule = AnnotationLinksExists()
        errors = rule.check(node)
        assert errors == []


# ---------------------------------------------------------------------------
# 13. UsageLinksHasNotConflicts
# ---------------------------------------------------------------------------


class TestUsageLinksHasNotConflicts:
    def test_default_name(self):
        rule = UsageLinksHasNotConflicts()
        assert rule.name == "usage_links_has_not_conflicts"

    def test_positive_no_conflicts(self):
        root = DocumentRoot(
            header=HeaderNode(
                imports=ImportsNode(types=[ImportTypeItemNode(type_name={"Foo"}, from_path="a")]),
                usages=UsagesNode(items=[UsageItemNode(name="mypract")]),
            )
        )
        node = DocumentNode(root=root)
        rule = UsageLinksHasNotConflicts()
        errors = rule.check(node)
        assert errors == []

    def test_negative_usage_name_conflicts_with_type_name(self):
        root = DocumentRoot(
            header=HeaderNode(
                imports=ImportsNode(types=[ImportTypeItemNode(type_name={"Foo"}, from_path="a")]),
                usages=UsagesNode(items=[UsageItemNode(name="Foo")]),
            )
        )
        node = DocumentNode(root=root)
        rule = UsageLinksHasNotConflicts()
        errors = rule.check(node)
        assert len(errors) == 1
        assert isinstance(errors[0], DocumentRuleError)
        assert errors[0].rule == "usage_links_has_not_conflicts"
        assert "conflicts with imported name" in errors[0].message
        assert "rename the usage or use an alias" in errors[0].message

    def test_positive_conflict_resolved_through_alias(self):
        root = DocumentRoot(
            header=HeaderNode(
                imports=ImportsNode(types=[ImportTypeItemNode(type_name={"Foo"}, from_path="a", alias="FooAlias")]),
                usages=UsagesNode(items=[UsageItemNode(name="Foo")]),
            )
        )
        node = DocumentNode(root=root)
        rule = UsageLinksHasNotConflicts()
        errors = rule.check(node)
        assert errors == []

    def test_negative_usage_name_conflicts_with_entity_name(self):
        root = DocumentRoot(
            header=HeaderNode(
                usages=UsagesNode(items=[UsageItemNode(name="MyEntity")]),
            ),
            body=BodyNode(entities=[EntityTypeNode(name="MyEntity")]),
        )
        node = DocumentNode(root=root)
        rule = UsageLinksHasNotConflicts()
        errors = rule.check(node)
        assert len(errors) == 1
        assert isinstance(errors[0], DocumentRuleError)
        assert errors[0].rule == "usage_links_has_not_conflicts"
        assert "conflicts with" in errors[0].message
        assert "rename the usage to avoid ambiguity" in errors[0].message


# ---------------------------------------------------------------------------
# 14. EntitiesAndRoutinesHasNotConflicts
# ---------------------------------------------------------------------------


class TestEntitiesAndRoutinesHasNotConflicts:
    def test_default_name(self):
        rule = EntitiesAndRoutinesHasNotConflicts()
        assert rule.name == "entities_and_routines_has_not_conflicts"

    def test_positive_no_conflicts(self):
        root = DocumentRoot(
            header=HeaderNode(
                imports=ImportsNode(types=[ImportTypeItemNode(type_name={"Foo"}, from_path="a")]),
            ),
            body=BodyNode(
                entities=[EntityTypeNode(name="MyEntity")],
                routines=[RoutineTypeNode(name="my_func")],
            ),
        )
        node = DocumentNode(root=root)
        rule = EntitiesAndRoutinesHasNotConflicts()
        errors = rule.check(node)
        assert errors == []

    def test_negative_entity_name_conflicts_with_type_name(self):
        root = DocumentRoot(
            header=HeaderNode(
                imports=ImportsNode(types=[ImportTypeItemNode(type_name={"Foo"}, from_path="a")]),
            ),
            body=BodyNode(
                entities=[EntityTypeNode(name="Foo")],
            ),
        )
        node = DocumentNode(root=root)
        rule = EntitiesAndRoutinesHasNotConflicts()
        errors = rule.check(node)
        assert len(errors) == 1
        assert isinstance(errors[0], DocumentRuleError)
        assert errors[0].rule == "entities_and_routines_has_not_conflicts"
        assert "has the same name as imported name" in errors[0].message

    def test_positive_conflict_resolved_through_alias(self):
        root = DocumentRoot(
            header=HeaderNode(
                imports=ImportsNode(types=[ImportTypeItemNode(type_name={"Foo"}, from_path="a", alias="FooAlias")]),
            ),
            body=BodyNode(
                entities=[EntityTypeNode(name="Foo")],
            ),
        )
        node = DocumentNode(root=root)
        rule = EntitiesAndRoutinesHasNotConflicts()
        errors = rule.check(node)
        assert errors == []

    def test_negative_routine_name_conflicts_with_type_name(self):
        root = DocumentRoot(
            header=HeaderNode(
                imports=ImportsNode(types=[ImportTypeItemNode(type_name={"Bar"}, from_path="a")]),
            ),
            body=BodyNode(
                routines=[RoutineTypeNode(name="Bar")],
            ),
        )
        node = DocumentNode(root=root)
        rule = EntitiesAndRoutinesHasNotConflicts()
        errors = rule.check(node)
        assert len(errors) == 1
        assert isinstance(errors[0], DocumentRuleError)
        assert errors[0].rule == "entities_and_routines_has_not_conflicts"
        assert "has the same name as imported name" in errors[0].message

    def test_positive_embedded_entity_with_conflicting_name_no_error(self):
        """Embedded entity with name matching an imported type is skipped — no error."""
        root = DocumentRoot(
            header=HeaderNode(
                imports=ImportsNode(types=[ImportTypeItemNode(type_name={"Foo"}, from_path="a")]),
            ),
            body=BodyNode(
                entities=[EntityTypeNode(name="Foo", embedded=True)],
            ),
        )
        node = DocumentNode(root=root)
        rule = EntitiesAndRoutinesHasNotConflicts()
        errors = rule.check(node)
        assert errors == []

    def test_positive_embedded_routine_with_conflicting_name_no_error(self):
        """Embedded routine with name matching an imported type is skipped — no error."""
        root = DocumentRoot(
            header=HeaderNode(
                imports=ImportsNode(types=[ImportTypeItemNode(type_name={"Bar"}, from_path="a")]),
            ),
            body=BodyNode(
                routines=[RoutineTypeNode(name="Bar", embedded=True)],
            ),
        )
        node = DocumentNode(root=root)
        rule = EntitiesAndRoutinesHasNotConflicts()
        errors = rule.check(node)
        assert errors == []

    def test_negative_non_embedded_entity_with_conflicting_name_still_errors(self):
        """Non-embedded entity with name matching an imported type still produces error."""
        root = DocumentRoot(
            header=HeaderNode(
                imports=ImportsNode(types=[ImportTypeItemNode(type_name={"Foo"}, from_path="a")]),
            ),
            body=BodyNode(
                entities=[EntityTypeNode(name="Foo", embedded=False)],
                routines=[RoutineTypeNode(name="Bar", embedded=False)],
            ),
        )
        node = DocumentNode(root=root)
        rule = EntitiesAndRoutinesHasNotConflicts()
        errors = rule.check(node)
        assert len(errors) == 1
        assert isinstance(errors[0], DocumentRuleError)
        assert errors[0].rule == "entities_and_routines_has_not_conflicts"
        assert "has the same name as imported name" in errors[0].message

    def test_negative_non_embedded_routine_with_conflicting_name_still_errors(self):
        """Non-embedded routine with name matching an imported type still produces error."""
        root = DocumentRoot(
            header=HeaderNode(
                imports=ImportsNode(types=[ImportTypeItemNode(type_name={"Bar"}, from_path="a")]),
            ),
            body=BodyNode(
                entities=[EntityTypeNode(name="Other", embedded=False)],
                routines=[RoutineTypeNode(name="Bar", embedded=False)],
            ),
        )
        node = DocumentNode(root=root)
        rule = EntitiesAndRoutinesHasNotConflicts()
        errors = rule.check(node)
        assert len(errors) == 1
        assert isinstance(errors[0], DocumentRuleError)
        assert errors[0].rule == "entities_and_routines_has_not_conflicts"
        assert "has the same name as imported name" in errors[0].message


# ---------------------------------------------------------------------------
# 15. MutationExists
# ---------------------------------------------------------------------------


class TestMutationExists:
    def test_default_name(self):
        rule = MutationExists()
        assert rule.name == "mutation_exists"

    def test_positive_mutation_found_among_entities(self):
        root = DocumentRoot(
            header=HeaderNode(),
            body=BodyNode(
                entities=[
                    EntityTypeNode(name="MyEntity", mutations=[("OtherEntity", "path")]),
                    EntityTypeNode(name="OtherEntity"),
                ],
            ),
        )
        node = DocumentNode(root=root)
        rule = MutationExists()
        errors = rule.check(node)
        assert errors == []

    def test_positive_mutation_found_among_routines(self):
        root = DocumentRoot(
            header=HeaderNode(),
            body=BodyNode(
                entities=[EntityTypeNode(name="MyEntity", mutations=[("do_stuff", "path")])],
                routines=[RoutineTypeNode(name="do_stuff")],
            ),
        )
        node = DocumentNode(root=root)
        rule = MutationExists()
        errors = rule.check(node)
        assert errors == []

    def test_positive_mutation_found_among_import_types(self):
        root = DocumentRoot(
            header=HeaderNode(
                imports=ImportsNode(types=[ImportTypeItemNode(type_name={"ImportedType"}, from_path="a")]),
            ),
            body=BodyNode(
                entities=[EntityTypeNode(name="MyEntity", mutations=[("ImportedType", "path")])],
            ),
        )
        node = DocumentNode(root=root)
        rule = MutationExists()
        errors = rule.check(node)
        assert errors == []

    def test_negative_mutation_not_found(self):
        root = DocumentRoot(
            header=HeaderNode(
                imports=ImportsNode(types=[ImportTypeItemNode(type_name={"Foo"}, from_path="a")]),
            ),
            body=BodyNode(
                entities=[EntityTypeNode(name="MyEntity", mutations=[("NonExistent", "path")])],
                routines=[RoutineTypeNode(name="some_func")],
            ),
        )
        node = DocumentNode(root=root)
        rule = MutationExists()
        errors = rule.check(node)
        assert len(errors) == 1
        assert isinstance(errors[0], DocumentRuleError)
        assert errors[0].rule == "mutation_exists"
        assert "Base type" in errors[0].message
        assert "not found in imports, entities, or routines" in errors[0].message


# ---------------------------------------------------------------------------
# 16. MutationIsValid
# ---------------------------------------------------------------------------


class TestMutationIsValid:
    def test_default_name(self):
        rule = MutationIsValid()
        assert rule.name == "mutation_is_valid"

    def test_positive_mutation_not_matching_entity_name(self):
        root = DocumentRoot(
            header=HeaderNode(),
            body=BodyNode(
                entities=[EntityTypeNode(name="MyEntity", mutations=[("OtherEntity", "path")])],
            ),
        )
        node = DocumentNode(root=root)
        rule = MutationIsValid()
        errors = rule.check(node)
        assert errors == []

    def test_negative_mutation_matches_entity_name(self):
        root = DocumentRoot(
            header=HeaderNode(),
            body=BodyNode(
                entities=[EntityTypeNode(name="MyEntity", mutations=[("MyEntity", "path")])],
            ),
        )
        node = DocumentNode(root=root)
        rule = MutationIsValid()
        errors = rule.check(node)
        assert len(errors) == 1
        assert isinstance(errors[0], DocumentRuleError)
        assert errors[0].rule == "mutation_is_valid"
        assert "references itself" in errors[0].message


# ---------------------------------------------------------------------------
# 17. ReturnTypeHasLink
# ---------------------------------------------------------------------------


class TestReturnTypeHasLink:
    def test_default_name(self):
        rule = ReturnTypeHasLink()
        assert rule.name == "return_type_has_link"

    def test_positive_signature_with_label_colon_type(self):
        entity = EntityTypeNode(
            name="MyClass",
            signature="do_work() -> result:str",
        )
        root = DocumentRoot(
            header=HeaderNode(),
            body=BodyNode(entities=[entity]),
        )
        node = DocumentNode(root=root)
        rule = ReturnTypeHasLink()
        errors = rule.check(node)
        assert errors == []

    def test_negative_signature_without_label(self):
        entity = EntityTypeNode(
            name="MyClass",
            signature="do_work() -> str",
        )
        root = DocumentRoot(
            header=HeaderNode(),
            body=BodyNode(entities=[entity]),
        )
        node = DocumentNode(root=root)
        rule = ReturnTypeHasLink()
        errors = rule.check(node)
        assert len(errors) == 1
        assert isinstance(errors[0], DocumentRuleError)
        assert errors[0].rule == "return_type_has_link"
        assert "is missing a semantic label" in errors[0].message

    def test_positive_signature_no_return_type(self):
        """Signature without -> has no return type, so no error."""
        entity = EntityTypeNode(
            name="MyClass",
            signature="do_work()",
        )
        root = DocumentRoot(
            header=HeaderNode(),
            body=BodyNode(entities=[entity]),
        )
        node = DocumentNode(root=root)
        rule = ReturnTypeHasLink()
        errors = rule.check(node)
        assert errors == []

    def test_positive_method_signature_with_label(self):
        method = MethodNode(
            name="do_work",
            signature="execute() -> result:int",
        )
        entity = EntityTypeNode(name="MyClass", methods=[method])
        root = DocumentRoot(
            header=HeaderNode(),
            body=BodyNode(entities=[entity]),
        )
        node = DocumentNode(root=root)
        rule = ReturnTypeHasLink()
        errors = rule.check(node)
        assert errors == []

    def test_positive_routine_signature_with_label(self):
        routine = RoutineTypeNode(
            name="my_func",
            signature="run() -> output:bool",
        )
        root = DocumentRoot(
            header=HeaderNode(),
            body=BodyNode(routines=[routine]),
        )
        node = DocumentNode(root=root)
        rule = ReturnTypeHasLink()
        errors = rule.check(node)
        assert errors == []


# ---------------------------------------------------------------------------
# 18. EmbeddedEntityCanNotHasMutations
# ---------------------------------------------------------------------------


class TestEmbeddedEntityCanNotHasMutations:
    def test_default_name(self):
        rule = EmbeddedEntityCanNotHasMutations()
        assert rule.name == "embedded_entity_can_not_has_mutations"

    def test_positive_non_embedded_entity_with_mutations(self):
        root = DocumentRoot(
            header=HeaderNode(),
            body=BodyNode(
                entities=[EntityTypeNode(name="MyEntity", embedded=False, mutations=[("MutA", "path")])],
            ),
        )
        node = DocumentNode(root=root)
        rule = EmbeddedEntityCanNotHasMutations()
        errors = rule.check(node)
        assert errors == []

    def test_negative_embedded_entity_with_mutations(self):
        root = DocumentRoot(
            header=HeaderNode(),
            body=BodyNode(
                entities=[EntityTypeNode(name="MyEntity", embedded=True, mutations=[("MutA", "path")])],
            ),
        )
        node = DocumentNode(root=root)
        rule = EmbeddedEntityCanNotHasMutations()
        errors = rule.check(node)
        assert len(errors) == 1
        assert isinstance(errors[0], DocumentRuleError)
        assert errors[0].rule == "embedded_entity_can_not_has_mutations"
        assert "(->Entity)" in errors[0].message
        assert "cannot define mutations" in errors[0].message

    def test_positive_embedded_entity_without_mutations(self):
        root = DocumentRoot(
            header=HeaderNode(),
            body=BodyNode(
                entities=[EntityTypeNode(name="MyEntity", embedded=True, mutations=[])],
            ),
        )
        node = DocumentNode(root=root)
        rule = EmbeddedEntityCanNotHasMutations()
        errors = rule.check(node)
        assert errors == []


# ---------------------------------------------------------------------------
# 19. EmbeddedTypeHasLowLevel (ASTRule)
# ---------------------------------------------------------------------------


class TestEmbeddedTypeHasLowLevel:
    def test_default_name(self):
        rule = EmbeddedTypeHasLowLevel(tree=[])
        assert rule.name == "embedded_type_has_low_level"

    def test_positive_embedded_from_child_directory(self):
        """Embedded type defined in a child directory — no error."""
        parent_doc = DocumentRoot(
            path="/project/parent",
            body=BodyNode(
                entities=[EntityTypeNode(name="ChildType", embedded=True)],
                routines=[],
            ),
        )
        child_doc = DocumentRoot(
            path="/project/parent/child",
            body=BodyNode(
                entities=[EntityTypeNode(name="ChildType", embedded=False)],
                routines=[],
            ),
        )
        rule = EmbeddedTypeHasLowLevel(tree=[parent_doc, child_doc])
        errors = rule.check(parent_doc)
        assert errors == []

    def test_negative_embedded_from_parent_directory(self):
        """Embedded type defined in a parent directory — error."""
        child_doc = DocumentRoot(
            path="/project/parent/child",
            body=BodyNode(
                entities=[EntityTypeNode(name="ParentType", embedded=True)],
                routines=[],
            ),
        )
        parent_doc = DocumentRoot(
            path="/project/parent",
            body=BodyNode(
                entities=[EntityTypeNode(name="ParentType", embedded=False)],
                routines=[],
            ),
        )
        rule = EmbeddedTypeHasLowLevel(tree=[parent_doc, child_doc])
        errors = rule.check(child_doc)
        assert len(errors) == 1
        assert isinstance(errors[0], ASTRuleError)
        assert errors[0].rule == "embedded_type_has_low_level"

    def test_negative_embedded_from_same_level(self):
        """Embedded type defined at the same directory level — error (not lower)."""
        doc_a = DocumentRoot(
            path="/project/level_a",
            body=BodyNode(
                entities=[EntityTypeNode(name="SharedType", embedded=True)],
                routines=[],
            ),
        )
        doc_b = DocumentRoot(
            path="/project/level_b",
            body=BodyNode(
                entities=[EntityTypeNode(name="SharedType", embedded=False)],
                routines=[],
            ),
        )
        rule = EmbeddedTypeHasLowLevel(tree=[doc_a, doc_b])
        errors = rule.check(doc_a)
        assert len(errors) == 1
        assert isinstance(errors[0], ASTRuleError)
        assert errors[0].rule == "embedded_type_has_low_level"


# ---------------------------------------------------------------------------
# 20. ImportsHasOnlyValidKeys
# ---------------------------------------------------------------------------


class TestImportsHasOnlyValidKeys:
    def test_default_name(self):
        rule = ImportsHasOnlyValidKeys()
        assert rule.name == "imports_has_only_valid_keys"

    def test_positive_valid_keys(self):
        """Import item with only Types and From keys — no errors."""
        root = DocumentRoot(
            header=HeaderNode(
                imports=ImportsNode(
                    types=[
                        ImportTypeItemNode(type_name={"Foo"}, from_path="a", data={"Types": ["Foo"], "From": "a"}),
                    ],
                ),
            ),
        )
        node = DocumentNode(root=root)
        rule = ImportsHasOnlyValidKeys()
        errors = rule.check(node)
        assert errors == []

    def test_negative_unknown_key(self):
        """Import item with extra key like 'Extra' — error."""
        root = DocumentRoot(
            header=HeaderNode(
                imports=ImportsNode(
                    types=[
                        ImportTypeItemNode(
                            type_name={"Foo"}, from_path="a", data={"Types": ["Foo"], "From": "a", "Extra": True}
                        ),
                    ],
                ),
            ),
        )
        node = DocumentNode(root=root)
        rule = ImportsHasOnlyValidKeys()
        errors = rule.check(node)
        assert len(errors) == 1
        assert isinstance(errors[0], DocumentRuleError)
        assert errors[0].rule == "imports_has_only_valid_keys"
        assert "contains unknown keys" in errors[0].message
        assert "— allowed: Types, Usages, From" in errors[0].message
        root = DocumentRoot(
            header=HeaderNode(
                imports=ImportsNode(
                    types=[
                        ImportTypeItemNode(type_name={"Foo"}, from_path="a", data={}),
                    ],
                ),
            ),
        )
        node = DocumentNode(root=root)
        rule = ImportsHasOnlyValidKeys()
        errors = rule.check(node)
        assert errors == []


# ---------------------------------------------------------------------------
# 21. EntityHasOnlyValidKeys
# ---------------------------------------------------------------------------


class TestEntityHasOnlyValidKeys:
    def test_default_name(self):
        rule = EntityHasOnlyValidKeys()
        assert rule.name == "entity_has_only_valid_keys"

    def test_positive_all_valid_keys(self):
        """Entity with all 4 valid keys — no errors."""
        root = DocumentRoot(
            header=HeaderNode(),
            body=BodyNode(
                entities=[
                    EntityTypeNode(
                        name="MyEntity",
                        data={"location": "a.py", "annotations": "...", "properties": {}, "methods": {}},
                    ),
                ],
            ),
        )
        node = DocumentNode(root=root)
        rule = EntityHasOnlyValidKeys()
        errors = rule.check(node)
        assert errors == []

    def test_negative_unknown_key(self):
        """Entity with extra key — error."""
        root = DocumentRoot(
            header=HeaderNode(),
            body=BodyNode(
                entities=[
                    EntityTypeNode(name="MyEntity", data={"location": "a.py", "Extra": True}),
                ],
            ),
        )
        node = DocumentNode(root=root)
        rule = EntityHasOnlyValidKeys()
        errors = rule.check(node)
        assert len(errors) == 1
        assert isinstance(errors[0], DocumentRuleError)
        assert "— allowed: location, annotations, methods, properties" in errors[0].message

    def test_positive_empty_data(self):
        """Entity with empty data — no errors."""
        root = DocumentRoot(
            header=HeaderNode(),
            body=BodyNode(entities=[EntityTypeNode(name="E", data={})]),
        )
        node = DocumentNode(root=root)
        rule = EntityHasOnlyValidKeys()
        errors = rule.check(node)
        assert errors == []


# ---------------------------------------------------------------------------
# 22. RoutineHasOnlyValidKeys
# ---------------------------------------------------------------------------


class TestRoutineHasOnlyValidKeys:
    def test_default_name(self):
        rule = RoutineHasOnlyValidKeys()
        assert rule.name == "routine_has_only_valid_keys"

    def test_positive_valid_keys(self):
        """Routine with location and annotations — no errors."""
        root = DocumentRoot(
            header=HeaderNode(),
            body=BodyNode(
                routines=[
                    RoutineTypeNode(name="my_func", data={"location": "a.py", "annotations": "..."}),
                ],
            ),
        )
        node = DocumentNode(root=root)
        rule = RoutineHasOnlyValidKeys()
        errors = rule.check(node)
        assert errors == []

    def test_negative_unknown_key(self):
        """Routine with extra key — error."""
        root = DocumentRoot(
            header=HeaderNode(),
            body=BodyNode(
                routines=[
                    RoutineTypeNode(name="my_func", data={"location": "a.py", "Extra": True}),
                ],
            ),
        )
        node = DocumentNode(root=root)
        rule = RoutineHasOnlyValidKeys()
        errors = rule.check(node)
        assert len(errors) == 1
        assert isinstance(errors[0], DocumentRuleError)
        assert "— allowed: location, annotations" in errors[0].message

    def test_positive_empty_data(self):
        root = DocumentRoot(
            header=HeaderNode(),
            body=BodyNode(routines=[RoutineTypeNode(name="r", data={})]),
        )
        node = DocumentNode(root=root)
        rule = RoutineHasOnlyValidKeys()
        errors = rule.check(node)
        assert errors == []


# ---------------------------------------------------------------------------
# 23. ImportTypeExists (ASTRule)
# ---------------------------------------------------------------------------


class TestImportTypeExists:
    def test_default_name(self):
        rule = ImportTypeExists(tree=[])
        assert rule.name == "import_type_exists"

    def test_positive_type_exists_in_target_doc(self):
        """Imported type exists as entity in target document — no errors."""
        target_doc = DocumentRoot(
            path="target_pkg",
            header=HeaderNode(),
            body=BodyNode(entities=[EntityTypeNode(name="MyType")]),
        )
        current_doc = DocumentRoot(
            path="current_pkg",
            header=HeaderNode(
                imports=ImportsNode(
                    types=[
                        ImportTypeItemNode(type_name={"MyType"}, from_path="target_pkg"),
                    ],
                ),
            ),
        )
        rule = ImportTypeExists(tree=[current_doc, target_doc])
        errors = rule.check(current_doc)
        assert errors == []

    def test_positive_type_exists_as_routine(self):
        """Imported type exists as routine in target — no errors."""
        target_doc = DocumentRoot(
            path="target_pkg",
            header=HeaderNode(),
            body=BodyNode(routines=[RoutineTypeNode(name="MyFunc")]),
        )
        current_doc = DocumentRoot(
            path="current_pkg",
            header=HeaderNode(
                imports=ImportsNode(
                    types=[
                        ImportTypeItemNode(type_name={"MyFunc"}, from_path="target_pkg"),
                    ],
                ),
            ),
        )
        rule = ImportTypeExists(tree=[current_doc, target_doc])
        errors = rule.check(current_doc)
        assert errors == []

    def test_positive_type_exists_in_header_types(self):
        """Imported type exists in header.types — no errors."""
        target_doc = DocumentRoot(
            path="target_pkg",
            header=HeaderNode(types=["ReExportedType"]),
        )
        current_doc = DocumentRoot(
            path="current_pkg",
            header=HeaderNode(
                imports=ImportsNode(
                    types=[
                        ImportTypeItemNode(type_name={"ReExportedType"}, from_path="target_pkg"),
                    ],
                ),
            ),
        )
        rule = ImportTypeExists(tree=[current_doc, target_doc])
        errors = rule.check(current_doc)
        assert errors == []

    def test_negative_type_not_found(self, tmp_path: Path):
        """Imported type not found in target doc — error."""
        target_dir = tmp_path / "target_pkg"
        target_dir.mkdir()

        target_doc = DocumentRoot(
            path=str(target_dir),
            header=HeaderNode(),
            body=BodyNode(entities=[EntityTypeNode(name="OtherType")]),
        )
        current_doc = DocumentRoot(
            path="current_pkg",
            header=HeaderNode(
                imports=ImportsNode(
                    types=[
                        ImportTypeItemNode(type_name={"MissingType"}, from_path=str(target_dir)),
                    ],
                ),
            ),
        )
        rule = ImportTypeExists(tree=[current_doc, target_doc])
        errors = rule.check(current_doc)
        assert len(errors) == 1
        assert isinstance(errors[0], ASTRuleError)
        assert "MissingType" in errors[0].message

    def test_positive_from_path_not_on_filesystem_skipped(self):
        """from_path that doesn't exist on filesystem — check skipped, no errors."""
        current_doc = DocumentRoot(
            path="current_pkg",
            header=HeaderNode(
                imports=ImportsNode(
                    types=[
                        ImportTypeItemNode(type_name={"MyType"}, from_path="/nonexistent/path"),
                    ],
                ),
            ),
        )
        rule = ImportTypeExists(tree=[current_doc])
        errors = rule.check(current_doc)
        assert errors == []

    def test_positive_target_doc_not_in_tree_no_error_if_path_missing(self):
        """from_path not found in tree and not on filesystem — no error."""
        current_doc = DocumentRoot(
            path="current_pkg",
            header=HeaderNode(
                imports=ImportsNode(
                    types=[
                        ImportTypeItemNode(type_name={"MyType"}, from_path="missing_pkg"),
                    ],
                ),
            ),
        )
        rule = ImportTypeExists(tree=[current_doc])
        errors = rule.check(current_doc)
        assert errors == []

    def test_negative_target_doc_in_tree_but_type_missing(self, tmp_path: Path):
        """Target doc in tree but type not there — error."""
        target_dir = tmp_path / "target_pkg"
        target_dir.mkdir()

        target_doc = DocumentRoot(
            path=str(target_dir),
            header=HeaderNode(),
            body=BodyNode(entities=[]),
        )
        current_doc = DocumentRoot(
            path="current_pkg",
            header=HeaderNode(
                imports=ImportsNode(
                    types=[
                        ImportTypeItemNode(type_name={"Missing"}, from_path=str(target_dir)),
                    ],
                ),
            ),
        )
        rule = ImportTypeExists(tree=[current_doc, target_doc])
        errors = rule.check(current_doc)
        assert len(errors) == 1


# ---------------------------------------------------------------------------
# 24. ImportHasValidFromPath — hierarchy checks
# ---------------------------------------------------------------------------


class TestImportHasValidFromPathHierarchy:
    def test_positive_same_level(self, tmp_path: Path):
        """from_path at the same level as document — no hierarchy error."""
        cwd = Path.cwd().resolve()
        sibling = cwd / "_test_sibling_pkg"
        sibling.mkdir(exist_ok=True)
        try:
            (sibling / "CODEMANIFEST").write_text("---\n---\n---\n", encoding="utf-8")

            doc_dir = cwd / "_test_current_pkg"
            doc_dir.mkdir(exist_ok=True)
            try:
                root = DocumentRoot(
                    path=str(doc_dir),
                    header=HeaderNode(
                        imports=ImportsNode(
                            types=[
                                ImportTypeItemNode(type_name={"Foo"}, from_path=str(sibling)),
                            ],
                        ),
                    ),
                )
                node = DocumentNode(root=root)
                rule = ImportHasValidFromPath()
                errors = rule.check(node)
                assert errors == []
            finally:
                doc_dir.rmdir()
        finally:
            (sibling / "CODEMANIFEST").unlink(missing_ok=True)
            sibling.rmdir()

    def test_positive_below_document(self, tmp_path: Path):
        """from_path below document in hierarchy — no hierarchy error."""
        cwd = Path.cwd().resolve()
        doc_dir = cwd / "_test_doc_pkg"
        doc_dir.mkdir(exist_ok=True)
        child = doc_dir / "child_pkg"
        child.mkdir(exist_ok=True)
        try:
            root = DocumentRoot(
                path=str(doc_dir),
                header=HeaderNode(
                    imports=ImportsNode(
                        types=[
                            ImportTypeItemNode(type_name={"Foo"}, from_path=str(child)),
                        ],
                    ),
                ),
            )
            node = DocumentNode(root=root)
            rule = ImportHasValidFromPath()
            errors = rule.check(node)
            assert errors == []
        finally:
            child.rmdir()
            doc_dir.rmdir()

    def test_positive_above_document_no_hierarchy_error(self, tmp_path: Path):
        """from_path above document — no longer an error after hierarchy check removal."""
        cwd = Path.cwd().resolve()
        parent_pkg = cwd / "_test_parent_pkg"
        parent_pkg.mkdir(exist_ok=True)
        doc_dir = parent_pkg / "child_pkg"
        doc_dir.mkdir(exist_ok=True)
        try:
            (parent_pkg / "CODEMANIFEST").write_text("---\n---\n---\n", encoding="utf-8")

            root = DocumentRoot(
                path=str(doc_dir),
                header=HeaderNode(
                    imports=ImportsNode(
                        types=[
                            ImportTypeItemNode(type_name={"Foo"}, from_path=str(parent_pkg)),
                        ],
                    ),
                ),
            )
            node = DocumentNode(root=root)
            rule = ImportHasValidFromPath()
            errors = rule.check(node)
            assert errors == []
        finally:
            (parent_pkg / "CODEMANIFEST").unlink(missing_ok=True)
            doc_dir.rmdir()
            parent_pkg.rmdir()


# ---------------------------------------------------------------------------
# N. signature_contains_type_name
# ---------------------------------------------------------------------------


class TestSignatureContainsTypeName:
    def test_facade_availability(self):
        """signature_contains_type_name must be importable from the rules facade."""
        assert callable(signature_contains_type_name)

    def test_positive_in_params(self):
        assert signature_contains_type_name("(param: TypeName)", "TypeName") is True

    def test_positive_in_params_multi(self):
        assert signature_contains_type_name("(param: TypeName, param_2: Type)", "TypeName") is True

    def test_positive_in_return_type(self):
        assert signature_contains_type_name("(param: Type) -> rv:TypeName", "TypeName") is True

    def test_negative_partial_suffix(self):
        assert signature_contains_type_name("(param: TypeNameOne)", "TypeName") is False

    def test_negative_partial_prefix(self):
        assert signature_contains_type_name("(param: TwoTypeName)", "TypeName") is False

    def test_negative_quoted_string(self):
        assert signature_contains_type_name('(param: Type: = "TypeName")', "TypeName") is False

    def test_edge_empty_signature(self):
        assert signature_contains_type_name("", "TypeName") is False

    def test_edge_empty_type_name(self):
        assert signature_contains_type_name("(param: SomeType)", "") is False

    def test_edge_return_type_after_colon(self):
        assert signature_contains_type_name("() -> label:TypeName", "TypeName") is True

    def test_positive_type_in_list_brackets(self):
        assert signature_contains_type_name("(param: list[TypeName])", "TypeName") is True

    def test_positive_type_in_nested_brackets(self):
        assert signature_contains_type_name("(param: dict[str, TypeName])", "TypeName") is True

    def test_positive_type_in_return_list(self):
        assert signature_contains_type_name("() -> items:list[TypeName]", "TypeName") is True

    def test_negative_type_as_part_of_other_bracketed(self):
        assert signature_contains_type_name("(param: list[TypeNameExtra])", "TypeName") is False


# ---------------------------------------------------------------------------
# N+1. SignatureIsValid
# ---------------------------------------------------------------------------


class TestSignatureIsValid:
    def test_default_name(self):
        rule = SignatureIsValid()
        assert rule.name == "signature_is_valid"

    def test_positive_entity_valid_signature_with_return(self):
        """Entity with signature '(...)' -> ...' produces no errors."""
        entity = EntityTypeNode(
            name="MyEntity",
            signature="(param: str) -> result:str",
        )
        root = DocumentRoot(
            header=HeaderNode(),
            body=BodyNode(entities=[entity]),
        )
        node = DocumentNode(root=root)
        rule = SignatureIsValid()
        errors = rule.check(node)
        assert errors == []

    def test_positive_entity_valid_signature_no_return(self):
        """Entity with signature '(...)' (no return) produces no errors."""
        entity = EntityTypeNode(
            name="MyEntity",
            signature="()",
        )
        root = DocumentRoot(
            header=HeaderNode(),
            body=BodyNode(entities=[entity]),
        )
        node = DocumentNode(root=root)
        rule = SignatureIsValid()
        errors = rule.check(node)
        assert errors == []

    def test_positive_routine_valid_signature(self):
        """Routine with valid signature produces no errors."""
        routine = RoutineTypeNode(
            name="run",
            signature="() -> void:null",
        )
        root = DocumentRoot(
            header=HeaderNode(),
            body=BodyNode(routines=[routine]),
        )
        node = DocumentNode(root=root)
        rule = SignatureIsValid()
        errors = rule.check(node)
        assert errors == []

    def test_negative_entity_invalid_signature_no_parens(self):
        """Entity with signature missing parentheses produces an error."""
        entity = EntityTypeNode(
            name="MyEntity",
            signature="no parens here",
        )
        root = DocumentRoot(
            header=HeaderNode(),
            body=BodyNode(entities=[entity]),
        )
        node = DocumentNode(root=root)
        rule = SignatureIsValid()
        errors = rule.check(node)
        assert len(errors) == 1
        assert isinstance(errors[0], DocumentRuleError)
        assert errors[0].rule == "signature_is_valid"

    def test_negative_method_invalid_signature(self):
        """Method with invalid signature produces an error."""
        method = MethodNode(
            name="do_stuff",
            signature="invalid_sig",
        )
        entity = EntityTypeNode(name="MyEntity", signature="()", methods=[method])
        root = DocumentRoot(
            header=HeaderNode(),
            body=BodyNode(entities=[entity]),
        )
        node = DocumentNode(root=root)
        rule = SignatureIsValid()
        errors = rule.check(node)
        assert len(errors) == 1
        assert isinstance(errors[0], DocumentRuleError)
        assert errors[0].rule == "signature_is_valid"

    def test_error_message_format(self):
        """Error message follows template: signature '{sig}' has invalid format, use '(...) -> ...' or '(...)'."""
        entity = EntityTypeNode(
            name="MyEntity",
            signature="bad signature",
        )
        root = DocumentRoot(
            header=HeaderNode(),
            body=BodyNode(entities=[entity]),
        )
        node = DocumentNode(root=root)
        rule = SignatureIsValid()
        errors = rule.check(node)
        assert len(errors) == 1
        assert errors[0].message == "signature 'bad signature' has invalid format, use '(...) -> ...' or '(...)'"


# ---------------------------------------------------------------------------
# N+2. ImportIsUsed
# ---------------------------------------------------------------------------


def _make_import_is_used_doc(  # noqa: PLR0913
    *,
    import_names: set[str] | None = None,
    import_from: str = "goga/ast/nodes",
    import_alias: str = "",
    header_links: list[str] | None = None,
    usage_links: list[str] | None = None,
    entities: list[EntityTypeNode] | None = None,
    routines: list[RoutineTypeNode] | None = None,
    embeddings: list[tuple[str, str]] | None = None,
    doc_path: str = "test_doc",
) -> DocumentNode:
    """Helper to build a DocumentNode for ImportIsUsed tests."""
    import_item = ImportTypeItemNode(type_name=import_names or {"Node"}, from_path=import_from, alias=import_alias)
    header = HeaderNode(
        imports=ImportsNode(types=[import_item]),
    )
    if header_links:
        header.annotations = AnnotationsNode(links=header_links)
    if usage_links:
        usage_item = UsageItemNode(name="some_usage", annotations=AnnotationsNode(links=usage_links))
        header.usages = UsagesNode(items=[usage_item])
    body = BodyNode(
        entities=entities or [],
        routines=routines or [],
    )
    root = DocumentRoot(path=doc_path, header=header, body=body, embeddings=embeddings or [])
    return DocumentNode(root=root)


class TestImportIsUsed:
    def test_default_name(self):
        rule = ImportIsUsed()
        assert rule.name == "import_is_used"

    def test_positive_header_annotations_links(self):
        """Type referenced in header annotations links -> no errors."""
        node = _make_import_is_used_doc(header_links=["Node"])
        rule = ImportIsUsed()
        assert rule.check(node) == []

    def test_positive_entity_annotation_links(self):
        """Type referenced in entity annotation links -> no errors."""
        entity = EntityTypeNode(name="MyEntity", annotations=AnnotationsNode(links=["Node"]))
        node = _make_import_is_used_doc(entities=[entity])
        rule = ImportIsUsed()
        assert rule.check(node) == []

    def test_positive_method_annotation_links(self):
        """Type referenced in method annotation links -> no errors."""
        method = MethodNode(name="do_it", annotations=AnnotationsNode(links=["Node"]))
        entity = EntityTypeNode(name="MyEntity", methods=[method])
        node = _make_import_is_used_doc(entities=[entity])
        rule = ImportIsUsed()
        assert rule.check(node) == []

    def test_positive_property_annotation_links(self):
        """Type referenced in property annotation links -> no errors."""
        prop = PropertyNode(name="field", annotations=AnnotationsNode(links=["Node"]))
        entity = EntityTypeNode(name="MyEntity", properties=[prop])
        node = _make_import_is_used_doc(entities=[entity])
        rule = ImportIsUsed()
        assert rule.check(node) == []

    def test_positive_routine_annotation_links(self):
        """Type referenced in routine annotation links -> no errors."""
        routine = RoutineTypeNode(name="run", annotations=AnnotationsNode(links=["Node"]))
        node = _make_import_is_used_doc(routines=[routine])
        rule = ImportIsUsed()
        assert rule.check(node) == []

    def test_positive_usage_item_annotation_links(self):
        """Type referenced in usage item annotation links -> no errors."""
        node = _make_import_is_used_doc(usage_links=["Node"])
        rule = ImportIsUsed()
        assert rule.check(node) == []

    def test_positive_entity_signature(self):
        """Type referenced in entity signature -> no errors."""
        entity = EntityTypeNode(name="MyEntity", signature="(param: Node) -> result:void")
        node = _make_import_is_used_doc(entities=[entity])
        rule = ImportIsUsed()
        assert rule.check(node) == []

    def test_positive_method_signature(self):
        """Type referenced in method signature -> no errors."""
        method = MethodNode(name="do_it", signature="(param: Node)")
        entity = EntityTypeNode(name="MyEntity", methods=[method])
        node = _make_import_is_used_doc(entities=[entity])
        rule = ImportIsUsed()
        assert rule.check(node) == []

    def test_positive_routine_signature(self):
        """Type referenced in routine signature -> no errors."""
        routine = RoutineTypeNode(name="run", signature="(param: Node) -> void:null")
        node = _make_import_is_used_doc(routines=[routine])
        rule = ImportIsUsed()
        assert rule.check(node) == []

    def test_positive_alias_used(self):
        """Alias used in annotations -> no errors (checks alias, not type_name)."""
        node = _make_import_is_used_doc(import_names={"Node"}, import_alias="N", header_links=["N"])
        rule = ImportIsUsed()
        assert rule.check(node) == []

    def test_negative_imported_type_not_used(self):
        """Imported type not used anywhere -> error."""
        node = _make_import_is_used_doc(import_names={"Node"}, doc_path="my_project")
        rule = ImportIsUsed()
        errors = rule.check(node)
        assert len(errors) == 1
        assert isinstance(errors[0], DocumentRuleError)
        assert errors[0].rule == "import_is_used"

    def test_error_message_format(self):
        """Error message follows template: Type '{type_name}' was imported, but not used in '{doc_path}'."""
        node = _make_import_is_used_doc(import_names={"Node"}, doc_path="my_project")
        rule = ImportIsUsed()
        errors = rule.check(node)
        assert len(errors) == 1
        assert errors[0].message == "Type 'Node' was imported, but not used in 'my_project'"

    def test_positive_embedded_entity_annotation_links(self):
        """Imported type used via embedding (->Node) -> no errors."""
        entity = EntityTypeNode(name="Node", embedded=True)
        node = _make_import_is_used_doc(entities=[entity], embeddings=[("Node", "goga/ast/nodes")])
        rule = ImportIsUsed()
        assert rule.check(node) == []

    def test_positive_embedded_routine(self):
        """Imported routine type used via embedding -> no errors."""
        routine = RoutineTypeNode(name="helper", embedded=True)
        node = _make_import_is_used_doc(routines=[routine], embeddings=[("Node", "goga/ast/nodes")])
        rule = ImportIsUsed()
        assert rule.check(node) == []

    def test_negative_property_type_on_embedded_entity_not_counted(self):
        """Property type on embedded entity should NOT count as usage -> error."""
        prop = PropertyNode(name="items", type="Node")
        entity = EntityTypeNode(name="Node", embedded=True, properties=[prop])
        node = _make_import_is_used_doc(entities=[entity], embeddings=[("Node", "goga/ast/nodes")])
        rule = ImportIsUsed()
        # The embedding itself counts as usage, so no error expected
        assert rule.check(node) == []

    def test_negative_property_type_on_embedded_entity_without_embedding(self):
        """Property type on embedded entity without embedding match -> error."""
        prop = PropertyNode(name="items", type="Node")
        embedded_entity = EntityTypeNode(name="OtherEntity", embedded=True, properties=[prop])
        node = _make_import_is_used_doc(entities=[embedded_entity], import_names={"Node"})
        rule = ImportIsUsed()
        errors = rule.check(node)
        assert len(errors) == 1
        assert errors[0].rule == "import_is_used"

    def test_negative_type_not_embedded_and_not_used(self):
        """Type imported but not embedded and not used anywhere -> error."""
        node = _make_import_is_used_doc()
        rule = ImportIsUsed()
        errors = rule.check(node)
        assert len(errors) == 1
        assert errors[0].rule == "import_is_used"

    def test_positive_property_type_usage(self):
        """Type used as prop.type of an entity property -> no error."""
        prop = PropertyNode(name="items", type="Node")
        entity = EntityTypeNode(name="MyEntity", properties=[prop])
        node = _make_import_is_used_doc(entities=[entity], import_names={"Node"})
        rule = ImportIsUsed()
        assert rule.check(node) == []

    def test_positive_property_type_not_matching_no_false_positive(self):
        """Property type does not match imported type and type unused elsewhere -> error."""
        prop = PropertyNode(name="items", type="OtherType")
        entity = EntityTypeNode(name="MyEntity", properties=[prop])
        node = _make_import_is_used_doc(entities=[entity], import_names={"Node"})
        rule = ImportIsUsed()
        errors = rule.check(node)
        assert len(errors) == 1
        assert errors[0].rule == "import_is_used"

    def test_positive_property_type_with_alias(self):
        """Alias used as property type -> no error."""
        prop = PropertyNode(name="items", type="N")
        entity = EntityTypeNode(name="MyEntity", properties=[prop])
        node = _make_import_is_used_doc(entities=[entity], import_names={"Node"}, import_alias="N")
        rule = ImportIsUsed()
        assert rule.check(node) == []

    def test_positive_usage_import_used_in_usage_links(self):
        """ImportUsageItemNode referenced in usage links -> no error."""
        usage_item = ImportUsageItemNode(usage_name={"my_usage"}, from_path="some/path")
        header = HeaderNode(
            imports=ImportsNode(usages=[usage_item]),
            usages=UsagesNode(items=[UsageItemNode(name="my_usage", annotations=AnnotationsNode(links=["my_usage"]))]),
        )
        body = BodyNode(entities=[], routines=[])
        root = DocumentRoot(path="test_doc", header=header, body=body, embeddings=[])
        node = DocumentNode(root=root)
        rule = ImportIsUsed()
        assert rule.check(node) == []

    def test_negative_usage_import_not_used(self):
        """ImportUsageItemNode not referenced in any usage links -> error."""
        usage_item = ImportUsageItemNode(usage_name={"my_usage"}, from_path="some/path")
        header = HeaderNode(
            imports=ImportsNode(usages=[usage_item]),
            usages=UsagesNode(items=[UsageItemNode(name="other_usage")]),
        )
        body = BodyNode(entities=[], routines=[])
        root = DocumentRoot(path="test_doc", header=header, body=body, embeddings=[])
        node = DocumentNode(root=root)
        rule = ImportIsUsed()
        errors = rule.check(node)
        assert len(errors) == 1
        assert errors[0].rule == "import_is_used"
        assert "my_usage" in errors[0].message
        assert "test_doc" in errors[0].message

    def test_positive_usage_import_alias_used(self):
        """ImportUsageItemNode alias referenced in usage links -> no error."""
        usage_item = ImportUsageItemNode(usage_name={"my_usage"}, from_path="some/path", alias="mu")
        header = HeaderNode(
            imports=ImportsNode(usages=[usage_item]),
            usages=UsagesNode(items=[UsageItemNode(name="my_usage", annotations=AnnotationsNode(links=["mu"]))]),
        )
        body = BodyNode(entities=[], routines=[])
        root = DocumentRoot(path="test_doc", header=header, body=body, embeddings=[])
        node = DocumentNode(root=root)
        rule = ImportIsUsed()
        assert rule.check(node) == []


# ---------------------------------------------------------------------------
# N+3. UsageFilepathExists
# ---------------------------------------------------------------------------


class TestUsageFilepathExists:
    def test_usage_filepath_exists_importable(self):
        """UsageFilepathExists must be importable from the rules facade."""
        assert isinstance(UsageFilepathExists, type)

    def test_usage_filepath_exists_is_document_rule(self):
        assert issubclass(UsageFilepathExists, DocumentRule)

    def test_usage_filepath_exists_default_name(self):
        rule = UsageFilepathExists()
        assert rule.name == "usage_filepath_exists"

    def test_usage_filepath_exists_file_present(self):
        test_dir = Path.cwd() / "_test_usage_filepath_exists"
        test_dir.mkdir(exist_ok=True)
        try:
            specs_dir = test_dir / "specs"
            specs_dir.mkdir(exist_ok=True)
            pattern_file = specs_dir / "pattern.md"
            pattern_file.write_text("# test")

            root = DocumentRoot(
                header=HeaderNode(
                    usages=UsagesNode(
                        items=[
                            UsageItemNode(
                                name="existing",
                                annotations=AnnotationsNode(filepath=str(pattern_file)),
                            )
                        ]
                    )
                )
            )
            node = DocumentNode(root=root)
            rule = UsageFilepathExists()
            errors = rule.check(node)
            assert errors == []
        finally:
            pattern_file.unlink(missing_ok=True)
            specs_dir.rmdir()
            test_dir.rmdir()

    def test_usage_filepath_inline_skipped(self):
        root = DocumentRoot(
            header=HeaderNode(
                usages=UsagesNode(
                    items=[
                        UsageItemNode(
                            name="inline",
                            annotations=AnnotationsNode(text="Some inline pattern"),
                        )
                    ]
                )
            )
        )
        node = DocumentNode(root=root)
        rule = UsageFilepathExists()
        errors = rule.check(node)
        assert errors == []

    def test_usage_filepath_not_found(self):
        root = DocumentRoot(
            header=HeaderNode(
                usages=UsagesNode(
                    items=[
                        UsageItemNode(
                            name="missing",
                            annotations=AnnotationsNode(filepath="nonexistent/file.md"),
                        )
                    ]
                )
            )
        )
        node = DocumentNode(root=root)
        rule = UsageFilepathExists()
        errors = rule.check(node)
        assert len(errors) == 1
        assert errors[0].rule == "usage_filepath_exists"
        assert "does not exist" in errors[0].message

    def test_usage_filepath_outside_project(self):
        root = DocumentRoot(
            header=HeaderNode(
                usages=UsagesNode(
                    items=[
                        UsageItemNode(
                            name="outside",
                            annotations=AnnotationsNode(filepath="/etc/passwd"),
                        )
                    ]
                )
            )
        )
        node = DocumentNode(root=root)
        rule = UsageFilepathExists()
        errors = rule.check(node)
        assert len(errors) == 1
        assert errors[0].rule == "usage_filepath_exists"
        assert "not built from the root of the project" in errors[0].message

    def test_usage_filepath_empty_usages(self):
        root = DocumentRoot(header=HeaderNode(usages=UsagesNode(items=[])))
        node = DocumentNode(root=root)
        rule = UsageFilepathExists()
        errors = rule.check(node)
        assert errors == []

    def test_usage_filepath_multiple_missing(self):
        root = DocumentRoot(
            header=HeaderNode(
                usages=UsagesNode(
                    items=[
                        UsageItemNode(name="a", annotations=AnnotationsNode(filepath="missing_a.md")),
                        UsageItemNode(name="b", annotations=AnnotationsNode(filepath="missing_b.md")),
                    ]
                )
            )
        )
        node = DocumentNode(root=root)
        rule = UsageFilepathExists()
        errors = rule.check(node)
        assert len(errors) == 2


# ---------------------------------------------------------------------------
# N+4. UsageUrlIsAccessible
# ---------------------------------------------------------------------------


class TestUsageUrlIsAccessible:
    def test_usage_url_is_accessible_importable(self):
        """UsageUrlIsAccessible must be importable from the rules facade."""
        assert isinstance(UsageUrlIsAccessible, type)

    def test_usage_url_is_accessible_is_document_rule(self):
        assert issubclass(UsageUrlIsAccessible, DocumentRule)

    def test_usage_url_is_accessible_default_name(self):
        rule = UsageUrlIsAccessible()
        assert rule.name == "usage_url_is_accessible"

    def test_usage_url_is_accessible_returns_200(self):
        mock_response = MagicMock()
        mock_response.status = 200
        with patch("urllib.request.urlopen", return_value=mock_response):
            root = DocumentRoot(
                header=HeaderNode(
                    usages=UsagesNode(
                        items=[
                            UsageItemNode(
                                name="docs",
                                annotations=AnnotationsNode(url="https://example.com/docs.md"),
                            )
                        ]
                    )
                )
            )
            node = DocumentNode(root=root)
            rule = UsageUrlIsAccessible()
            errors = rule.check(node)
            assert errors == []

    def test_usage_url_filepath_skipped(self):
        root = DocumentRoot(
            header=HeaderNode(
                usages=UsagesNode(
                    items=[
                        UsageItemNode(
                            name="local",
                            annotations=AnnotationsNode(filepath="specs/pattern.md"),
                        )
                    ]
                )
            )
        )
        node = DocumentNode(root=root)
        rule = UsageUrlIsAccessible()
        errors = rule.check(node)
        assert errors == []

    def test_usage_url_http_error_non_200(self):
        http_error = urllib.error.HTTPError(
            "https://example.com/docs.md", 404, "Not Found", None, None
        )
        with patch("urllib.request.urlopen", side_effect=http_error):
            root = DocumentRoot(
                header=HeaderNode(
                    usages=UsagesNode(
                        items=[
                            UsageItemNode(
                                name="docs",
                                annotations=AnnotationsNode(url="https://example.com/docs.md"),
                            )
                        ]
                    )
                )
            )
            node = DocumentNode(root=root)
            rule = UsageUrlIsAccessible()
            errors = rule.check(node)
            assert len(errors) == 1
            assert errors[0].rule == "usage_url_is_accessible"
            assert "HTTP 404" in errors[0].message

    def test_usage_url_http_error_500(self):
        http_error = urllib.error.HTTPError(
            "https://example.com/docs.md", 500, "Internal Server Error", None, None
        )
        with patch("urllib.request.urlopen", side_effect=http_error):
            root = DocumentRoot(
                header=HeaderNode(
                    usages=UsagesNode(
                        items=[
                            UsageItemNode(
                                name="docs",
                                annotations=AnnotationsNode(url="https://example.com/docs.md"),
                            )
                        ]
                    )
                )
            )
            node = DocumentNode(root=root)
            rule = UsageUrlIsAccessible()
            errors = rule.check(node)
            assert len(errors) == 1
            assert "HTTP 500" in errors[0].message

    def test_usage_url_request_failed_timeout(self):
        with patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.URLError(TimeoutError("timed out")),
        ):
            root = DocumentRoot(
                header=HeaderNode(
                    usages=UsagesNode(
                        items=[
                            UsageItemNode(
                                name="docs",
                                annotations=AnnotationsNode(url="https://example.com/docs.md"),
                            )
                        ]
                    )
                )
            )
            node = DocumentNode(root=root)
            rule = UsageUrlIsAccessible()
            errors = rule.check(node)
            assert len(errors) == 1
            assert errors[0].rule == "usage_url_is_accessible"
            assert "request failed" in errors[0].message

    def test_usage_url_head_fallback_to_get(self):
        mock_get_response = MagicMock()
        mock_get_response.status = 200
        head_error = urllib.error.HTTPError(
            "https://example.com/docs.md", 405, "Method Not Allowed", None, None
        )

        with patch("urllib.request.urlopen", side_effect=[head_error, mock_get_response]):
            root = DocumentRoot(
                header=HeaderNode(
                    usages=UsagesNode(
                        items=[
                            UsageItemNode(
                                name="docs",
                                annotations=AnnotationsNode(url="https://example.com/docs.md"),
                            )
                        ]
                    )
                )
            )
            node = DocumentNode(root=root)
            rule = UsageUrlIsAccessible()
            errors = rule.check(node)
            assert errors == []

    def test_usage_url_head_fallback_get_also_fails(self):
        head_error = urllib.error.HTTPError(
            "https://example.com/docs.md", 405, "Method Not Allowed", None, None
        )
        get_error = urllib.error.URLError("connection refused")
        with patch("urllib.request.urlopen", side_effect=[head_error, get_error]):
            root = DocumentRoot(
                header=HeaderNode(
                    usages=UsagesNode(
                        items=[
                            UsageItemNode(
                                name="docs",
                                annotations=AnnotationsNode(url="https://example.com/docs.md"),
                            )
                        ]
                    )
                )
            )
            node = DocumentNode(root=root)
            rule = UsageUrlIsAccessible()
            errors = rule.check(node)
            assert len(errors) == 1
            assert errors[0].rule == "usage_url_is_accessible"
            assert "request failed" in errors[0].message

    def test_usage_url_empty_url_string(self):
        root = DocumentRoot(
            header=HeaderNode(
                usages=UsagesNode(
                    items=[
                        UsageItemNode(
                            name="empty",
                            annotations=AnnotationsNode(url=""),
                        )
                    ]
                )
            )
        )
        node = DocumentNode(root=root)
        rule = UsageUrlIsAccessible()
        errors = rule.check(node)
        assert errors == []

    def test_usage_url_invalid_format(self):
        with patch(
            "urllib.request.urlopen",
            side_effect=ValueError("unknown url type: 'not-a-valid-url'"),
        ):
            root = DocumentRoot(
                header=HeaderNode(
                    usages=UsagesNode(
                        items=[
                            UsageItemNode(
                                name="bad",
                                annotations=AnnotationsNode(url="not-a-valid-url"),
                            )
                        ]
                    )
                )
            )
            node = DocumentNode(root=root)
            rule = UsageUrlIsAccessible()
            errors = rule.check(node)
            assert len(errors) == 1
            assert errors[0].rule == "usage_url_is_accessible"
            assert "request failed" in errors[0].message
