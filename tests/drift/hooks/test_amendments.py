"""Contract and logic tests for the entities declared in
``goga/drift/hooks/CODEMANIFEST`` with ``location: amendments.py``:

- ``ReportAmendment(report)`` — the read-and-adjust view of one tool for
  the report: the finished scoped report plus the whole-list adjustment
  buffer of this tool alone
- ``EntryAmendment(entry)`` — the read-and-contribute view of one tool
  for one entry: the entry facts plus the buffer of this tool's
  contributions

Supported data only — no mocks, no filesystem: the views carry the
constructor facts verbatim and buffer this tool's payloads alone. Task 11
delivers the views through the platform proxy over the real registry.
"""

from __future__ import annotations

import dataclasses
import inspect
import typing

import pytest

from tests.conftest import is_kw_only_dataclass


@pytest.fixture
def report() -> object:
    """A minimal scoped report — the shared read surface of every amending tool."""
    from goga.drift.hooks import EntryFacts

    return [
        EntryFacts(kind="schema_only", cell="goga/config", types=["ProjectConfig"]),
        EntryFacts(kind="codegraph_only", cell="goga/extra", types=None),
    ]


@pytest.fixture
def entry() -> object:
    """A minimal report entry — the shared read surface of every contributing tool."""
    from goga.drift.hooks import EntryFacts

    return EntryFacts(kind="schema_only", cell="goga/config", types=["ProjectConfig"])


@pytest.fixture
def report_view(report: object) -> object:
    """The read-and-adjust view of one tool."""
    from goga.drift.hooks import ReportAmendment

    return ReportAmendment(report=report)


@pytest.fixture
def entry_view(entry: object) -> object:
    """The read-and-contribute view of one tool."""
    from goga.drift.hooks import EntryAmendment

    return EntryAmendment(entry=entry)


# --- Contract tests ---


class TestAmendmentsContract:
    def test_views_are_importable_from_the_facade(self) -> None:
        """Both names live on the zone facade and resolve to ``amendments.py``."""
        import goga.drift.hooks as facade
        from goga.drift.hooks.amendments import EntryAmendment, ReportAmendment

        assert facade.ReportAmendment is ReportAmendment
        assert facade.EntryAmendment is EntryAmendment

        assert "ReportAmendment" in facade.__all__
        assert "EntryAmendment" in facade.__all__
        assert facade.__all__ == sorted(facade.__all__)

    def test_views_are_kw_only_dataclasses_not_frozen(self) -> None:
        """Keyword-only construction; the buffers are mutable state, not frozen."""
        from goga.drift.hooks import EntryAmendment, ReportAmendment

        for view in (ReportAmendment, EntryAmendment):
            assert dataclasses.is_dataclass(view)
            assert is_kw_only_dataclass(view)
            assert not view.__dataclass_params__.frozen

        with pytest.raises(TypeError):
            ReportAmendment("report")  # type: ignore[misc]
        with pytest.raises(TypeError):
            EntryAmendment("entry")  # type: ignore[misc]

    def test_views_carry_exactly_the_declared_fields(self) -> None:
        """One fact field plus the private buffer each — names, order, no view defaults."""
        from goga.drift.hooks import EntryAmendment, ReportAmendment

        assert [f.name for f in dataclasses.fields(ReportAmendment)] == ["report", "_adjustment"]
        assert [f.name for f in dataclasses.fields(EntryAmendment)] == ["entry", "_pending"]

        for view, fact in ((ReportAmendment, "report"), (EntryAmendment, "entry")):
            fact_field = view.__dataclass_fields__[fact]

            assert fact_field.default is dataclasses.MISSING
            assert fact_field.default_factory is dataclasses.MISSING

    def test_facts_are_plain_attributes(self) -> None:
        """``report`` / ``entry`` are declared fields, not properties — plain read access."""
        from goga.drift.hooks import EntryAmendment, ReportAmendment

        assert "report" in ReportAmendment.__dataclass_fields__
        assert "entry" in EntryAmendment.__dataclass_fields__
        assert not isinstance(vars(ReportAmendment).get("report"), property)
        assert not isinstance(vars(EntryAmendment).get("entry"), property)

    def test_buffers_are_private_init_false(self) -> None:
        """``_adjustment`` / ``_pending`` — not constructor surface, not repr."""
        from goga.drift.hooks import EntryAmendment, ReportAmendment

        adjustment = ReportAmendment.__dataclass_fields__["_adjustment"]
        pending = EntryAmendment.__dataclass_fields__["_pending"]

        assert adjustment.init is False
        assert adjustment.repr is False
        assert adjustment.default is None

        assert pending.init is False
        assert pending.repr is False
        assert pending.default_factory is list

    def test_buffers_are_invisible_to_constructor_and_repr(self, report_view: object, entry_view: object) -> None:
        """The buffers stay out of the constructor signature and out of ``repr``."""
        from goga.drift.hooks import EntryAmendment, ReportAmendment

        assert list(inspect.signature(ReportAmendment).parameters) == ["report"]
        assert list(inspect.signature(EntryAmendment).parameters) == ["entry"]

        report_view.adjust([])
        entry_view.contribute({"a": 1})

        assert "_adjustment" not in repr(report_view)
        assert repr(report_view).startswith("ReportAmendment(report=")
        assert "_pending" not in repr(entry_view)
        assert repr(entry_view).startswith("EntryAmendment(entry=")

    def test_adjust_carries_the_declared_signature(self) -> None:
        """``adjust(entries)`` — one parameter, typed, empty return."""
        from goga.drift.hooks import ReportAmendment

        method = ReportAmendment.adjust

        assert callable(method)
        assert list(inspect.signature(method).parameters) == ["self", "entries"]

        hints = typing.get_type_hints(method)

        assert hints["entries"] == list[dict[str, object]]
        assert hints["return"] is type(None)

    def test_contribute_carries_the_declared_signature(self) -> None:
        """``contribute(facts)`` — one parameter, typed, empty return."""
        from goga.drift.hooks import EntryAmendment

        method = EntryAmendment.contribute

        assert callable(method)
        assert list(inspect.signature(method).parameters) == ["self", "facts"]

        hints = typing.get_type_hints(method)

        assert hints["facts"] == dict[str, object]
        assert hints["return"] is type(None)


# --- Logic tests: the adjustment buffer ---


class TestAdjustSemantics:
    def test_adjust_buffers_verbatim(self, report_view: object) -> None:
        """The payload is stored as passed — no validation at the view."""
        report_view.adjust([{"kind": "schema_only", "cell": "a"}])

        assert report_view._adjustment == [{"kind": "schema_only", "cell": "a"}]

    def test_second_adjust_replaces_it_whole(self, report_view: object) -> None:
        """A later call replaces the earlier adjustment — clearing is valid."""
        report_view.adjust([{"kind": "schema_only", "cell": "a"}])
        report_view.adjust([])

        assert report_view._adjustment == []

    def test_non_list_payload_is_stored_verbatim(self, report_view: object) -> None:
        """No validation at the view — the delivery's guard is Task 11."""
        payload = ("not", "a list")

        report_view.adjust(payload)

        assert report_view._adjustment is payload

    def test_adjust_returns_none(self, report_view: object) -> None:
        """The call buffers only — no return value."""
        assert report_view.adjust([]) is None

    def test_fresh_view_starts_unadjusted(self, report_view: object) -> None:
        """No call, no adjustment — the sentinel absence."""
        assert report_view._adjustment is None

    def test_buffers_belong_to_this_view_alone(self, report: object) -> None:
        """Two views over the same report never share buffer state."""
        from goga.drift.hooks import ReportAmendment

        first = ReportAmendment(report=report)
        second = ReportAmendment(report=report)

        first.adjust([])

        assert first._adjustment == []
        assert second._adjustment is None

    def test_view_report_returns_the_passed_list(self, report_view: object, report: object) -> None:
        """The read delivers the finished scoped report by reference."""
        assert report_view.report is report


# --- Logic tests: the contribution buffer ---


class TestContributeSemantics:
    def test_contribute_buffers_verbatim_in_call_order(self, entry_view: object) -> None:
        """Each payload is appended as passed — no merge, no validation here."""
        entry_view.contribute({"ticket": "GOGA-1"})
        entry_view.contribute({"ticket": "GOGA-2"})

        assert entry_view._pending == [{"ticket": "GOGA-1"}, {"ticket": "GOGA-2"}]

    def test_contribute_empty_mapping_buffers_verbatim(self, entry_view: object) -> None:
        """``{}`` buffers ``[{}]`` — the empty-mapping rule is the delivery's."""
        entry_view.contribute({})

        assert entry_view._pending == [{}]

    def test_non_dict_payload_is_stored_verbatim(self, entry_view: object) -> None:
        """No validation at the view — the delivery's guard is Task 11."""
        payload = [("a", 1)]

        entry_view.contribute(payload)

        assert entry_view._pending == [[("a", 1)]]
        assert entry_view._pending[0] is payload

    def test_contribute_returns_none(self, entry_view: object) -> None:
        """The call buffers only — no return value."""
        assert entry_view.contribute({"a": 1}) is None

    def test_buffers_belong_to_this_view_alone(self, entry: object) -> None:
        """Two views over the same entry never share buffer state."""
        from goga.drift.hooks import EntryAmendment

        first = EntryAmendment(entry=entry)
        second = EntryAmendment(entry=entry)

        first.contribute({"a": 1})

        assert first._pending == [{"a": 1}]
        assert second._pending == []

    def test_view_entry_returns_the_passed_facts(self, entry_view: object, entry: object) -> None:
        """The read delivers the entry facts by reference."""
        assert entry_view.entry is entry
