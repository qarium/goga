"""Contract and logic tests for ``render_graph`` of ``goga/codegraph``.

Routine under test (declared in ``goga/codegraph/CODEMANIFEST`` with
``location: render.py``):

- ``render_graph(units, links, cells, max_depth, depends_on)
  -> list[CodegraphNode]`` — assemble the hierarchical node tree from the
  flat units (structural compression: only cell units carry nodes, non-cell
  units survive as ancestors), aggregate the links into per-node
  dependencies, apply the three schema-parity filters in order.

Pure logic over records — no filesystem, no mocks.
"""

from __future__ import annotations

from dataclasses import fields
from pathlib import Path

from goga.codegraph.facts import CellLink, CodegraphNode, Unit


def _find_root(tree: list[CodegraphNode], cell: str) -> CodegraphNode:
    """Return the forest root node with the given cell path."""
    return next(node for node in tree if node.cell == cell)


class TestRenderGraph:
    """Facade and call contract of the graph renderer."""

    def test_render_graph_importable_from_facade(self) -> None:
        """``render_graph`` is importable from the codegraph cell facade."""
        from goga.codegraph import render_graph  # noqa: F401

    def test_render_graph_returns_unserialized_object_tree(self) -> None:
        """No units and no links render as the empty node list."""
        from goga.codegraph import render_graph
        from goga.codegraph.facts import CodegraphNode

        result = render_graph(units=[], links=[], cells=[], max_depth=None, depends_on=[])

        assert result == []
        assert all(isinstance(node, CodegraphNode) for node in result)


class TestRenderGraphNesting:
    """Design scenario: nesting, structural compression, dependencies."""

    def test_render_graph_nesting_compression_and_dependencies(self) -> None:
        """Non-cell ancestors compress out; links aggregate into node dependencies."""
        from goga.codegraph import render_graph

        units = [
            Unit(path=Path("app"), facade=["Boot"], is_cell=True),
            Unit(path=Path("app/lib"), facade=[], is_cell=False),
            Unit(path=Path("app/lib/db"), facade=["connect"], is_cell=True),
            Unit(path=Path("standalone"), facade=["solo"], is_cell=True),
        ]
        links = [CellLink(source=Path("app/lib/db"), target=Path("app"), types=["Boot"])]

        tree = render_graph(units, links, [], None, [])

        assert [node.cell for node in tree] == ["app", "standalone"]

        child = tree[0].children[0]

        assert child.cell == "app/lib/db"
        assert child.dependencies == {"app": ["Boot"]}
        assert len(tree[0].children) == 1
        assert {field.name for field in fields(tree[0])} == {"cell", "types", "dependencies", "children", "tools"}
        assert render_graph(units, links, [], None, []) == tree


class TestRenderGraphFilterParity:
    """Design scenario: cells, depends_on, and max_depth — schema parity."""

    def test_render_graph_filter_parity_cells_depends_on_depth(self) -> None:
        """The three filters in order mirror the schema output semantics."""
        from goga.codegraph import render_graph

        units = [
            Unit(path=Path("root"), facade=["RootType"], is_cell=True),
            Unit(path=Path("ext"), facade=["ExtType"], is_cell=True),
            Unit(path=Path("root/mid"), facade=["MidType"], is_cell=True),
            Unit(path=Path("root/mid/leaf"), facade=["LeafType"], is_cell=True),
        ]
        links = [CellLink(source=Path("root/mid/leaf"), target=Path("ext"), types=["ExtType"])]

        def cells_in_tree(tree: list[CodegraphNode]) -> set[str]:
            found: set[str] = set()

            def walk(nodes: list[CodegraphNode]) -> None:
                for node in nodes:
                    found.add(node.cell)
                    walk(node.children)

            walk(tree)

            return found

        case1 = render_graph(units, links, ["root/mid/leaf"], None, [])

        assert cells_in_tree(case1) == {"root", "root/mid", "root/mid/leaf"}

        case2 = render_graph(units, links, [], None, ["ext"])

        assert cells_in_tree(case2) == {"root", "root/mid", "root/mid/leaf"}

        leaf = _find_root(case2, "root").children[0].children[0]

        assert leaf.dependencies == {"ext": ["ExtType"]}

        case3 = render_graph(units, links, [], 1, [])
        root3 = _find_root(case3, "root")

        assert len(root3.children) == 1
        assert root3.children[0].children == []

        case4 = render_graph(units, links, [], 0, [])
        root4 = _find_root(case4, "root")

        assert root4.children == []
