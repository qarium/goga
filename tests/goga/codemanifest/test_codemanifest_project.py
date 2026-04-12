"""Contract tests for the codemanifest root package — Project class."""

import os
from pathlib import Path

import pytest
from goga.codemanifest import Project
from goga.codemanifest.errors import ManifestRuleError
from goga.codemanifest.nodes import DocumentRoot

# ---------------------------------------------------------------------------
# 1. Facade availability
# ---------------------------------------------------------------------------


class TestFacadeAvailability:
    def test_import_project_from_codemanifest(self):
        from goga.codemanifest import Project as Reimported  # noqa: PLC0415

        assert Reimported is Project


# ---------------------------------------------------------------------------
# 2. Initial state
# ---------------------------------------------------------------------------


class TestInitialState:
    def test_path_property(self):
        p = Project("/some/path")
        assert p.path == "/some/path"

    def test_tree_initially_empty(self):
        p = Project("/some/path")
        assert p.tree == []

    def test_errors_initially_empty(self):
        p = Project("/some/path")
        assert p.errors == []


# ---------------------------------------------------------------------------
# 3. load() with empty directory
# ---------------------------------------------------------------------------


class TestLoadEmptyDirectory:
    def test_empty_dir_no_tree_no_errors(self, tmp_path):
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        p = Project(str(empty_dir))
        p.load()
        assert p.tree == []
        assert p.errors == []


# ---------------------------------------------------------------------------
# 4. load() with single CODEMANIFEST
# ---------------------------------------------------------------------------


VALID_SINGLE_DOC = """\
Imports:
  - Types:
      - Node
    From: goga/codemanifest/nodes

---
"MyClass()":
  location: myclass.py
  annotations: |
    A test class
  methods:
    "do_work() -> result:str": |
      Does work

---
Author: Test
CreatedAt: 11/04/26
Description: Test
"""


class TestLoadSingleDocument:
    def test_tree_has_one_root(self, tmp_path):
        doc_dir = tmp_path / "myproject"
        doc_dir.mkdir()
        (doc_dir / "CODEMANIFEST").write_text(VALID_SINGLE_DOC)

        p = Project(str(doc_dir))
        p.load()
        assert len(p.tree) == 1
        assert p.tree[0].path == str(doc_dir)


# ---------------------------------------------------------------------------
# 5. load() with nested CODEMANIFEST files (3+ levels)
# ---------------------------------------------------------------------------


class TestLoadNestedDocuments:
    def test_three_level_hierarchy(self, tmp_path):
        root_dir = tmp_path / "level1"
        root_dir.mkdir()
        (root_dir / "CODEMANIFEST").write_text(VALID_SINGLE_DOC)

        level2 = root_dir / "level2"
        level2.mkdir()
        (level2 / "CODEMANIFEST").write_text(VALID_SINGLE_DOC)

        level3 = level2 / "level3"
        level3.mkdir()
        (level3 / "CODEMANIFEST").write_text(VALID_SINGLE_DOC)

        p = Project(str(root_dir))
        p.load()

        # Only one top-level document
        assert len(p.tree) == 1

        root_doc = p.tree[0]
        assert root_doc.path == str(root_dir)

        # level2 is child of level1
        assert len(root_doc.children) == 1
        child2 = root_doc.children[0]
        assert child2.path == str(level2)

        # level3 is child of level2
        assert len(child2.children) == 1
        child3 = child2.children[0]
        assert child3.path == str(level3)

        # level3 has no children
        assert len(child3.children) == 0

    def test_multiple_children_at_same_level(self, tmp_path):
        root_dir = tmp_path / "root"
        root_dir.mkdir()
        (root_dir / "CODEMANIFEST").write_text(VALID_SINGLE_DOC)

        child_a = root_dir / "child_a"
        child_a.mkdir()
        (child_a / "CODEMANIFEST").write_text(VALID_SINGLE_DOC)

        child_b = root_dir / "child_b"
        child_b.mkdir()
        (child_b / "CODEMANIFEST").write_text(VALID_SINGLE_DOC)

        p = Project(str(root_dir))
        p.load()

        assert len(p.tree) == 1
        assert len(p.tree[0].children) == 2


# ---------------------------------------------------------------------------
# 6. load() detects document-level rule violations
# ---------------------------------------------------------------------------


EMPTY_IMPORTS_DOC = """\
Imports: []

---
"MyClass()":
  location: myclass.py
  annotations: |
    A test class

---
Author: Test
CreatedAt: 11/04/26
Description: Test
"""


class TestDocumentRuleViolations:
    def test_empty_imports_produces_manifest_rule_error(self, tmp_path):
        doc_dir = tmp_path / "badproject"
        doc_dir.mkdir()
        (doc_dir / "CODEMANIFEST").write_text(EMPTY_IMPORTS_DOC)

        p = Project(str(doc_dir))
        p.load()

        manifest_errors = [e for e in p.errors if isinstance(e, ManifestRuleError)]
        assert len(manifest_errors) > 0

    def test_empty_imports_rule_name(self, tmp_path):
        doc_dir = tmp_path / "badproject"
        doc_dir.mkdir()
        (doc_dir / "CODEMANIFEST").write_text(EMPTY_IMPORTS_DOC)

        p = Project(str(doc_dir))
        p.load()

        rule_names = [e.rule for e in p.errors if isinstance(e, ManifestRuleError)]
        assert "imports_can_not_be_empty" in rule_names


# ---------------------------------------------------------------------------
# 7. load() detects project-level rule violations
# ---------------------------------------------------------------------------


UNUSED_USAGE_DOC = """\
Imports:
  - Types:
      - Node
    From: goga/codemanifest/nodes
Usages:
  NEVER_REFERENCED_ANYWHERE: some value

---
"MyClass()":
  location: myclass.py
  annotations: |
    A test class without referencing the usage

---
Author: Test
CreatedAt: 11/04/26
Description: Test
"""


class TestProjectRuleViolations:
    def test_unused_usage_produces_manifest_rule_error(self, tmp_path):
        doc_dir = tmp_path / "unusedusage"
        doc_dir.mkdir()
        (doc_dir / "CODEMANIFEST").write_text(UNUSED_USAGE_DOC)

        p = Project(str(doc_dir))
        p.load()

        manifest_errors = [e for e in p.errors if isinstance(e, ManifestRuleError)]
        usage_errors = [e for e in manifest_errors if e.rule == "all_usages_is_used"]
        assert len(usage_errors) > 0

    def test_unused_usage_rule_name(self, tmp_path):
        doc_dir = tmp_path / "unusedusage"
        doc_dir.mkdir()
        (doc_dir / "CODEMANIFEST").write_text(UNUSED_USAGE_DOC)

        p = Project(str(doc_dir))
        p.load()

        rule_names = [e.rule for e in p.errors if isinstance(e, ManifestRuleError)]
        assert "all_usages_is_used" in rule_names


# ---------------------------------------------------------------------------
# 8. load() accumulates errors from both visitor and analyzer
# ---------------------------------------------------------------------------


EMPTY_IMPORTS_AND_UNUSED_USAGE_DOC = """\
Imports: []
Usages:
  NEVER_USED: value

---
"MyClass()":
  location: myclass.py
  annotations: |
    A test class

---
Author: Test
CreatedAt: 11/04/26
Description: Test
"""


class TestAccumulatedErrors:
    def test_both_manifest_rule_errors_from_different_rules(self, tmp_path):
        doc_dir = tmp_path / "accum"
        doc_dir.mkdir()
        (doc_dir / "CODEMANIFEST").write_text(EMPTY_IMPORTS_AND_UNUSED_USAGE_DOC)

        p = Project(str(doc_dir))
        p.load()

        manifest_errors = [e for e in p.errors if isinstance(e, ManifestRuleError)]
        rule_names = {e.rule for e in manifest_errors}

        assert len(manifest_errors) >= 2, "Expected at least two ManifestRuleError"
        assert "imports_can_not_be_empty" in rule_names
        assert "all_usages_is_used" in rule_names

    def test_errors_are_all_manifest_rule_errors(self, tmp_path):
        doc_dir = tmp_path / "accum2"
        doc_dir.mkdir()
        (doc_dir / "CODEMANIFEST").write_text(EMPTY_IMPORTS_AND_UNUSED_USAGE_DOC)

        p = Project(str(doc_dir))
        p.load()

        # Both errors are now ManifestRuleError
        for e in p.errors:
            assert isinstance(e, ManifestRuleError)


# ---------------------------------------------------------------------------
# 9. load() with intermediate directory without CODEMANIFEST
# ---------------------------------------------------------------------------


class TestIntermediateDirectoryWithoutCodemanifest:
    def test_child_found_through_empty_intermediate_dir(self, tmp_path):
        """Parent-child wiring works when an intermediate dir has no CODEMANIFEST."""
        root_dir = tmp_path / "root"
        root_dir.mkdir()
        (root_dir / "CODEMANIFEST").write_text(VALID_SINGLE_DOC)

        # Intermediate dir — no CODEMANIFEST
        intermediate = root_dir / "subpkg"
        intermediate.mkdir()

        # Nested child — has CODEMANIFEST
        child_dir = intermediate / "child"
        child_dir.mkdir()
        (child_dir / "CODEMANIFEST").write_text(VALID_SINGLE_DOC)

        p = Project(str(root_dir))
        p.load()

        # root is top-level
        assert len(p.tree) == 1
        root_doc = p.tree[0]

        # child is a direct child of root (intermediate skipped)
        assert len(root_doc.children) == 1
        child_doc = root_doc.children[0]
        assert child_doc.path == str(child_dir)

    def test_load_clears_previous_state(self, tmp_path):
        """Calling load() twice resets tree and errors."""
        doc_dir = tmp_path / "clearable"
        doc_dir.mkdir()
        (doc_dir / "CODEMANIFEST").write_text(VALID_SINGLE_DOC)

        p = Project(str(doc_dir))
        p.load()
        assert len(p.tree) == 1

        # Remove CODEMANIFEST, load again
        (doc_dir / "CODEMANIFEST").unlink()
        p.load()
        assert p.tree == []
        assert p.errors == []


# ---------------------------------------------------------------------------
# 10. codemanifest() lookup by path
# ---------------------------------------------------------------------------


class TestCodemanifestLookup:
    """Contract tests for the Project.codemanifest(path) method."""

    # -- helpers --

    @staticmethod
    def _make_three_level_tree(tmp_path):
        """Create a 3-level CODEMANIFEST hierarchy and return (root_dir, level2, level3)."""
        root_dir = tmp_path / "level1"
        root_dir.mkdir()
        (root_dir / "CODEMANIFEST").write_text(VALID_SINGLE_DOC)

        level2 = root_dir / "level2"
        level2.mkdir()
        (level2 / "CODEMANIFEST").write_text(VALID_SINGLE_DOC)

        level3 = level2 / "level3"
        level3.mkdir()
        (level3 / "CODEMANIFEST").write_text(VALID_SINGLE_DOC)

        return root_dir, level2, level3

    # -- 1. Facade availability --

    def test_project_has_codemanifest_method(self):
        """Project exposes a codemanifest method."""
        p = Project("/tmp")
        assert hasattr(p, "codemanifest")
        assert callable(p.codemanifest)

    # -- 2. API shape --

    def test_codemanifest_accepts_str_returns_document_root(self, tmp_path):
        """codemanifest(path) takes a str and returns a DocumentRoot."""
        root_dir, _, _ = self._make_three_level_tree(tmp_path)
        p = Project(str(root_dir))
        p.load()

        result = p.codemanifest(str(root_dir))
        assert isinstance(result, DocumentRoot)

    # -- 3. Positive — relative path with dot --

    def test_relative_path_with_dot(self, tmp_path):
        """codemanifest('./relative') resolves and finds the document."""
        root_dir, _level2, level3 = self._make_three_level_tree(tmp_path)
        p = Project(str(root_dir))
        p.load()

        # Build "./" + relative from root_dir, and resolve from root_dir as cwd
        relative = os.path.relpath(str(level3), str(root_dir))
        dotted_path = "./" + relative

        original_cwd = Path.cwd()
        try:
            os.chdir(str(root_dir))
            doc = p.codemanifest(dotted_path)
        finally:
            os.chdir(str(original_cwd))

        assert doc.path == str(Path(str(level3)).resolve())

    # -- 4. Positive — relative path without dot --

    def test_relative_path_without_dot(self, tmp_path):
        """codemanifest('path/path') resolves and finds the document."""
        root_dir, level2, _level3 = self._make_three_level_tree(tmp_path)
        p = Project(str(root_dir))
        p.load()

        relative = os.path.relpath(str(level2), str(root_dir))

        original_cwd = Path.cwd()
        try:
            os.chdir(str(root_dir))
            doc = p.codemanifest(relative)
        finally:
            os.chdir(str(original_cwd))

        assert doc.path == str(Path(str(level2)).resolve())

    # -- 5. Positive — absolute path --

    def test_absolute_path(self, tmp_path):
        """codemanifest(absolute_path) returns the correct document."""
        root_dir, _level2, level3 = self._make_three_level_tree(tmp_path)
        p = Project(str(root_dir))
        p.load()

        doc = p.codemanifest(str(level3))
        assert doc.path == str(level3)

    # -- 6. Negative — nonexistent path --

    def test_nonexistent_path_raises_key_error(self, tmp_path):
        """codemanifest('/nonexistent/path') raises KeyError."""
        root_dir, _, _ = self._make_three_level_tree(tmp_path)
        p = Project(str(root_dir))
        p.load()

        with pytest.raises(KeyError, match="Document not found for path"):
            p.codemanifest("/nonexistent/path")

    # -- 7. Negative — call before load() --

    def test_call_before_load_raises_key_error(self):
        """codemanifest() before load() raises KeyError (index is empty)."""
        p = Project("/some/path")
        with pytest.raises(KeyError, match="Document not found for path"):
            p.codemanifest("any/path")

    # -- 8. Edge — path normalization --

    def test_path_normalization(self, tmp_path):
        """codemanifest('path/./subpath/../subpath') resolves via normalization."""
        root_dir, _level2, level3 = self._make_three_level_tree(tmp_path)
        p = Project(str(root_dir))
        p.load()

        # Construct a path with . and .. segments
        tricky_path = str(level3) + "/../level3"
        doc = p.codemanifest(tricky_path)
        assert doc.path == str(Path(str(level3)).resolve())

    # -- 9. Edge — load() rebuilds index --

    def test_load_rebuilds_index(self, tmp_path):
        """Calling load() twice picks up documents from the second load."""
        root_dir = tmp_path / "rebuild_root"
        root_dir.mkdir()
        (root_dir / "CODEMANIFEST").write_text(VALID_SINGLE_DOC)

        new_dir = tmp_path / "rebuild_new"
        new_dir.mkdir()
        # No CODEMANIFEST yet

        p = Project(str(tmp_path))
        p.load()

        # root_dir is findable, new_dir is not
        doc = p.codemanifest(str(root_dir))
        assert doc.path == str(Path(str(root_dir)).resolve())

        with pytest.raises(KeyError):
            p.codemanifest(str(new_dir))

        # Now add CODEMANIFEST to new_dir and reload
        (new_dir / "CODEMANIFEST").write_text(VALID_SINGLE_DOC)
        p.load()

        # Both should be findable now
        doc_root = p.codemanifest(str(root_dir))
        assert doc_root.path == str(Path(str(root_dir)).resolve())

        doc_new = p.codemanifest(str(new_dir))
        assert doc_new.path == str(Path(str(new_dir)).resolve())


# ---------------------------------------------------------------------------
# 11. load() detects ImportHasNotDuplicate violations
# ---------------------------------------------------------------------------


DUPLICATE_IMPORT_DOC = """\
Imports:
  - Types:
      - Node
    From: goga/codemanifest/nodes
  - Types:
      - Node
    From: goga/codemanifest/other

---
"MyClass()":
  location: myclass.py
  annotations: |
    A test class

---
Author: Test
CreatedAt: 11/04/26
Description: Test
"""


class TestImportHasNotDuplicateViolation:
    def test_duplicate_import_produces_manifest_rule_error(self, tmp_path):
        doc_dir = tmp_path / "dupimport"
        doc_dir.mkdir()
        (doc_dir / "CODEMANIFEST").write_text(DUPLICATE_IMPORT_DOC)

        p = Project(str(doc_dir))
        p.load()

        rule_names = [e.rule for e in p.errors if isinstance(e, ManifestRuleError)]
        assert "import_has_not_duplicate" in rule_names


# ---------------------------------------------------------------------------
# 12. load() detects AnnotationLinksExists violations
# ---------------------------------------------------------------------------


BROKEN_LINK_DOC = """\
Imports:
  - Types:
      - Node
    From: goga/codemanifest/nodes

---
"MyClass()":
  location: myclass.py
  annotations: |
    Uses `NonExistent` link

---
Author: Test
CreatedAt: 11/04/26
Description: Test
"""


class TestAnnotationLinksExistsViolation:
    def test_broken_annotation_link_produces_manifest_rule_error(self, tmp_path):
        doc_dir = tmp_path / "brokenlink"
        doc_dir.mkdir()
        (doc_dir / "CODEMANIFEST").write_text(BROKEN_LINK_DOC)

        p = Project(str(doc_dir))
        p.load()

        rule_names = [e.rule for e in p.errors if isinstance(e, ManifestRuleError)]
        assert "annotation_links_exists" in rule_names


# ---------------------------------------------------------------------------
# 13. load() detects UsageLinksHasNotConflicts violations
# ---------------------------------------------------------------------------


USAGE_CONFLICT_DOC = """\
Imports:
  - Types:
      - Node
    From: goga/codemanifest/nodes
Usages:
  Node: some value

---
"MyClass()":
  location: myclass.py
  annotations: |
    Uses `Node`

---
Author: Test
CreatedAt: 11/04/26
Description: Test
"""


class TestUsageLinksHasNotConflictsViolation:
    def test_usage_conflicts_with_import_produces_manifest_rule_error(self, tmp_path):
        doc_dir = tmp_path / "usageconflict"
        doc_dir.mkdir()
        (doc_dir / "CODEMANIFEST").write_text(USAGE_CONFLICT_DOC)

        p = Project(str(doc_dir))
        p.load()

        rule_names = [e.rule for e in p.errors if isinstance(e, ManifestRuleError)]
        assert "usage_links_has_not_conflicts" in rule_names


# ---------------------------------------------------------------------------
# 14. load() detects EntitiesAndRoutinesHasNotConflicts violations
# ---------------------------------------------------------------------------


ENTITY_CONFLICT_DOC = """\
Imports:
  - Types:
      - Node
    From: goga/codemanifest/nodes

---
"Node()":
  location: node.py
  annotations: |
    Conflicts with import

---
Author: Test
CreatedAt: 11/04/26
Description: Test
"""


class TestEntitiesAndRoutinesHasNotConflictsViolation:
    def test_entity_name_conflicts_with_import_produces_manifest_rule_error(self, tmp_path):
        doc_dir = tmp_path / "entityconflict"
        doc_dir.mkdir()
        (doc_dir / "CODEMANIFEST").write_text(ENTITY_CONFLICT_DOC)

        p = Project(str(doc_dir))
        p.load()

        rule_names = [e.rule for e in p.errors if isinstance(e, ManifestRuleError)]
        assert "entities_and_routines_has_not_conflicts" in rule_names


# ---------------------------------------------------------------------------
# 15. load() detects MutationExists violations
# ---------------------------------------------------------------------------


INVALID_MUTATION_DOC = """\
Imports:
  - Types:
      - Node
    From: goga/codemanifest/nodes

---
"FakeMutation::MyClass()":
  location: myclass.py
  annotations: |
    Has a non-existent mutation

---
Author: Test
CreatedAt: 11/04/26
Description: Test
"""


class TestMutationExistsViolation:
    def test_nonexistent_mutation_produces_manifest_rule_error(self, tmp_path):
        doc_dir = tmp_path / "badmutation"
        doc_dir.mkdir()
        (doc_dir / "CODEMANIFEST").write_text(INVALID_MUTATION_DOC)

        p = Project(str(doc_dir))
        p.load()

        rule_names = [e.rule for e in p.errors if isinstance(e, ManifestRuleError)]
        assert "mutation_exists" in rule_names


# ---------------------------------------------------------------------------
# 16. load() detects MutationIsValid violations
# ---------------------------------------------------------------------------


SELF_MUTATION_DOC = """\
Imports:
  - Types:
      - Node
    From: goga/codemanifest/nodes

---
"MyClass::MyClass()":
  location: myclass.py
  annotations: |
    Self-mutation is invalid

---
Author: Test
CreatedAt: 11/04/26
Description: Test
"""


class TestMutationIsValidViolation:
    def test_self_mutation_produces_manifest_rule_error(self, tmp_path):
        doc_dir = tmp_path / "selfmutation"
        doc_dir.mkdir()
        (doc_dir / "CODEMANIFEST").write_text(SELF_MUTATION_DOC)

        p = Project(str(doc_dir))
        p.load()

        rule_names = [e.rule for e in p.errors if isinstance(e, ManifestRuleError)]
        assert "mutation_is_valid" in rule_names


# ---------------------------------------------------------------------------
# 17. load() detects ReturnTypeHasLink violations
# ---------------------------------------------------------------------------


MISSING_RETURN_LABEL_DOC = """\
Imports:
  - Types:
      - Node
    From: goga/codemanifest/nodes

---
"do_work() -> str":
  location: work.py
  annotations: |
    Missing label on return type

---
Author: Test
CreatedAt: 11/04/26
Description: Test
"""


class TestReturnTypeHasLinkViolation:
    def test_missing_return_label_produces_manifest_rule_error(self, tmp_path):
        doc_dir = tmp_path / "noreturnlabel"
        doc_dir.mkdir()
        (doc_dir / "CODEMANIFEST").write_text(MISSING_RETURN_LABEL_DOC)

        p = Project(str(doc_dir))
        p.load()

        rule_names = [e.rule for e in p.errors if isinstance(e, ManifestRuleError)]
        assert "return_type_has_link" in rule_names


# ---------------------------------------------------------------------------
# 18. load() detects EmbeddedEntityCanNotHasMutations violations
# ---------------------------------------------------------------------------


EMBEDDED_WITH_MUTATION_DOC = """\
Imports:
  - Types:
      - Node
    From: goga/codemanifest/nodes

---
"->MutA::EmbeddedClass()":
  location: embedded.py
  annotations: |
    Embedded entity with mutation
  methods:
    "do_work() -> result:str": |
      Does work

---
Author: Test
CreatedAt: 11/04/26
Description: Test
"""


class TestEmbeddedEntityCanNotHasMutationsViolation:
    def test_embedded_with_mutation_produces_manifest_rule_error(self, tmp_path):
        doc_dir = tmp_path / "embeddedmut"
        doc_dir.mkdir()
        (doc_dir / "CODEMANIFEST").write_text(EMBEDDED_WITH_MUTATION_DOC)

        p = Project(str(doc_dir))
        p.load()

        rule_names = [e.rule for e in p.errors if isinstance(e, ManifestRuleError)]
        assert "embedded_entity_can_not_has_mutations" in rule_names


# ---------------------------------------------------------------------------
# 19. Deferred routing: embedded type reclassified by original definition
# ---------------------------------------------------------------------------


class TestEmbeddedReclassification:
    """Embedded types are reclassified based on the original type definition."""

    def test_embedded_routine_reclassified_from_entity(self, tmp_path):
        """->MyRoutine pointing to a routine gets reclassified from entity to routine."""

        # Parent doc defines a routine
        parent_dir = tmp_path / "parent"
        parent_dir.mkdir()
        parent_doc = """\
Imports:
  - Types:
      - Node
    From: goga/codemanifest/nodes

---
"helper(x: int) -> result:int": |
  A helper routine

---
Author: Test
CreatedAt: 11/04/26
Description: Test
"""
        (parent_dir / "CODEMANIFEST").write_text(parent_doc)

        # Child doc embeds the routine via -> prefix
        child_dir = parent_dir / "child"
        child_dir.mkdir()
        child_doc = """\
Imports:
  - Types:
      - helper
    From: ..

---
"->helper": {}

---
Author: Test
CreatedAt: 11/04/26
Description: Test
"""
        (child_dir / "CODEMANIFEST").write_text(child_doc)

        p = Project(str(parent_dir))
        p.load()

        # Find the child document
        child_root = p.codemanifest(str(child_dir))

        # helper should be reclassified as a routine, not entity
        entity_names = [e.name for e in child_root.body.entities]
        routine_names = [r.name for r in child_root.body.routines]
        assert "helper" not in entity_names
        assert "helper" in routine_names
        routine = next(r for r in child_root.body.routines if r.name == "helper")
        assert routine.embedded is True

    def test_embedded_entity_stays_entity(self, tmp_path):
        """->MyEntity pointing to an entity stays as entity."""
        parent_dir = tmp_path / "parent"
        parent_dir.mkdir()
        parent_doc = """\
Imports:
  - Types:
      - Node
    From: goga/codemanifest/nodes

---
"MyEntity":
  location: entity.py
  annotations: |
    An entity
  methods:
    "run() -> void:null": |
      Runs

---
Author: Test
CreatedAt: 11/04/26
Description: Test
"""
        (parent_dir / "CODEMANIFEST").write_text(parent_doc)

        child_dir = parent_dir / "child"
        child_dir.mkdir()
        child_doc = """\
Imports:
  - Types:
      - MyEntity
    From: ..

---
"->MyEntity": {}

---
Author: Test
CreatedAt: 11/04/26
Description: Test
"""
        (child_dir / "CODEMANIFEST").write_text(child_doc)

        p = Project(str(parent_dir))
        p.load()

        child_root = p.codemanifest(str(child_dir))

        # MyEntity should remain as entity
        entity_names = [e.name for e in child_root.body.entities]
        assert "MyEntity" in entity_names
        entity = next(e for e in child_root.body.entities if e.name == "MyEntity")
        assert entity.embedded is True

    def test_embeddings_populated_for_entity(self, tmp_path):
        """Factory stores (type_name, from_path) in doc.embeddings for embedded entities with matching imports."""
        parent_dir = tmp_path / "parent"
        parent_dir.mkdir()
        parent_doc = """\
Imports:
  - Types:
      - Node
    From: goga/codemanifest/nodes

---
"MyEntity":
  location: entity.py
  annotations: |
    An entity

---
Author: Test
CreatedAt: 11/04/26
Description: Test
"""
        (parent_dir / "CODEMANIFEST").write_text(parent_doc)

        child_dir = parent_dir / "child"
        child_dir.mkdir()
        child_doc = """\
Imports:
  - Types:
      - MyEntity
    From: ..

---
"->MyEntity": {}

---
Author: Test
CreatedAt: 11/04/26
Description: Test
"""
        (child_dir / "CODEMANIFEST").write_text(child_doc)

        p = Project(str(parent_dir))
        p.load()

        child_root = p.codemanifest(str(child_dir))

        # embeddings list should contain (MyEntity, ..) tuple
        embedding_names = [name for name, _ in child_root.embeddings]
        assert "MyEntity" in embedding_names
        from_paths = [fp for name, fp in child_root.embeddings if name == "MyEntity"]
        assert from_paths[0] == ".."

    def test_embeddings_populated_for_routine(self, tmp_path):
        """Factory stores (type_name, from_path) in doc.embeddings for embedded routines with matching imports."""
        parent_dir = tmp_path / "parent"
        parent_dir.mkdir()
        parent_doc = """\
Imports:
  - Types:
      - Node
    From: goga/codemanifest/nodes

---
"helper(x: int) -> result:int": |
  A helper routine

---
Author: Test
CreatedAt: 11/04/26
Description: Test
"""
        (parent_dir / "CODEMANIFEST").write_text(parent_doc)

        child_dir = parent_dir / "child"
        child_dir.mkdir()
        child_doc = """\
Imports:
  - Types:
      - helper
    From: ..

---
"->helper": {}

---
Author: Test
CreatedAt: 11/04/26
Description: Test
"""
        (child_dir / "CODEMANIFEST").write_text(child_doc)

        p = Project(str(parent_dir))
        p.load()

        child_root = p.codemanifest(str(child_dir))

        # embeddings list should contain (helper, ..) tuple
        embedding_names = [name for name, _ in child_root.embeddings]
        assert "helper" in embedding_names
        from_paths = [fp for name, fp in child_root.embeddings if name == "helper"]
        assert from_paths[0] == ".."

    def test_no_embeddings_without_embedded_types(self, tmp_path):
        """Document without ->prefix types has empty embeddings list."""
        doc_dir = tmp_path / "solo"
        doc_dir.mkdir()
        (doc_dir / "CODEMANIFEST").write_text(VALID_SINGLE_DOC)

        p = Project(str(doc_dir))
        p.load()

        root = p.codemanifest(str(doc_dir))
        assert root.embeddings == []

    def test_embedded_entity_has_original_properties_and_methods(self, tmp_path):
        """Embedded entity copy preserves properties and methods from original definition."""
        parent_dir = tmp_path / "parent"
        parent_dir.mkdir()
        parent_doc = """\
Imports:
  - Types:
      - Node
    From: goga/codemanifest/nodes

---
"MyEntity":
  location: entity.py
  annotations: |
    An entity with props and methods
  properties:
    "count -> int": counter value
  methods:
    "run() -> void:null": |
      Runs the entity

---
Author: Test
CreatedAt: 11/04/26
Description: Test
"""
        (parent_dir / "CODEMANIFEST").write_text(parent_doc)

        child_dir = parent_dir / "child"
        child_dir.mkdir()
        child_doc = """\
Imports:
  - Types:
      - MyEntity
    From: ..

---
"->MyEntity": {}

---
Author: Test
CreatedAt: 11/04/26
Description: Test
"""
        (child_dir / "CODEMANIFEST").write_text(child_doc)

        p = Project(str(parent_dir))
        p.load()

        child_root = p.codemanifest(str(child_dir))

        embedded_entities = [e for e in child_root.body.entities if e.name == "MyEntity"]
        assert len(embedded_entities) == 1
        ent = embedded_entities[0]
        assert ent.embedded is True
        assert len(ent.properties) == 1
        assert ent.properties[0].name == "count"
        assert len(ent.methods) == 1
        assert ent.methods[0].name == "run"

    def test_embedded_routine_has_original_signature(self, tmp_path):
        """Embedded routine copy preserves signature from original definition."""
        parent_dir = tmp_path / "parent"
        parent_dir.mkdir()
        parent_doc = """\
Imports:
  - Types:
      - Node
    From: goga/codemanifest/nodes

---
"compute(x: int, y: int) -> result:int": |
  A computation routine

---
Author: Test
CreatedAt: 11/04/26
Description: Test
"""
        (parent_dir / "CODEMANIFEST").write_text(parent_doc)

        child_dir = parent_dir / "child"
        child_dir.mkdir()
        child_doc = """\
Imports:
  - Types:
      - compute
    From: ..

---
"->compute": {}

---
Author: Test
CreatedAt: 11/04/26
Description: Test
"""
        (child_dir / "CODEMANIFEST").write_text(child_doc)

        p = Project(str(parent_dir))
        p.load()

        child_root = p.codemanifest(str(child_dir))

        embedded_routines = [r for r in child_root.body.routines if r.name == "compute"]
        assert len(embedded_routines) == 1
        routine = embedded_routines[0]
        assert routine.embedded is True
        assert routine.signature == "(x: int, y: int) -> result:int"

    def test_multiple_embedded_types_from_same_source(self, tmp_path):
        """Multiple embedded types from the same parent document are all reclassified correctly."""
        parent_dir = tmp_path / "parent"
        parent_dir.mkdir()
        parent_doc = """\
Imports:
  - Types:
      - Node
    From: goga/codemanifest/nodes

---
"MyEntity":
  location: entity.py
  annotations: |
    An entity
  methods:
    "run() -> void:null": |
      Runs
"helper(x: int) -> result:int": |
  A helper routine

---
Author: Test
CreatedAt: 11/04/26
Description: Test
"""
        (parent_dir / "CODEMANIFEST").write_text(parent_doc)

        child_dir = parent_dir / "child"
        child_dir.mkdir()
        child_doc = """\
Imports:
  - Types:
      - MyEntity
      - helper
    From: ..

---
"->MyEntity": {}
"->helper": {}

---
Author: Test
CreatedAt: 11/04/26
Description: Test
"""
        (child_dir / "CODEMANIFEST").write_text(child_doc)

        p = Project(str(parent_dir))
        p.load()

        child_root = p.codemanifest(str(child_dir))

        # Both should be in embeddings
        embedding_names = {name for name, _ in child_root.embeddings}
        assert "MyEntity" in embedding_names
        assert "helper" in embedding_names

        # MyEntity should be in entities with embedded=True
        entity_names = [e.name for e in child_root.body.entities]
        assert "MyEntity" in entity_names
        ent = next(e for e in child_root.body.entities if e.name == "MyEntity")
        assert ent.embedded is True

        # helper should be in routines with embedded=True
        routine_names = [r.name for r in child_root.body.routines]
        assert "helper" in routine_names
        rout = next(r for r in child_root.body.routines if r.name == "helper")
        assert rout.embedded is True

    def test_three_level_embedded_chain(self, tmp_path):
        """Embedded type defined at level 1 is available at level 3 via reclassification."""
        # Level 1: defines the original entity
        level1_dir = tmp_path / "level1"
        level1_dir.mkdir()
        level1_doc = """\
Imports:
  - Types:
      - Node
    From: goga/codemanifest/nodes

---
"BaseEntity":
  location: base.py
  annotations: |
    Base entity
  methods:
    "run() -> void:null": |
      Runs

---
Author: Test
CreatedAt: 11/04/26
Description: Test
"""
        (level1_dir / "CODEMANIFEST").write_text(level1_doc)

        # Level 2: embeds BaseEntity from level 1
        level2_dir = level1_dir / "level2"
        level2_dir.mkdir()
        level2_doc = """\
Imports:
  - Types:
      - BaseEntity
    From: ..

---
"->BaseEntity": {}

---
Author: Test
CreatedAt: 11/04/26
Description: Test
"""
        (level2_dir / "CODEMANIFEST").write_text(level2_doc)

        # Level 3: embeds BaseEntity from level 2
        level3_dir = level2_dir / "level3"
        level3_dir.mkdir()
        level3_doc = """\
Imports:
  - Types:
      - BaseEntity
    From: ..

---
"->BaseEntity": {}

---
Author: Test
CreatedAt: 11/04/26
Description: Test
"""
        (level3_dir / "CODEMANIFEST").write_text(level3_doc)

        p = Project(str(level1_dir))
        p.load()

        # Level 2 should have BaseEntity embedded
        level2_root = p.codemanifest(str(level2_dir))
        l2_entities = [e for e in level2_root.body.entities if e.name == "BaseEntity"]
        assert len(l2_entities) == 1
        assert l2_entities[0].embedded is True

        # Level 3 should also have BaseEntity embedded
        level3_root = p.codemanifest(str(level3_dir))
        l3_entities = [e for e in level3_root.body.entities if e.name == "BaseEntity"]
        assert len(l3_entities) == 1
        assert l3_entities[0].embedded is True

    def test_parent_does_not_get_child_embedded_types(self, tmp_path):
        """Embedding is one-directional: parent does not receive child's embedded types."""
        parent_dir = tmp_path / "parent"
        parent_dir.mkdir()
        parent_doc = """\
Imports:
  - Types:
      - Node
    From: goga/codemanifest/nodes

---
"MyEntity":
  location: entity.py
  annotations: |
    An entity
  methods:
    "run() -> void:null": |
      Runs

---
Author: Test
CreatedAt: 11/04/26
Description: Test
"""
        (parent_dir / "CODEMANIFEST").write_text(parent_doc)

        child_dir = parent_dir / "child"
        child_dir.mkdir()
        child_doc = """\
Imports:
  - Types:
      - MyEntity
    From: ..

---
"->MyEntity": {}

---
Author: Test
CreatedAt: 11/04/26
Description: Test
"""
        (child_dir / "CODEMANIFEST").write_text(child_doc)

        p = Project(str(parent_dir))
        p.load()

        parent_root = p.codemanifest(str(parent_dir))

        # Parent has MyEntity as non-embedded (original definition)
        parent_entities = [e for e in parent_root.body.entities if e.name == "MyEntity"]
        assert len(parent_entities) == 1
        assert parent_entities[0].embedded is False

        # Parent has no embeddings (it doesn't embed anything)
        assert parent_root.embeddings == []
