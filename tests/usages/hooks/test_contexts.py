"""Contract and logic tests for the entities declared in
``goga/usages/hooks/CODEMANIFEST`` with ``location: contexts.py``: the four
read-only context entities of the zone — ``SyncStarted``,
``StatusStarted``, ``SyncCompleted``, ``StatusCompleted``.

Supported data only — no mocks: the contexts carry no behavior, so the pin
set (frozen kw_only construction, field sets, the ``reason`` default) is the
full coverage. Until the zone facade lands, the module is imported directly
from ``goga.usages.hooks.contexts`` — the zone package is a namespace
package without ``__init__.py``.
"""

from __future__ import annotations

import dataclasses

import pytest
from goga.usages.hooks.contexts import (
    StatusCompleted,
    StatusStarted,
    SyncCompleted,
    SyncStarted,
)
from goga.usages.hooks.facts import Completion, UsagesMoment

from tests.conftest import is_kw_only_dataclass


class TestContexts:
    def test_contexts_are_frozen_kw_only_dataclasses_with_pinned_field_sets(self) -> None:
        """The four contexts are frozen kw_only dataclasses; the field sets pin the wire shape.

        The crash invariants (``success`` False whenever crashed, ``reason``
        present exactly when crashed) are guaranteed by the emitting
        operations, not enforced here — facts, not police.
        """
        m = UsagesMoment(operation="sync", group=None, dep=None)

        for cls in (SyncStarted, StatusStarted, SyncCompleted, StatusCompleted):
            assert dataclasses.is_dataclass(cls)
            assert cls.__dataclass_params__.frozen
            assert is_kw_only_dataclass(cls)

            with pytest.raises(TypeError):
                cls("x")  # type: ignore[misc]  # positional construction refuses

        assert [f.name for f in dataclasses.fields(SyncStarted)] == ["moment", "force"]
        assert [f.name for f in dataclasses.fields(StatusStarted)] == ["moment"]
        assert [f.name for f in dataclasses.fields(SyncCompleted)] == [
            "moment",
            "deps",
            "success",
            "completion",
            "reason",
        ]
        assert [f.name for f in dataclasses.fields(StatusCompleted)] == [
            "moment",
            "changed",
            "success",
            "completion",
            "reason",
        ]
        completed = SyncCompleted(moment=m, deps=[], success=True, completion=Completion.finished)

        assert completed.reason is None  # the None default

        with pytest.raises(dataclasses.FrozenInstanceError):
            SyncStarted(moment=m, force=False).force = True  # type: ignore[misc]  # assignment refuses

    def test_contexts_construction_and_defaults(self) -> None:
        """Positive construction: every field round-trips, ``reason`` defaults to None.

        ``reason`` is the explicit absence of a crash fact — set only by the
        emitting operation when the terminal marker is crashed.
        """
        m = UsagesMoment(operation="status", group="libs", dep="click")

        started = SyncStarted(moment=m, force=True)
        status_started = StatusStarted(moment=m)
        finished = SyncCompleted(moment=m, deps=[], success=True, completion=Completion.finished)
        changed = StatusCompleted(moment=m, changed=[], success=False, completion=Completion.crashed)

        assert (started.moment, started.force) == (m, True)
        assert status_started.moment is m
        assert (finished.moment, finished.deps, finished.success, finished.completion) == (
            m,
            [],
            True,
            Completion.finished,
        )
        assert (changed.moment, changed.changed, changed.success, changed.completion) == (
            m,
            [],
            False,
            Completion.crashed,
        )
