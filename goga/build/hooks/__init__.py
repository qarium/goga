"""Hooks zone of the build domain — the checkpoint surface of build runs."""

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
