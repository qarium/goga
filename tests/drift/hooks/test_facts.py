"""Contract and logic tests for the entities declared in
``goga/drift/hooks/CODEMANIFEST`` with ``location: facts.py``:

- ``DriftFilters(cells, max_depth, depends_on)`` — the start-moment
  facts, the filters the run was asked to apply
- ``EntryFacts(kind, cell, types)`` — the delivered read view of one
  report entry
- ``ReportEntry(kind, cell, types, tools)`` — the completion-moment
  report entry projection
- ``RunOutcome`` — the fixed value set of a drift run's terminal
  outcome
- ``RunCompletion(report, outcome, reason)`` — the completion-moment
  facts, the terminal state of one run

Supported data only — no mocks, no filesystem: the records carry the
constructor facts verbatim in fresh containers; the run projects them,
nothing is read inside.
"""

from __future__ import annotations

import dataclasses
import typing
from enum import Enum

import pytest

from tests.conftest import is_kw_only_dataclass

# --- Contract tests ---


class TestFactsContract:
    def test_facts_are_importable_from_the_facade(self) -> None:
        """The five names live on the zone facade and resolve to ``facts.py``."""
        import goga.drift.hooks as facade
        from goga.drift.hooks.facts import (
            DriftFilters,
            EntryFacts,
            ReportEntry,
            RunCompletion,
            RunOutcome,
        )

        assert facade.DriftFilters is DriftFilters
        assert facade.EntryFacts is EntryFacts
        assert facade.ReportEntry is ReportEntry
        assert facade.RunCompletion is RunCompletion
        assert facade.RunOutcome is RunOutcome

        for name in ("DriftFilters", "EntryFacts", "ReportEntry", "RunCompletion", "RunOutcome"):
            assert name in facade.__all__

        assert facade.__all__ == sorted(facade.__all__)

    def test_records_are_frozen_kw_only_dataclasses(self) -> None:
        """Pure frozen data, keyword-only construction."""
        from goga.drift.hooks import DriftFilters, EntryFacts, ReportEntry, RunCompletion, RunOutcome

        for record in (DriftFilters, EntryFacts, ReportEntry, RunCompletion):
            assert dataclasses.is_dataclass(record)
            assert is_kw_only_dataclass(record)
            assert record.__dataclass_params__.frozen

        with pytest.raises(TypeError):
            DriftFilters(["a"], None, [])  # type: ignore[misc]

        with pytest.raises(TypeError):
            EntryFacts("schema_only", "a", None)  # type: ignore[misc]

        with pytest.raises(TypeError):
            ReportEntry("schema_only", "a", None, {})  # type: ignore[misc]

        with pytest.raises(TypeError):
            RunCompletion(None, RunOutcome.crashed, "x")  # type: ignore[misc]

    def test_drift_filters_carries_exactly_the_declared_fields(self) -> None:
        """``cells, max_depth, depends_on`` — names, order, all required."""
        from goga.drift.hooks import DriftFilters

        assert [field.name for field in dataclasses.fields(DriftFilters)] == [
            "cells",
            "max_depth",
            "depends_on",
        ]

        assert all(
            field.default is dataclasses.MISSING and field.default_factory is dataclasses.MISSING
            for field in dataclasses.fields(DriftFilters)
        )

        hints = typing.get_type_hints(DriftFilters)

        assert hints["cells"] == list[str]
        assert hints["max_depth"] == int | None
        assert hints["depends_on"] == list[str]

    def test_entry_facts_carries_exactly_the_declared_fields(self) -> None:
        """``kind, cell, types`` — names, order, all required."""
        from goga.drift.hooks import EntryFacts

        assert [field.name for field in dataclasses.fields(EntryFacts)] == ["kind", "cell", "types"]

        assert all(
            field.default is dataclasses.MISSING and field.default_factory is dataclasses.MISSING
            for field in dataclasses.fields(EntryFacts)
        )

        hints = typing.get_type_hints(EntryFacts)

        assert hints["kind"] is str
        assert hints["cell"] is str
        assert hints["types"] == list[str] | None

    def test_report_entry_carries_the_declared_fields_with_tools_defaulted(self) -> None:
        """``kind, cell, types, tools`` — the overlay field defaults empty."""
        from goga.drift.hooks import ReportEntry

        assert [field.name for field in dataclasses.fields(ReportEntry)] == [
            "kind",
            "cell",
            "types",
            "tools",
        ]

        fields_by_name = {field.name: field for field in dataclasses.fields(ReportEntry)}

        assert fields_by_name["types"].default is None
        assert fields_by_name["tools"].default_factory() == {}

        hints = typing.get_type_hints(ReportEntry)

        assert hints["kind"] is str
        assert hints["cell"] is str
        assert hints["types"] == list[str] | None
        assert hints["tools"] == dict[str, dict[str, object]]

    def test_run_outcome_is_an_enum_with_exactly_the_two_members(self) -> None:
        """``finished`` and ``crashed`` — string member values, nothing else."""
        from goga.drift.hooks import RunOutcome

        assert issubclass(RunOutcome, Enum)
        assert [member.name for member in RunOutcome] == ["finished", "crashed"]
        assert RunOutcome.finished.value == "finished"
        assert RunOutcome.crashed.value == "crashed"

    def test_run_completion_carries_exactly_the_declared_fields(self) -> None:
        """``report, outcome, reason`` — names, order, all required."""
        from goga.drift.hooks import ReportEntry, RunCompletion, RunOutcome

        assert [field.name for field in dataclasses.fields(RunCompletion)] == [
            "report",
            "outcome",
            "reason",
        ]

        assert all(
            field.default is dataclasses.MISSING and field.default_factory is dataclasses.MISSING
            for field in dataclasses.fields(RunCompletion)
        )

        hints = typing.get_type_hints(RunCompletion)

        assert hints["report"] == list[ReportEntry] | None
        assert hints["outcome"] is RunOutcome
        assert hints["reason"] is str


# --- Logic tests: pure facts ---


class TestRunOutcomeAndCompletion:
    def test_run_outcome_members_and_run_completion_none_report(self) -> None:
        """The fixed member set; ``None`` is the recorded absence of a report."""
        from goga.drift.hooks import RunCompletion, RunOutcome

        assert RunOutcome.finished.value == "finished"
        assert RunOutcome.crashed.value == "crashed"
        assert list(RunOutcome) == [RunOutcome.finished, RunOutcome.crashed]

        completion = RunCompletion(report=None, outcome=RunOutcome.crashed, reason="x")

        assert dataclasses.is_dataclass(RunCompletion)
        assert is_kw_only_dataclass(RunCompletion)
        assert completion.report is None
        assert completion.outcome is RunOutcome.crashed
        assert completion.reason == "x"

    def test_run_completion_carries_the_final_report_verbatim(self) -> None:
        """A finished run's completion carries the final report stage."""
        from goga.drift.hooks import ReportEntry, RunCompletion, RunOutcome

        completion = RunCompletion(
            report=[ReportEntry(kind="schema_only", cell="a", types=None, tools={})],
            outcome=RunOutcome.finished,
            reason="",
        )

        assert completion.report == [ReportEntry(kind="schema_only", cell="a", types=None)]
        assert completion.outcome is RunOutcome.finished
        assert completion.reason == ""

    def test_frozen_completion_blocks_attribute_assignment(self) -> None:
        """``FrozenInstanceError`` — surfacing as ``AttributeError``."""
        from goga.drift.hooks import RunCompletion, RunOutcome

        completion = RunCompletion(report=None, outcome=RunOutcome.crashed, reason="x")

        with pytest.raises(dataclasses.FrozenInstanceError) as raise_info:
            completion.reason = "y"  # type: ignore[misc]

        assert isinstance(raise_info.value, AttributeError)


class TestFactsValues:
    def test_fields_hold_the_passed_values_verbatim(self) -> None:
        """Pure facts — every field round-trips the exact value passed."""
        from goga.drift.hooks import DriftFilters, EntryFacts

        filters = DriftFilters(cells=["goga/config"], max_depth=2, depends_on=["goga/hooks"])
        entry = EntryFacts(kind="schema_only", cell="goga/config", types=["ProjectConfig"])

        assert filters.cells == ["goga/config"]
        assert filters.max_depth == 2
        assert filters.depends_on == ["goga/hooks"]

        assert entry.kind == "schema_only"
        assert entry.cell == "goga/config"
        assert entry.types == ["ProjectConfig"]

    def test_constructor_lists_are_copied_fresh(self) -> None:
        """Mutating the caller's lists never reaches the records."""
        from goga.drift.hooks import DriftFilters, EntryFacts, ReportEntry

        cells = ["goga/config"]
        depends_on = ["goga/hooks"]
        types = ["ProjectConfig"]

        filters = DriftFilters(cells=cells, max_depth=None, depends_on=depends_on)
        facts = EntryFacts(kind="schema_only", cell="a", types=types)
        entry = ReportEntry(kind="schema_only", cell="a", types=types)

        cells.append("goga/commands")
        depends_on.append("goga/commands")
        types.append("LintConfig")

        assert filters.cells == ["goga/config"]
        assert filters.depends_on == ["goga/hooks"]
        assert facts.types == ["ProjectConfig"]
        assert entry.types == ["ProjectConfig"]

    def test_report_entry_defaults_tools_empty_and_types_none(self) -> None:
        """Omitted fields default — ``tools == {}``, ``types is None``."""
        from goga.drift.hooks import ReportEntry

        entry = ReportEntry(kind="schema_only", cell="a")

        assert entry.tools == {}
        assert entry.types is None

    def test_report_entry_keeps_an_explicit_overlay_verbatim(self) -> None:
        """A contributed overlay round-trips untouched."""
        from goga.drift.hooks import ReportEntry

        entry = ReportEntry(kind="schema_only", cell="a", types=["T"], tools={"docs": {"ticket": 1}})

        assert entry.types == ["T"]
        assert entry.tools == {"docs": {"ticket": 1}}

    def test_frozen_facts_block_attribute_assignment(self) -> None:
        """``FrozenInstanceError`` — surfacing as ``AttributeError``."""
        from goga.drift.hooks import DriftFilters, EntryFacts, ReportEntry

        with pytest.raises(AttributeError):
            DriftFilters(cells=[], max_depth=None, depends_on=[]).cells = []  # type: ignore[misc]

        with pytest.raises(AttributeError):
            EntryFacts(kind="schema_only", cell="a", types=None).cell = "x"  # type: ignore[misc]

        with pytest.raises(AttributeError):
            ReportEntry(kind="schema_only", cell="a").tools = {}  # type: ignore[misc]


class TestFactsEdgeCases:
    def test_empty_filters_construct_and_compare_equal(self) -> None:
        """The unfiltered run — empty filter lists, no depth limit."""
        from goga.drift.hooks import DriftFilters

        first = DriftFilters(cells=[], max_depth=None, depends_on=[])
        second = DriftFilters(cells=[], max_depth=None, depends_on=[])

        assert first == second

    def test_none_types_mark_the_cell_level_entry(self) -> None:
        """``None`` types stay ``None`` on both entry records."""
        from goga.drift.hooks import EntryFacts, ReportEntry

        assert EntryFacts(kind="schema_only", cell="a", types=None).types is None
        assert ReportEntry(kind="codegraph_only", cell="a", types=None).types is None

    def test_empty_types_list_is_carried_verbatim(self) -> None:
        """An empty type list is a list of strings — distinct from ``None``."""
        from goga.drift.hooks import EntryFacts, ReportEntry

        assert EntryFacts(kind="codegraph_only", cell="a", types=[]).types == []
        assert ReportEntry(kind="codegraph_only", cell="a", types=[]).types == []
