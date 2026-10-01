"""Contract and logic tests for the entity declared in
``goga/schema/hooks/CODEMANIFEST`` with ``location: amendments.py``:

- ``CellAmendment(cell)`` — the read-and-contribute view of one tool for
  one cell: the authored facts of the cell being built plus the buffer of
  this tool's contributions

Supported data only — no mocks, no filesystem: the view carries the
constructor fact verbatim and buffers the contributions of this tool
alone. Task 6 delivers the view through the platform proxy over the real
registry.
"""

from __future__ import annotations

import dataclasses
import inspect
import typing

import pytest

from tests.conftest import is_kw_only_dataclass


@pytest.fixture
def cell() -> object:
    """A minimal authored cell — the shared read surface of every tool."""
    from goga.schema.hooks import CellFacts

    return CellFacts(
        path="goga/schema",
        description="Owner of the schema generation walk.",
        types=["schema"],
        usages=["schema-usage"],
        dependencies=[],
        children=["goga/schema/hooks"],
    )


@pytest.fixture
def view(cell: object) -> object:
    """The read-and-contribute view of one tool."""
    from goga.schema.hooks import CellAmendment

    return CellAmendment(cell=cell)


# --- Contract tests ---


class TestAmendmentContract:
    def test_view_is_importable_from_the_facade(self) -> None:
        """The name lives on the zone facade and resolves to ``amendments.py``."""
        import goga.schema.hooks as facade
        from goga.schema.hooks.amendments import CellAmendment

        assert facade.CellAmendment is CellAmendment

        assert "CellAmendment" in facade.__all__
        assert facade.__all__ == sorted(facade.__all__)

    def test_view_is_a_kw_only_dataclass_not_frozen(self) -> None:
        """Keyword-only construction; the buffer is mutable state, not frozen."""
        from goga.schema.hooks import CellAmendment

        assert dataclasses.is_dataclass(CellAmendment)
        assert is_kw_only_dataclass(CellAmendment)
        assert not CellAmendment.__dataclass_params__.frozen

        with pytest.raises(TypeError):
            CellAmendment("cell")  # type: ignore[misc]

    def test_view_carries_exactly_the_declared_fields(self, cell: object) -> None:
        """``cell`` plus the private buffer — names, order, no view defaults."""
        from goga.schema.hooks import CellAmendment

        assert [field.name for field in dataclasses.fields(CellAmendment)] == ["cell", "_pending"]

        cell_field = CellAmendment.__dataclass_fields__["cell"]

        assert cell_field.default is dataclasses.MISSING
        assert cell_field.default_factory is dataclasses.MISSING
        assert CellAmendment(cell=cell)

    def test_cell_is_a_plain_attribute(self) -> None:
        """``cell`` is a declared field, not a property — plain read access."""
        from goga.schema.hooks import CellAmendment

        assert "cell" in CellAmendment.__dataclass_fields__
        assert not isinstance(vars(CellAmendment).get("cell"), property)

    def test_buffer_is_private_init_false_default_empty(self, cell: object) -> None:
        """``_pending`` — not constructor surface, not repr, starts empty."""
        from goga.schema.hooks import CellAmendment

        buffer = CellAmendment.__dataclass_fields__["_pending"]

        assert buffer.init is False
        assert buffer.repr is False
        assert buffer.default_factory is list
        assert CellAmendment(cell=cell)._pending == []

    def test_pending_absent_from_constructor_signature_and_repr(self, view: object) -> None:
        """The buffer is invisible to the constructor and to ``repr``."""
        from goga.schema.hooks import CellAmendment

        assert list(inspect.signature(CellAmendment).parameters) == ["cell"]

        view.contribute({"a": 1})

        assert "_pending" not in repr(view)
        assert repr(view).startswith("CellAmendment(cell=")

    def test_contribute_carries_the_declared_signature(self) -> None:
        """``contribute(facts)`` — one parameter, typed, empty return."""
        from goga.schema.hooks import CellAmendment

        method = CellAmendment.contribute

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

    def test_contribute_empty_mapping_buffers_verbatim(self, view: object, cell: object) -> None:
        """``{}`` buffers ``[{}]`` — the empty-mapping rule is the delivery's."""
        view.contribute({})

        assert view._pending == [{}]
        assert view.cell is cell

    def test_non_dict_payload_is_stored_verbatim(self, view: object) -> None:
        """No validation at the view — the delivery's guard is Task 6."""
        payload = [("a", 1)]

        view.contribute(payload)

        assert view._pending == [[("a", 1)]]
        assert view._pending[0] is payload

    def test_contribute_returns_none(self, view: object) -> None:
        """The call buffers only — no return value."""
        assert view.contribute({"a": 1}) is None

    def test_buffers_belong_to_this_view_alone(self, cell: object) -> None:
        """Two views over the same cell never share buffer state."""
        from goga.schema.hooks import CellAmendment

        first = CellAmendment(cell=cell)
        second = CellAmendment(cell=cell)

        first.contribute({"a": 1})

        assert first._pending == [{"a": 1}]
        assert second._pending == []


# --- Logic tests: the view facts ---


class TestViewFacts:
    def test_constructor_fact_round_trips_verbatim(self, view: object, cell: object) -> None:
        """The read delivers the authored facts by reference."""
        assert view.cell is cell

    def test_reads_deliver_the_authored_facts(self, view: object) -> None:
        """Attribute reads observe the authored facts as constructed."""
        assert view.cell.path == "goga/schema"
        assert view.cell.types == ["schema"]
        assert view.cell.children == ["goga/schema/hooks"]
