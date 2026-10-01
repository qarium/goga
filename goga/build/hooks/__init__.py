"""Hooks zone of the build domain — the checkpoint surface of build runs.

The zone owns the fact vocabulary of the run events (work identity, moment,
stage facts), the read-only contexts of the five moments, the
verdict-collecting gate view, and the ``BuildHooks`` checkpoint surface
delivering the domain's hard gate ``build/validate_build`` and the four soft
notifications ``build/build_started`` / ``build/pass_started`` /
``build/pass_completed`` / ``build/build_completed`` over the platform
facade. The gate follows the staged per-tool walk of the platform with one
domain-local deviation: the walk never stops early — every subscribed tool's
validation hooks run to completion and the vetoes are collected into one
verdict.

Built incrementally: each entity task added its module's import and
``__all__`` entry. With the fact vocabulary, the run-event contexts, and
the checkpoint surface landed, the thirteen contract names of the zone
are re-exported here.
"""

from __future__ import annotations

from .contexts import BuildCompleted, BuildStarted, BuildValidation, PassCompleted, PassStarted
from .events import BuildHooks
from .facts import (
    AdditionalFacts,
    BuildMoment,
    GateVerdict,
    RelocationOutcome,
    StageFacts,
    Violation,
    WorkIdentity,
)

__all__: list[str] = [
    "AdditionalFacts",
    "BuildCompleted",
    "BuildHooks",
    "BuildMoment",
    "BuildStarted",
    "BuildValidation",
    "GateVerdict",
    "PassCompleted",
    "PassStarted",
    "RelocationOutcome",
    "StageFacts",
    "Violation",
    "WorkIdentity",
]
