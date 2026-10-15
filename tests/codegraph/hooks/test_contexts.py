"""Contract and logic tests for the entity declared in
``goga/codegraph/hooks/CODEMANIFEST`` with ``location: contexts.py``:

- ``GraphValidation(tree)`` — the gate's delivered view of one tool: the
  read-only final tree plus the veto buffer of this tool alone

Supported data only — no mocks, no filesystem: the view carries the
constructed tree verbatim and buffers the veto of this tool alone; the
delivery proxy closes the tree against attribute writes while ``veto``
passes through.
"""

from __future__ import annotations

import dataclasses
import typing

import pytest
from goga.hooks import wrap_context

from tests.conftest import is_kw_only_dataclass


@pytest.fixture
def tree() -> list[object]:
    """A minimal final tree — one leaf node, no tools overlay."""
    from goga.codegraph.facts import CodegraphNode

    return [
        CodegraphNode(
            cell="goga/config",
            types=["ProjectConfig"],
            dependencies={"goga/hooks": ["HookRegistry"]},
            children=[],
        )
    ]


# --- Contract tests ---


class TestGraphValidationContract:
    def test_view_is_importable_from_the_facade(self) -> None:
        """The name lives on the zone facade and resolves to ``contexts.py``."""
        import goga.codegraph.hooks as facade
        from goga.codegraph.hooks.contexts import GraphValidation

        assert facade.GraphValidation is GraphValidation
        assert "GraphValidation" in facade.__all__
        assert facade.__all__ == sorted(facade.__all__)

    def test_view_is_kw_only_and_not_frozen(self) -> None:
        """The buffer must be writable — the proxy, not frozen-ness, closes the tree."""
        from goga.codegraph.hooks import GraphValidation

        assert dataclasses.is_dataclass(GraphValidation)
        assert is_kw_only_dataclass(GraphValidation)
        assert not GraphValidation.__dataclass_params__.frozen

        with pytest.raises(TypeError):
            GraphValidation([])  # type: ignore[misc]

    def test_view_carries_exactly_the_declared_fields(self, tree: list[object]) -> None:
        """``tree`` plus the private ``init=False`` buffer, excluded from ``repr``."""
        from goga.codegraph.hooks import GraphValidation

        assert [field.name for field in dataclasses.fields(GraphValidation)] == ["tree", "_veto"]

        declared = dataclasses.fields(GraphValidation)[0]
        buffer = dataclasses.fields(GraphValidation)[-1]

        assert declared.init
        assert declared.default is dataclasses.MISSING
        assert declared.default_factory is dataclasses.MISSING

        assert buffer.init is False
        assert buffer.default is None
        assert buffer.repr is False

        view = GraphValidation(tree=tree)

        assert view._veto is None
        assert "_veto" not in repr(view)

    def test_view_annotates_the_declared_property_types(self) -> None:
        """The field carries the contract property type."""
        from goga.codegraph.facts import CodegraphNode
        from goga.codegraph.hooks import GraphValidation

        hints = typing.get_type_hints(GraphValidation)

        assert hints["tree"] == list[CodegraphNode]

    def test_veto_is_callable(self, tree: list[object]) -> None:
        """``veto`` is a method — the single write channel of the view."""
        from goga.codegraph.hooks import GraphValidation

        assert callable(GraphValidation.veto)

        view = GraphValidation(tree=tree)
        view.veto("broken")


# --- Logic tests ---


class TestGraphValidation:
    def test_veto_semantics_and_write_protection(self, tree: list[object]) -> None:
        """Whole replacement, verbatim empty reason, reads pass, writes blocked."""
        from goga.codegraph.hooks import GraphValidation

        view = GraphValidation(tree=tree)

        assert view._veto is None

        view.veto("first")
        view.veto("")

        assert view._veto == ""

        proxy = wrap_context(view)

        assert proxy.tree is view.tree

        with pytest.raises(AttributeError, match="read-only"):
            proxy.tree = []  # type: ignore[misc]

        assert view.tree is tree

        proxy.veto("via proxy")

        assert view._veto == "via proxy"
        assert callable(proxy.veto)

    def test_second_veto_replaces_the_reason_whole(self, tree: list[object]) -> None:
        """A later call replaces the earlier reason — no merge, no append."""
        from goga.codegraph.hooks import GraphValidation

        view = GraphValidation(tree=tree)

        view.veto("broken")
        view.veto("worse")

        assert view._veto == "worse"

    def test_veto_stores_whitespace_reason_verbatim(self, tree: list[object]) -> None:
        """A whitespace-only reason is stored as given — a veto, not a pass."""
        from goga.codegraph.hooks import GraphValidation

        view = GraphValidation(tree=tree)

        view.veto("   ")

        assert view._veto == "   "

    def test_veto_returns_none(self, tree: list[object]) -> None:
        """The call buffers only — no return value."""
        from goga.codegraph.hooks import GraphValidation

        view = GraphValidation(tree=tree)

        assert view.veto("broken") is None

    def test_tree_carries_the_constructed_value_verbatim(self, tree: list[object]) -> None:
        """Nothing is read, copied, or resolved inside — the passed list stays."""
        from goga.codegraph.hooks import GraphValidation

        view = GraphValidation(tree=tree)

        assert view.tree is tree

    def test_veto_changes_no_delivered_fact(self, tree: list[object]) -> None:
        """The write channel touches the buffer alone — the tree stays as constructed."""
        from goga.codegraph.hooks import GraphValidation

        view = GraphValidation(tree=tree)

        view.veto("policy")

        assert view.tree is tree
        assert view.tree[0].cell == "goga/config"

    def test_the_buffer_belongs_to_this_view_alone(self, tree: list[object]) -> None:
        """One view per tool — a veto never reaches another view's buffer."""
        from goga.codegraph.hooks import GraphValidation

        first = GraphValidation(tree=tree)
        second = GraphValidation(tree=tree)

        first.veto("one tool's reason")

        assert first._veto == "one tool's reason"
        assert second._veto is None
