"""Local fixtures of the status scale cell tests."""

from __future__ import annotations

import pytest
from goga.history.statuses import Stage, StatusScale


@pytest.fixture
def builtin_scale() -> StatusScale:
    """Deterministic built-in scale — nine entries with the contract artifacts.

    The deepening order is the contract: empty, new, defined, discovered,
    backlog, designed, specified, planned, done.
    """
    return StatusScale(
        stages=[
            Stage(name="empty", filepath=""),
            Stage(name="new", filepath="title.txt"),
            Stage(name="defined", filepath="prd.md"),
            Stage(name="discovered", filepath="adr.md"),
            Stage(name="backlog", filepath="task.md"),
            Stage(name="designed", filepath="arch.md"),
            Stage(name="specified", filepath="design.md"),
            Stage(name="planned", filepath="plan.md"),
            Stage(name="done", filepath="completed/plan.md"),
        ]
    )
