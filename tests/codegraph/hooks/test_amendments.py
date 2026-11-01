"""Contract and logic tests for the entity declared in
``goga/codegraph/hooks/CODEMANIFEST`` with ``location: amendments.py``:

- ``NodeAmendment(node)`` — the read-and-contribute view of one tool for
  one node: the code-derived facts of the node being amended plus the
  buffer of this tool's contributions

Supported data only — no mocks, no filesystem: the view carries the
constructor fact verbatim and buffers the contributions of this tool
alone. Task 7 delivers the view through the platform proxy over the real
registry.
"""

from __future__ import annotations

import dataclasses
import inspect
import typing

import pytest

from tests.conftest import is_kw_only_dataclass


@pytest.fixture
def node() -> object:
    """A minimal code-derived node — the shared read surface of every tool."""
    from goga.codegraph.hooks import NodeFacts

    return NodeFacts(
        cell="goga/config",
        types=["ProjectConfig"],
        dependencies={"goga/hooks": ["HookRegistry"]},
        children=["goga/config/hooks"],
    )


@pytest.fixture
def view(node: object) -> object:
    """The read-and-contribute view of one tool."""
    from goga.codegraph.hooks import NodeAmendment

    return NodeAmendment(node=node)


# --- Contract tests ---


class TestAmendmentContract:
    def test_view_is_importable_from_the_facade(self) -> None:
        """The name lives on the zone facade and resolves to ``amendments.py``."""
        import goga.codegraph.hooks as facade
        from goga.codegraph.hooks.amendments import NodeAmendment

        assert facade.NodeAmendment is NodeAmendment

        assert "NodeAmendment" in facade.__all__
        assert facade.__all__ == sorted(facade.__all__)

    def test_view_is_a_kw_only_dataclass_not_frozen(self) -> None:
        """Keyword-only construction; the buffer is mutable state, not frozen."""
        from goga.codegraph.hooks import NodeAmendment

        assert dataclasses.is_dataclass(NodeAmendment)
        assert is_kw_only_dataclass(NodeAmendment)
        assert not NodeAmendment.__dataclass_params__.frozen

        with pytest.raises(TypeError):
            NodeAmendment("node")  # type: ignore[misc]

    def test_view_carries_exactly_the_declared_fields(self, node: object) -> None:
        """``node`` plus the private buffer — names, order, no view defaults."""
        from goga.codegraph.hooks import NodeAmendment

        assert [field.name for field in dataclasses.fields(NodeAmendment)] == ["node", "_pending"]

        node_field = NodeAmendment.__dataclass_fields__["node"]

        assert node_field.default is dataclasses.MISSING
        assert node_field.default_factory is dataclasses.MISSING
        assert NodeAmendment(node=node)

    def test_node_is_a_plain_attribute(self) -> None:
        """``node`` is a declared field, not a property — plain read access."""
        from goga.codegraph.hooks import NodeAmendment

        assert "node" in NodeAmendment.__dataclass_fields__
        assert not isinstance(vars(NodeAmendment).get("node"), property)

    def test_buffer_is_private_init_false_default_empty(self, node: object) -> None:
        """``_pending`` — not constructor surface, not repr, starts empty."""
        from goga.codegraph.hooks import NodeAmendment

        buffer = NodeAmendment.__dataclass_fields__["_pending"]

        assert buffer.init is False
        assert buffer.repr is False
        assert buffer.default_factory is list
        assert NodeAmendment(node=node)._pending == []

    def test_pending_absent_from_constructor_signature_and_repr(self, view: object) -> None:
        """The buffer is invisible to the constructor and to ``repr``."""
        from goga.codegraph.hooks import NodeAmendment

        assert list(inspect.signature(NodeAmendment).parameters) == ["node"]

        view.contribute({"a": 1})

        assert "_pending" not in repr(view)
        assert repr(view).startswith("NodeAmendment(node=")

    def test_contribute_carries_the_declared_signature(self) -> None:
        """``contribute(facts)`` — one parameter, typed, empty return."""
        from goga.codegraph.hooks import NodeAmendment

        method = NodeAmendment.contribute

        assert callable(method)
        assert list(inspect.signature(method).parameters) == ["self", "facts"]

        hints = typing.get_type_hints(method)

        assert hints["facts"] == dict[str, object]
        assert hints["return"] is type(None)


# --- Logic tests: the buffer ---


class TestBufferSemantics:
    def test_contribute_buffers_verbatim_in_call_order(self, view: object) -> None:
        """Each payload is appended as passed — no merge, no validation here."""
        view.contribute({"a": 1, "b": 2})
        view.contribute({"a": 3})

        assert view._pending == [{"a": 1, "b": 2}, {"a": 3}]

    def test_contribute_empty_mapping_buffers_verbatim(self, view: object, node: object) -> None:
        """``{}`` buffers ``[{}]`` — the empty-mapping rule is the delivery's."""
        view.contribute({})

        assert view._pending == [{}]
        assert view.node is node

    def test_non_dict_payload_is_stored_verbatim(self, view: object) -> None:
        """No validation at the view — the delivery's guard is Task 7."""
        payload = [("a", 1)]

        view.contribute(payload)

        assert view._pending == [[("a", 1)]]
        assert view._pending[0] is payload

    def test_contribute_returns_none(self, view: object) -> None:
        """The call buffers only — no return value."""
        assert view.contribute({"a": 1}) is None

    def test_buffers_belong_to_this_view_alone(self, node: object) -> None:
        """Two views over the same node never share buffer state."""
        from goga.codegraph.hooks import NodeAmendment

        first = NodeAmendment(node=node)
        second = NodeAmendment(node=node)

        first.contribute({"a": 1})

        assert first._pending == [{"a": 1}]
        assert second._pending == []


# --- Logic tests: the view facts ---


class TestViewFacts:
    def test_constructor_fact_round_trips_verbatim(self, view: object, node: object) -> None:
        """The read delivers the code-derived facts by reference."""
        assert view.node is node

    def test_reads_deliver_the_code_derived_facts(self, view: object) -> None:
        """Attribute reads observe the code-derived facts as constructed."""
        assert view.node.cell == "goga/config"
        assert view.node.types == ["ProjectConfig"]
        assert view.node.children == ["goga/config/hooks"]
