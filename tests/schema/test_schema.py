from __future__ import annotations

import copy
import importlib
import inspect
import json
import os
import typing
from collections.abc import Iterator
from pathlib import Path

import pytest
from goga.ast.nodes import (
    BodyNode,
    DocumentRoot,
    EntityTypeNode,
    FooterNode,
    HeaderNode,
    ImportTypeItemNode,
    ImportUsageItemNode,
    RoutineTypeNode,
)
from goga.schema.hooks import SchemaHooks, SchemaNode
from goga.schema.hooks.events import _copy_json
from goga.schema.schema import (
    _build_cell_tree,
    _build_dependencies,
    _cell_in_set,
    _filter_by_depends_on,
    _filter_tree,
    _find_usages_files,
    _has_dependency,
    _prune_by_dependency,
    _prune_depth,
    _to_schema_node,
    schema,
)

from tests.conftest import cwd as _cwd
from tests.schema.conftest import (
    WALK_CHILD,
    WALK_ROOT_WITH_CHILD,
    _install_docs_tool,
    _install_gate_tools,
    _write_codemanifest,
    _write_walk_project,
)

_schema_mod = importlib.import_module("goga.schema.schema")


@pytest.fixture(autouse=True)
def _empty_package_environment(pin_package_environment) -> None:
    """Pin the package environment empty for every test of this module.

    Every non-empty tree the routine builds now delivers the checkpoint
    through the real registry, so an unpinned environment would make the
    output depend on the machine's installed ``goga_tool_*`` packages.
    Tests that install a tool pin their own environment on top — the
    later pin wins.
    """
    pin_package_environment({})


def _make_doc(  # noqa: PLR0913, PLR0917
    path: str,
    entities: list[str] | None = None,
    routines: list[str] | None = None,
    description: str = "",
    children: list[DocumentRoot] | None = None,
    import_types: list[tuple[str, set[str]]] | None = None,
    import_usages: list[tuple[str, set[str]]] | None = None,
) -> DocumentRoot:
    body = BodyNode()
    body.entities = [EntityTypeNode(name=n) for n in (entities or [])]
    body.routines = [RoutineTypeNode(name=n) for n in (routines or [])]

    header = HeaderNode()
    if import_types:
        header.imports.types = [ImportTypeItemNode(from_path=p, type_name=names) for p, names in import_types]
    if import_usages:
        header.imports.usages = [ImportUsageItemNode(from_path=p, usage_name=names) for p, names in import_usages]

    footer = FooterNode(description=description)
    doc = DocumentRoot(
        path=path,
        header=header,
        body=body,
        footer=footer,
        children=children or [],
    )
    for child in doc.children:
        child.parent = doc
    return doc


class TestFindUsagesFiles:
    def test_returns_sorted_md_files(self, tmp_path: Path) -> None:
        usages = tmp_path / ".usages"
        usages.mkdir()
        (usages / "beta.md").write_text("# B", encoding="utf-8")
        (usages / "alpha.md").write_text("# A", encoding="utf-8")
        (usages / "notes.txt").write_text("not md", encoding="utf-8")

        result = _find_usages_files(str(tmp_path))
        assert result == ["alpha.md", "beta.md"]

    def test_returns_empty_for_missing_dir(self, tmp_path: Path) -> None:
        result = _find_usages_files(str(tmp_path / "nonexistent"))
        assert result == []

    def test_returns_empty_for_empty_usages_dir(self, tmp_path: Path) -> None:
        (tmp_path / ".usages").mkdir()
        result = _find_usages_files(str(tmp_path))
        assert result == []


class TestCellInSet:
    def test_cell_in_set_matches_self(self) -> None:
        doc = _make_doc("goga/cell_a")
        assert _cell_in_set(doc, frozenset({"goga/cell_a"})) is True

    def test_matches_child(self) -> None:
        child = _make_doc("goga/cell_b")
        parent = _make_doc("goga/cell_a", children=[child])
        assert _cell_in_set(parent, frozenset({"goga/cell_b"})) is True

    def test_cell_in_set_no_match(self) -> None:
        doc = _make_doc("goga/cell_a")
        assert _cell_in_set(doc, frozenset({"goga/cell_z"})) is False


class TestBuildDependencies:
    def test_build_dependencies_types_and_usages(self) -> None:
        doc = _make_doc(
            "goga/cell",
            import_types=[("goga/other", {"EntityA"})],
            import_usages=[("goga/other", {"usage_x"})],
        )
        result = _build_dependencies(doc)
        assert "goga/other" in result
        assert result["goga/other"]["types"] == ["EntityA"]
        assert result["goga/other"]["usages"] == ["usage_x"]

    def test_deduplicates_and_sorts(self) -> None:
        doc = _make_doc(
            "goga/cell",
            import_types=[
                ("goga/lib", {"A", "B"}),
                ("goga/lib", {"B", "C"}),
            ],
        )
        result = _build_dependencies(doc)
        assert result["goga/lib"]["types"] == ["A", "B", "C"]

    def test_empty_imports(self) -> None:
        doc = _make_doc("goga/cell")
        result = _build_dependencies(doc)
        assert result == {}


class TestBuildCellTree:
    def test_build_cell_tree_basic_structure(self) -> None:
        doc = _make_doc("goga/cell", entities=["E1"], routines=["R1"], description="desc")
        result = _build_cell_tree(doc)
        assert result["cell"] == os.path.normpath("goga/cell")
        assert result["description"] == "desc"
        assert "E1" in result["types"]
        assert "R1" in result["types"]
        assert result["children"] == []

    def test_nested_children(self) -> None:
        child = _make_doc("goga/cell/child", entities=["ChildE"])
        parent = _make_doc("goga/cell", children=[child])
        result = _build_cell_tree(parent)
        assert len(result["children"]) == 1
        assert result["children"][0]["cell"] == os.path.normpath("goga/cell/child")

    def test_allowed_cells_filters(self) -> None:
        child_a = _make_doc("goga/cell/a")
        child_b = _make_doc("goga/cell/b")
        parent = _make_doc("goga/cell", children=[child_a, child_b])
        result = _build_cell_tree(
            parent,
            allowed_cells=frozenset({os.path.normpath("goga/cell/a")}),
        )
        assert len(result["children"]) == 1
        assert result["children"][0]["cell"] == os.path.normpath("goga/cell/a")


class TestPruneDepth:
    def test_depth_0_removes_children(self) -> None:
        cell = {"cell": "root", "children": [{"cell": "child", "children": []}]}
        result = _prune_depth(cell, 0)
        assert result["children"] == []
        assert result["cell"] == "root"

    def test_prune_depth_1_keeps_first_level(self) -> None:
        cell = {
            "cell": "root",
            "children": [
                {
                    "cell": "child",
                    "children": [{"cell": "grandchild", "children": []}],
                }
            ],
        }
        result = _prune_depth(cell, 1)
        assert len(result["children"]) == 1
        assert result["children"][0]["children"] == []

    def test_unlimited_depth(self) -> None:
        cell = {
            "cell": "root",
            "children": [{"cell": "child", "children": [{"cell": "gc", "children": []}]}],
        }
        result = _prune_depth(cell, 5)
        assert len(result["children"]) == 1
        assert len(result["children"][0]["children"]) == 1


class TestFilterTree:
    def test_no_cells_returns_all(self) -> None:
        docs = [_make_doc("a"), _make_doc("b")]
        result = _filter_tree(docs, [])
        assert len(result) == 2

    def test_filters_by_cell_path(self) -> None:
        docs = [_make_doc("a"), _make_doc("b")]
        result = _filter_tree(docs, ["a"])
        assert len(result) == 1
        assert os.path.normpath(result[0].path) == os.path.normpath("a")

    def test_keeps_parent_if_child_matches(self) -> None:
        child = _make_doc("parent/child")
        parent = _make_doc("parent", children=[child])
        result = _filter_tree([parent], ["parent/child"])
        assert len(result) == 1


class TestHasDependency:
    def test_matches_direct_dep(self) -> None:
        cell = {"dependencies": {"goga/lib": {"types": [], "usages": []}}, "children": []}
        assert _has_dependency(cell, frozenset({"goga/lib"})) is True

    def test_no_match(self) -> None:
        cell = {"dependencies": {}, "children": []}
        assert _has_dependency(cell, frozenset({"goga/lib"})) is False

    def test_matches_child_dep(self) -> None:
        cell = {
            "dependencies": {},
            "children": [{"dependencies": {"goga/lib": {"types": [], "usages": []}}, "children": []}],
        }
        assert _has_dependency(cell, frozenset({"goga/lib"})) is True


class TestFilterByDependsOn:
    def test_no_filter(self) -> None:
        cells = [{"cell": "a", "dependencies": {}, "children": []}]
        assert _filter_by_depends_on(cells, []) == cells

    def test_filters_matching(self) -> None:
        cells = [
            {"cell": "a", "dependencies": {"goga/lib": {}}, "children": []},
            {"cell": "b", "dependencies": {}, "children": []},
        ]
        result = _filter_by_depends_on(cells, ["goga/lib"])
        assert len(result) == 1
        assert result[0]["cell"] == "a"

    def test_prunes_non_matching_children_of_matching_root(self) -> None:
        cells = [
            {
                "cell": "root",
                "dependencies": {"goga/lib": {"types": [], "usages": []}},
                "children": [
                    {"cell": "depends", "dependencies": {"goga/lib": {"types": [], "usages": []}}, "children": []},
                    {"cell": "no_dep", "dependencies": {}, "children": []},
                ],
            },
        ]
        result = _filter_by_depends_on(cells, ["goga/lib"])
        assert len(result) == 1
        kept_children = [c["cell"] for c in result[0]["children"]]
        assert kept_children == ["depends"]

    def test_keeps_skeleton_path_to_dependent_descendant(self) -> None:
        cells = [
            {
                "cell": "root",
                "dependencies": {},
                "children": [
                    {
                        "cell": "mid",
                        "dependencies": {},
                        "children": [
                            {"cell": "leaf", "dependencies": {"goga/lib": {"types": [], "usages": []}}, "children": []},
                            {"cell": "leaf_no_dep", "dependencies": {}, "children": []},
                        ],
                    },
                    {"cell": "sibling_no_dep", "dependencies": {}, "children": []},
                ],
            },
        ]
        result = _filter_by_depends_on(cells, ["goga/lib"])
        assert len(result) == 1
        assert result[0]["cell"] == "root"
        assert len(result[0]["children"]) == 1
        mid = result[0]["children"][0]
        assert mid["cell"] == "mid"
        kept_leaves = [c["cell"] for c in mid["children"]]
        assert kept_leaves == ["leaf"]

    def test_no_match_returns_empty(self) -> None:
        cells = [{"cell": "root", "dependencies": {}, "children": []}]
        result = _filter_by_depends_on(cells, ["goga/absent"])
        assert result == []


class TestPruneByDependency:
    def test_keeps_dependent_child_and_prunes_other(self) -> None:
        cell = {
            "cell": "root",
            "dependencies": {},
            "children": [
                {"cell": "dep", "dependencies": {"goga/lib": {"types": [], "usages": []}}, "children": []},
                {"cell": "no_dep", "dependencies": {}, "children": []},
            ],
        }
        result = _prune_by_dependency(cell, frozenset({"goga/lib"}))
        kept = [c["cell"] for c in result["children"]]
        assert kept == ["dep"]

    def test_preserves_other_node_fields(self) -> None:
        cell = {
            "cell": "root",
            "description": "desc",
            "types": ["E1"],
            "dependencies": {"goga/lib": {"types": ["T"], "usages": []}},
            "children": [],
        }
        result = _prune_by_dependency(cell, frozenset({"goga/lib"}))
        assert result["description"] == "desc"
        assert result["types"] == ["E1"]
        assert result["dependencies"] == {"goga/lib": {"types": ["T"], "usages": []}}


FUNCTION_EMPTY_IMPORTS_CELL = """\
Imports: []

Usages: {}

Annotations: ""

---
"Helper()":
  location: helper.py
  annotations: |
    A helper

---
Author: Test
CreatedAt: 01/01/01
Description: Sub package
"""

FUNCTION_LEAF_CELL = """\
Usages: {}

Annotations: ""

---
"LeafEntity()":
  location: leaf_entity.py
  annotations: ""

---
Author: Test
CreatedAt: 01/01/01
Description: Leaf cell
"""

FUNCTION_UNICODE_CELL = """\
Usages: {}

Annotations: ""

---
"Helper()":
  location: helper.py
  annotations: |
    A helper

---
Author: Test
CreatedAt: 01/01/01
Description: Описание ячейки
"""

FUNCTION_DEP_PROVIDER = """\
Usages: {}

Annotations: ""

---
"Thing()":
  location: thing.py
  annotations: ""

---
Author: Test
CreatedAt: 01/01/01
Description: Dep cell
"""

FUNCTION_CELL_WITH_DEP = """\
Imports:
  - Types:
      - Thing
    From: dep

Usages: {}

Annotations: |
  Uses `Thing` here

---
"CellEntity()":
  location: cell_entity.py
  annotations: ""

---
Author: Test
CreatedAt: 01/01/01
Description: Cell with dep
"""

FUNCTION_LIB_PROVIDER = """\
Usages: {}

Annotations: ""

---
"A()":
  location: a.py
  annotations: ""
"B()":
  location: b.py
  annotations: ""
"C()":
  location: c.py
  annotations: ""

---
Author: Test
CreatedAt: 01/01/01
Description: Lib cell
"""

FUNCTION_DEDUP_ROOT = """\
Imports:
  - Types:
      - A
      - B
      - C
    From: lib
  - Usages:
      - u1
    From: lib

Usages: {}

Annotations: |
  Uses `A`, `B`, `C` and `u1`

---
"MyClass()":
  location: myclass.py
  annotations: |
    A test class

---
Author: Test
CreatedAt: 01/01/01
Description: Root cell
"""


class TestSchemaFunction:
    """The routine over real CODEMANIFEST trees under ``tmp_path``.

    The parser (``goga.ast``) runs for real — the walk, the filters, and
    the serialization are asserted over trees the real loader builds,
    with manifest text the real rule set accepts (or, for the error
    paths, rejects a deterministic number of times).
    """

    def test_empty_tree_returns_empty_json(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)

        result = schema([], None, [])

        assert json.loads(result) == []

    def test_ast_errors_raises_value_error(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # `Imports: []` — one real rule violation (imports_can_not_be_empty).
        _write_codemanifest(tmp_path, FUNCTION_EMPTY_IMPORTS_CELL)
        monkeypatch.chdir(tmp_path)

        with pytest.raises(ValueError, match="AST parsing failed with 1 error"):
            schema([], None, [])

    def test_full_tree_produces_json(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _write_codemanifest(tmp_path, WALK_ROOT_WITH_CHILD)
        subpkg = tmp_path / "subpkg"
        subpkg.mkdir()
        _write_codemanifest(subpkg, WALK_CHILD)
        monkeypatch.chdir(tmp_path)

        result = schema([], None, [])

        data = json.loads(result)
        assert len(data) == 1
        assert data[0]["cell"] == os.path.normpath(".")
        assert data[0]["description"] == "Root cell"
        assert "MyClass" in data[0]["types"]

    def test_schema_cells_filter(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        cell_a = tmp_path / "a"
        cell_a.mkdir()
        _write_codemanifest(cell_a, FUNCTION_LEAF_CELL)
        cell_b = tmp_path / "b"
        cell_b.mkdir()
        _write_codemanifest(cell_b, FUNCTION_LEAF_CELL)
        monkeypatch.chdir(tmp_path)

        result = schema(["a"], None, [])

        data = json.loads(result)
        assert len(data) == 1
        assert data[0]["cell"] == "a"

    def test_depends_on_filter(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        dep = tmp_path / "dep"
        dep.mkdir()
        _write_codemanifest(dep, FUNCTION_DEP_PROVIDER)
        cell_dir = tmp_path / "cell"
        cell_dir.mkdir()
        _write_codemanifest(cell_dir, FUNCTION_CELL_WITH_DEP)
        other = tmp_path / "other"
        other.mkdir()
        _write_codemanifest(other, FUNCTION_LEAF_CELL)
        monkeypatch.chdir(tmp_path)

        result = schema([], None, ["dep"])

        data = json.loads(result)
        assert len(data) == 1
        assert data[0]["cell"] == "cell"

    def test_schema_max_depth_prunes(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _write_codemanifest(tmp_path, WALK_ROOT_WITH_CHILD)
        subpkg = tmp_path / "subpkg"
        subpkg.mkdir()
        _write_codemanifest(subpkg, WALK_CHILD)
        monkeypatch.chdir(tmp_path)

        result = schema([], 0, [])

        data = json.loads(result)
        assert data[0]["children"] == []

    def test_combined_filters(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        dep = tmp_path / "dep"
        dep.mkdir()
        _write_codemanifest(dep, FUNCTION_DEP_PROVIDER)
        _write_codemanifest(tmp_path, FUNCTION_CELL_WITH_DEP)
        subpkg = tmp_path / "subpkg"
        subpkg.mkdir()
        _write_codemanifest(subpkg, WALK_CHILD)
        monkeypatch.chdir(tmp_path)

        result = schema([], 1, ["dep"])

        data = json.loads(result)
        assert len(data) == 1
        assert data[0]["cell"] == os.path.normpath(".")
        # children have no dependency on dep and no dependent descendants → pruned
        assert data[0]["children"] == []

    def test_schema_json_is_pretty_formatted(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _write_codemanifest(tmp_path, WALK_ROOT_WITH_CHILD)
        subpkg = tmp_path / "subpkg"
        subpkg.mkdir()
        _write_codemanifest(subpkg, WALK_CHILD)
        monkeypatch.chdir(tmp_path)

        result = schema([], None, [])

        assert "    " in result
        parsed = json.loads(result)
        assert parsed == json.loads(json.dumps(parsed, indent=4, sort_keys=True, ensure_ascii=False))

    def test_unicode_description(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _write_codemanifest(tmp_path, FUNCTION_UNICODE_CELL)
        monkeypatch.chdir(tmp_path)

        result = schema([], None, [])

        assert "Описание ячейки" in result

    def test_multiple_ast_errors(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # Three malformed documents — one real rule violation each.
        for name in ("bad_one", "bad_two", "bad_three"):
            bad = tmp_path / name
            bad.mkdir()
            _write_codemanifest(bad, FUNCTION_EMPTY_IMPORTS_CELL)
        monkeypatch.chdir(tmp_path)

        with pytest.raises(ValueError, match="3 error"):
            schema([], None, [])

    def test_deduplicated_dependencies(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        lib = tmp_path / "lib"
        lib.mkdir()
        _write_codemanifest(lib, FUNCTION_LIB_PROVIDER)
        (lib / ".usages").mkdir()
        (lib / ".usages" / "u1.md").write_text("usage", encoding="utf-8")
        _write_codemanifest(tmp_path, FUNCTION_DEDUP_ROOT)
        monkeypatch.chdir(tmp_path)

        result = schema([], None, [])

        data = json.loads(result)
        deps = data[0]["dependencies"]
        assert deps["lib"]["types"] == ["A", "B", "C"]
        assert deps["lib"]["usages"] == ["u1"]


# --- The checkpoint delivery of the generation walk ---
# The walk tests below build CODEMANIFEST trees under ``tmp_path`` (the
# ``tests/commands/test_schema.py`` fixture style) and pin the platform
# environment boundary through the fixtures of ``tests/schema/conftest.py``
# — the registry, the delivery, and the walk run for real. The tree
# scaffolding itself lives in ``tests/schema/conftest.py``.


class TestWalkCheckpointContract:
    def test_schema_importable_from_the_facade(self) -> None:
        from goga.schema import schema as facade_schema

        assert facade_schema is schema


FILTERS_ROOT = """\
Usages: {}

Annotations: ""

---
"RootEntity()":
  location: root.py
  annotations: ""

---
Author: Test
CreatedAt: 01/01/01
Description: Root
"""

FILTERS_PKG = """\
Usages: {}

Annotations: ""

---
"PkgEntity()":
  location: pkg.py
  annotations: ""

---
Author: Test
CreatedAt: 01/01/01
Description: Package cell
"""

FILTERS_SUB_A = """\
Imports:
  - Types:
      - LibType
    From: lib

Usages: {}

Annotations: |
  Uses `LibType` here

---
"SubAEntity()":
  location: sub_a.py
  annotations: ""

---
Author: Test
CreatedAt: 01/01/01
Description: Sub cell A
"""

FILTERS_SUB_B = """\
Usages: {}

Annotations: ""

---
"SubBEntity()":
  location: sub_b.py
  annotations: ""

---
Author: Test
CreatedAt: 01/01/01
Description: Sub cell B
"""

FILTERS_LEAF = """\
Usages: {}

Annotations: ""

---
"LeafEntity()":
  location: leaf.py
  annotations: ""

---
Author: Test
CreatedAt: 01/01/01
Description: Leaf cell
"""

FILTERS_LIB = """\
Usages: {}

Annotations: ""

---
"LibType()":
  location: lib.py
  annotations: ""

---
Author: Test
CreatedAt: 01/01/01
Description: Lib cell
"""


def _pre_order(nodes: list[dict]) -> Iterator[dict]:
    for node in nodes:
        yield node
        yield from _pre_order(node["children"])


def test_schema_output_byte_identical_without_subscriptions(
    tmp_path: Path,
    pin_package_environment,
    install_tool_package,
) -> None:
    _write_codemanifest(tmp_path, WALK_ROOT_WITH_CHILD)
    (tmp_path / ".usages").mkdir()
    (tmp_path / ".usages" / "spec.md").write_text("test", encoding="utf-8")
    subpkg = tmp_path / "subpkg"
    subpkg.mkdir()
    _write_codemanifest(subpkg, WALK_CHILD)
    (subpkg / ".usages").mkdir()
    (subpkg / ".usages" / "helper.md").write_text("test", encoding="utf-8")

    boundary_a = pin_package_environment({})

    with _cwd(tmp_path):
        output_a = schema([], None, [])

    def read_only(context) -> None:
        _ = context.cell.path  # subscribed but silent: reads the facts, contributes nothing

    boundary_b = _install_docs_tool(pin_package_environment, install_tool_package, read_only)

    with _cwd(tmp_path):
        output_b = schema([], None, [])

    assert '"tools"' not in output_a
    assert '"tools"' not in output_b
    assert output_a == output_b
    assert boundary_a.call_count == 1
    assert boundary_b.call_count == 1


def test_schema_empty_tree_skips_enumeration_entirely(
    tmp_path: Path,
    pin_package_environment,
    install_tool_package,
) -> None:
    def contribute(context) -> None:
        context.contribute({"x": 1})

    boundary = _install_docs_tool(pin_package_environment, install_tool_package, contribute)

    with _cwd(tmp_path):
        result = schema([], None, [])

    assert result == "[]"
    assert boundary.call_count == 0


@pytest.mark.parametrize(
    ("cells", "max_depth", "depends_on"),
    [
        pytest.param(["pkg"], None, [], id="cells"),
        pytest.param([], 1, [], id="max_depth"),
        pytest.param([], None, ["lib"], id="depends_on"),
        pytest.param(["pkg"], None, ["lib"], id="combined"),
    ],
)
def test_filters_prune_delivery_exactly_as_output(  # noqa: PLR0913, PLR0917
    tmp_path: Path,
    pin_package_environment,
    install_tool_package,
    cells: list[str],
    max_depth: int | None,
    depends_on: list[str],
) -> None:
    _write_codemanifest(tmp_path, FILTERS_ROOT)
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    _write_codemanifest(pkg, FILTERS_PKG)
    sub_a = pkg / "sub_a"
    sub_a.mkdir()
    _write_codemanifest(sub_a, FILTERS_SUB_A)
    sub_b = pkg / "sub_b"
    sub_b.mkdir()
    _write_codemanifest(sub_b, FILTERS_SUB_B)
    lib = tmp_path / "lib"
    lib.mkdir()
    _write_codemanifest(lib, FILTERS_LIB)

    delivered: list[str] = []

    def record(context) -> None:
        delivered.append(context.cell.path)

    _install_docs_tool(pin_package_environment, install_tool_package, record)

    with _cwd(tmp_path):
        result = schema(cells, max_depth, depends_on)

    data = json.loads(result)
    assert len(delivered) == len(set(delivered))  # every surviving cell delivered exactly once
    assert set(delivered) == {node["cell"] for node in _pre_order(data)}


def test_delivered_facts_carry_authored_children_under_max_depth(
    tmp_path: Path,
    pin_package_environment,
    install_tool_package,
) -> None:
    _write_codemanifest(tmp_path, FILTERS_ROOT)
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    _write_codemanifest(pkg, FILTERS_PKG)
    leaf = pkg / "leaf"
    leaf.mkdir()
    _write_codemanifest(leaf, FILTERS_LEAF)

    recorded: dict[str, list[str]] = {}

    def record(context) -> None:
        recorded[context.cell.path] = list(context.cell.children)

    _install_docs_tool(pin_package_environment, install_tool_package, record)

    with _cwd(tmp_path):
        result = schema([], 1, [])

    data = json.loads(result)
    pkg_node = data[0]["children"][0]
    assert pkg_node["children"] == []  # pruned from the output
    assert recorded["pkg"] == [os.path.normpath("pkg/leaf")]  # the authored projection


def test_delivered_facts_mirror_the_authored_cell(
    tmp_path: Path,
    pin_package_environment,
    install_tool_package,
) -> None:
    """The checkpoint reads the authored projection — every facts field mirrors the authored manifests.

    Pins all six delivered fields against the authored CODEMANIFEST
    documents (and, where the shapes align, against the serialized
    node's own base fields) — not only the paths and children the other
    walk tests read.
    """
    _write_codemanifest(tmp_path, WALK_ROOT_WITH_CHILD)
    (tmp_path / ".usages").mkdir()
    (tmp_path / ".usages" / "spec.md").write_text("test", encoding="utf-8")
    subpkg = tmp_path / "subpkg"
    subpkg.mkdir()
    _write_codemanifest(subpkg, WALK_CHILD)

    recorded: dict[str, dict] = {}

    def record(context) -> None:
        cell = context.cell
        recorded[cell.path] = {
            "description": cell.description,
            "types": list(cell.types),
            "usages": list(cell.usages),
            "dependencies": [(d.path, list(d.types), list(d.usages)) for d in cell.dependencies],
            "children": list(cell.children),
        }

    _install_docs_tool(pin_package_environment, install_tool_package, record)

    with _cwd(tmp_path):
        result = schema([], None, [])

    root_path = os.path.normpath(".")
    assert set(recorded) == {root_path, "subpkg"}  # both authored cells delivered

    root = recorded[root_path]
    assert root["description"] == "Root cell"
    assert root["types"] == ["MyClass"]
    assert root["usages"] == ["spec.md"]
    assert root["dependencies"] == [("subpkg", ["Helper"], [])]
    assert root["children"] == ["subpkg"]

    child = recorded["subpkg"]
    assert child["description"] == "Sub package"
    assert child["types"] == ["Helper"]
    assert child["usages"] == []
    assert child["dependencies"] == []
    assert child["children"] == []

    # The facts mirror the serialized node's own base fields.
    node = json.loads(result)[0]
    assert root["description"] == node["description"]
    assert root["types"] == node["types"]
    assert root["usages"] == node["usages"]
    assert root["children"] == [child_node["cell"] for child_node in node["children"]]
    assert node["dependencies"]["subpkg"] == {"types": ["Helper"], "usages": []}


def test_schema_hard_failure_propagates_without_partial_output(
    tmp_path: Path,
    pin_package_environment,
    install_tool_package,
) -> None:
    _write_codemanifest(tmp_path, WALK_ROOT_WITH_CHILD)
    subpkg = tmp_path / "subpkg"
    subpkg.mkdir()
    _write_codemanifest(subpkg, WALK_CHILD)

    invocations: list[str] = []

    def explode(context) -> None:
        invocations.append(context.cell.path)
        if len(invocations) == 2:
            raise RuntimeError("kaput")

    _install_docs_tool(pin_package_environment, install_tool_package, explode)

    with (
        _cwd(tmp_path),
        pytest.raises(ValueError, match=r"failed on schema\.amend_cell at subpkg: kaput"),
    ):
        schema([], None, [])

    assert invocations == [os.path.normpath("."), "subpkg"]  # the failure names the second cell, not the first


# --- The validation gate of the generation walk (schema/validate_schema) ---


class TestGateWiringContract:
    def test_schema_keeps_the_declared_signature(self) -> None:
        """The gate is a step of the walk, not a re-sign of the routine."""
        parameters = inspect.signature(schema).parameters

        assert list(parameters) == ["cells", "max_depth", "depends_on"]
        assert typing.get_type_hints(schema)["return"] is str

    def test_module_carries_the_gate_wiring_imports(self) -> None:
        """The module imports the projection record and the overlay copier of the hooks zone."""
        assert _schema_mod.SchemaNode is SchemaNode
        assert _schema_mod._copy_json is _copy_json


def test_schema_empty_tree_returns_early_no_gate(
    tmp_path: Path,
    pin_package_environment,
    install_tool_package,
) -> None:
    """The emptied tree returns "[]" before any checkpoint — a vetoing tool never runs."""
    _write_walk_project(tmp_path)
    invoked: list[str] = []

    def register(hooks: object) -> None:
        def veto(context) -> None:
            invoked.append("veto")
            context.veto("the gate fired")

        hooks.subscribe("schema", "validate_schema", "veto", veto)  # type: ignore[attr-defined]

    _install_gate_tools(pin_package_environment, install_tool_package, {"alpha": register})

    with _cwd(tmp_path):
        result = schema(["nonexistent-cell"], None, [])

    assert result == "[]"
    assert invoked == []


def test_gate_leaves_caller_tree_untouched_after_run(
    pin_package_environment,
    install_tool_package,
) -> None:
    """The gate↔domain boundary: an approved walk mutates nothing the caller handed in.

    A real projection — ``_to_schema_node`` over a small final dict tree,
    the committed tools overlay included — goes through the gate with a
    subscribing tool that only reads. The verdict approves, and the
    caller's records are the same objects with the same contents: deep
    equality against a pre-run snapshot and identity of the handed-in
    nodes both hold.
    """
    small_dict_tree: list[dict] = [
        {
            "cell": ".",
            "description": "Root cell",
            "types": ["MyClass"],
            "usages": ["spec.md"],
            "dependencies": {"subpkg": {"types": ["Helper"], "usages": []}},
            "children": [
                {
                    "cell": "subpkg",
                    "description": "Sub package",
                    "types": ["Helper"],
                    "usages": [],
                    "dependencies": {},
                    "children": [],
                },
            ],
            "tools": {"alpha": {"nested": {"k": 1}}},
        },
    ]
    nodes = [_to_schema_node(node) for node in small_dict_tree]
    snapshot = copy.deepcopy(nodes)
    handed_in = [id(node) for node in nodes] + [id(child) for child in nodes[0].children]

    def register_alpha(hooks: object) -> None:
        def read_only(context) -> None:
            _ = context.tree[0].path  # subscribed but silent: reads the tree, vetoes nothing
            _ = context.tree[0].tools["alpha"]["nested"]["k"]

        hooks.subscribe("schema", "validate_schema", "read_only", read_only)  # type: ignore[attr-defined]

    _install_gate_tools(pin_package_environment, install_tool_package, {"alpha": register_alpha})

    verdict = SchemaHooks().validate_schema(nodes)

    assert verdict.approved is True
    assert nodes == snapshot  # deep equality — no field moved anywhere in the tree
    assert [id(node) for node in nodes] + [id(child) for child in nodes[0].children] == handed_in


def test_gate_tuple_carried_overlay_value_is_not_shared_with_the_caller(
    pin_package_environment,
    install_tool_package,
) -> None:
    """A tuple-carried overlay value copies as a list — never shared with the caller.

    The commit point admits a tuple as a list, so a committed overlay may
    carry one; a copy that passed the tuple through by identity would
    share its nested containers with the caller's projection, and a
    hostile validator's in-place write would reach them — piercing the
    mutual-blindness guarantee the gate exists to hold. The copy delivers
    a fresh list instead — JSON-identical, since the view represents the
    serialized result where a tuple and a list are one array.
    """
    small_dict_tree: list[dict] = [
        {
            "cell": ".",
            "description": "Root cell",
            "types": ["MyClass"],
            "usages": [],
            "dependencies": {},
            "children": [],
            "tools": {"alpha": {"items": ("a", {"k": 1})}},
        },
    ]
    nodes = [_to_schema_node(node) for node in small_dict_tree]
    snapshot = copy.deepcopy(nodes)

    def register_alpha(hooks: object) -> None:
        def hostile(context) -> None:
            # A write through the tuple-carried container — it must stay
            # local to this tool's view and die with it.
            context.tree[0].tools["alpha"]["items"][1]["k"] = 2

        hooks.subscribe("schema", "validate_schema", "hostile", hostile)  # type: ignore[attr-defined]

    _install_gate_tools(pin_package_environment, install_tool_package, {"alpha": register_alpha})

    verdict = SchemaHooks().validate_schema(nodes)

    assert verdict.approved is True
    assert nodes == snapshot
    assert nodes[0].tools["alpha"]["items"][1]["k"] == 1
