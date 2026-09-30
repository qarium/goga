"""Contract and logic tests for the entity declared in
``goga/contract/hooks/CODEMANIFEST`` with ``location: amendments.py``:

- ``ContractAmendment(cell)`` — the read-and-contribute view of one
  tool for one cell: the comparison facts of the cell being amended
  plus the buffer of this tool's type-addressed contributions

Supported data only — no mocks, no filesystem: the view carries the
delivered facts verbatim and buffers the contributions of this tool
alone. Task 6 delivers the view through the platform proxy over the
real registry. The tests import from
``goga.contract.hooks.amendments`` directly — the facade identity
assertions belong to the facade suite.
"""

from __future__ import annotations

import dataclasses
import inspect
import typing

import pytest

from tests.conftest import is_kw_only_dataclass


@pytest.fixture
def cell() -> object:
    """A minimal compared cell — the shared read surface of every tool."""
    from goga.contract.hooks.facts import CellFacts

    return CellFacts(path="goga/config", types=[])


@pytest.fixture
def view(cell: object) -> object:
    """The read-and-contribute view of one tool."""
    from goga.contract.hooks.amendments import ContractAmendment

    return ContractAmendment(cell=cell)


# --- Contract tests ---


class TestAmendmentContract:
    def test_view_is_importable_from_the_module(self) -> None:
        """The name lives in ``amendments.py`` of the zone."""
        from goga.contract.hooks.amendments import ContractAmendment

        assert callable(ContractAmendment)

    def test_view_is_a_kw_only_dataclass_not_frozen(self) -> None:
        """Keyword-only construction; the buffer is mutable state, not frozen."""
        from goga.contract.hooks.amendments import ContractAmendment

        assert dataclasses.is_dataclass(ContractAmendment)
        assert is_kw_only_dataclass(ContractAmendment)
        assert not ContractAmendment.__dataclass_params__.frozen

        with pytest.raises(TypeError):
            ContractAmendment("cell")  # type: ignore[misc]

    def test_view_carries_exactly_the_declared_fields(self, cell: object) -> None:
        """``cell`` plus the private buffer — names, order, no view defaults."""
        from goga.contract.hooks.amendments import ContractAmendment

        assert [field.name for field in dataclasses.fields(ContractAmendment)] == ["cell", "_pending"]

        cell_field = ContractAmendment.__dataclass_fields__["cell"]

        assert cell_field.default is dataclasses.MISSING
        assert cell_field.default_factory is dataclasses.MISSING
        assert ContractAmendment(cell=cell)

    def test_cell_is_a_plain_attribute(self) -> None:
        """``cell`` is a declared field, not a property — plain read access."""
        from goga.contract.hooks.amendments import ContractAmendment

        assert "cell" in ContractAmendment.__dataclass_fields__
        assert not isinstance(vars(ContractAmendment).get("cell"), property)

    def test_buffer_is_private_init_false_default_empty(self, cell: object) -> None:
        """``_pending`` — not constructor surface, not repr, starts empty."""
        from goga.contract.hooks.amendments import ContractAmendment

        buffer = ContractAmendment.__dataclass_fields__["_pending"]

        assert buffer.init is False
        assert buffer.repr is False
        assert buffer.default_factory is list
        assert ContractAmendment(cell=cell)._pending == []

    def test_pending_absent_from_constructor_signature_and_repr(self, view: object) -> None:
        """The buffer is invisible to the constructor and to ``repr``."""
        from goga.contract.hooks.amendments import ContractAmendment

        assert list(inspect.signature(ContractAmendment).parameters) == ["cell"]

        view.contribute({"A": {"x": 1}})

        assert "_pending" not in repr(view)
        assert repr(view).startswith("ContractAmendment(cell=")

    def test_contribute_carries_the_declared_signature(self) -> None:
        """``contribute(facts)`` — one parameter, typed, empty return."""
        from goga.contract.hooks.amendments import ContractAmendment

        method = ContractAmendment.contribute

        assert callable(method)
        assert list(inspect.signature(method).parameters) == ["self", "facts"]

        hints = typing.get_type_hints(method)

        assert hints["facts"] == dict[str, dict[str, object]]
        assert hints["return"] is type(None)


# --- Logic tests: the buffer ---


class TestBufferSemantics:
    def test_contribute_buffers_verbatim_in_call_order(self, view: object) -> None:
        """Each payload is appended as passed — no merge, no validation here."""
        view.contribute({"A": {"x": 1}})
        view.contribute({"A": {"y": 2}})

        assert view._pending == [{"A": {"x": 1}}, {"A": {"y": 2}}]

    def test_contribute_empty_mapping_buffers_verbatim(self, view: object, cell: object) -> None:
        """``{}`` buffers ``[{}]`` — the empty-mapping rule is the delivery's."""
        view.contribute({})

        assert view._pending == [{}]
        assert view.cell is cell

    def test_non_mapping_payload_is_stored_verbatim(self, view: object) -> None:
        """No validation at the view — the delivery's guard is Task 6."""
        payload = [("ProjectConfig", {"x": 1})]

        view.contribute(payload)

        assert view._pending == [[("ProjectConfig", {"x": 1})]]
        assert view._pending[0] is payload

    def test_contribute_returns_none(self, view: object) -> None:
        """The call buffers only — no return value."""
        assert view.contribute({"A": {"x": 1}}) is None

    def test_buffers_belong_to_this_view_alone(self, cell: object) -> None:
        """Two views over the same cell never share buffer state."""
        from goga.contract.hooks.amendments import ContractAmendment

        first = ContractAmendment(cell=cell)
        second = ContractAmendment(cell=cell)

        first.contribute({"A": {"x": 1}})

        assert first._pending == [{"A": {"x": 1}}]
        assert second._pending == []


# --- Logic tests: the view facts ---


class TestViewFacts:
    def test_delivered_facts_round_trip_verbatim(self, view: object, cell: object) -> None:
        """The read delivers the comparison facts by reference."""
        assert view.cell is cell

    def test_reads_deliver_the_comparison_facts(self, view: object) -> None:
        """Attribute reads observe the comparison facts as constructed."""
        assert view.cell.path == "goga/config"
        assert view.cell.types == []
