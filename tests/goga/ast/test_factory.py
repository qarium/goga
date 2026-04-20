"""Contract tests for goga.ast.factory package.

Verifies Factory parsing of CODEMANIFEST YAML files into DocumentRoot trees,
covering header, body, footer parsing, alias handling, usage detection,
entity/routine classification, location resolution, error handling, and
deep hierarchy support.
"""

from pathlib import Path

import pytest
from goga.ast.errors import DocumentParseError
from goga.ast.factory import Factory
from goga.ast.nodes import (
    AnnotationsNode,
    BodyNode,
    DocumentRoot,
    EntityTypeNode,
    FooterNode,
    HeaderNode,
    ImportsNode,
    RoutineTypeNode,
    UsagesNode,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_codemanifest(
    directory: str,
    content: str,
) -> str:
    """Write a CODEMANIFEST file into *directory* and return the dir path."""
    dir_path = Path(directory)
    dir_path.mkdir(parents=True, exist_ok=True)
    (dir_path / "CODEMANIFEST").write_text(content, encoding="utf-8")
    return directory


# Full manifest with all sections for basic parsing tests.
_FULL_MANIFEST = """\
Imports:
  - Types:
      - DocumentRoot
      - DocumentNode AS Node
    From: goga/ast/nodes
  - Types:
      - DocumentParseError
    From: goga/ast/errors

Usages:
  nodes: .usages/nodes.md
  yaml: |
    pyyaml library for parsing

Annotations: |
  Global annotations text

---
"Project(path: str)":
  location: project.py
  annotations: |
    Loads manifest tree
  properties:
    "tree -> list[DocumentRoot]": |
      Document tree
    "errors -> list[str]": |
      Error list
  methods:
    "load()": |
      Loads the tree

"helper(x: int) -> result:int": |
  A helper routine annotation

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
# 1. Facade availability
# ---------------------------------------------------------------------------


class TestFacadeAvailability:
    def test_factory_importable(self) -> None:
        assert Factory is not None

    def test_factory_requires_path(self) -> None:
        f = Factory("/some/path")
        assert f.path == "/some/path"


# ---------------------------------------------------------------------------
# 2. Basic parsing — header imports
# ---------------------------------------------------------------------------


class TestBasicParsingHeaderImports:
    def test_header_imports_parsed(self, tmp_path) -> None:
        pkg = _create_full_manifest(tmp_path)
        root = Factory(pkg).create()
        assert isinstance(root.header.imports, ImportsNode)
        assert len(root.header.imports.types) == 3

    def test_import_type_without_alias(self, tmp_path) -> None:
        pkg = _create_full_manifest(tmp_path)
        root = Factory(pkg).create()
        item = root.header.imports.types[0]
        # DocumentRoot — no alias
        assert "DocumentRoot" in item.type_name
        assert item.alias == ""
        assert item.from_path == "goga/ast/nodes"

    def test_import_type_with_alias(self, tmp_path) -> None:
        pkg = _create_full_manifest(tmp_path)
        root = Factory(pkg).create()
        item = root.header.imports.types[1]
        # DocumentNode AS Node
        assert "DocumentNode" in item.type_name
        assert item.alias == "Node"
        assert item.from_path == "goga/ast/nodes"

    def test_import_single_type(self, tmp_path) -> None:
        pkg = _create_full_manifest(tmp_path)
        root = Factory(pkg).create()
        item = root.header.imports.types[2]
        assert "DocumentParseError" in item.type_name
        assert item.alias == ""
        assert item.from_path == "goga/ast/errors"

    def test_header_types_list_populated(self, tmp_path) -> None:
        pkg = _create_full_manifest(tmp_path)
        root = Factory(pkg).create()
        types = root.header.types
        assert "DocumentRoot" in types
        assert "DocumentNode" in types
        assert "DocumentParseError" in types


# ---------------------------------------------------------------------------
# 3. Basic parsing — header usages
# ---------------------------------------------------------------------------


class TestBasicParsingHeaderUsages:
    def test_usages_parsed(self, tmp_path) -> None:
        pkg = _create_full_manifest(tmp_path)
        root = Factory(pkg).create()
        assert isinstance(root.header.usages, UsagesNode)
        assert len(root.header.usages.items) == 2

    def test_usages_file_path_detection(self, tmp_path) -> None:
        pkg = _create_full_manifest(tmp_path)
        root = Factory(pkg).create()
        nodes_item = root.header.usages.items[0]
        assert nodes_item.name == "nodes"
        assert nodes_item.annotations.filepath == ".usages/nodes.md"

    def test_usages_inline_text(self, tmp_path) -> None:
        pkg = _create_full_manifest(tmp_path)
        root = Factory(pkg).create()
        yaml_item = root.header.usages.items[1]
        assert yaml_item.name == "yaml"
        # The inline text value contains "pyyaml library for parsing\n"
        assert "pyyaml" in yaml_item.annotations.text


# ---------------------------------------------------------------------------
# 4. Basic parsing — header annotations
# ---------------------------------------------------------------------------


class TestBasicParsingHeaderAnnotations:
    def test_header_annotations_parsed(self, tmp_path) -> None:
        pkg = _create_full_manifest(tmp_path)
        root = Factory(pkg).create()
        assert isinstance(root.header.annotations, AnnotationsNode)
        assert "Global annotations" in root.header.annotations.text


# ---------------------------------------------------------------------------
# 5. Basic parsing — body entity
# ---------------------------------------------------------------------------


class TestBasicParsingBodyEntity:
    def test_entity_parsed(self, tmp_path) -> None:
        pkg = _create_full_manifest(tmp_path)
        root = Factory(pkg).create()
        assert len(root.body.entities) == 1
        entity = root.body.entities[0]
        assert isinstance(entity, EntityTypeNode)

    def test_entity_name_and_signature(self, tmp_path) -> None:
        pkg = _create_full_manifest(tmp_path)
        root = Factory(pkg).create()
        entity = root.body.entities[0]
        assert entity.name == "Project"
        assert entity.signature == "(path: str)"

    def test_entity_location_resolved(self, tmp_path) -> None:
        pkg = _create_full_manifest(tmp_path)
        root = Factory(pkg).create()
        entity = root.body.entities[0]
        expected = str(Path(pkg) / "project.py")
        assert entity.location == expected

    def test_entity_annotations(self, tmp_path) -> None:
        pkg = _create_full_manifest(tmp_path)
        root = Factory(pkg).create()
        entity = root.body.entities[0]
        assert "Loads manifest tree" in entity.annotations.text

    def test_entity_properties(self, tmp_path) -> None:
        pkg = _create_full_manifest(tmp_path)
        root = Factory(pkg).create()
        entity = root.body.entities[0]
        assert len(entity.properties) == 2
        tree_prop = entity.properties[0]
        assert tree_prop.name == "tree"
        assert "list[DocumentRoot]" in tree_prop.type

    def test_entity_methods(self, tmp_path) -> None:
        pkg = _create_full_manifest(tmp_path)
        root = Factory(pkg).create()
        entity = root.body.entities[0]
        assert len(entity.methods) == 1
        load_method = entity.methods[0]
        assert load_method.name == "load"
        assert load_method.signature == "()"

    def test_entity_not_embedded(self, tmp_path) -> None:
        pkg = _create_full_manifest(tmp_path)
        root = Factory(pkg).create()
        entity = root.body.entities[0]
        assert entity.embedded is False
        assert entity.mutations == []


# ---------------------------------------------------------------------------
# 6. Basic parsing — body routine
# ---------------------------------------------------------------------------


class TestBasicParsingBodyRoutine:
    def test_routine_parsed(self, tmp_path) -> None:
        pkg = _create_full_manifest(tmp_path)
        root = Factory(pkg).create()
        assert len(root.body.routines) == 1
        routine = root.body.routines[0]
        assert isinstance(routine, RoutineTypeNode)

    def test_routine_name_and_signature(self, tmp_path) -> None:
        pkg = _create_full_manifest(tmp_path)
        root = Factory(pkg).create()
        routine = root.body.routines[0]
        assert routine.name == "helper"
        assert routine.signature == "(x: int) -> result:int"

    def test_routine_annotations(self, tmp_path) -> None:
        pkg = _create_full_manifest(tmp_path)
        root = Factory(pkg).create()
        routine = root.body.routines[0]
        assert "A helper routine" in routine.annotations.text


# ---------------------------------------------------------------------------
# 7. Basic parsing — footer
# ---------------------------------------------------------------------------


class TestBasicParsingFooter:
    def test_footer_parsed(self, tmp_path) -> None:
        pkg = _create_full_manifest(tmp_path)
        root = Factory(pkg).create()
        assert isinstance(root.footer, FooterNode)

    def test_footer_author(self, tmp_path) -> None:
        pkg = _create_full_manifest(tmp_path)
        root = Factory(pkg).create()
        assert root.footer.author == "Test Author"

    def test_footer_created_at(self, tmp_path) -> None:
        pkg = _create_full_manifest(tmp_path)
        root = Factory(pkg).create()
        assert root.footer.created_at == "11/04/26"

    def test_footer_description(self, tmp_path) -> None:
        pkg = _create_full_manifest(tmp_path)
        root = Factory(pkg).create()
        assert "Test manifest description" in root.footer.description


# ---------------------------------------------------------------------------
# 8. Alias edge cases
# ---------------------------------------------------------------------------


class TestAliasParsing:
    def test_alias_correct(self, tmp_path) -> None:
        """'Type AS Alias' produces type_name={'Type'}, alias='Alias'."""
        yaml_content = """\
Imports:
  - Types:
      - MyType AS MyAlias
    From: some/path

---
---
"""
        pkg = _write_codemanifest(str(tmp_path / "alias_ok"), yaml_content)
        root = Factory(pkg).create()
        item = root.header.imports.types[0]
        assert "MyType" in item.type_name
        assert item.alias == "MyAlias"

    def test_alias_lowercase_as_is_type_name(self, tmp_path) -> None:
        """'TypeWithAs' (lowercase) is treated as a single type name."""
        yaml_content = """\
Imports:
  - Types:
      - TypeWithAs
    From: some/path

---
---
"""
        pkg = _write_codemanifest(str(tmp_path / "alias_lower"), yaml_content)
        root = Factory(pkg).create()
        item = root.header.imports.types[0]
        assert "TypeWithAs" in item.type_name
        assert item.alias == ""

    def test_alias_no_space_before_as(self, tmp_path) -> None:
        """'TypeWithout AS' has space before but no space after AS.

        Since " AS " (with trailing space) is not in the string, the
        factory treats the whole value as a single type name.
        """
        yaml_content = """\
Imports:
  - Types:
      - TypeWithout AS
    From: some/path

---
---
"""
        pkg = _write_codemanifest(str(tmp_path / "alias_nospace"), yaml_content)
        root = Factory(pkg).create()
        item = root.header.imports.types[0]
        # No trailing space after AS -> " AS " not present -> whole string is type
        assert "TypeWithout AS" in item.type_name
        assert item.alias == ""


# ---------------------------------------------------------------------------
# 9. Usages detection (file / url / text)
# ---------------------------------------------------------------------------


class TestUsagesDetection:
    def test_usages_url_detection(self, tmp_path) -> None:
        """URLs starting with http:// or https:// set the url field."""
        yaml_content = """\
Usages:
  docs: https://example.com/docs.md
  local: http://localhost/api.md

---
---
"""
        pkg = _write_codemanifest(str(tmp_path / "usages_url"), yaml_content)
        root = Factory(pkg).create()
        docs_item = root.header.usages.items[0]
        assert docs_item.annotations.url == "https://example.com/docs.md"
        local_item = root.header.usages.items[1]
        assert local_item.annotations.url == "http://localhost/api.md"


# ---------------------------------------------------------------------------
# 10. Entity with mutations but no properties/methods
# ---------------------------------------------------------------------------


class TestEntityWithMutations:
    def test_entity_with_mutations_no_properties(self, tmp_path) -> None:
        """Signature with '::' creates EntityTypeNode with mutations."""
        yaml_content = """\
Imports:
  - Types:
      - DocumentRule
    From: goga/ast/rules

---
"DocumentRule::SomeRule(name: str = 'some_rule')":
  location: rules.py
  annotations: |
    A rule with mutations

---
"""
        pkg = _write_codemanifest(str(tmp_path / "mutations"), yaml_content)
        root = Factory(pkg).create()
        assert len(root.body.entities) == 1
        assert len(root.body.routines) == 0
        entity = root.body.entities[0]
        assert entity.name == "SomeRule"
        assert entity.mutations == [("DocumentRule", pkg)]
        assert entity.embedded is False
        assert entity.properties == []
        assert entity.methods == []


# ---------------------------------------------------------------------------
# 11. Entity with properties but no methods
# ---------------------------------------------------------------------------


class TestEntityWithPropertiesNoMethods:
    def test_dict_with_properties_creates_entity(self, tmp_path) -> None:
        yaml_content = """\
---
---
"MyClass(x: int)":
  location: myclass.py
  properties:
    "value -> int": |
      The value

---
"""
        pkg = _write_codemanifest(str(tmp_path / "props"), yaml_content)
        root = Factory(pkg).create()
        assert len(root.body.entities) == 1
        entity = root.body.entities[0]
        assert entity.name == "MyClass"
        assert len(entity.properties) == 1
        assert entity.properties[0].name == "value"


# ---------------------------------------------------------------------------
# 12. Routine with no properties and no methods
# ---------------------------------------------------------------------------


class TestRoutineNoPropertiesNoMethods:
    def test_plain_string_value_creates_routine(self, tmp_path) -> None:
        yaml_content = """\
---
---
"my_func(x: int) -> int": |
  Computes something

---
"""
        pkg = _write_codemanifest(str(tmp_path / "routine"), yaml_content)
        root = Factory(pkg).create()
        assert len(root.body.routines) == 1
        assert len(root.body.entities) == 0
        routine = root.body.routines[0]
        assert routine.name == "my_func"
        assert routine.signature == "(x: int) -> int"

    def test_dict_without_entity_features_creates_routine(self, tmp_path) -> None:
        """Dict value without properties, methods, or mutations -> routine."""
        yaml_content = """\
---
---
"setup(cfg: str)":
  location: setup.py
  annotations: |
    Setup routine

---
"""
        pkg = _write_codemanifest(str(tmp_path / "dict_routine"), yaml_content)
        root = Factory(pkg).create()
        assert len(root.body.routines) == 1
        assert len(root.body.entities) == 0
        routine = root.body.routines[0]
        assert routine.name == "setup"
        assert "Setup routine" in routine.annotations.text


# ---------------------------------------------------------------------------
# 13. Unknown keys in header/footer raise DocumentParseError
# ---------------------------------------------------------------------------


class TestUnknownKeys:
    def test_unknown_keys_in_header_raises_parse_error(self, tmp_path) -> None:
        yaml_content = """\
UnknownKey: some_value

---
---
"""
        pkg = _write_codemanifest(str(tmp_path / "bad_header"), yaml_content)
        with pytest.raises(DocumentParseError, match="Unknown keys in header"):
            Factory(pkg).create()

    def test_unknown_keys_in_footer_raises_parse_error(self, tmp_path) -> None:
        yaml_content = """\
---
---
---
BogusFooterKey: oops
"""
        pkg = _write_codemanifest(str(tmp_path / "bad_footer"), yaml_content)
        with pytest.raises(DocumentParseError, match="Unknown keys in footer"):
            Factory(pkg).create()


# ---------------------------------------------------------------------------
# 14. Key case sensitivity
# ---------------------------------------------------------------------------


class TestCaseSensitiveKeys:
    def test_lowercase_imports_treated_as_unknown(self, tmp_path) -> None:
        """'imports:' (lowercase) is an unknown header key -> error."""
        yaml_content = """\
imports:
  - Types:
      - Foo
    From: bar

---
---
"""
        pkg = _write_codemanifest(str(tmp_path / "lower_imports"), yaml_content)
        with pytest.raises(DocumentParseError, match="Unknown keys in header"):
            Factory(pkg).create()

    def test_uppercase_imports_is_valid(self, tmp_path) -> None:
        """'Imports:' (uppercase) is valid."""
        yaml_content = """\
Imports:
  - Types:
      - Foo
    From: bar

---
---
"""
        pkg = _write_codemanifest(str(tmp_path / "upper_imports"), yaml_content)
        root = Factory(pkg).create()
        assert len(root.header.imports.types) == 1


# ---------------------------------------------------------------------------
# 15. Location path transformation
# ---------------------------------------------------------------------------


class TestLocationPathTransformation:
    def test_bare_filename_prepends_path(self, tmp_path) -> None:
        yaml_content = """\
---
---
"MyClass()":
  location: base.py
  properties:
    "x -> int": val

---
"""
        pkg_dir = str(tmp_path / "goga" / "codemanifest" / "nodes")
        _write_codemanifest(pkg_dir, yaml_content)
        root = Factory(pkg_dir).create()
        entity = root.body.entities[0]
        expected = str(Path(pkg_dir) / "base.py")
        assert entity.location == expected

    def test_path_with_slash_left_as_is(self, tmp_path) -> None:
        yaml_content = """\
---
---
"MyClass()":
  location: some/deep/path.py
  properties:
    "x -> int": val

---
"""
        pkg = _write_codemanifest(str(tmp_path / "locpath"), yaml_content)
        root = Factory(pkg).create()
        entity = root.body.entities[0]
        assert entity.location == "some/deep/path.py"


# ---------------------------------------------------------------------------
# 16. Deep hierarchy (3 levels)
# ---------------------------------------------------------------------------


class TestDeepHierarchy:
    def test_deep_hierarchy_three_levels(self, tmp_path) -> None:
        """Create CODEMANIFEST at 3 directory levels and wire parents."""
        level1 = str(tmp_path / "level1")
        level2 = str(tmp_path / "level1" / "level2")
        level3 = str(tmp_path / "level1" / "level2" / "level3")

        _write_codemanifest(
            level1,
            """\
---
---
"Root()":
  properties:
    "name -> str": root name
---
Author: L1
""",
        )
        _write_codemanifest(
            level2,
            """\
---
---
"Child()":
  properties:
    "val -> int": child val
---
Author: L2
""",
        )
        _write_codemanifest(
            level3,
            """\
---
---
"Leaf()":
  properties:
    "flag -> bool": leaf flag
---
Author: L3
""",
        )

        root1 = Factory(level1).create()
        root2 = Factory(level2).create(parent=root1)
        root3 = Factory(level3).create(parent=root2)

        assert root1.parent is None
        assert root2.parent is root1
        assert root3.parent is root2

        assert len(root1.body.entities) == 1
        assert root1.body.entities[0].name == "Root"

        assert len(root2.body.entities) == 1
        assert root2.body.entities[0].name == "Child"

        assert len(root3.body.entities) == 1
        assert root3.body.entities[0].name == "Leaf"

    def test_parent_reference_set(self, tmp_path) -> None:
        """Factory.create(parent=...) sets DocumentRoot.parent."""
        parent_dir = str(tmp_path / "parent_pkg")
        child_dir = str(tmp_path / "parent_pkg" / "child_pkg")

        _write_codemanifest(parent_dir, "---\n---\n---\n")
        _write_codemanifest(child_dir, "---\n---\n---\n")

        parent_root = Factory(parent_dir).create()
        child_root = Factory(child_dir).create(parent=parent_root)

        assert child_root.parent is parent_root
        assert parent_root.parent is None


# ---------------------------------------------------------------------------
# 17. All node properties populated
# ---------------------------------------------------------------------------


class TestAllNodePropertiesPopulated:
    def test_document_root_fields(self, tmp_path) -> None:
        pkg = _create_full_manifest(tmp_path)
        root = Factory(pkg).create()
        assert isinstance(root, DocumentRoot)
        assert root.path == pkg
        assert isinstance(root.header, HeaderNode)
        assert isinstance(root.body, BodyNode)
        assert isinstance(root.footer, FooterNode)
        assert isinstance(root.links, dict)
        assert isinstance(root.types, dict)

    def test_root_reference_on_all_nodes(self, tmp_path) -> None:
        """Every sub-node must have root set to the DocumentRoot."""
        pkg = _create_full_manifest(tmp_path)
        root = Factory(pkg).create()

        assert root.header.root is root
        assert root.header.imports.root is root
        for item in root.header.imports.types + root.header.imports.usages:
            assert item.root is root
        assert root.header.usages.root is root
        for item in root.header.usages.items:
            assert item.root is root
        assert root.header.annotations.root is root

        assert root.body.root is root
        for entity in root.body.entities:
            assert entity.root is root
            assert entity.annotations.root is root
            for prop in entity.properties:
                assert prop.root is root
            for method in entity.methods:
                assert method.root is root
        for routine in root.body.routines:
            assert routine.root is root
            assert routine.annotations.root is root

        assert root.footer.root is root

    def test_types_dict_populated(self, tmp_path) -> None:
        pkg = _create_full_manifest(tmp_path)
        root = Factory(pkg).create()
        assert "Project" in root.types
        assert "helper" in root.types
        assert isinstance(root.types["Project"], list)
        assert isinstance(root.types["helper"], list)
        assert isinstance(root.types["Project"][0], EntityTypeNode)
        assert isinstance(root.types["helper"][0], RoutineTypeNode)

    def test_entity_all_fields(self, tmp_path) -> None:
        pkg = _create_full_manifest(tmp_path)
        root = Factory(pkg).create()
        entity = root.body.entities[0]
        assert entity.name == "Project"
        assert entity.signature == "(path: str)"
        assert entity.location == str(Path(pkg) / "project.py")
        assert entity.embedded is False
        assert entity.mutations == []
        assert len(entity.properties) == 2
        assert len(entity.methods) == 1

    def test_property_all_fields(self, tmp_path) -> None:
        pkg = _create_full_manifest(tmp_path)
        root = Factory(pkg).create()
        prop = root.body.entities[0].properties[0]
        assert prop.name == "tree"
        assert "list[DocumentRoot]" in prop.type
        assert "Document tree" in prop.annotations.text

    def test_method_all_fields(self, tmp_path) -> None:
        pkg = _create_full_manifest(tmp_path)
        root = Factory(pkg).create()
        method = root.body.entities[0].methods[0]
        assert method.name == "load"
        assert method.signature == "()"
        assert "Loads the tree" in method.annotations.text

    def test_routine_all_fields(self, tmp_path) -> None:
        pkg = _create_full_manifest(tmp_path)
        root = Factory(pkg).create()
        routine = root.body.routines[0]
        assert routine.name == "helper"
        assert routine.signature == "(x: int) -> result:int"
        assert routine.location == ""
        assert routine.embedded is False

    def test_footer_all_fields(self, tmp_path) -> None:
        pkg = _create_full_manifest(tmp_path)
        root = Factory(pkg).create()
        assert root.footer.author == "Test Author"
        assert root.footer.created_at == "11/04/26"
        assert "Test manifest description" in root.footer.description

    def test_import_item_all_fields(self, tmp_path) -> None:
        pkg = _create_full_manifest(tmp_path)
        root = Factory(pkg).create()
        # Item with alias
        aliased = root.header.imports.types[1]
        assert "DocumentNode" in aliased.type_name
        assert aliased.alias == "Node"
        assert aliased.from_path == "goga/ast/nodes"

    def test_usage_item_all_fields(self, tmp_path) -> None:
        pkg = _create_full_manifest(tmp_path)
        root = Factory(pkg).create()
        item = root.header.usages.items[0]
        assert item.name == "nodes"
        assert item.annotations.filepath == ".usages/nodes.md"
        assert item.annotations.url is None
        assert item.annotations.text == ""


# ---------------------------------------------------------------------------
# 18. Edge cases for uncovered branches
# ---------------------------------------------------------------------------


class TestNonDictSections:
    """YAML sections that parse as non-dict values (strings, numbers)."""

    def test_non_dict_header_treated_as_empty(self, tmp_path) -> None:
        """If the first YAML document is a plain string, header becomes empty dict."""
        yaml_content = "just a string\n---\n---\n"
        pkg = _write_codemanifest(str(tmp_path / "str_header"), yaml_content)
        root = Factory(pkg).create()
        assert len(root.header.imports.types) == 0

    def test_non_dict_body_treated_as_empty(self, tmp_path) -> None:
        """If the second YAML document is a plain string, body becomes empty."""
        yaml_content = "---\njust a string\n---\n"
        pkg = _write_codemanifest(str(tmp_path / "str_body"), yaml_content)
        root = Factory(pkg).create()
        assert len(root.body.entities) == 0
        assert len(root.body.routines) == 0

    def test_non_dict_footer_treated_as_empty(self, tmp_path) -> None:
        """If the third YAML document is a plain string, footer gets defaults."""
        yaml_content = "---\n---\njust a string\n"
        pkg = _write_codemanifest(str(tmp_path / "str_footer"), yaml_content)
        root = Factory(pkg).create()
        assert root.footer.author == ""
        assert root.footer.created_at == ""


class TestNonDictImportsEntry:
    """Imports list entries that are not dicts are skipped."""

    def test_non_dict_import_entry_skipped(self, tmp_path) -> None:
        yaml_content = """\
Imports:
  - plain_string_entry
  - 42
  - Types:
      - ValidType
    From: some/path

---
---
"""
        pkg = _write_codemanifest(str(tmp_path / "non_dict_import"), yaml_content)
        root = Factory(pkg).create()
        assert len(root.header.imports.types) == 1
        assert "ValidType" in root.header.imports.types[0].type_name


class TestNonListTypes:
    """Types field in an import entry that is not a list is skipped."""

    def test_non_list_types_skipped(self, tmp_path) -> None:
        yaml_content = """\
Imports:
  - Types: not_a_list
    From: some/path

---
---
"""
        pkg = _write_codemanifest(str(tmp_path / "non_list_types"), yaml_content)
        root = Factory(pkg).create()
        assert len(root.header.imports.types) == 0


class TestNonDictUsages:
    """Usages section that is not a dict produces empty items."""

    def test_non_dict_usages_empty(self, tmp_path) -> None:
        yaml_content = """\
Usages:
  - item1
  - item2

---
---
"""
        pkg = _write_codemanifest(str(tmp_path / "non_dict_usages"), yaml_content)
        root = Factory(pkg).create()
        assert len(root.header.usages.items) == 0


class TestPropertyWithoutArrow:
    """Property key without ' -> ' uses empty type."""

    def test_property_without_arrow_type(self, tmp_path) -> None:
        yaml_content = """\
---
---
"MyClass()":
  location: myclass.py
  properties:
    simplekey: some annotation

---
"""
        pkg = _write_codemanifest(str(tmp_path / "no_arrow"), yaml_content)
        root = Factory(pkg).create()
        assert len(root.body.entities) == 1
        prop = root.body.entities[0].properties[0]
        assert prop.name == "simplekey"
        assert prop.type == ""


class TestNameWithoutParens:
    """Body key without parentheses -> empty signature."""

    def test_no_parens_empty_signature(self, tmp_path) -> None:
        yaml_content = """\
---
---
my_standalone_func: |
  A standalone function

---
"""
        pkg = _write_codemanifest(str(tmp_path / "no_parens"), yaml_content)
        root = Factory(pkg).create()
        assert len(root.body.routines) == 1
        assert root.body.routines[0].name == "my_standalone_func"
        assert root.body.routines[0].signature == ""


class TestDuplicateTypeNames:
    """Multiple types with the same name are grouped in the types dict."""

    def test_duplicate_type_names_grouped(self, tmp_path) -> None:
        yaml_content = """\
---
---
"MyClass()":
  properties:
    "x -> int": val
"MyClass(x: int)":
  methods:
    "do()": does something

---
"""
        pkg = _write_codemanifest(str(tmp_path / "dup_types"), yaml_content)
        root = Factory(pkg).create()
        assert "MyClass" in root.types
        assert len(root.types["MyClass"]) == 2


class TestAnnotationsWithNoneValue:
    """Annotations that parse as None default to empty string."""

    def test_none_annotations_becomes_empty(self, tmp_path) -> None:
        yaml_content = """\
Imports:
  - Types:
      - Foo
    From: bar
Annotations:

---
"Routine()":
  location: routine.py
  annotations:

---
"""
        pkg = _write_codemanifest(str(tmp_path / "none_ann"), yaml_content)
        root = Factory(pkg).create()
        assert root.header.annotations.text == ""
        assert root.body.routines[0].annotations.text == ""


class TestImportsNotList:
    """Imports value that is not a list raises DocumentParseError."""

    def test_imports_string_raises_error(self, tmp_path) -> None:
        yaml_content = """\
Imports: not_a_list

---
---
"""
        pkg = _write_codemanifest(str(tmp_path / "import_str"), yaml_content)
        with pytest.raises(DocumentParseError, match="Imports must be a list"):
            Factory(pkg).create()


# ---------------------------------------------------------------------------
# 11b. Embedded types via -> prefix
# ---------------------------------------------------------------------------


class TestEmbeddedEntityType:
    """Embedded type via -> prefix is deferred to embeddings, not added to body."""

    def test_embedded_entity_not_in_body(self, tmp_path) -> None:
        yaml_content = """\
Imports:
  - Types:
      - Entity
    From: some/folder

---
"->Entity": {}
"""
        pkg = _write_codemanifest(str(tmp_path / "embedded_entity"), yaml_content)
        root = Factory(pkg).create()
        # Matched embedded entity is now in BOTH embeddings AND body
        assert len(root.body.entities) == 1
        assert len(root.body.routines) == 0
        assert ("Entity", "some/folder") in root.embeddings

    def test_embedded_entity_with_methods_in_embeddings(self, tmp_path) -> None:
        yaml_content = """\
Imports:
  - Types:
      - Service
    From: some/folder

---
"->Service":
  location: service.py
  annotations: |
    Embedded service
  methods:
    "run() -> void:null": |
      Runs the service
"""
        pkg = _write_codemanifest(str(tmp_path / "embedded_service"), yaml_content)
        root = Factory(pkg).create()
        # Matched embedded entity is now in BOTH embeddings AND body
        assert len(root.body.entities) == 1
        assert ("Service", "some/folder") in root.embeddings


class TestEmbeddedRoutineType:
    """Embedded routine via -> prefix is deferred to embeddings, not added to body."""

    def test_embedded_routine_string_value_in_embeddings(self, tmp_path) -> None:
        yaml_content = """\
Imports:
  - Types:
      - helper
    From: some/folder

---
"->helper(x: int) -> result:int": |
  An embedded helper function
"""
        pkg = _write_codemanifest(str(tmp_path / "embedded_routine"), yaml_content)
        root = Factory(pkg).create()
        # Matched embedded routine is now in BOTH embeddings AND body
        assert len(root.body.routines) == 1
        assert len(root.body.entities) == 0
        assert ("helper", "some/folder") in root.embeddings

    def test_embedded_routine_dict_value_in_embeddings(self, tmp_path) -> None:
        """Embedded type with -> prefix is deferred to embeddings."""
        yaml_content = """\
Imports:
  - Types:
      - setup
    From: some/folder

---
"->setup(cfg: str)":
  location: setup.py
  annotations: |
    Embedded setup routine
"""
        pkg = _write_codemanifest(str(tmp_path / "embedded_dict_routine"), yaml_content)
        root = Factory(pkg).create()
        # Matched embedded type is now in BOTH embeddings AND body
        assert len(root.body.entities) == 1
        assert ("setup", "some/folder") in root.embeddings


class TestMutationDoesNotSetEmbedded:
    """Mutation syntax (::) sets mutations but NOT embedded."""

    def test_mutation_entity_not_embedded(self, tmp_path) -> None:
        yaml_content = """\
Imports:
  - Types:
      - BaseType
    From: some/folder

---
"BaseType::Derived()":
  location: derived.py
  annotations: |
    A derived type
  methods:
    "run() -> void:null": |
      Runs
"""
        pkg = _write_codemanifest(str(tmp_path / "mutation_not_embedded"), yaml_content)
        root = Factory(pkg).create()
        assert len(root.body.entities) == 1
        entity = root.body.entities[0]
        assert entity.name == "Derived"
        assert entity.mutations == [("BaseType", pkg)]
        assert entity.embedded is False


# ---------------------------------------------------------------------------
# 11c. Embeddings contract: empty, multiple, unmatched
# ---------------------------------------------------------------------------


class TestEmbeddingsEmpty:
    """embeddings list is empty when no embedded types are present."""

    def test_no_embedded_types_empty_embeddings(self, tmp_path) -> None:
        yaml_content = """\
Imports:
  - Types:
      - SomeType
    From: some/path

---
"NormalEntity()":
  properties:
    "x -> int": value

---
"""
        pkg = _write_codemanifest(str(tmp_path / "no_embedded"), yaml_content)
        root = Factory(pkg).create()
        assert root.embeddings == []
        assert len(root.body.entities) == 1
        assert len(root.body.routines) == 0

    def test_full_manifest_has_no_embeddings(self, tmp_path) -> None:
        """The standard _FULL_MANIFEST fixture has no -> prefixed types."""
        pkg = _create_full_manifest(tmp_path)
        root = Factory(pkg).create()
        assert root.embeddings == []

    def test_minimal_manifest_empty_embeddings(self, tmp_path) -> None:
        yaml_content = "---\n---\n---\n"
        pkg = _write_codemanifest(str(tmp_path / "minimal"), yaml_content)
        root = Factory(pkg).create()
        assert root.embeddings == []


class TestMultipleEmbeddedTypes:
    """Multiple embedded types are all collected correctly into embeddings."""

    def test_multiple_embedded_entities(self, tmp_path) -> None:
        yaml_content = """\
Imports:
  - Types:
      - EntityA
      - EntityB
    From: shared/module

---
"->EntityA":
  location: a.py
  properties:
    "x -> int": value
"->EntityB":
  location: b.py
  methods:
    "run()": runs

---
"""
        pkg = _write_codemanifest(str(tmp_path / "multi_embedded"), yaml_content)
        root = Factory(pkg).create()
        assert len(root.embeddings) == 2
        assert ("EntityA", "shared/module") in root.embeddings
        assert ("EntityB", "shared/module") in root.embeddings
        # Matched embedded entities are now in BOTH embeddings AND body
        assert len(root.body.entities) == 2
        assert len(root.body.routines) == 0

    def test_mixed_embedded_entities_and_routines(self, tmp_path) -> None:
        yaml_content = """\
Imports:
  - Types:
      - Service
    From: svc/module
  - Types:
      - helper
    From: util/module

---
"->Service":
  location: service.py
  methods:
    "start()": starts service
"->helper(x: int) -> result:int": |
  An embedded helper

---
"""
        pkg = _write_codemanifest(str(tmp_path / "mixed_embedded"), yaml_content)
        root = Factory(pkg).create()
        assert len(root.embeddings) == 2
        assert ("Service", "svc/module") in root.embeddings
        assert ("helper", "util/module") in root.embeddings
        # Matched embedded types are now in BOTH embeddings AND body
        assert len(root.body.entities) == 1
        assert len(root.body.routines) == 1

    def test_embedded_routines_from_different_sources(self, tmp_path) -> None:
        yaml_content = """\
Imports:
  - Types:
      - func_a
    From: pkg_a
  - Types:
      - func_b
    From: pkg_b

---
"->func_a()": |
  Func A description
"->func_b(x: str)": |
  Func B description

---
"""
        pkg = _write_codemanifest(str(tmp_path / "multi_routine_embedded"), yaml_content)
        root = Factory(pkg).create()
        assert len(root.embeddings) == 2
        assert ("func_a", "pkg_a") in root.embeddings
        assert ("func_b", "pkg_b") in root.embeddings

    def test_embedded_entity_from_separate_import_entries(self, tmp_path) -> None:
        yaml_content = """\
Imports:
  - Types:
      - TypeA
    From: alpha
  - Types:
      - TypeB
    From: beta

---
"->TypeA": {}
"->TypeB": {}

---
"""
        pkg = _write_codemanifest(str(tmp_path / "sep_imports"), yaml_content)
        root = Factory(pkg).create()
        assert len(root.embeddings) == 2
        assert ("TypeA", "alpha") in root.embeddings
        assert ("TypeB", "beta") in root.embeddings


class TestEmbeddedWithoutImport:
    """Embedded type without a matching import entry is added to body with embedded=True."""

    def test_embedded_entity_no_import_added_to_body(self, tmp_path) -> None:
        yaml_content = """\
---
---
"->OrphanEntity()":
  location: orphan.py
  properties:
    "val -> int": some value
---
"""
        pkg = _write_codemanifest(str(tmp_path / "orphan_entity"), yaml_content)
        root = Factory(pkg).create()
        assert root.embeddings == []
        assert len(root.body.entities) == 1
        entity = root.body.entities[0]
        assert entity.name == "OrphanEntity"
        assert entity.embedded is True
        assert entity.signature == "()"

    def test_embedded_routine_no_import_added_to_body(self, tmp_path) -> None:
        yaml_content = """\
---
---
"->orphan_helper(x: int) -> int": |
  An orphan routine
---
"""
        pkg = _write_codemanifest(str(tmp_path / "orphan_routine"), yaml_content)
        root = Factory(pkg).create()
        assert root.embeddings == []
        assert len(root.body.routines) == 1
        assert len(root.body.entities) == 0
        routine = root.body.routines[0]
        assert routine.name == "orphan_helper"
        assert routine.embedded is True
        assert routine.signature == "(x: int) -> int"

    def test_embedded_dict_routine_no_import_added_to_body(self, tmp_path) -> None:
        """Unmatched embedded type with dict value but no entity features is added as entity."""
        yaml_content = """\
---
---
"->setup(cfg: str)":
  location: setup.py
  annotations: |
    Setup routine
---
"""
        pkg = _write_codemanifest(str(tmp_path / "orphan_dict_routine"), yaml_content)
        root = Factory(pkg).create()
        assert root.embeddings == []
        # Unmatched embedded dict without properties/methods goes through _parse_entity
        # because the -> prefix triggers entity classification
        assert len(root.body.entities) == 1
        assert len(root.body.routines) == 0
        entity = root.body.entities[0]
        assert entity.name == "setup"
        assert entity.embedded is True

    def test_partial_match_only_matched_in_embeddings(self, tmp_path) -> None:
        """One embedded type has import, another does not; they route differently."""
        yaml_content = """\
Imports:
  - Types:
      - Matched
    From: known/path

---
"->Matched": {}
"->Unmatched":
  location: unmatched.py
  properties:
    "x -> str": value

---
"""
        pkg = _write_codemanifest(str(tmp_path / "partial_match"), yaml_content)
        root = Factory(pkg).create()
        assert len(root.embeddings) == 1
        assert ("Matched", "known/path") in root.embeddings
        # Both Matched and Unmatched are in body now (matched + unmatched both in body)
        assert len(root.body.entities) == 2
        entity_names = [e.name for e in root.body.entities]
        assert "Unmatched" in entity_names
        assert "Matched" in entity_names
        unmatched = next(e for e in root.body.entities if e.name == "Unmatched")
        assert unmatched.embedded is True

    def test_embedded_and_normal_coexist(self, tmp_path) -> None:
        """Normal types remain in body alongside embedded types."""
        yaml_content = """\
Imports:
  - Types:
      - EmbeddedType
    From: ext/module

---
"NormalType()":
  location: normal.py
  properties:
    "x -> int": value
"->EmbeddedType": {}

---
"""
        pkg = _write_codemanifest(str(tmp_path / "mixed_normal_embedded"), yaml_content)
        root = Factory(pkg).create()
        assert len(root.embeddings) == 1
        assert ("EmbeddedType", "ext/module") in root.embeddings
        # Both NormalType and EmbeddedType are in body now
        assert len(root.body.entities) == 2
        entity_names = [e.name for e in root.body.entities]
        assert "NormalType" in entity_names
        assert "EmbeddedType" in entity_names
        normal = next(e for e in root.body.entities if e.name == "NormalType")
        assert normal.embedded is False
