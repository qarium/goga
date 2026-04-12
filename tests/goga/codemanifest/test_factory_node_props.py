"""Contract tests for Factory node properties: data, parent, links.

Verifies that Factory correctly fills `data`, `parent`, and `links` on all
node types produced during CODEMANIFEST parsing.
"""

from pathlib import Path

from goga.codemanifest.factory import Factory

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_codemanifest(directory: str, content: str) -> str:
    """Write a CODEMANIFEST file into *directory* and return the dir path."""
    dir_path = Path(directory)
    dir_path.mkdir(parents=True, exist_ok=True)
    (dir_path / "CODEMANIFEST").write_text(content, encoding="utf-8")
    return directory


# Complete manifest with all sections and backtick links in annotations.
_FULL_MANIFEST = """\
Imports:
  - Types:
      - DocumentRoot
      - DocumentNode AS Node
    From: goga/codemanifest/nodes
  - Types:
      - ManifestParseError
    From: goga/codemanifest/errors

Usages:
  nodes: .usages/nodes.md
  yaml: |
    pyyaml library for parsing

Annotations: |
  See `DocumentRoot` for the main entry point.

---
"Project(path: str)":
  location: project.py
  annotations: |
    This entity references `HeaderNode` and `BodyNode`.
  properties:
    "tree -> list[DocumentRoot]": |
      Stores `DocumentRoot` instances.
    "errors -> list[str]": |
      Error list
  methods:
    "load()": |
      Loads the tree, calls `Factory.create()`.

"helper(x: int) -> result:int": |
  A helper routine that uses `Project` type.

"dict_routine(key: str)":
  location: routines.py
  annotations: |
    Uses `MethodNode` internally.

---
Author: Test Author
CreatedAt: 11/04/26
Description: |
  Test manifest description
"""


def _create_full_manifest(tmp_path, subdir: str = "pkg") -> str:
    """Create a directory with the full manifest and return its path."""
    pkg_dir = str(tmp_path / subdir)
    _write_codemanifest(pkg_dir, _FULL_MANIFEST)
    return pkg_dir


# ---------------------------------------------------------------------------
# 1. Data population tests
# ---------------------------------------------------------------------------


class TestDataImportItemNode:
    def test_data_contains_raw_import_entry(self, tmp_path) -> None:
        """ImportItemNode.data is a copy of the raw import entry dict."""
        pkg = _create_full_manifest(tmp_path)
        root = Factory(pkg).create()

        item = root.header.imports.items[0]
        assert isinstance(item.data, dict)
        # First import entry has Types and From
        assert "Types" in item.data
        assert "From" in item.data
        assert item.data["From"] == "goga/codemanifest/nodes"
        assert isinstance(item.data["Types"], list)

    def test_data_second_import_entry(self, tmp_path) -> None:
        """Second import entry also carries raw dict in data."""
        pkg = _create_full_manifest(tmp_path)
        root = Factory(pkg).create()

        # The second entry in Imports list
        item = root.header.imports.items[2]
        assert "ManifestParseError" in str(item.data["Types"])
        assert item.data["From"] == "goga/codemanifest/errors"


class TestDataEntityTypeNode:
    def test_data_contains_raw_entity_dict(self, tmp_path) -> None:
        """EntityTypeNode.data contains raw entity dict with location, properties."""
        pkg = _create_full_manifest(tmp_path)
        root = Factory(pkg).create()

        entity = root.body.entities[0]
        assert isinstance(entity.data, dict)
        assert "location" in entity.data
        assert "properties" in entity.data
        assert "annotations" in entity.data
        assert entity.data["location"] == "project.py"


class TestDataPropertyNode:
    def test_data_contains_raw_property_entry(self, tmp_path) -> None:
        """PropertyNode.data contains {prop_key: prop_value}."""
        pkg = _create_full_manifest(tmp_path)
        root = Factory(pkg).create()

        prop = root.body.entities[0].properties[0]
        assert isinstance(prop.data, dict)
        assert len(prop.data) == 1
        # Key is "tree -> list[DocumentRoot]", value is the annotation text
        key = next(iter(prop.data.keys()))
        assert "tree" in key
        assert "DocumentRoot" in prop.data[key]


class TestDataMethodNode:
    def test_data_contains_raw_method_entry(self, tmp_path) -> None:
        """MethodNode.data contains {method_key: method_value}."""
        pkg = _create_full_manifest(tmp_path)
        root = Factory(pkg).create()

        method = root.body.entities[0].methods[0]
        assert isinstance(method.data, dict)
        assert len(method.data) == 1
        key = next(iter(method.data.keys()))
        assert "load()" in key


class TestDataUsageItemNode:
    def test_data_contains_raw_usage_entry(self, tmp_path) -> None:
        """UsageItemNode.data contains {name: value}."""
        pkg = _create_full_manifest(tmp_path)
        root = Factory(pkg).create()

        item = root.header.usages.items[0]
        assert isinstance(item.data, dict)
        assert "nodes" in item.data
        assert ".usages/nodes.md" in str(item.data["nodes"])


class TestDataRoutineTypeNode:
    def test_data_string_routine(self, tmp_path) -> None:
        """RoutineTypeNode.data for string routine contains {key: value}."""
        pkg = _create_full_manifest(tmp_path)
        root = Factory(pkg).create()

        # String routine: "helper(x: int) -> result:int": A helper...
        routine = root.body.routines[0]
        assert isinstance(routine.data, dict)
        key = next(iter(routine.data.keys()))
        assert "helper" in key

    def test_data_dict_routine(self, tmp_path) -> None:
        """RoutineTypeNode.data for dict routine contains raw dict."""
        pkg = _create_full_manifest(tmp_path)
        root = Factory(pkg).create()

        # Dict routine: "dict_routine(key: str)": {location, annotations}
        routine = root.body.routines[1]
        assert isinstance(routine.data, dict)
        assert "location" in routine.data
        assert "annotations" in routine.data


class TestDataHeaderNode:
    def test_data_contains_raw_header_dict(self, tmp_path) -> None:
        """HeaderNode.data contains copy of raw header dict."""
        pkg = _create_full_manifest(tmp_path)
        root = Factory(pkg).create()

        header = root.header
        assert isinstance(header.data, dict)
        assert "Imports" in header.data
        assert "Usages" in header.data
        assert "Annotations" in header.data


class TestDataBodyNode:
    def test_data_contains_raw_body_dict(self, tmp_path) -> None:
        """BodyNode.data contains copy of raw body dict."""
        pkg = _create_full_manifest(tmp_path)
        root = Factory(pkg).create()

        body = root.body
        assert isinstance(body.data, dict)
        # Body should contain entity and routine keys
        assert len(body.data) >= 2


class TestDataFooterNode:
    def test_data_contains_raw_footer_dict(self, tmp_path) -> None:
        """FooterNode.data contains copy of raw footer dict."""
        pkg = _create_full_manifest(tmp_path)
        root = Factory(pkg).create()

        footer = root.footer
        assert isinstance(footer.data, dict)
        assert "Author" in footer.data
        assert "CreatedAt" in footer.data
        assert "Description" in footer.data
        assert footer.data["Author"] == "Test Author"


# ---------------------------------------------------------------------------
# 2. Parent chain tests
# ---------------------------------------------------------------------------


class TestParentHeaderNode:
    def test_header_parent_is_document_root(self, tmp_path) -> None:
        """HeaderNode.parent is the DocumentRoot."""
        pkg = _create_full_manifest(tmp_path)
        root = Factory(pkg).create()
        assert root.header.parent is root


class TestParentImportsNode:
    def test_imports_parent_is_header(self, tmp_path) -> None:
        """ImportsNode.parent is HeaderNode."""
        pkg = _create_full_manifest(tmp_path)
        root = Factory(pkg).create()
        assert root.header.imports.parent is root.header


class TestParentImportItemNode:
    def test_import_item_parent_is_imports(self, tmp_path) -> None:
        """ImportItemNode.parent is ImportsNode."""
        pkg = _create_full_manifest(tmp_path)
        root = Factory(pkg).create()
        for item in root.header.imports.items:
            assert item.parent is root.header.imports


class TestParentUsagesNode:
    def test_usages_parent_is_header(self, tmp_path) -> None:
        """UsagesNode.parent is HeaderNode."""
        pkg = _create_full_manifest(tmp_path)
        root = Factory(pkg).create()
        assert root.header.usages.parent is root.header


class TestParentUsageItemNode:
    def test_usage_item_parent_is_usages(self, tmp_path) -> None:
        """UsageItemNode.parent is UsagesNode."""
        pkg = _create_full_manifest(tmp_path)
        root = Factory(pkg).create()
        for item in root.header.usages.items:
            assert item.parent is root.header.usages


class TestParentBodyNode:
    def test_body_parent_is_document_root(self, tmp_path) -> None:
        """BodyNode.parent is DocumentRoot."""
        pkg = _create_full_manifest(tmp_path)
        root = Factory(pkg).create()
        assert root.body.parent is root


class TestParentEntityTypeNode:
    def test_entity_parent_is_body(self, tmp_path) -> None:
        """EntityTypeNode.parent is BodyNode."""
        pkg = _create_full_manifest(tmp_path)
        root = Factory(pkg).create()
        for entity in root.body.entities:
            assert entity.parent is root.body


class TestParentPropertyNode:
    def test_property_parent_is_entity(self, tmp_path) -> None:
        """PropertyNode.parent is EntityTypeNode."""
        pkg = _create_full_manifest(tmp_path)
        root = Factory(pkg).create()
        entity = root.body.entities[0]
        for prop in entity.properties:
            assert prop.parent is entity


class TestParentMethodNode:
    def test_method_parent_is_entity(self, tmp_path) -> None:
        """MethodNode.parent is EntityTypeNode."""
        pkg = _create_full_manifest(tmp_path)
        root = Factory(pkg).create()
        entity = root.body.entities[0]
        for method in entity.methods:
            assert method.parent is entity


class TestParentFooterNode:
    def test_footer_parent_is_document_root(self, tmp_path) -> None:
        """FooterNode.parent is DocumentRoot."""
        pkg = _create_full_manifest(tmp_path)
        root = Factory(pkg).create()
        assert root.footer.parent is root


class TestParentRoutineTypeNode:
    def test_routine_parent_is_body(self, tmp_path) -> None:
        """RoutineTypeNode.parent is BodyNode."""
        pkg = _create_full_manifest(tmp_path)
        root = Factory(pkg).create()
        for routine in root.body.routines:
            assert routine.parent is root.body


# ---------------------------------------------------------------------------
# 3. Links extraction tests
# ---------------------------------------------------------------------------


class TestLinksHeaderAnnotations:
    def test_header_annotations_backtick_links(self, tmp_path) -> None:
        """Header AnnotationsNode.links contains backtick refs from header text."""
        pkg = _create_full_manifest(tmp_path)
        root = Factory(pkg).create()

        links = root.header.annotations.links
        assert isinstance(links, list)
        assert "DocumentRoot" in links


class TestLinksEntityAnnotations:
    def test_entity_annotations_backtick_links(self, tmp_path) -> None:
        """Entity AnnotationsNode.links contains backtick refs from entity text."""
        pkg = _create_full_manifest(tmp_path)
        root = Factory(pkg).create()

        entity = root.body.entities[0]
        links = entity.annotations.links
        assert isinstance(links, list)
        assert "HeaderNode" in links
        assert "BodyNode" in links


class TestLinksMethodAnnotations:
    def test_method_annotations_backtick_links(self, tmp_path) -> None:
        """Method AnnotationsNode.links contains backtick refs from method text."""
        pkg = _create_full_manifest(tmp_path)
        root = Factory(pkg).create()

        method = root.body.entities[0].methods[0]
        links = method.annotations.links
        assert isinstance(links, list)
        assert "Factory.create()" in links


class TestLinksPropertyAnnotations:
    def test_property_annotations_backtick_links(self, tmp_path) -> None:
        """Property AnnotationsNode.links contains backtick refs from property text."""
        pkg = _create_full_manifest(tmp_path)
        root = Factory(pkg).create()

        prop = root.body.entities[0].properties[0]
        links = prop.annotations.links
        assert isinstance(links, list)
        assert "DocumentRoot" in links


class TestLinksRoutineAnnotations:
    def test_string_routine_annotations_backtick_links(self, tmp_path) -> None:
        """Routine (string) AnnotationsNode.links contains backtick refs."""
        pkg = _create_full_manifest(tmp_path)
        root = Factory(pkg).create()

        # String routine: uses `Project` type
        routine = root.body.routines[0]
        links = routine.annotations.links
        assert isinstance(links, list)
        assert "Project" in links

    def test_dict_routine_annotations_backtick_links(self, tmp_path) -> None:
        """Routine (dict) AnnotationsNode.links contains backtick refs."""
        pkg = _create_full_manifest(tmp_path)
        root = Factory(pkg).create()

        # Dict routine: uses `MethodNode` internally
        routine = root.body.routines[1]
        links = routine.annotations.links
        assert isinstance(links, list)
        assert "MethodNode" in links


# ---------------------------------------------------------------------------
# 4. DocumentRoot.links aggregate
# ---------------------------------------------------------------------------


class TestExtractLinks:
    """Unit tests for Factory._extract_links static method."""

    def test_empty_string_returns_empty_list(self) -> None:
        assert Factory._extract_links("") == []

    def test_no_backticks_returns_empty_list(self) -> None:
        assert Factory._extract_links("plain text without links") == []

    def test_single_backtick_link(self) -> None:
        assert Factory._extract_links("Use `yaml` here") == ["yaml"]

    def test_multiple_backtick_links(self) -> None:
        result = Factory._extract_links("Use `nodes` and `yaml` here")
        assert result == ["nodes", "yaml"]

    def test_link_with_dots_and_parens(self) -> None:
        result = Factory._extract_links("calls `Factory.create()` internally")
        assert result == ["Factory.create()"]

    def test_unclosed_backtick_ignored(self) -> None:
        result = Factory._extract_links("see `unclosed link text")
        assert result == []

    def test_triple_backtick_block_not_matched(self) -> None:
        result = Factory._extract_links("```\ncode\n```")
        assert result == []

    def test_double_backtick_not_matched(self) -> None:
        result = Factory._extract_links("``notalink``")
        assert result == []

    def test_four_backtick_not_matched(self) -> None:
        result = Factory._extract_links("````notalink````")
        assert result == []

    def test_link_after_triple_backtick_block(self) -> None:
        result = Factory._extract_links("```\nError: msg\n``` see `MyType`")
        assert result == ["MyType"]

    def test_multiline_content_inside_single_backtick_not_matched(self) -> None:
        result = Factory._extract_links("`line1\nline2`")
        assert result == []

    def test_adjacent_with_text_between(self) -> None:
        result = Factory._extract_links("`a` and `b`")
        assert result == ["a", "b"]

    def test_five_backtick_not_matched(self) -> None:
        result = Factory._extract_links("`````notalink`````")
        assert result == []

    def test_triple_backtick_with_single_inside(self) -> None:
        result = Factory._extract_links("```foo `bar` baz```")
        assert result == []


class TestDataImportsNode:
    def test_imports_node_data_is_copy_of_raw_imports_list(self, tmp_path) -> None:
        """ImportsNode.data is not set by factory (empty dict) — data is on ImportItemNode."""
        pkg = _create_full_manifest(tmp_path)
        root = Factory(pkg).create()

        imports = root.header.imports
        assert isinstance(imports.data, dict)
        # ImportsNode is created without explicit data — items carry the data
        assert isinstance(imports.items, list)
        assert len(imports.items) == 3
        for item in imports.items:
            assert "Types" in item.data
            assert "From" in item.data


class TestDataUsagesNode:
    def test_usages_node_data_is_copy_of_raw_usages_dict(self, tmp_path) -> None:
        """UsagesNode.data is not set by factory (empty dict) — data is on UsageItemNode."""
        pkg = _create_full_manifest(tmp_path)
        root = Factory(pkg).create()

        usages = root.header.usages
        assert isinstance(usages.data, dict)
        assert isinstance(usages.items, list)
        assert len(usages.items) == 2
        for item in usages.items:
            assert isinstance(item.data, dict)
            assert len(item.data) == 1


class TestRootLinksAggregate:
    def test_root_links_collects_all_backtick_refs(self, tmp_path) -> None:
        """DocumentRoot.links aggregates link references from all annotations."""
        pkg = _create_full_manifest(tmp_path)
        root = Factory(pkg).create()

        assert isinstance(root.links, dict)
        # All backtick refs should appear as keys
        assert "DocumentRoot" in root.links
        assert "HeaderNode" in root.links
        assert "BodyNode" in root.links
        assert "Project" in root.links
        assert "MethodNode" in root.links
        assert "Factory.create()" in root.links
