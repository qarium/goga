"""Contract tests for the codemanifest root package — Project class."""

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
