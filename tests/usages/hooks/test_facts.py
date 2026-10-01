"""Contract and logic tests for the entities declared in
``goga/usages/hooks/CODEMANIFEST`` with ``location: facts.py``: the eight
fact entities of the zone — ``UsagesMoment``, ``SyncOutcome``,
``SyncDepOutcome``, ``DriftVerdict``, ``ChangeVerdict``, ``FileChange``,
``Completion``, ``DepDrift``.

Supported data only — no mocks: the facts carry no behavior, so the pin set
(frozen kw_only construction, field sets, enum member values) is the full
coverage. The entities are imported directly from their declaring module
``goga.usages.hooks.facts`` — the ``location`` the cell CODEMANIFEST pins
(the facade re-export is pinned separately by ``test_facade.py``).
"""

from __future__ import annotations

import dataclasses

import pytest
from goga.usages.hooks.facts import (
    ChangeVerdict,
    Completion,
    DepDrift,
    DriftVerdict,
    FileChange,
    SyncDepOutcome,
    SyncOutcome,
    UsagesMoment,
)

from tests.conftest import is_kw_only_dataclass


class TestFacts:
    def test_facts_are_frozen_kw_only_dataclasses_and_enums_are_pinned(self) -> None:
        """The four fact records are frozen kw_only dataclasses; the four enums are pinned.

        The enum display strings are contractual — tools string-match the
        verdicts — and the field sets pin the wire shape against accidental
        growth.
        """
        moment = UsagesMoment(operation="sync", group=None, dep=None)

        assert moment.operation == "sync"
        assert moment.group is None
        assert moment.dep is None

        for cls in (UsagesMoment, SyncDepOutcome, FileChange, DepDrift):
            assert dataclasses.is_dataclass(cls)
            assert cls.__dataclass_params__.frozen
            assert is_kw_only_dataclass(cls)

            with pytest.raises(TypeError):
                cls("x")  # type: ignore[misc]  # positional construction refuses

        assert [f.name for f in dataclasses.fields(UsagesMoment)] == ["operation", "group", "dep"]
        assert [f.name for f in dataclasses.fields(FileChange)] == ["path", "change"]
        assert [f.name for f in dataclasses.fields(SyncDepOutcome)] == ["group", "dep", "outcome", "message"]
        assert [f.name for f in dataclasses.fields(DepDrift)] == ["group", "dep", "verdict", "changes", "message"]
        assert SyncDepOutcome(group="libs", dep="click", outcome=SyncOutcome.failed).message is None  # the None default

        with pytest.raises(dataclasses.FrozenInstanceError):
            moment.operation = "status"  # type: ignore[misc]  # assignment refuses

        assert [m.value for m in SyncOutcome] == ["synced", "skipped", "failed"]
        assert [m.value for m in DriftVerdict] == ["new", "out of date", "error"]
        assert [m.value for m in ChangeVerdict] == ["added", "modified", "removed"]
        assert [m.value for m in Completion] == ["finished", "crashed"]

    def test_fact_records_construction_and_defaults(self) -> None:
        """Positive construction: every field round-trips, ``message`` defaults to None.

        ``message`` is the explicit absence of a failure fact — set only by
        the emitting operation when its outcome is failed or its verdict is
        error.
        """
        moment = UsagesMoment(operation="status", group="libs", dep="click")
        outcome = SyncDepOutcome(group="libs", dep="click", outcome=SyncOutcome.synced)
        change = FileChange(path="docs/a.md", change=ChangeVerdict.added)
        drift = DepDrift(group="libs", dep="click", verdict=DriftVerdict.out_of_date, changes=[change])

        assert (moment.operation, moment.group, moment.dep) == ("status", "libs", "click")
        assert (outcome.group, outcome.dep, outcome.outcome) == ("libs", "click", SyncOutcome.synced)
        assert outcome.message is None
        assert (change.path, change.change) == ("docs/a.md", ChangeVerdict.added)
        assert (drift.group, drift.dep, drift.verdict, drift.changes, drift.message) == (
            "libs",
            "click",
            DriftVerdict.out_of_date,
            [change],
            None,
        )
