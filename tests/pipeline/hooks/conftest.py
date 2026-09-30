"""Shared fixtures of the pipeline hooks zone tests — the platform boundary.

Re-exports the two boundary fixtures of the hooks platform tests
(``pin_package_environment`` / ``install_tool_package``) so the zone suites pin
the same two outside-world points — the ``packages_distributions`` read and the
``sys.modules`` entry of a ``goga_tool_*`` package — with the platform code
under test running for real.

The zone suites also share the model-level scaffolding: the eleven-name zone
facade list, the ``(name, default)`` field introspector, and the four fact
fixtures (``pipeline`` / ``decision`` / ``workflow`` / ``work``) the context and
amendment tests compose their documents from.
"""

from __future__ import annotations

import dataclasses

import pytest
from goga.pipeline.hooks import PipelineIdentity, WorkflowDecision, WorkIdentity
from goga.pipeline.workflow import WorkflowDocument

from tests.hooks.conftest import install_tool_package, pin_package_environment  # noqa: F401

ZONE_ALL: list[str] = [
    "CompositionStage",
    "PipelineHooks",
    "PipelineIdentity",
    "RunCompleted",
    "RunCreated",
    "ToolContribution",
    "WorkIdentity",
    "WorkflowAmendment",
    "WorkflowDecision",
    "WorkflowOverlay",
    "merge_workflow_overlay",
]
"""The completed zone facade — exactly the eleven contract names."""


def field_defaults(cls: type) -> list[tuple[str, object]]:
    """(name, default) per declared field — ``MISSING`` for required fields."""
    return [(field.name, field.default) for field in dataclasses.fields(cls)]


@pytest.fixture
def pipeline() -> PipelineIdentity:
    """The identity of the running pipeline."""
    return PipelineIdentity(
        name="deploy",
        display_name="Deploy the service",
        description="Ships the service",
        source="project",
    )


@pytest.fixture
def decision() -> WorkflowDecision:
    """The workflow decision of the operation."""
    return WorkflowDecision(kind="auto-match", workflow_name="deploy")


@pytest.fixture
def workflow() -> WorkflowDocument:
    """The authored workflow the operation composes — pre-layer, identical for every tool."""
    return WorkflowDocument(prompt="authored")


@pytest.fixture
def work() -> WorkIdentity:
    """The current work identity — the topic-hosting form."""
    return WorkIdentity(branch="feature-demo", slug="feature-demo", year="2026")
