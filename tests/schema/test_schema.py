from __future__ import annotations

import importlib
import json
import os
from collections.abc import Iterator
from pathlib import Path
from unittest import mock

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
    schema,
)

from tests.conftest import cwd as _cwd

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
    def test_matches_self(self) -> None:
        doc = _make_doc("goga/cell_a")
        assert _cell_in_set(doc, frozenset({"goga/cell_a"})) is True

    def test_matches_child(self) -> None:
        child = _make_doc("goga/cell_b")
        parent = _make_doc("goga/cell_a", children=[child])
        assert _cell_in_set(parent, frozenset({"goga/cell_b"})) is True

    def test_no_match(self) -> None:
        doc = _make_doc("goga/cell_a")
        assert _cell_in_set(doc, frozenset({"goga/cell_z"})) is False


class TestBuildDependencies:
    def test_types_and_usages(self) -> None:
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
    def test_basic_structure(self) -> None:
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

    def test_depth_1_keeps_first_level(self) -> None:
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


class TestSchemaFunction:
    def test_empty_tree_returns_empty_json(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        with mock.patch.object(_schema_mod, "AST") as mock_ast_cls:
            mock_ast = mock.MagicMock()
            mock_ast.tree = []
            mock_ast.errors = []
            mock_ast_cls.return_value = mock_ast
            result = schema([], None, [])
        assert json.loads(result) == []

    def test_ast_errors_raises_value_error(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        with mock.patch.object(_schema_mod, "AST") as mock_ast_cls:
            mock_ast = mock.MagicMock()
            mock_ast.errors = ["some error"]
            mock_ast_cls.return_value = mock_ast
            with pytest.raises(ValueError, match="AST parsing failed with 1 error"):
                schema([], None, [])

    def test_full_tree_produces_json(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        doc = _make_doc("goga/cell", entities=["E1"], description="test cell")
        monkeypatch.chdir(tmp_path)
        with mock.patch.object(_schema_mod, "AST") as mock_ast_cls:
            mock_ast = mock.MagicMock()
            mock_ast.tree = [doc]
            mock_ast.errors = []
            mock_ast_cls.return_value = mock_ast
            result = schema([], None, [])
        data = json.loads(result)
        assert len(data) == 1
        assert data[0]["cell"] == os.path.normpath("goga/cell")
        assert data[0]["description"] == "test cell"
        assert "E1" in data[0]["types"]

    def test_cells_filter(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        doc_a = _make_doc("goga/a")
        doc_b = _make_doc("goga/b")
        monkeypatch.chdir(tmp_path)
        with mock.patch.object(_schema_mod, "AST") as mock_ast_cls:
            mock_ast = mock.MagicMock()
            mock_ast.tree = [doc_a, doc_b]
            mock_ast.errors = []
            mock_ast_cls.return_value = mock_ast
            result = schema(["goga/a"], None, [])
        data = json.loads(result)
        assert len(data) == 1
        assert data[0]["cell"] == os.path.normpath("goga/a")

    def test_depends_on_filter(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        doc_with_dep = _make_doc(
            "goga/cell",
            import_types=[("goga/dep", {"SomeType"})],
        )
        doc_without_dep = _make_doc("goga/other")
        monkeypatch.chdir(tmp_path)
        with mock.patch.object(_schema_mod, "AST") as mock_ast_cls:
            mock_ast = mock.MagicMock()
            mock_ast.tree = [doc_with_dep, doc_without_dep]
            mock_ast.errors = []
            mock_ast_cls.return_value = mock_ast
            result = schema([], None, ["goga/dep"])
        data = json.loads(result)
        assert len(data) == 1
        assert data[0]["cell"] == os.path.normpath("goga/cell")

    def test_max_depth_prunes(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        child = _make_doc("goga/cell/child")
        parent = _make_doc("goga/cell", children=[child])
        monkeypatch.chdir(tmp_path)
        with mock.patch.object(_schema_mod, "AST") as mock_ast_cls:
            mock_ast = mock.MagicMock()
            mock_ast.tree = [parent]
            mock_ast.errors = []
            mock_ast_cls.return_value = mock_ast
            result = schema([], 0, [])
        data = json.loads(result)
        assert data[0]["children"] == []

    def test_combined_filters(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        child = _make_doc("goga/cell/child")
        parent = _make_doc(
            "goga/cell",
            import_types=[("goga/dep", {"T"})],
            children=[child],
        )
        monkeypatch.chdir(tmp_path)
        with mock.patch.object(_schema_mod, "AST") as mock_ast_cls:
            mock_ast = mock.MagicMock()
            mock_ast.tree = [parent]
            mock_ast.errors = []
            mock_ast_cls.return_value = mock_ast
            result = schema([], 1, ["goga/dep"])
        data = json.loads(result)
        assert len(data) == 1
        assert data[0]["cell"] == os.path.normpath("goga/cell")
        # child has no dependency on goga/dep and no dependent descendants → pruned
        assert data[0]["children"] == []

    def test_json_is_pretty_formatted(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        doc = _make_doc("goga/cell")
        monkeypatch.chdir(tmp_path)
        with mock.patch.object(_schema_mod, "AST") as mock_ast_cls:
            mock_ast = mock.MagicMock()
            mock_ast.tree = [doc]
            mock_ast.errors = []
            mock_ast_cls.return_value = mock_ast
            result = schema([], None, [])
        assert "    " in result
        parsed = json.loads(result)
        assert parsed == json.loads(json.dumps(parsed, indent=4, sort_keys=True, ensure_ascii=False))

    def test_unicode_description(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        doc = _make_doc("goga/cell", description="Описание ячейки")
        monkeypatch.chdir(tmp_path)
        with mock.patch.object(_schema_mod, "AST") as mock_ast_cls:
            mock_ast = mock.MagicMock()
            mock_ast.tree = [doc]
            mock_ast.errors = []
            mock_ast_cls.return_value = mock_ast
            result = schema([], None, [])
        assert "Описание ячейки" in result

    def test_multiple_ast_errors(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        with mock.patch.object(_schema_mod, "AST") as mock_ast_cls:
            mock_ast = mock.MagicMock()
            mock_ast.errors = ["err1", "err2", "err3"]
            mock_ast_cls.return_value = mock_ast
            with pytest.raises(ValueError, match="3 error"):
                schema([], None, [])

    def test_deduplicated_dependencies(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        doc = _make_doc(
            "goga/cell",
            import_types=[
                ("goga/lib", {"A", "B"}),
                ("goga/lib", {"B", "C"}),
            ],
            import_usages=[
                ("goga/lib", {"u1"}),
            ],
        )
        monkeypatch.chdir(tmp_path)
        with mock.patch.object(_schema_mod, "AST") as mock_ast_cls:
            mock_ast = mock.MagicMock()
            mock_ast.tree = [doc]
            mock_ast.errors = []
            mock_ast_cls.return_value = mock_ast
            result = schema([], None, [])
        data = json.loads(result)
        deps = data[0]["dependencies"]
        assert deps["goga/lib"]["types"] == ["A", "B", "C"]
        assert deps["goga/lib"]["usages"] == ["u1"]


# --- The checkpoint delivery of the generation walk ---
# The walk tests below build CODEMANIFEST trees under ``tmp_path`` (the
# ``tests/commands/test_schema.py`` fixture style) and pin the platform
# environment boundary through the fixtures of ``tests/schema/conftest.py``
# — the registry, the delivery, and the walk run for real.


def _write_codemanifest(directory: Path, content: str) -> None:
    (directory / "CODEMANIFEST").write_text(content, encoding="utf-8")


WALK_ROOT_WITH_CHILD = """\
Imports:
  - Types:
      - Helper
    From: subpkg

Usages: {}

Annotations: |
  Uses `Helper` here

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

WALK_CHILD = """\
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


def _install_docs_tool(
    pin_package_environment,
    install_tool_package,
    hook,
):
    """Pin the environment to one docs tool and install its facade carrying ``hook``.

    Args:
        pin_package_environment: the boundary-pinning fixture factory.
        install_tool_package: the package-installing fixture factory.
        hook: the hook subscribed to the ``schema.amend_cell`` address.

    Returns:
        The boundary mock — the installed-packages read of the run.
    """
    boundary = pin_package_environment({"goga_tool_docs": ["docs-dist"]})

    def register(registrar: object) -> None:
        registrar.subscribe("schema", "amend_cell", "cover", hook)  # type: ignore[attr-defined]

    install_tool_package("goga_tool_docs", register_hooks=register)
    return boundary


class TestWalkCheckpointContract:
    def test_schema_importable_from_the_facade(self) -> None:
        from goga.schema import schema as facade_schema

        assert facade_schema is schema

    def test_schema_walk_places_tools_on_nodes(
        self,
        tmp_path: Path,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        _write_codemanifest(tmp_path, WALK_ROOT_WITH_CHILD)
        subpkg = tmp_path / "subpkg"
        subpkg.mkdir()
        _write_codemanifest(subpkg, WALK_CHILD)

        def cover(context) -> None:
            context.contribute({"score": 3})

        _install_docs_tool(pin_package_environment, install_tool_package, cover)

        with _cwd(tmp_path):
            result = schema([], None, [])

        data = json.loads(result)
        assert data[0]["tools"] == {"docs": {"score": 3}}


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


def test_schema_walk_places_tools_and_keeps_base_fields(
    tmp_path: Path,
    pin_package_environment,
    install_tool_package,
) -> None:
    _write_codemanifest(tmp_path, WALK_ROOT_WITH_CHILD)
    subpkg = tmp_path / "subpkg"
    subpkg.mkdir()
    _write_codemanifest(subpkg, WALK_CHILD)

    def cover(context) -> None:
        context.contribute({"score": 3})

    _install_docs_tool(pin_package_environment, install_tool_package, cover)

    with _cwd(tmp_path):
        result = schema([], None, [])

    data = json.loads(result)
    assert data[0]["tools"] == {"docs": {"score": 3}}
    assert data[0]["children"][0]["tools"] == {"docs": {"score": 3}}
    assert set(data[0].keys()) == {"cell", "children", "dependencies", "description", "tools", "types", "usages"}


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
