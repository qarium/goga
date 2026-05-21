"""Contract tests for the codemanifest root package — AST class."""

import os
from pathlib import Path

import pytest
from goga.ast import AST
from goga.ast.errors import DocumentNotFoundError, DocumentRuleError
from goga.ast.nodes import DocumentRoot

# ---------------------------------------------------------------------------
# 1. Facade availability
# ---------------------------------------------------------------------------


class TestFacadeAvailability:
    def test_import_ast_from_codemanifest(self):
        from goga.ast import AST as Reimported  # noqa: N811

        assert Reimported is AST


# ---------------------------------------------------------------------------
# 2. Initial state
# ---------------------------------------------------------------------------


class TestInitialState:
    def test_path_property(self):
        ast_obj = AST("/some/path")
        assert ast_obj.path == "/some/path"

    def test_tree_initially_empty(self):
        ast_obj = AST("/some/path")
        assert ast_obj.tree == []

    def test_errors_initially_empty(self):
        ast_obj = AST("/some/path")
        assert ast_obj.errors == []


# ---------------------------------------------------------------------------
# 3. load() with empty directory
# ---------------------------------------------------------------------------


class TestLoadEmptyDirectory:
    def test_empty_dir_no_tree_no_errors(self, tmp_path):
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        ast_obj = AST(str(empty_dir))
        ast_obj.load()
        assert ast_obj.tree == []
        assert ast_obj.errors == []


# ---------------------------------------------------------------------------
# 4. load() with single CODEMANIFEST
# ---------------------------------------------------------------------------


VALID_SINGLE_DOC = """\
Imports:
  - Types:
      - Node
    From: goga/ast/nodes

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

        ast_obj = AST(str(doc_dir))
        ast_obj.load()
        assert len(ast_obj.tree) == 1
        assert ast_obj.tree[0].path == os.path.normpath(os.path.relpath(str(doc_dir)))


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

        ast_obj = AST(str(root_dir))
        ast_obj.load()

        # Only one top-level document
        assert len(ast_obj.tree) == 1

        root_doc = ast_obj.tree[0]
        assert root_doc.path == os.path.normpath(os.path.relpath(str(root_dir)))

        # level2 is child of level1
        assert len(root_doc.children) == 1
        child2 = root_doc.children[0]
        assert child2.path == os.path.normpath(os.path.relpath(str(level2)))

        # level3 is child of level2
        assert len(child2.children) == 1
        child3 = child2.children[0]
        assert child3.path == os.path.normpath(os.path.relpath(str(level3)))

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

        ast_obj = AST(str(root_dir))
        ast_obj.load()

        assert len(ast_obj.tree) == 1
        assert len(ast_obj.tree[0].children) == 2


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
    def test_empty_imports_produces_document_rule_error(self, tmp_path):
        doc_dir = tmp_path / "badproject"
        doc_dir.mkdir()
        (doc_dir / "CODEMANIFEST").write_text(EMPTY_IMPORTS_DOC)

        ast_obj = AST(str(doc_dir))
        ast_obj.load()

        document_errors = [e for e in ast_obj.errors if isinstance(e, DocumentRuleError)]
        assert len(document_errors) > 0

    def test_empty_imports_rule_name(self, tmp_path):
        doc_dir = tmp_path / "badproject"
        doc_dir.mkdir()
        (doc_dir / "CODEMANIFEST").write_text(EMPTY_IMPORTS_DOC)

        ast_obj = AST(str(doc_dir))
        ast_obj.load()

        rule_names = [e.rule for e in ast_obj.errors if isinstance(e, DocumentRuleError)]
        assert "imports_can_not_be_empty" in rule_names


# ---------------------------------------------------------------------------
# 7. load() detects project-level rule violations
# ---------------------------------------------------------------------------


UNUSED_USAGE_DOC = """\
Imports:
  - Types:
      - Node
    From: goga/ast/nodes
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


class TestASTRuleViolations:
    def test_unused_usage_produces_document_rule_error(self, tmp_path):
        doc_dir = tmp_path / "unusedusage"
        doc_dir.mkdir()
        (doc_dir / "CODEMANIFEST").write_text(UNUSED_USAGE_DOC)

        ast_obj = AST(str(doc_dir))
        ast_obj.load()

        document_errors = [e for e in ast_obj.errors if isinstance(e, DocumentRuleError)]
        usage_errors = [e for e in document_errors if e.rule == "all_usages_is_used"]
        assert len(usage_errors) > 0

    def test_unused_usage_rule_name(self, tmp_path):
        doc_dir = tmp_path / "unusedusage"
        doc_dir.mkdir()
        (doc_dir / "CODEMANIFEST").write_text(UNUSED_USAGE_DOC)

        ast_obj = AST(str(doc_dir))
        ast_obj.load()

        rule_names = [e.rule for e in ast_obj.errors if isinstance(e, DocumentRuleError)]
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
    def test_both_document_rule_errors_from_different_rules(self, tmp_path):
        doc_dir = tmp_path / "accum"
        doc_dir.mkdir()
        (doc_dir / "CODEMANIFEST").write_text(EMPTY_IMPORTS_AND_UNUSED_USAGE_DOC)

        ast_obj = AST(str(doc_dir))
        ast_obj.load()

        document_errors = [e for e in ast_obj.errors if isinstance(e, DocumentRuleError)]
        rule_names = {e.rule for e in document_errors}

        assert len(document_errors) >= 2, "Expected at least two DocumentRuleError"
        assert "imports_can_not_be_empty" in rule_names
        assert "all_usages_is_used" in rule_names

    def test_errors_are_all_document_rule_errors(self, tmp_path):
        doc_dir = tmp_path / "accum2"
        doc_dir.mkdir()
        (doc_dir / "CODEMANIFEST").write_text(EMPTY_IMPORTS_AND_UNUSED_USAGE_DOC)

        ast_obj = AST(str(doc_dir))
        ast_obj.load()

        # Both errors are now DocumentRuleError
        for e in ast_obj.errors:
            assert isinstance(e, DocumentRuleError)


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

        ast_obj = AST(str(root_dir))
        ast_obj.load()

        # root is top-level
        assert len(ast_obj.tree) == 1
        root_doc = ast_obj.tree[0]

        # child is a direct child of root (intermediate skipped)
        assert len(root_doc.children) == 1
        child_doc = root_doc.children[0]
        assert child_doc.path == os.path.normpath(os.path.relpath(str(child_dir)))

    def test_load_clears_previous_state(self, tmp_path):
        """Calling load() twice resets tree and errors."""
        doc_dir = tmp_path / "clearable"
        doc_dir.mkdir()
        (doc_dir / "CODEMANIFEST").write_text(VALID_SINGLE_DOC)

        ast_obj = AST(str(doc_dir))
        ast_obj.load()
        assert len(ast_obj.tree) == 1

        # Remove CODEMANIFEST, load again
        (doc_dir / "CODEMANIFEST").unlink()
        ast_obj.load()
        assert ast_obj.tree == []
        assert ast_obj.errors == []


# ---------------------------------------------------------------------------
# 10. document() lookup by path
# ---------------------------------------------------------------------------


class TestDocumentLookup:
    """Contract tests for the AST.document(path) method."""

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

    def test_ast_has_document_method(self):
        """AST exposes a document method."""
        ast_obj = AST("/tmp")
        assert hasattr(ast_obj, "document")
        assert callable(ast_obj.document)

    # -- 2. API shape --

    def test_document_accepts_str_returns_document_root(self, tmp_path):
        """document(path) takes a str and returns a DocumentRoot."""
        root_dir, _, _ = self._make_three_level_tree(tmp_path)
        ast_obj = AST(str(root_dir))
        ast_obj.load()

        result = ast_obj.document(str(root_dir))
        assert isinstance(result, DocumentRoot)

    # -- 3. Positive — relative path with dot --

    def test_relative_path_with_dot(self, tmp_path, monkeypatch):
        """document('./relative') resolves and finds the document."""
        root_dir, _level2, level3 = self._make_three_level_tree(tmp_path)

        monkeypatch.chdir(root_dir)
        ast_obj = AST(path=".")
        ast_obj.load()

        # Build "./" + relative from root_dir
        relative = os.path.relpath(str(level3), str(root_dir))
        dotted_path = "./" + relative

        doc = ast_obj.document(dotted_path)

        assert doc.path == os.path.normpath(os.path.relpath(str(level3), str(root_dir)))

    # -- 4. Positive — relative path without dot --

    def test_relative_path_without_dot(self, tmp_path, monkeypatch):
        """document('path/path') resolves and finds the document."""
        root_dir, level2, _level3 = self._make_three_level_tree(tmp_path)

        monkeypatch.chdir(root_dir)
        ast_obj = AST(path=".")
        ast_obj.load()

        relative = os.path.relpath(str(level2), str(root_dir))
        doc = ast_obj.document(relative)

        assert doc.path == os.path.normpath(os.path.relpath(str(level2), str(root_dir)))

    # -- 5. Positive — absolute path --

    def test_absolute_path(self, tmp_path):
        """document(absolute_path) returns the correct document."""
        root_dir, _level2, level3 = self._make_three_level_tree(tmp_path)
        ast_obj = AST(str(root_dir))
        ast_obj.load()

        doc = ast_obj.document(str(level3))
        assert doc.path == os.path.normpath(os.path.relpath(str(level3)))

    # -- 6. Negative — nonexistent path --

    def test_nonexistent_path_raises_document_not_found(self, tmp_path):
        """document('/nonexistent/path') raises DocumentNotFoundError."""
        root_dir, _, _ = self._make_three_level_tree(tmp_path)
        ast_obj = AST(str(root_dir))
        ast_obj.load()

        with pytest.raises(DocumentNotFoundError, match="Document not found for path"):
            ast_obj.document("/nonexistent/path")

    # -- 7. Negative — call before load() --

    def test_call_before_load_raises_document_not_found(self):
        """document() before load() raises DocumentNotFoundError (index is empty)."""
        ast_obj = AST("/some/path")
        with pytest.raises(DocumentNotFoundError, match="Document not found for path"):
            ast_obj.document("any/path")

    # -- 8. Edge — path normalization --

    def test_path_normalization(self, tmp_path):
        """document('path/./subpath/../subpath') resolves via normalization."""
        root_dir, _level2, level3 = self._make_three_level_tree(tmp_path)
        ast_obj = AST(str(root_dir))
        ast_obj.load()

        # Construct a path with . and .. segments
        tricky_path = str(level3) + "/../level3"
        doc = ast_obj.document(tricky_path)
        assert doc.path == os.path.normpath(os.path.relpath(str(Path(str(level3)).resolve())))

    # -- 9. Edge — load() rebuilds index --

    def test_load_rebuilds_index(self, tmp_path):
        """Calling load() twice picks up documents from the second load."""
        root_dir = tmp_path / "rebuild_root"
        root_dir.mkdir()
        (root_dir / "CODEMANIFEST").write_text(VALID_SINGLE_DOC)

        new_dir = tmp_path / "rebuild_new"
        new_dir.mkdir()
        # No CODEMANIFEST yet

        ast_obj = AST(str(tmp_path))
        ast_obj.load()

        # root_dir is findable, new_dir is not
        doc = ast_obj.document(str(root_dir))
        assert doc.path == os.path.normpath(os.path.relpath(str(Path(str(root_dir)).resolve())))

        with pytest.raises(DocumentNotFoundError):
            ast_obj.document(str(new_dir))

        # Now add CODEMANIFEST to new_dir and reload
        (new_dir / "CODEMANIFEST").write_text(VALID_SINGLE_DOC)
        ast_obj.load()

        # Both should be findable now
        doc_root = ast_obj.document(str(root_dir))
        assert doc_root.path == os.path.normpath(os.path.relpath(str(Path(str(root_dir)).resolve())))

        doc_new = ast_obj.document(str(new_dir))
        assert doc_new.path == os.path.normpath(os.path.relpath(str(Path(str(new_dir)).resolve())))


# ---------------------------------------------------------------------------
# 11. load() detects ImportHasNotDuplicate violations
# ---------------------------------------------------------------------------


DUPLICATE_IMPORT_DOC = """\
Imports:
  - Types:
      - Node
    From: goga/ast/nodes
  - Types:
      - Node
    From: goga/ast/other

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
    def test_duplicate_import_produces_document_rule_error(self, tmp_path):
        doc_dir = tmp_path / "dupimport"
        doc_dir.mkdir()
        (doc_dir / "CODEMANIFEST").write_text(DUPLICATE_IMPORT_DOC)

        ast_obj = AST(str(doc_dir))
        ast_obj.load()

        rule_names = [e.rule for e in ast_obj.errors if isinstance(e, DocumentRuleError)]
        assert "import_has_not_duplicate" in rule_names


# ---------------------------------------------------------------------------
# 12. load() detects AnnotationLinksExists violations
# ---------------------------------------------------------------------------


BROKEN_LINK_DOC = """\
Imports:
  - Types:
      - Node
    From: goga/ast/nodes

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
    def test_broken_annotation_link_produces_document_rule_error(self, tmp_path):
        doc_dir = tmp_path / "brokenlink"
        doc_dir.mkdir()
        (doc_dir / "CODEMANIFEST").write_text(BROKEN_LINK_DOC)

        ast_obj = AST(str(doc_dir))
        ast_obj.load()

        rule_names = [e.rule for e in ast_obj.errors if isinstance(e, DocumentRuleError)]
        assert "annotation_links_exists" in rule_names


# ---------------------------------------------------------------------------
# 13. load() detects UsageLinksHasNotConflicts violations
# ---------------------------------------------------------------------------


USAGE_CONFLICT_DOC = """\
Imports:
  - Types:
      - Node
    From: goga/ast/nodes
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
    def test_usage_conflicts_with_import_produces_document_rule_error(self, tmp_path):
        doc_dir = tmp_path / "usageconflict"
        doc_dir.mkdir()
        (doc_dir / "CODEMANIFEST").write_text(USAGE_CONFLICT_DOC)

        ast_obj = AST(str(doc_dir))
        ast_obj.load()

        rule_names = [e.rule for e in ast_obj.errors if isinstance(e, DocumentRuleError)]
        assert "usage_links_has_not_conflicts" in rule_names


# ---------------------------------------------------------------------------
# 14. load() detects EntitiesAndRoutinesHasNotConflicts violations
# ---------------------------------------------------------------------------


ENTITY_CONFLICT_DOC = """\
Imports:
  - Types:
      - Node
    From: goga/ast/nodes

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
    def test_entity_name_conflicts_with_import_produces_document_rule_error(self, tmp_path):
        doc_dir = tmp_path / "entityconflict"
        doc_dir.mkdir()
        (doc_dir / "CODEMANIFEST").write_text(ENTITY_CONFLICT_DOC)

        ast_obj = AST(str(doc_dir))
        ast_obj.load()

        rule_names = [e.rule for e in ast_obj.errors if isinstance(e, DocumentRuleError)]
        assert "entities_and_routines_has_not_conflicts" in rule_names


# ---------------------------------------------------------------------------
# 15. load() detects MutationExists violations
# ---------------------------------------------------------------------------


INVALID_MUTATION_DOC = """\
Imports:
  - Types:
      - Node
    From: goga/ast/nodes

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
    def test_nonexistent_mutation_produces_document_rule_error(self, tmp_path):
        doc_dir = tmp_path / "badmutation"
        doc_dir.mkdir()
        (doc_dir / "CODEMANIFEST").write_text(INVALID_MUTATION_DOC)

        ast_obj = AST(str(doc_dir))
        ast_obj.load()

        rule_names = [e.rule for e in ast_obj.errors if isinstance(e, DocumentRuleError)]
        assert "mutation_exists" in rule_names


# ---------------------------------------------------------------------------
# 16. load() detects MutationIsValid violations
# ---------------------------------------------------------------------------


SELF_MUTATION_DOC = """\
Imports:
  - Types:
      - Node
    From: goga/ast/nodes

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
    def test_self_mutation_produces_document_rule_error(self, tmp_path):
        doc_dir = tmp_path / "selfmutation"
        doc_dir.mkdir()
        (doc_dir / "CODEMANIFEST").write_text(SELF_MUTATION_DOC)

        ast_obj = AST(str(doc_dir))
        ast_obj.load()

        rule_names = [e.rule for e in ast_obj.errors if isinstance(e, DocumentRuleError)]
        assert "mutation_is_valid" in rule_names


# ---------------------------------------------------------------------------
# 17. load() detects ReturnTypeHasLink violations
# ---------------------------------------------------------------------------


MISSING_RETURN_LABEL_DOC = """\
Imports:
  - Types:
      - Node
    From: goga/ast/nodes

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
    def test_missing_return_label_produces_document_rule_error(self, tmp_path):
        doc_dir = tmp_path / "noreturnlabel"
        doc_dir.mkdir()
        (doc_dir / "CODEMANIFEST").write_text(MISSING_RETURN_LABEL_DOC)

        ast_obj = AST(str(doc_dir))
        ast_obj.load()

        rule_names = [e.rule for e in ast_obj.errors if isinstance(e, DocumentRuleError)]
        assert "return_type_has_link" in rule_names


# ---------------------------------------------------------------------------
# 18. load() detects EmbeddedEntityCanNotHasMutations violations
# ---------------------------------------------------------------------------


EMBEDDED_WITH_MUTATION_DOC = """\
Imports:
  - Types:
      - Node
    From: goga/ast/nodes

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
    def test_embedded_with_mutation_produces_document_rule_error(self, tmp_path):
        doc_dir = tmp_path / "embeddedmut"
        doc_dir.mkdir()
        (doc_dir / "CODEMANIFEST").write_text(EMBEDDED_WITH_MUTATION_DOC)

        ast_obj = AST(str(doc_dir))
        ast_obj.load()

        rule_names = [e.rule for e in ast_obj.errors if isinstance(e, DocumentRuleError)]
        assert "embedded_entity_can_not_has_mutations" in rule_names


# ---------------------------------------------------------------------------
# 19. Deferred routing: embedded type reclassified by original definition
# ---------------------------------------------------------------------------


class TestEmbeddedReclassification:
    """Embedded types are reclassified based on the original type definition."""

    def test_embedded_routine_reclassified_from_entity(self, tmp_path):
        """->helper pointing to a routine: factory puts it in body as entity, _reclassify moves to routines."""

        # Parent doc defines a routine
        parent_dir = tmp_path / "parent"
        parent_dir.mkdir()
        parent_doc = """\
Imports:
  - Types:
      - Node
    From: goga/ast/nodes

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

        ast_obj = AST(str(parent_dir))
        ast_obj.load()

        # Find the child document
        child_root = ast_obj.document(str(child_dir))

        # Factory creates helper as embedded entity; _reclassify moves it to routines
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
    From: goga/ast/nodes

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

        ast_obj = AST(str(parent_dir))
        ast_obj.load()

        child_root = ast_obj.document(str(child_dir))

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
    From: goga/ast/nodes

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

        ast_obj = AST(str(parent_dir))
        ast_obj.load()

        child_root = ast_obj.document(str(child_dir))

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
    From: goga/ast/nodes

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

        ast_obj = AST(str(parent_dir))
        ast_obj.load()

        child_root = ast_obj.document(str(child_dir))

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

        ast_obj = AST(str(doc_dir))
        ast_obj.load()

        root = ast_obj.document(str(doc_dir))
        assert root.embeddings == []

    def test_embedded_entity_has_original_properties_and_methods(self, tmp_path):
        """Embedded entity in body has properties/methods from the local definition in child doc."""
        parent_dir = tmp_path / "parent"
        parent_dir.mkdir()
        parent_doc = """\
Imports:
  - Types:
      - Node
    From: goga/ast/nodes

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
"->MyEntity":
  location: embedded.py
  annotations: |
    Embedded entity with own data
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
        (child_dir / "CODEMANIFEST").write_text(child_doc)

        ast_obj = AST(str(parent_dir))
        ast_obj.load()

        child_root = ast_obj.document(str(child_dir))

        embedded_entities = [e for e in child_root.body.entities if e.name == "MyEntity"]
        assert len(embedded_entities) == 1
        ent = embedded_entities[0]
        assert ent.embedded is True
        assert len(ent.properties) == 1
        assert ent.properties[0].name == "count"
        assert len(ent.methods) == 1
        assert ent.methods[0].name == "run"

    def test_embedded_routine_has_original_signature(self, tmp_path):
        """Embedded routine in body preserves signature from child doc definition."""
        parent_dir = tmp_path / "parent"
        parent_dir.mkdir()
        parent_doc = """\
Imports:
  - Types:
      - Node
    From: goga/ast/nodes

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
"->compute(x: int, y: int) -> result:int": |
  A computation routine

---
Author: Test
CreatedAt: 11/04/26
Description: Test
"""
        (child_dir / "CODEMANIFEST").write_text(child_doc)

        ast_obj = AST(str(parent_dir))
        ast_obj.load()

        child_root = ast_obj.document(str(child_dir))

        # Factory creates embedded string-value routine as RoutineTypeNode in body
        embedded_routines = [r for r in child_root.body.routines if r.name == "compute"]
        assert len(embedded_routines) == 1
        routine = embedded_routines[0]
        assert routine.embedded is True
        assert routine.signature == "(x: int, y: int) -> result:int"

    def test_multiple_embedded_types_from_same_source(self, tmp_path):
        """Multiple embedded types from the same parent document are all in body with embedded=True."""
        parent_dir = tmp_path / "parent"
        parent_dir.mkdir()
        parent_doc = """\
Imports:
  - Types:
      - Node
    From: goga/ast/nodes

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

        ast_obj = AST(str(parent_dir))
        ast_obj.load()

        child_root = ast_obj.document(str(child_dir))

        # Both should be in embeddings
        embedding_names = {name for name, _ in child_root.embeddings}
        assert "MyEntity" in embedding_names
        assert "helper" in embedding_names

        # MyEntity (original is entity) stays in body.entities; helper (original is routine) moves to routines
        entity_names = [e.name for e in child_root.body.entities]
        routine_names = [r.name for r in child_root.body.routines]
        assert "MyEntity" in entity_names
        ent = next(e for e in child_root.body.entities if e.name == "MyEntity")
        assert ent.embedded is True

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
    From: goga/ast/nodes

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

        ast_obj = AST(str(level1_dir))
        ast_obj.load()

        # Level 2 should have BaseEntity embedded
        level2_root = ast_obj.document(str(level2_dir))
        l2_entities = [e for e in level2_root.body.entities if e.name == "BaseEntity"]
        assert len(l2_entities) == 1
        assert l2_entities[0].embedded is True

        # Level 3 should also have BaseEntity embedded
        level3_root = ast_obj.document(str(level3_dir))
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
    From: goga/ast/nodes

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

        ast_obj = AST(str(parent_dir))
        ast_obj.load()

        parent_root = ast_obj.document(str(parent_dir))

        # Parent has MyEntity as non-embedded (original definition)
        parent_entities = [e for e in parent_root.body.entities if e.name == "MyEntity"]
        assert len(parent_entities) == 1
        assert parent_entities[0].embedded is False

        # Parent has no embeddings (it doesn't embed anything)
        assert parent_root.embeddings == []
