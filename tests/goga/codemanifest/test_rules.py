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
from goga.codemanifest.nodes import BodyNode, EntityTypeNode, MethodNode, PropertyNode, RoutineTypeNode
from goga.codemanifest.rules import (
    AllUsagesIsUsed,
    AnnotationLinksExists,
    DocumentRule,
    EmbeddedEntityCanNotHasMutations,
    EmbeddedTypeHasLowLevel,
    EntitiesAndRoutinesHasNotConflicts,
    ImportHasNotDuplicate,
    ImportHasTypeRule,
    ImportHasValidFromPathRule,
    ImportsCanNotBeEmptyRule,
    ImportsHasNotCyclicalDepsRule,
    MutationExists,
    MutationIsValid,
    ProjectRule,
    ReturnTypeHasLink,
    UsageLinksHasNotConflicts,
)

# ---------------------------------------------------------------------------
# 1. Facade: all 7 rule classes are importable
# ---------------------------------------------------------------------------

EXPECTED_RULE_CLASSES = [
    DocumentRule,
    ImportsCanNotBeEmptyRule,
    ImportHasTypeRule,
    ImportHasValidFromPathRule,
    ImportHasNotDuplicate,
    AllUsagesIsUsed,
    AnnotationLinksExists,
    UsageLinksHasNotConflicts,
    EntitiesAndRoutinesHasNotConflicts,
    MutationExists,
    MutationIsValid,
    ReturnTypeHasLink,
    EmbeddedEntityCanNotHasMutations,
    ProjectRule,
    ImportsHasNotCyclicalDepsRule,
    EmbeddedTypeHasLowLevel,
]


def test_all_rule_classes_importable():
    """All 16 rule classes must be importable from the rules facade."""
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
        assert isinstance(errors[0], ManifestRuleError)
        assert errors[0].rule == "all_usages_is_used"


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
                    items=[
                        ImportItemNode(type_name={"Foo"}, from_path="a"),
                        ImportItemNode(type_name={"Bar"}, from_path="b"),
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
                    items=[
                        ImportItemNode(type_name={"Foo"}, from_path="a"),
                        ImportItemNode(type_name={"Foo"}, from_path="b"),
                    ]
                )
            )
        )
        node = DocumentNode(root=root)
        rule = ImportHasNotDuplicate()
        errors = rule.check(node)
        assert len(errors) == 1
        assert isinstance(errors[0], ManifestRuleError)
        assert errors[0].rule == "import_has_not_duplicate"
        assert "Duplicate" in errors[0].message
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
                imports=ImportsNode(items=[ImportItemNode(type_name={"MyType"}, from_path="a")]),
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
                imports=ImportsNode(items=[ImportItemNode(type_name={"OtherType"}, from_path="a")]),
                annotations=AnnotationsNode(text="uses `Missing`", links=["Missing"]),
            )
        )
        node = DocumentNode(root=root)
        rule = AnnotationLinksExists()
        errors = rule.check(node)
        assert len(errors) == 1
        assert isinstance(errors[0], ManifestRuleError)
        assert errors[0].rule == "annotation_links_exists"
        assert "Missing" in errors[0].message

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
        assert "param" in errors[0].message

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
                imports=ImportsNode(items=[ImportItemNode(type_name={"MyType"}, from_path="a")]),
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
                imports=ImportsNode(items=[ImportItemNode(type_name={"Foo"}, from_path="a")]),
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
                imports=ImportsNode(items=[ImportItemNode(type_name={"Foo"}, from_path="a")]),
                usages=UsagesNode(items=[UsageItemNode(name="Foo")]),
            )
        )
        node = DocumentNode(root=root)
        rule = UsageLinksHasNotConflicts()
        errors = rule.check(node)
        assert len(errors) == 1
        assert isinstance(errors[0], ManifestRuleError)
        assert errors[0].rule == "usage_links_has_not_conflicts"
        assert "Foo" in errors[0].message

    def test_positive_conflict_resolved_through_alias(self):
        root = DocumentRoot(
            header=HeaderNode(
                imports=ImportsNode(items=[ImportItemNode(type_name={"Foo"}, from_path="a", alias="FooAlias")]),
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
        assert isinstance(errors[0], ManifestRuleError)
        assert errors[0].rule == "usage_links_has_not_conflicts"
        assert "MyEntity" in errors[0].message


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
                imports=ImportsNode(items=[ImportItemNode(type_name={"Foo"}, from_path="a")]),
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
                imports=ImportsNode(items=[ImportItemNode(type_name={"Foo"}, from_path="a")]),
            ),
            body=BodyNode(
                entities=[EntityTypeNode(name="Foo")],
            ),
        )
        node = DocumentNode(root=root)
        rule = EntitiesAndRoutinesHasNotConflicts()
        errors = rule.check(node)
        assert len(errors) == 1
        assert isinstance(errors[0], ManifestRuleError)
        assert errors[0].rule == "entities_and_routines_has_not_conflicts"
        assert "Foo" in errors[0].message

    def test_positive_conflict_resolved_through_alias(self):
        root = DocumentRoot(
            header=HeaderNode(
                imports=ImportsNode(items=[ImportItemNode(type_name={"Foo"}, from_path="a", alias="FooAlias")]),
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
                imports=ImportsNode(items=[ImportItemNode(type_name={"Bar"}, from_path="a")]),
            ),
            body=BodyNode(
                routines=[RoutineTypeNode(name="Bar")],
            ),
        )
        node = DocumentNode(root=root)
        rule = EntitiesAndRoutinesHasNotConflicts()
        errors = rule.check(node)
        assert len(errors) == 1
        assert isinstance(errors[0], ManifestRuleError)
        assert errors[0].rule == "entities_and_routines_has_not_conflicts"
        assert "Bar" in errors[0].message


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
                    EntityTypeNode(name="MyEntity", mutations=["OtherEntity"]),
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
                entities=[EntityTypeNode(name="MyEntity", mutations=["do_stuff"])],
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
                imports=ImportsNode(items=[ImportItemNode(type_name={"ImportedType"}, from_path="a")]),
            ),
            body=BodyNode(
                entities=[EntityTypeNode(name="MyEntity", mutations=["ImportedType"])],
            ),
        )
        node = DocumentNode(root=root)
        rule = MutationExists()
        errors = rule.check(node)
        assert errors == []

    def test_negative_mutation_not_found(self):
        root = DocumentRoot(
            header=HeaderNode(
                imports=ImportsNode(items=[ImportItemNode(type_name={"Foo"}, from_path="a")]),
            ),
            body=BodyNode(
                entities=[EntityTypeNode(name="MyEntity", mutations=["NonExistent"])],
                routines=[RoutineTypeNode(name="some_func")],
            ),
        )
        node = DocumentNode(root=root)
        rule = MutationExists()
        errors = rule.check(node)
        assert len(errors) == 1
        assert isinstance(errors[0], ManifestRuleError)
        assert errors[0].rule == "mutation_exists"
        assert "NonExistent" in errors[0].message


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
                entities=[EntityTypeNode(name="MyEntity", mutations=["OtherEntity"])],
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
                entities=[EntityTypeNode(name="MyEntity", mutations=["MyEntity"])],
            ),
        )
        node = DocumentNode(root=root)
        rule = MutationIsValid()
        errors = rule.check(node)
        assert len(errors) == 1
        assert isinstance(errors[0], ManifestRuleError)
        assert errors[0].rule == "mutation_is_valid"
        assert "MyEntity" in errors[0].message


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
        assert isinstance(errors[0], ManifestRuleError)
        assert errors[0].rule == "return_type_has_link"

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
                entities=[EntityTypeNode(name="MyEntity", embedded=False, mutations=["MutA"])],
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
                entities=[EntityTypeNode(name="MyEntity", embedded=True, mutations=["MutA"])],
            ),
        )
        node = DocumentNode(root=root)
        rule = EmbeddedEntityCanNotHasMutations()
        errors = rule.check(node)
        assert len(errors) == 1
        assert isinstance(errors[0], ManifestRuleError)
        assert errors[0].rule == "embedded_entity_can_not_has_mutations"
        assert "MyEntity" in errors[0].message

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
# 19. EmbeddedTypeHasLowLevel (ProjectRule)
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
        assert isinstance(errors[0], ProjectRuleError)
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
        assert isinstance(errors[0], ProjectRuleError)
        assert errors[0].rule == "embedded_type_has_low_level"
