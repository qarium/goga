"""Contract and logic tests for the entity declared in
``goga/pipeline/hooks/CODEMANIFEST`` with ``location: amendments.py``:

- ``WorkflowAmendment(pipeline, decision, workflow, work)`` — the
  read-and-contribute view of one tool: the delivered facts of the
  amendment checkpoint plus the buffer of one tool's contribution

Supported data only — no mocks, no filesystem: the view carries the
constructor facts verbatim and buffers the one contribution of this tool
alone. Task 7 delivers the view through the platform proxy.
"""

from __future__ import annotations

import dataclasses
import inspect

import pytest
from goga.pipeline.hooks import (
    PipelineIdentity,
    WorkflowAmendment,
    WorkflowDecision,
    WorkIdentity,
)
from goga.pipeline.workflow import WorkflowDocument

from tests.conftest import is_kw_only_dataclass


def _field_defaults(cls: type) -> list[tuple[str, object]]:
    """(name, default) per declared field — ``MISSING`` for required fields."""
    return [(field.name, field.default) for field in dataclasses.fields(cls)]


def _field(cls: type, name: str) -> dataclasses.Field:
    """The declared field metadata of ``name``."""
    for field in dataclasses.fields(cls):
        if field.name == name:
            return field

    raise AssertionError(f"{cls.__name__} carries no field {name!r}")


@pytest.fixture
def pipeline() -> PipelineIdentity:
    """The identity of the pipeline being composed."""
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
    """The original authored workflow — pre-layer, identical for every tool."""
    return WorkflowDocument(prompt="authored")


@pytest.fixture
def work() -> WorkIdentity:
    """The current work identity."""
    return WorkIdentity(branch="feature-demo", slug="feature-demo", year="2026")


@pytest.fixture
def view(
    pipeline: PipelineIdentity,
    decision: WorkflowDecision,
    workflow: WorkflowDocument,
    work: WorkIdentity,
) -> WorkflowAmendment:
    """The read-and-contribute view of one tool."""
    return WorkflowAmendment(
        pipeline=pipeline,
        decision=decision,
        workflow=workflow,
        work=work,
    )


# --- Contract tests ---


class TestAmendmentContract:
    def test_entity_is_importable_from_the_zone_facade(self) -> None:
        """The view lives on the zone package and its ``__all__`` is exact."""
        import goga.pipeline.hooks as zone

        assert zone.WorkflowAmendment is WorkflowAmendment
        # The facade grows incrementally — the amendments task added the
        # tenth name; Task 7 completes the surface to the eleven contract
        # names.
        assert zone.__all__ == [
            "CompositionStage",
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

    def test_model_is_a_kw_only_dataclass(self) -> None:
        """Positional construction raises ``TypeError``."""
        assert dataclasses.is_dataclass(WorkflowAmendment)
        assert is_kw_only_dataclass(WorkflowAmendment)

        with pytest.raises(TypeError):
            WorkflowAmendment(  # type: ignore[misc]
                PipelineIdentity(name="deploy", description="d", source="project"),
                WorkflowDecision(kind="explicit", workflow_name="ci"),
                None,
                WorkIdentity(branch="b"),
            )

    def test_view_carries_exactly_the_declared_fields(self) -> None:
        """``pipeline, decision, workflow, work`` — names, order, no defaults."""
        init_defaults = [
            (name, default) for name, default in _field_defaults(WorkflowAmendment) if name != "_contribution"
        ]

        assert init_defaults == [
            ("pipeline", dataclasses.MISSING),
            ("decision", dataclasses.MISSING),
            ("workflow", dataclasses.MISSING),
            ("work", dataclasses.MISSING),
        ]
        assert [field.name for field in dataclasses.fields(WorkflowAmendment)][:-1] == [
            "pipeline",
            "decision",
            "workflow",
            "work",
        ]

    def test_contribution_buffer_is_private_init_false_default_none(self) -> None:
        """``_contribution`` — not constructor surface, not repr, starts ``None``."""
        buffer = _field(WorkflowAmendment, "_contribution")

        assert buffer.init is False
        assert buffer.default is None
        assert buffer.repr is False

    def test_contribute_is_a_public_method_taking_document(self) -> None:
        """``contribute(document)`` — one parameter, no return value promised."""
        assert callable(WorkflowAmendment.contribute)
        assert not WorkflowAmendment.contribute.__name__.startswith("_")

        signature = inspect.signature(WorkflowAmendment.contribute)

        assert list(signature.parameters) == ["self", "document"]


# --- Logic tests ---


class TestContribute:
    def test_fresh_view_starts_with_an_empty_buffer(
        self,
        view: WorkflowAmendment,
    ) -> None:
        """A view that has not contributed yet carries no buffered document."""
        assert view._contribution is None

    def test_contribute_sets_the_buffer(self, view: WorkflowAmendment) -> None:
        """The buffered document is the exact object this tool contributed."""
        document = WorkflowDocument(prompt="a")

        view.contribute(document)

        assert view._contribution is document
        assert view._contribution.prompt == "a"

    def test_second_contribute_replaces_the_buffer_whole(self, view: WorkflowAmendment) -> None:
        """Whole replacement — a later call replaces the earlier document."""
        view.contribute(WorkflowDocument(prompt="a"))
        replacement = WorkflowDocument(prompt="b")

        view.contribute(replacement)

        assert view._contribution is replacement
        assert view._contribution.prompt == "b"

    def test_contribute_returns_none(self, view: WorkflowAmendment) -> None:
        """The call buffers silently — no value returns."""
        assert view.contribute(WorkflowDocument(prompt="a")) is None


class TestViewFacts:
    def test_constructor_facts_round_trip_verbatim(
        self,
        view: WorkflowAmendment,
        pipeline: PipelineIdentity,
        decision: WorkflowDecision,
        workflow: WorkflowDocument,
        work: WorkIdentity,
    ) -> None:
        """The reads deliver the original facts by reference."""
        assert view.pipeline is pipeline
        assert view.decision is decision
        assert view.workflow is workflow
        assert view.work is work

    def test_workflow_none_serves_the_unresolved_moment(self) -> None:
        """``workflow`` is ``None`` when no workflow resolved."""
        view = WorkflowAmendment(
            pipeline=PipelineIdentity(name="deploy", description="d", source="project"),
            decision=WorkflowDecision(kind="silent-miss", workflow_name=None),
            workflow=None,
            work=WorkIdentity(branch="b"),
        )

        assert view.workflow is None

    def test_contribute_changes_no_constructor_fact(self, view: WorkflowAmendment) -> None:
        """No staged-application state — the four facts stay the constructor's."""
        facts_before = (view.pipeline, view.decision, view.workflow, view.work)

        view.contribute(WorkflowDocument(prompt="a"))

        assert (view.pipeline, view.decision, view.workflow, view.work) == facts_before

    def test_buffer_belongs_to_this_view_alone(
        self,
        pipeline: PipelineIdentity,
        decision: WorkflowDecision,
        workflow: WorkflowDocument,
        work: WorkIdentity,
    ) -> None:
        """Two identically-built views never share a buffer — per-tool state."""
        first = WorkflowAmendment(pipeline=pipeline, decision=decision, workflow=workflow, work=work)
        second = WorkflowAmendment(pipeline=pipeline, decision=decision, workflow=workflow, work=work)

        first.contribute(WorkflowDocument(prompt="mine"))

        assert first._contribution is not None
        assert second._contribution is None
