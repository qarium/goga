"""Contract and logic tests for the entities declared in
``goga/pipeline/hooks/CODEMANIFEST`` with ``location: contexts.py``:

- ``CompositionStage(id, title)`` — one row of the final composition, as
  the card shows it
- ``RunCreated(...)`` — the read-only context of the run-creation
  notification, the facts of the composed moment
- ``RunCompleted(...)`` — the same facts recomputed at the completion
  moment, plus the launch attempt's ``exit_code``

Supported data only — no mocks, no filesystem: the models are pure fact
carriers (a hook observes and cannot alter), every resolution happens in
the constructing operation. Task 7 appends the delivery/emission classes.
"""

from __future__ import annotations

import dataclasses

import pytest
from goga.pipeline.hooks import (
    CompositionStage,
    PipelineIdentity,
    RunCompleted,
    RunCreated,
    WorkflowDecision,
    WorkIdentity,
)
from goga.pipeline.workflow import WorkflowDocument

from tests.conftest import is_kw_only_dataclass

_CREATED_FIELDS: list[tuple[str, object]] = [
    ("pipeline", dataclasses.MISSING),
    ("decision", dataclasses.MISSING),
    ("workflow", dataclasses.MISSING),
    ("composition", dataclasses.MISSING),
    ("provenance", dataclasses.MISSING),
    ("work", dataclasses.MISSING),
    ("statuses", dataclasses.MISSING),
    ("runtime_dir", dataclasses.MISSING),
]


def _field_defaults(cls: type) -> list[tuple[str, object]]:
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
    """The final effective workflow."""
    return WorkflowDocument(prompt="authored")


@pytest.fixture
def work() -> WorkIdentity:
    """The current work identity — the topic-hosting form."""
    return WorkIdentity(branch="feature-demo", slug="feature-demo", year="2026")


# --- Contract tests ---


class TestContextsContract:
    def test_entities_are_importable_from_the_zone_facade(self) -> None:
        """All three models live on the zone package and its ``__all__`` is exact."""
        import goga.pipeline.hooks as zone

        assert zone.CompositionStage is CompositionStage
        assert zone.RunCreated is RunCreated
        assert zone.RunCompleted is RunCompleted
        assert zone.__all__ == [
            "CompositionStage",
            "PipelineIdentity",
            "RunCompleted",
            "RunCreated",
            "WorkIdentity",
            "WorkflowDecision",
        ]

    def test_models_are_kw_only_dataclasses(self) -> None:
        """Positional construction raises ``TypeError`` for every model."""
        for cls in (CompositionStage, RunCreated, RunCompleted):
            assert dataclasses.is_dataclass(cls)
            assert is_kw_only_dataclass(cls)

        with pytest.raises(TypeError):
            CompositionStage("build", "Build")  # type: ignore[misc]

        with pytest.raises(TypeError):
            RunCreated(  # type: ignore[misc]
                PipelineIdentity(name="deploy", description="d", source="project"),
                WorkflowDecision(kind="explicit", workflow_name="ci"),
                None,
                [],
                [],
                WorkIdentity(branch="b"),
                [],
                "/runtime",
            )

        with pytest.raises(TypeError):
            RunCompleted(  # type: ignore[misc]
                PipelineIdentity(name="deploy", description="d", source="project"),
                WorkflowDecision(kind="explicit", workflow_name="ci"),
                None,
                [],
                [],
                WorkIdentity(branch="b"),
                [],
                "/runtime",
                0,
            )

    def test_composition_stage_carries_exactly_the_declared_fields(self) -> None:
        """``id, title`` — both required, no defaults."""
        assert _field_defaults(CompositionStage) == [
            ("id", dataclasses.MISSING),
            ("title", dataclasses.MISSING),
        ]

    def test_run_created_carries_exactly_the_declared_fields(self) -> None:
        """The eight composed-moment facts — names, order, no defaults."""
        assert _field_defaults(RunCreated) == _CREATED_FIELDS

    def test_run_completed_is_run_created_plus_exit_code_last(self) -> None:
        """The same eight fields plus ``exit_code`` as the ninth and last."""
        assert _field_defaults(RunCompleted) == [*_CREATED_FIELDS, ("exit_code", dataclasses.MISSING)]


# --- Logic tests ---


class TestCompositionStage:
    def test_row_carries_id_and_title_verbatim(self) -> None:
        """One row of the final composition as the card shows it."""
        row = CompositionStage(id="build", title="Build")

        assert row.id == "build"
        assert row.title == "Build"


class TestRunCreated:
    def test_construction_carries_every_field_verbatim(self) -> None:
        """Each attribute round-trips — the facts are observed, not derived."""
        composition = [CompositionStage(id="build", title="Build")]
        provenance = ["goga_tool_demo"]
        statuses = ["todo"]

        context = RunCreated(
            pipeline=PipelineIdentity(name="deploy", display_name="Deploy", description="d", source="user"),
            decision=WorkflowDecision(kind="explicit", workflow_name="ci"),
            workflow=WorkflowDocument(prompt="authored"),
            composition=composition,
            provenance=provenance,
            work=WorkIdentity(branch="feature-demo", slug="feature-demo", year="2026"),
            statuses=statuses,
            runtime_dir="/runtime/afm",
        )

        assert context.pipeline.name == "deploy"
        assert context.decision.kind == "explicit"
        assert context.workflow is not None
        assert context.workflow.prompt == "authored"
        assert context.composition == composition
        assert context.provenance == provenance
        assert context.work.slug == "feature-demo"
        assert context.statuses == statuses
        assert context.runtime_dir == "/runtime/afm"

    def test_workflow_none_serves_the_silent_miss_moment(self) -> None:
        """``workflow`` is ``None`` when no effective workflow exists."""
        context = RunCreated(
            pipeline=PipelineIdentity(name="deploy", description="d", source="project"),
            decision=WorkflowDecision(kind="silent-miss", workflow_name=None),
            workflow=None,
            composition=[],
            provenance=[],
            work=WorkIdentity(branch="b"),
            statuses=[],
            runtime_dir="/runtime",
        )

        assert context.workflow is None

    def test_identically_built_contexts_are_equal(self) -> None:
        """Dataclass equality holds for two identically-built contexts."""

        def build() -> RunCreated:
            return RunCreated(
                pipeline=PipelineIdentity(name="deploy", description="d", source="project"),
                decision=WorkflowDecision(kind="auto-match", workflow_name="deploy"),
                workflow=WorkflowDocument(prompt="authored"),
                composition=[CompositionStage(id="build", title="Build")],
                provenance=["goga_tool_demo"],
                work=WorkIdentity(branch="b"),
                statuses=["todo"],
                runtime_dir="/runtime",
            )

        assert build() == build()


class TestRunCompleted:
    def test_construction_carries_every_field_verbatim(
        self,
        pipeline: PipelineIdentity,
        decision: WorkflowDecision,
        workflow: WorkflowDocument,
        work: WorkIdentity,
    ) -> None:
        """Each attribute round-trips — completion is a fact, not a success claim."""
        composition = [CompositionStage(id="build", title="Build")]

        context = RunCompleted(
            pipeline=pipeline,
            decision=decision,
            workflow=workflow,
            composition=composition,
            provenance=["goga_tool_demo"],
            work=work,
            statuses=["done"],
            runtime_dir="/runtime/afm",
            exit_code=0,
        )

        assert context.pipeline is pipeline
        assert context.decision is decision
        assert context.workflow is workflow
        assert context.composition == composition
        assert context.provenance == ["goga_tool_demo"]
        assert context.work is work
        assert context.statuses == ["done"]
        assert context.runtime_dir == "/runtime/afm"
        assert context.exit_code == 0

    @pytest.mark.parametrize("exit_code", [0, 3, 127])
    def test_exit_code_accepts_zero_nonzero_and_spawn_failure(self, exit_code: int) -> None:
        """Zero, non-zero, and a spawn failure 126/127 are all plain facts."""
        context = RunCompleted(
            pipeline=PipelineIdentity(name="deploy", description="d", source="project"),
            decision=WorkflowDecision(kind="silent-miss", workflow_name=None),
            workflow=None,
            composition=[],
            provenance=[],
            work=WorkIdentity(branch="b"),
            statuses=[],
            runtime_dir="/runtime",
            exit_code=exit_code,
        )

        assert context.exit_code == exit_code

    def test_identically_built_contexts_are_equal(
        self,
        pipeline: PipelineIdentity,
        decision: WorkflowDecision,
        workflow: WorkflowDocument,
        work: WorkIdentity,
    ) -> None:
        """Dataclass equality holds for two identically-built contexts."""

        def build() -> RunCompleted:
            return RunCompleted(
                pipeline=pipeline,
                decision=decision,
                workflow=workflow,
                composition=[CompositionStage(id="build", title="Build")],
                provenance=["goga_tool_demo"],
                work=work,
                statuses=["done"],
                runtime_dir="/runtime",
                exit_code=3,
            )

        assert build() == build()
