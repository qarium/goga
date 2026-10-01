"""End-to-end walk and gate flows of the schema generation — cross-package.

The cross-package half of ``tests/schema/test_schema.py``: the real
``goga.ast`` parser over ``tmp_path`` CODEMANIFEST trees, the real
``goga.hooks`` registry with fake ``goga_tool_*`` packages, and the
``goga.schema.hooks`` checkpoint delivery and validation gate, asserting the
JSON output of ``goga.schema.schema``. The scaffolding (the manifest writer,
the two-cell fixture tree, the tool installers) lives in
``tests/schema/conftest.py`` and is shared with the zone suite.
"""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path

import pytest
from goga.schema.hooks import DependencyFacts, SchemaNode
from goga.schema.schema import schema

from tests.conftest import cwd as _cwd
from tests.schema.conftest import (
    WALK_CHILD,
    WALK_ROOT_WITH_CHILD,
    _install_docs_tool,
    _install_gate_tools,
    _write_codemanifest,
    _write_walk_project,
)


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


# --- the checkpoint delivery of the generation walk, cross-package ---


def test_schema_walk_places_tools_on_nodes(
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


# --- the validation gate of the generation walk, cross-package ---


GATE_GOLDEN = """[
    {
        "cell": ".",
        "children": [
            {
                "cell": "subpkg",
                "children": [],
                "dependencies": {},
                "description": "Sub package",
                "types": [
                    "Helper"
                ],
                "usages": []
            }
        ],
        "dependencies": {
            "subpkg": {
                "types": [
                    "Helper"
                ],
                "usages": []
            }
        },
        "description": "Root cell",
        "types": [
            "MyClass"
        ],
        "usages": []
    }
]"""


def test_schema_gate_no_subscriptions_byte_identical(
    tmp_path: Path,
    pin_package_environment,
) -> None:
    """No tool packages — the gate approves and the output stays the recorded golden, byte for byte."""
    _write_walk_project(tmp_path)
    pin_package_environment({})

    with _cwd(tmp_path):
        result = schema([], None, [])

    assert result == GATE_GOLDEN
    assert '"tools"' not in result
    assert json.loads(result) == json.loads(GATE_GOLDEN)


def test_schema_gate_veto_raises_merged_error_listing_every_violation(
    tmp_path: Path,
    pin_package_environment,
    install_tool_package,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A vetoed gate raises one merged error — one line per violation, every tool listed, nothing printed."""
    _write_walk_project(tmp_path)

    def register_alpha(hooks: object) -> None:
        def veto_alpha(context) -> None:
            context.veto("cell goga/x: broken")

        hooks.subscribe("schema", "validate_schema", "veto_alpha", veto_alpha)  # type: ignore[attr-defined]

    def register_beta(hooks: object) -> None:
        def crash_beta(context) -> None:
            raise ValueError("nope")

        hooks.subscribe("schema", "validate_schema", "crash_beta", crash_beta)  # type: ignore[attr-defined]

    def register_gamma(hooks: object) -> None:
        def veto_gamma(context) -> None:
            context.veto("   ")

        hooks.subscribe("schema", "validate_schema", "veto_gamma", veto_gamma)  # type: ignore[attr-defined]

    _install_gate_tools(
        pin_package_environment,
        install_tool_package,
        {"alpha": register_alpha, "beta": register_beta, "gamma": register_gamma},
    )

    with _cwd(tmp_path), pytest.raises(ValueError, match=r"schema validation failed:") as excinfo:
        schema([], None, [])

    message = str(excinfo.value)
    assert message.startswith("schema validation failed:")
    assert "- tool alpha / hook veto_alpha: cell goga/x: broken" in message
    assert "- tool beta / hook crash_beta: nope" in message
    assert "- tool gamma / hook veto_gamma:    " in message  # the whitespace reason renders verbatim
    assert message.count("\n") == 3  # exactly one line per violation

    captured = capsys.readouterr()
    assert captured.out == ""


def test_gate_delivers_the_projected_filtered_tree_with_the_committed_overlay(
    tmp_path: Path,
    pin_package_environment,
    install_tool_package,
) -> None:
    """The validator observes the real projection — every field, the filters, and the overlay.

    One tool contributes through ``amend_cell`` and observes through
    ``validate_schema``: the delivered view must be the walk's own final
    projection (the authored fields rebuilt as ``SchemaNode`` records, a
    swapped field would surface here), the ``cells`` filter must reach
    the view (the validator sees the filtered tree, never the unfiltered
    one), and the committed overlay must be visible in the view while
    the JSON output carries it under ``tools`` as committed.
    """
    _write_walk_project(tmp_path)
    seen: list[list[SchemaNode]] = []

    def register_alpha(hooks: object) -> None:
        def contribute(context) -> None:
            if context.cell.path == os.path.normpath("."):
                context.contribute({"score": 3, "tags": ("docs", {"nested": True})})

        def observe(context) -> None:
            seen.append(copy.deepcopy(context.tree))

        hooks.subscribe("schema", "amend_cell", "contribute", contribute)  # type: ignore[attr-defined]
        hooks.subscribe("schema", "validate_schema", "observe", observe)  # type: ignore[attr-defined]

    _install_gate_tools(pin_package_environment, install_tool_package, {"alpha": register_alpha})

    with _cwd(tmp_path):
        result = schema([], None, [])

    assert len(seen) == 1  # the gate fires exactly once
    assert len(seen[0]) == 1  # one root — the child nests under it
    root = seen[0][0]
    assert len(root.children) == 1
    child = root.children[0]
    assert root.path == os.path.normpath(".")
    assert root.description == "Root cell"
    assert root.types == ["MyClass"]
    assert root.usages == []
    assert root.dependencies == [DependencyFacts(path="subpkg", types=["Helper"], usages=[])]
    assert [node.path for node in root.children] == ["subpkg"]
    assert root.tools == {"alpha": {"score": 3, "tags": ["docs", {"nested": True}]}}  # the tuple copies as a list

    assert child.path == "subpkg"
    assert child.description == "Sub package"
    assert child.types == ["Helper"]
    assert child.dependencies == []
    assert child.children == []
    assert child.tools == {}  # no contribution committed on the child — no empty overlay key

    data = json.loads(result)
    assert data[0]["tools"] == {"alpha": {"score": 3, "tags": ["docs", {"nested": True}]}}
    assert "tools" not in data[0]["children"][0]

    # The depth filter reaches the delivered view — the validator sees the
    # pruned tree, never the unfiltered one.
    seen.clear()
    with _cwd(tmp_path):
        schema([], 0, [])

    assert len(seen) == 1
    assert [node.path for node in seen[0]] == [os.path.normpath(".")]
    assert seen[0][0].children == []
