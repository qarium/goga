from __future__ import annotations

import json
import os
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
    _prune_depth,
    schema,
)

import importlib
_schema_mod = importlib.import_module("goga.schema.schema")


def _make_doc(  # noqa: PLR0913
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
        assert len(data[0]["children"]) == 1
        assert data[0]["children"][0]["children"] == []

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
