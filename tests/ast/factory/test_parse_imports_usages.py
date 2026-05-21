"""Contract and logic tests for Factory._parse_imports handling Usages entries."""

from pathlib import Path

from goga.ast.factory import Factory
from goga.ast.nodes import ImportTypeItemNode, ImportUsageItemNode


def _write_codemanifest(directory: str, content: str) -> str:
    """Write a CODEMANIFEST file into *directory* and return the dir path."""
    dir_path = Path(directory)
    dir_path.mkdir(parents=True, exist_ok=True)
    (dir_path / "CODEMANIFEST").write_text(content, encoding="utf-8")
    return directory


_MANIFEST_TEMPLATE = """\
{imports_section}
---
---
"""


def _manifest(imports_yaml: str) -> str:
    return _MANIFEST_TEMPLATE.format(imports_section=imports_yaml)


# ---------------------------------------------------------------------------
# Contract tests
# ---------------------------------------------------------------------------


class TestParseImportsWithTypesAndUsages:
    def test_parse_imports_with_types_and_usages(self, tmp_path) -> None:
        """YAML with Types+Usages+From produces both ImportTypeItemNode and ImportUsageItemNode."""
        imports = """\
Imports:
  - Types:
      - Foo
      - Bar AS B
    Usages:
      - my_usage
    From: path/to/cell
"""
        pkg = _write_codemanifest(str(tmp_path / "both"), _manifest(imports))
        root = Factory(pkg).create()
        type_items = root.header.imports.types
        usage_items = root.header.imports.usages
        assert len(type_items) == 2
        assert len(usage_items) == 1
        assert "Foo" in type_items[0].type_name
        assert "Bar" in type_items[1].type_name
        assert type_items[1].alias == "B"
        assert "my_usage" in usage_items[0].usage_name
        assert usage_items[0].from_path == "path/to/cell"

    def test_parse_imports_usages_only(self, tmp_path) -> None:
        """YAML with only Usages produces only ImportUsageItemNode."""
        imports = """\
Imports:
  - Usages:
      - some_usage
      - another
    From: path/to/cell
"""
        pkg = _write_codemanifest(str(tmp_path / "usages_only"), _manifest(imports))
        root = Factory(pkg).create()
        usage_items = root.header.imports.usages
        assert all(isinstance(i, ImportUsageItemNode) for i in usage_items)
        assert len(usage_items) == 2
        assert "some_usage" in usage_items[0].usage_name
        assert "another" in usage_items[1].usage_name
        assert len(root.header.imports.types) == 0

    def test_parse_imports_types_only(self, tmp_path) -> None:
        """YAML with only Types produces only ImportTypeItemNode (as before)."""
        imports = """\
Imports:
  - Types:
      - Foo
      - Bar
    From: path/to/cell
"""
        pkg = _write_codemanifest(str(tmp_path / "types_only"), _manifest(imports))
        root = Factory(pkg).create()
        type_items = root.header.imports.types
        assert all(isinstance(i, ImportTypeItemNode) for i in type_items)
        assert len(type_items) == 2
        assert len(root.header.imports.usages) == 0

    def test_parse_imports_empty_types_creates_empty_item(self, tmp_path) -> None:
        """Types=[] creates ImportTypeItemNode with type_name=set()."""
        imports = """\
Imports:
  - Types: []
    From: path/to/cell
"""
        pkg = _write_codemanifest(str(tmp_path / "empty_types"), _manifest(imports))
        root = Factory(pkg).create()
        type_items = root.header.imports.types
        assert len(type_items) == 1
        assert isinstance(type_items[0], ImportTypeItemNode)
        assert type_items[0].type_name == set()

    def test_parse_imports_empty_usages_creates_empty_item(self, tmp_path) -> None:
        """Usages=[] creates ImportUsageItemNode with usage_name=set()."""
        imports = """\
Imports:
  - Usages: []
    From: path/to/cell
"""
        pkg = _write_codemanifest(str(tmp_path / "empty_usages"), _manifest(imports))
        root = Factory(pkg).create()
        usage_items = root.header.imports.usages
        assert len(usage_items) == 1
        assert isinstance(usage_items[0], ImportUsageItemNode)
        assert usage_items[0].usage_name == set()

    def test_parse_imports_no_types_no_usages(self, tmp_path) -> None:
        """Only From (no Types, no Usages) creates both empty type and usage items."""
        imports = """\
Imports:
  - From: path/to/cell
"""
        pkg = _write_codemanifest(str(tmp_path / "no_types_no_usages"), _manifest(imports))
        root = Factory(pkg).create()
        type_items = root.header.imports.types
        usage_items = root.header.imports.usages
        assert len(type_items) == 1
        assert isinstance(type_items[0], ImportTypeItemNode)
        assert type_items[0].type_name == set()
        assert len(usage_items) == 1
        assert isinstance(usage_items[0], ImportUsageItemNode)
        assert usage_items[0].usage_name == set()

    def test_parse_imports_usage_alias(self, tmp_path) -> None:
        """Usages=["long_name AS short"] -> usage_name={"long_name"}, alias="short"."""
        imports = """\
Imports:
  - Usages:
      - long_name AS short
    From: path/to/cell
"""
        pkg = _write_codemanifest(str(tmp_path / "usage_alias"), _manifest(imports))
        root = Factory(pkg).create()
        usage_items = root.header.imports.usages
        assert len(usage_items) == 1
        assert isinstance(usage_items[0], ImportUsageItemNode)
        assert "long_name" in usage_items[0].usage_name
        assert usage_items[0].alias == "short"


# ---------------------------------------------------------------------------
# Logic tests
# ---------------------------------------------------------------------------


class TestParseImportsLogic:
    def test_parse_imports_multiple_entries(self, tmp_path) -> None:
        """Multiple YAML entries with different From paths."""
        imports = """\
Imports:
  - Types:
      - Foo
    From: path/a
  - Usages:
      - my_usage
    From: path/b
  - Types:
      - Bar
    Usages:
      - shared_usage
    From: path/c
"""
        pkg = _write_codemanifest(str(tmp_path / "multi_entries"), _manifest(imports))
        root = Factory(pkg).create()
        type_items = root.header.imports.types
        usage_items = root.header.imports.usages
        assert len(type_items) == 2
        assert len(usage_items) == 2
        # Foo from path/a
        foo = [i for i in type_items if "Foo" in i.type_name]
        assert len(foo) == 1
        assert foo[0].from_path == "path/a"
        # my_usage from path/b
        usage = [i for i in usage_items if "my_usage" in i.usage_name]
        assert len(usage) == 1
        assert usage[0].from_path == "path/b"
        # Bar from path/c
        bar = [i for i in type_items if "Bar" in i.type_name]
        assert len(bar) == 1
        assert bar[0].from_path == "path/c"
        # shared_usage from path/c
        shared = [i for i in usage_items if "shared_usage" in i.usage_name]
        assert len(shared) == 1
        assert shared[0].from_path == "path/c"

    def test_parse_imports_invalid_usages_type(self, tmp_path) -> None:
        """Usages="not_a_list" -> skip (does not crash)."""
        imports = """\
Imports:
  - Types:
      - Foo
    Usages: not_a_list
    From: path/to/cell
"""
        pkg = _write_codemanifest(str(tmp_path / "invalid_usages"), _manifest(imports))
        root = Factory(pkg).create()
        type_items = root.header.imports.types
        usage_items = root.header.imports.usages
        assert len(type_items) == 1
        assert len(usage_items) == 0

    def test_parse_imports_mixed_types_and_usages(self, tmp_path) -> None:
        """One entry with Types+Usages, another with only Types."""
        imports = """\
Imports:
  - Types:
      - Foo
    Usages:
      - my_usage
    From: path/a
  - Types:
      - Bar
    From: path/b
"""
        pkg = _write_codemanifest(str(tmp_path / "mixed"), _manifest(imports))
        root = Factory(pkg).create()
        type_items = root.header.imports.types
        usage_items = root.header.imports.usages
        assert len(type_items) == 2
        assert len(usage_items) == 1


# ---------------------------------------------------------------------------
# _build_embeddings only uses ImportTypeItemNode
# ---------------------------------------------------------------------------


class TestBuildEmbeddingsWithUsageItems:
    def test_embeddings_ignores_usage_items(self, tmp_path) -> None:
        """_build_embeddings only looks at ImportTypeItemNode, not ImportUsageItemNode."""
        manifest = """\
Imports:
  - Types:
      - MyType
    Usages:
      - my_usage
    From: path/to/cell

---
"->MyType": {}
"""
        pkg = _write_codemanifest(str(tmp_path / "embed_ignore_usage"), manifest)
        root = Factory(pkg).create()
        assert ("MyType", "path/to/cell") in root.embeddings
        # my_usage should not create embeddings
        assert len(root.embeddings) == 1


# ---------------------------------------------------------------------------
# _parse_header collects types only from ImportTypeItemNode
# ---------------------------------------------------------------------------


class TestParseHeaderTypesWithUsageItems:
    def test_header_types_excludes_usage_names(self, tmp_path) -> None:
        """HeaderNode.types only includes type names, not usage names."""
        imports = """\
Imports:
  - Types:
      - Foo
    Usages:
      - my_usage
    From: path/to/cell
"""
        pkg = _write_codemanifest(str(tmp_path / "header_types"), _manifest(imports))
        root = Factory(pkg).create()
        assert "Foo" in root.header.types
        assert "my_usage" not in root.header.types


# ---------------------------------------------------------------------------
# No imports — both lists empty
# ---------------------------------------------------------------------------


class TestNoImports:
    def test_no_imports_both_lists_empty(self, tmp_path) -> None:
        """When Imports section is absent, both types and usages lists are empty."""
        manifest = """\

---
---
"""
        pkg = _write_codemanifest(str(tmp_path / "no_imports"), manifest)
        root = Factory(pkg).create()
        assert root.header.imports.types == []
        assert root.header.imports.usages == []


# ---------------------------------------------------------------------------
# _wire_references sets parent for both lists
# ---------------------------------------------------------------------------


class TestWireReferencesBothLists:
    def test_wire_references_sets_parent_for_both_lists(self, tmp_path) -> None:
        """_wire_references sets root and parent on items in both types and usages lists."""
        imports = """\
Imports:
  - Types:
      - Foo
    Usages:
      - my_usage
    From: path/to/cell
"""
        pkg = _write_codemanifest(str(tmp_path / "wire_refs"), _manifest(imports))
        root = Factory(pkg).create()

        type_item = root.header.imports.types[0]
        assert type_item.root is root
        assert type_item.parent is root.header.imports

        usage_item = root.header.imports.usages[0]
        assert usage_item.root is root
        assert usage_item.parent is root.header.imports
