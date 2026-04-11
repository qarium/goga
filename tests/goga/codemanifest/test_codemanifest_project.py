"""Contract tests for the codemanifest root package — Project class."""

import pytest
from goga.codemanifest import Project
from goga.codemanifest.errors import ManifestRuleError, ProjectRuleError

# ---------------------------------------------------------------------------
# 1. Facade availability
# ---------------------------------------------------------------------------


class TestFacadeAvailability:
    def test_import_project_from_codemanifest(self):
        from goga.codemanifest import Project as P

        assert P is Project


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
Architector: Test
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
Architector: Test
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
Architector: Test
CreatedAt: 11/04/26
Description: Test
"""


class TestProjectRuleViolations:
    def test_unused_usage_produces_project_rule_error(self, tmp_path):
        doc_dir = tmp_path / "unusedusage"
        doc_dir.mkdir()
        (doc_dir / "CODEMANIFEST").write_text(UNUSED_USAGE_DOC)

        p = Project(str(doc_dir))
        p.load()

        project_errors = [e for e in p.errors if isinstance(e, ProjectRuleError)]
        assert len(project_errors) > 0

    def test_unused_usage_rule_name(self, tmp_path):
        doc_dir = tmp_path / "unusedusage"
        doc_dir.mkdir()
        (doc_dir / "CODEMANIFEST").write_text(UNUSED_USAGE_DOC)

        p = Project(str(doc_dir))
        p.load()

        rule_names = [e.rule for e in p.errors if isinstance(e, ProjectRuleError)]
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
Architector: Test
CreatedAt: 11/04/26
Description: Test
"""


class TestAccumulatedErrors:
    def test_both_manifest_and_project_errors(self, tmp_path):
        doc_dir = tmp_path / "accum"
        doc_dir.mkdir()
        (doc_dir / "CODEMANIFEST").write_text(EMPTY_IMPORTS_AND_UNUSED_USAGE_DOC)

        p = Project(str(doc_dir))
        p.load()

        manifest_errors = [e for e in p.errors if isinstance(e, ManifestRuleError)]
        project_errors = [e for e in p.errors if isinstance(e, ProjectRuleError)]

        assert len(manifest_errors) > 0, "Expected at least one ManifestRuleError"
        assert len(project_errors) > 0, "Expected at least one ProjectRuleError"

    def test_errors_contains_both_types(self, tmp_path):
        doc_dir = tmp_path / "accum2"
        doc_dir.mkdir()
        (doc_dir / "CODEMANIFEST").write_text(EMPTY_IMPORTS_AND_UNUSED_USAGE_DOC)

        p = Project(str(doc_dir))
        p.load()

        types_set = {type(e) for e in p.errors}
        assert ManifestRuleError in types_set
        assert ProjectRuleError in types_set


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
        from goga.codemanifest.nodes import DocumentRoot

        root_dir, _, _ = self._make_three_level_tree(tmp_path)
        p = Project(str(root_dir))
        p.load()

        result = p.codemanifest(str(root_dir))
        assert isinstance(result, DocumentRoot)

    # -- 3. Positive — relative path with dot --

    def test_relative_path_with_dot(self, tmp_path):
        """codemanifest('./relative') resolves and finds the document."""
        import os

        root_dir, level2, level3 = self._make_three_level_tree(tmp_path)
        p = Project(str(root_dir))
        p.load()

        # Build "./" + relative from root_dir, and resolve from root_dir as cwd
        relative = os.path.relpath(str(level3), str(root_dir))
        dotted_path = "./" + relative

        original_cwd = os.getcwd()
        try:
            os.chdir(str(root_dir))
            doc = p.codemanifest(dotted_path)
        finally:
            os.chdir(original_cwd)

        assert doc.path == os.path.normpath(os.path.abspath(str(level3)))

    # -- 4. Positive — relative path without dot --

    def test_relative_path_without_dot(self, tmp_path):
        """codemanifest('path/path') resolves and finds the document."""
        import os

        root_dir, level2, level3 = self._make_three_level_tree(tmp_path)
        p = Project(str(root_dir))
        p.load()

        relative = os.path.relpath(str(level2), str(root_dir))

        original_cwd = os.getcwd()
        try:
            os.chdir(str(root_dir))
            doc = p.codemanifest(relative)
        finally:
            os.chdir(original_cwd)

        assert doc.path == os.path.normpath(os.path.abspath(str(level2)))

    # -- 5. Positive — absolute path --

    def test_absolute_path(self, tmp_path):
        """codemanifest(absolute_path) returns the correct document."""
        root_dir, level2, level3 = self._make_three_level_tree(tmp_path)
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
        import os

        root_dir, level2, level3 = self._make_three_level_tree(tmp_path)
        p = Project(str(root_dir))
        p.load()

        # Construct a path with . and .. segments
        tricky_path = str(level3) + "/../level3"
        doc = p.codemanifest(tricky_path)
        assert doc.path == os.path.normpath(os.path.abspath(str(level3)))

    # -- 9. Edge — load() rebuilds index --

    def test_load_rebuilds_index(self, tmp_path):
        """Calling load() twice picks up documents from the second load."""
        import os

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
        assert doc.path == os.path.normpath(os.path.abspath(str(root_dir)))

        with pytest.raises(KeyError):
            p.codemanifest(str(new_dir))

        # Now add CODEMANIFEST to new_dir and reload
        (new_dir / "CODEMANIFEST").write_text(VALID_SINGLE_DOC)
        p.load()

        # Both should be findable now
        doc_root = p.codemanifest(str(root_dir))
        assert doc_root.path == os.path.normpath(os.path.abspath(str(root_dir)))

        doc_new = p.codemanifest(str(new_dir))
        assert doc_new.path == os.path.normpath(os.path.abspath(str(new_dir)))
