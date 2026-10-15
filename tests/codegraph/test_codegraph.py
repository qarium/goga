"""Contract and logic tests for the ``codegraph`` orchestrator of ``goga/codegraph``.

Routine under test (declared in ``goga/codegraph/CODEMANIFEST`` with
``location: codegraph.py``):

- ``codegraph(cells, max_depth, depends_on) -> list[CodegraphNode]`` — load
  the project configuration, validate the language, discover the sources, run
  the three analysis stages in order, and assemble the node tree.

The scenarios build real trees on ``tmp_path`` (cwd pinned by the autouse
``_isolate_cwd`` fixture) — no mocks, the pipeline runs for real.
"""

from __future__ import annotations

import hashlib
import textwrap
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

from goga.codegraph.facts import CodegraphNode

GOLDEN_OUTPUT = textwrap.dedent("""\
    [
        {
            "cell": "greeting",
            "children": [],
            "dependencies": {},
            "tools": {},
            "types": [
                "hello"
            ]
        }
    ]
""").strip()


def _write_config(language: str, ignore: list[str] | None = None) -> None:
    """Write a minimal ``.goga/config.yml`` with the given language and lint ignores."""
    goga_dir = Path(".goga")
    goga_dir.mkdir(exist_ok=True)
    lines = [f"language: {language}\n"]

    if ignore is not None:
        lines.append("lint:\n  ignore:\n")
        lines.extend(f"    - {entry}\n" for entry in ignore)

    (goga_dir / "config.yml").write_text("".join(lines), encoding="utf-8")


def _snapshot_tree() -> dict[str, str]:
    """Snapshot the project tree — relative file paths to content hashes."""
    snapshot: dict[str, str] = {}

    for path in sorted(Path().rglob("*")):
        if path.is_file():
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            snapshot[path.as_posix()] = digest

    return snapshot


_MANIFEST_TEMPLATE = """\
Usages: {{}}

Annotations: ""

---
{body}
---
Author: Test
CreatedAt: 01/01/01
Description: {description}
"""


def _write_codemanifest(package: Path, declarations: list[str]) -> None:
    """Write a minimal routine-declaring CODEMANIFEST into ``package``."""
    entries = [f'"{name}()":\n  location: __init__.py\n  annotations: |\n    A test routine' for name in declarations]
    manifest = _MANIFEST_TEMPLATE.format(body="\n".join(entries), description=package.name)
    (package / "CODEMANIFEST").write_text(manifest, encoding="utf-8")


def _write_nested_project() -> None:
    """Write the nested project — the ``lib`` cell with its ``lib/inner`` child cell."""
    _write_config("python")

    lib = Path("lib")
    lib.mkdir()
    (lib / "__init__.py").write_text("def thing() -> None:\n    return\n", encoding="utf-8")
    _write_codemanifest(lib, ["thing"])

    inner = lib / "inner"
    inner.mkdir()
    (inner / "__init__.py").write_text("def run() -> None:\n    return\n", encoding="utf-8")
    _write_codemanifest(inner, ["run"])


def _walk_tree(nodes: list[CodegraphNode]) -> Iterator[CodegraphNode]:
    """Yield every node of the tree in pre-order — the node, then its children."""
    for node in nodes:
        yield node
        yield from _walk_tree(node.children)


def _strip_tools(nodes: list[CodegraphNode]) -> list[CodegraphNode]:
    """Rebuild the tree without the tools overlays — the base-field equality view."""
    return [replace(node, tools={}, children=_strip_tools(node.children)) for node in nodes]


class TestCodegraphCheckpointContract:
    """Contract: the routine delivers the node amendment and returns the amended records."""

    def test_codegraph_returns_amended_records_with_contributed_tools(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """A contributing tool's facts land on the returned records; base fields unchanged."""
        from goga.codegraph import codegraph

        pin_package_environment({"goga_tool_docs": ["docs-dist"]})

        def register(hooks: object) -> None:
            def cover(context: object) -> None:
                context.contribute({"coverage": 3})

            hooks.subscribe("codegraph", "amend_node", "cover", cover)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_docs", register_hooks=register)

        _write_nested_project()

        result = codegraph([], None, [])

        assert isinstance(result, list)
        assert all(isinstance(node, CodegraphNode) for node in result)
        assert all(node.tools == {"docs": {"coverage": 3}} for node in _walk_tree(result))

        pin_package_environment({})

        assert _strip_tools(result) == codegraph([], None, [])


class TestCodegraphCheckpointDelivery:
    """Design scenarios: the surviving nodes are delivered, the overlays are placed."""

    def test_codegraph_delivers_every_surviving_node_in_tree_order_with_complete_children(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """The cells filter prunes the delivery, never the facts — a pruned child stays named."""
        from goga.codegraph import codegraph

        pin_package_environment({"goga_tool_watch": ["watch-dist"]})
        delivered: list[tuple[str, list[str]]] = []

        def register(hooks: object) -> None:
            def watch(context: object) -> None:
                delivered.append((context.node.cell, list(context.node.children)))

            hooks.subscribe("codegraph", "amend_node", "watch", watch)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_watch", register_hooks=register)

        _write_nested_project()

        result = codegraph(["lib"], None, [])

        assert [cell for cell, _ in delivered] == ["lib"]
        assert [children for _, children in delivered] == [["lib/inner"]]

        assert [node.cell for node in result] == ["lib"]
        assert [node.cell for node in result[0].children] == []
        assert all(node.tools == {} for node in _walk_tree(result))

    def test_codegraph_places_overlays_and_returns_the_gated_tree(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """A contributing tool's overlay lands on every node; the base fields stay untouched."""
        from goga.codegraph import codegraph

        pin_package_environment({"goga_tool_docs": ["docs-dist"]})

        def register(hooks: object) -> None:
            def cover(context: object) -> None:
                context.contribute({"coverage": 3})

            hooks.subscribe("codegraph", "amend_node", "cover", cover)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_docs", register_hooks=register)

        _write_nested_project()

        result = codegraph([], None, [])

        assert [node.cell for node in result] == ["lib"]
        assert [node.cell for node in result[0].children] == ["lib/inner"]
        assert all(node.tools == {"docs": {"coverage": 3}} for node in _walk_tree(result))

        pin_package_environment({})

        assert _strip_tools(result) == codegraph([], None, [])


class TestCodegraphCheckpointFailures:
    """Design scenarios: the vetoed gate and the hard amendment failure propagate."""

    def test_codegraph_vetoed_gate_raises_one_merged_error_and_returns_no_tree(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """A vetoed gate is one merged ValueError — the tree was assembled first, never returned."""
        import pytest
        from goga.codegraph import codegraph

        pin_package_environment({"goga_tool_docs": ["docs-dist"], "goga_tool_gate": ["gate-dist"]})

        def register_docs(hooks: object) -> None:
            def cover(context: object) -> None:
                context.contribute({"coverage": 3})

            hooks.subscribe("codegraph", "amend_node", "cover", cover)  # type: ignore[attr-defined]

        def register_gate(hooks: object) -> None:
            def vetoer(context: object) -> None:
                context.veto("shape broken")

            hooks.subscribe("codegraph", "validate_graph", "vetoer", vetoer)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_docs", register_hooks=register_docs)
        install_tool_package("goga_tool_gate", register_hooks=register_gate)

        _write_nested_project()

        with pytest.raises(ValueError, match=r"codegraph validation failed:") as excinfo:
            codegraph([], None, [])

        assert "- tool gate / hook vetoer: shape broken" in str(excinfo.value)

    def test_codegraph_hard_amendment_failure_propagates_from_the_routine(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """A crashed amendment hook stops the routine — the failing node cell path is named."""
        import pytest
        from goga.codegraph import codegraph

        pin_package_environment({"goga_tool_docs": ["docs-dist"]})

        def register(hooks: object) -> None:
            def boom(context: object) -> None:
                raise RuntimeError("kaboom")

            hooks.subscribe("codegraph", "amend_node", "boom", boom)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_docs", register_hooks=register)

        _write_nested_project()

        with pytest.raises(ValueError, match=r"failed on codegraph\.amend_node at lib: kaboom"):
            codegraph([], None, [])


class TestCodegraphCheckpointEdges:
    """Design scenario: the empty tree returns before any checkpoint fires."""

    def test_codegraph_empty_project_returns_empty_before_any_checkpoint(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """A config-only project returns [] — no delivery, no gate, no enumeration side effects."""
        from goga.codegraph import codegraph

        pin_package_environment({"goga_tool_watch": ["watch-dist"]})
        calls: list[str] = []

        def register(hooks: object) -> None:
            def on_amend(context: object) -> None:
                calls.append("amend_node")

            def on_gate(context: object) -> None:
                calls.append("validate_graph")

            hooks.subscribe("codegraph", "amend_node", "on_amend", on_amend)  # type: ignore[attr-defined]
            hooks.subscribe("codegraph", "validate_graph", "on_gate", on_gate)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_watch", register_hooks=register)

        _write_config("python")

        assert codegraph([], None, []) == []
        assert calls == []


class TestCodegraph:
    """Facade and call contract of the orchestrator."""

    def test_codegraph_importable_from_facade(self) -> None:
        """``codegraph`` is importable from the codegraph cell facade."""
        from goga.codegraph import codegraph  # noqa: F401

    def test_codegraph_facade_all_exact(self) -> None:
        """The facade exposes exactly the three orchestrator-cell routines."""
        import goga.codegraph

        assert goga.codegraph.__all__ == ["codegraph", "discover_sources", "render_graph"]

    def test_codegraph_callable_no_arguments(self) -> None:
        """``codegraph`` is callable with no arguments and returns a node list."""
        from goga.codegraph import codegraph
        from goga.codegraph.facts import CodegraphNode

        _write_config("python")

        result = codegraph()

        assert isinstance(result, list)
        assert all(isinstance(node, CodegraphNode) for node in result)


class TestCodegraphEndToEnd:
    """Design scenario: the golden project renders the golden document."""

    def test_codegraph_end_to_end_golden_output(self) -> None:
        """The greeting package renders as the single golden root node."""
        import json
        from dataclasses import asdict

        from goga.codegraph import codegraph

        _write_config("python")

        greeting = Path("greeting")
        greeting.mkdir()
        (greeting / "__init__.py").write_text(
            '__all__ = ["hello"]\nfrom .impl import hello\n',
            encoding="utf-8",
        )
        (greeting / "impl.py").write_text(
            "def hello() -> str:\n    return 'hi'\n",
            encoding="utf-8",
        )

        assert [asdict(node) for node in codegraph()] == json.loads(GOLDEN_OUTPUT)

        assert codegraph() == codegraph()


class TestCodegraphFailures:
    """Design scenarios: the failure modes propagate uncaught."""

    def test_codegraph_uninitialized_project(self) -> None:
        """An absent ``.goga/config.yml`` raises FileNotFoundError."""
        import pytest
        from goga.codegraph import codegraph

        with pytest.raises(FileNotFoundError):
            codegraph()

    def test_codegraph_unsupported_language(self) -> None:
        """A language outside the whitelist raises ValueError naming it."""
        import pytest
        from goga.codegraph import codegraph

        _write_config("rust")

        with pytest.raises(ValueError, match="rust"):
            codegraph()


class TestCodegraphLintIgnore:
    """Design scenario: the lint exclusion list prunes the source discovery."""

    def test_codegraph_lint_ignore_prunes_discovery(self) -> None:
        """A package under an ignored directory renders no cell."""
        from goga.codegraph import codegraph

        _write_config("python", ignore=["generated"])

        greeting = Path("greeting")
        greeting.mkdir()
        (greeting / "__init__.py").write_text("def hello():\n    pass\n", encoding="utf-8")

        generated = Path("generated/vendored")
        generated.mkdir(parents=True)
        (generated / "__init__.py").write_text("def vendored():\n    pass\n", encoding="utf-8")

        assert [node.cell for node in codegraph()] == ["greeting"]


class TestCodegraphEmptyProject:
    """Design scenario: no analyzable units render as the empty list."""

    def test_render_graph_empty_project_renders_empty_list(self) -> None:
        """A loose non-unit file yields no units and the output is ``[]``."""
        from goga.codegraph import codegraph

        _write_config("python")
        Path("loose.py").write_text("def anything():\n    pass\n", encoding="utf-8")

        assert codegraph() == []


class TestCodegraphReadOnly:
    """Design scenario: the run leaves the project tree unchanged."""

    def test_codegraph_read_only(self) -> None:
        """The file set and file contents are identical before and after."""
        from goga.codegraph import codegraph

        _write_config("python")

        greeting = Path("greeting")
        greeting.mkdir()
        (greeting / "__init__.py").write_text(
            '__all__ = ["hello"]\nfrom .impl import hello\n',
            encoding="utf-8",
        )
        (greeting / "impl.py").write_text(
            "def hello() -> str:\n    return 'hi'\n",
            encoding="utf-8",
        )

        before = _snapshot_tree()

        codegraph()

        assert _snapshot_tree() == before
