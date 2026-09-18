"""Contract and logic tests for the entities declared in
``goga/pipeline/hooks/CODEMANIFEST`` with ``location: contexts.py`` and
``location: events.py``:

- ``CompositionStage(id, title)`` — one row of the final composition, as
  the card shows it
- ``RunCreated(...)`` — the read-only context of the run-creation
  notification, the facts of the composed moment
- ``RunCompleted(...)`` — the same facts recomputed at the completion
  moment, plus the launch attempt's ``exit_code``
- ``PipelineHooks()`` — the checkpoint surface delivering the hard
  amendment and emitting the two soft notifications

The context models are supported data only. The checkpoint surface runs
for real over the platform boundary fixtures of ``tests/hooks/conftest.py``
(re-exported by the zone test package) — the registry, the registrars, and
the delivery execute the actual platform code.
"""

from __future__ import annotations

import dataclasses
import inspect
import logging

import pytest
from goga.pipeline.hooks import (
    CompositionStage,
    PipelineHooks,
    PipelineIdentity,
    RunCompleted,
    RunCreated,
    WorkflowDecision,
    WorkflowOverlay,
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

_ZONE_ALL: list[str] = [
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
        # The facade grew incrementally through the zone tasks; Task 7
        # (the checkpoint surface) completed it to the eleven contract
        # names.
        assert zone.__all__ == _ZONE_ALL

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


# --- Task 7: the checkpoint surface — contract tests ---


class TestCheckpointContract:
    def test_zone_facade_exports_exactly_the_contract(self) -> None:
        """The facade IS the contract surface — the eleven names, importable."""
        import goga.pipeline.hooks as zone

        assert zone.PipelineHooks is PipelineHooks
        assert sorted(zone.__all__) == sorted(_ZONE_ALL)
        assert zone.__all__ == _ZONE_ALL

        for name in zone.__all__:
            assert getattr(zone, name, None) is not None, name

    def test_surface_carries_the_declared_method_signatures(self) -> None:
        """Every checkpoint takes exactly the declared parameters."""
        assert list(inspect.signature(PipelineHooks.amend_workflow).parameters) == [
            "self",
            "pipeline",
            "decision",
            "workflow",
            "work",
        ]
        assert list(inspect.signature(PipelineHooks.emit_run_created).parameters) == [
            "self",
            "pipeline",
            "decision",
            "overlay",
            "composition",
            "work",
            "statuses",
            "runtime_dir",
        ]
        assert list(inspect.signature(PipelineHooks.emit_run_completed).parameters) == [
            "self",
            "pipeline",
            "decision",
            "overlay",
            "composition",
            "work",
            "statuses",
            "runtime_dir",
            "exit_code",
        ]

    def test_construction_enumerates_nothing(self, pin_package_environment) -> None:
        """Cheap construction — the package environment stays unread."""
        boundary = pin_package_environment({"goga_tool_demo": ["demo-dist"]})

        PipelineHooks()

        assert boundary.call_count == 0


# --- Task 7: the checkpoint surface — logic tests (real platform) ---


def _facts() -> tuple[PipelineIdentity, WorkflowDecision, WorkIdentity]:
    """The amendment facts of a project deploy pipeline on a plain branch."""
    return (
        PipelineIdentity(name="deploy", description="Ships the service", source="project"),
        WorkflowDecision(kind="auto-match", workflow_name="deploy"),
        WorkIdentity(branch="b"),
    )


class TestAmendWorkflowDelivery:
    def test_amend_workflow_commits_per_tool_and_merges(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """Two tools commit one contribution each; both read the same original."""
        boundary = pin_package_environment(
            {
                "goga_tool_demo": ["demo-dist"],
                "goga_tool_second": ["second-dist"],
            }
        )

        def register_demo(hooks: object) -> None:
            def hardening(self: object, context: object) -> None:
                self.first_seen_workflow_id = id(context.workflow)
                self.seen_pipeline_name = context.pipeline.name
                self.seen_decision_kind = context.decision.kind
                context.contribute(WorkflowDocument(prompt="harden"))

            hooks.subscribe("pipeline", "amend_workflow", "hardening", hardening)  # type: ignore[attr-defined]

        def register_second(hooks: object) -> None:
            def softening(self: object, context: object) -> None:
                context.contribute(WorkflowDocument(prompt="second"))
                self.second_seen_workflow_id = id(context.workflow)
                self.second_seen_prompt = context.workflow.prompt

            hooks.subscribe("pipeline", "amend_workflow", "softening", softening)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_demo", register_hooks=register_demo)
        install_tool_package("goga_tool_second", register_hooks=register_second)

        pipeline, decision, work = _facts()
        authored = WorkflowDocument(prompt="authored")
        surface = PipelineHooks()

        overlay = surface.amend_workflow(
            pipeline=pipeline,
            decision=decision,
            workflow=authored,
            work=work,
        )

        assert boundary.call_count == 1  # the real enumeration, one build
        assert overlay.workflow is not None
        assert overlay.workflow.prompt == "authored\n\nharden\n\nsecond"
        # The platform derives the identities from the package names:
        # goga_tool_demo -> demo, goga_tool_second -> second.
        assert overlay.provenance == ["demo", "second"]

        # The facts each tool recorded in its own self context: the reads
        # delivered the amendment view, not the staged merge.
        demo_context = surface._registry.self_context("demo")
        second_context = surface._registry.self_context("second")

        assert demo_context.seen_pipeline_name == "deploy"
        assert demo_context.seen_decision_kind == "auto-match"
        assert demo_context.first_seen_workflow_id == second_context.second_seen_workflow_id
        assert second_context.second_seen_prompt == "authored"

    def test_amend_workflow_registry_built_once_across_checkpoints(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """The amendment and the completion share one registry build."""
        boundary = pin_package_environment({"goga_tool_demo": ["demo-dist"]})

        def register_both(hooks: object) -> None:
            def hardening(self: object, context: object) -> None:
                return None

            def notify(self: object, context: object) -> None:
                return None

            hooks.subscribe("pipeline", "amend_workflow", "hardening", hardening)  # type: ignore[attr-defined]
            hooks.subscribe("pipeline", "run_completed", "notify", notify)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_demo", register_hooks=register_both)

        pipeline, decision, work = _facts()
        hooks = PipelineHooks()

        hooks.amend_workflow(pipeline=pipeline, decision=decision, workflow=None, work=work)
        hooks.emit_run_completed(
            pipeline=pipeline,
            decision=decision,
            overlay=WorkflowOverlay(workflow=None, provenance=[]),
            composition=[],
            work=work,
            statuses=[],
            runtime_dir="/runtime",
            exit_code=0,
        )

        assert boundary.call_count == 1

    def test_amend_workflow_hard_failure_stops_command_and_discards(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """The first failing tool stops the walk — later tools never run."""
        pin_package_environment({"goga_tool_demo": ["demo-dist"], "goga_tool_second": ["second-dist"]})
        witnesses: list[str] = []

        def register_boom(hooks: object) -> None:
            def hardening(self: object, context: object) -> None:
                context.contribute(WorkflowDocument(prompt="x"))
                raise RuntimeError("boom")

            hooks.subscribe("pipeline", "amend_workflow", "hardening", hardening)  # type: ignore[attr-defined]

        def register_witness(hooks: object) -> None:
            def softening(self: object, context: object) -> None:
                witnesses.append("second-called")

            hooks.subscribe("pipeline", "amend_workflow", "softening", softening)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_demo", register_hooks=register_boom)
        install_tool_package("goga_tool_second", register_hooks=register_witness)

        pipeline, decision, work = _facts()

        with pytest.raises(ValueError, match=r"pipeline\.amend_workflow: boom"):
            PipelineHooks().amend_workflow(
                pipeline=pipeline,
                decision=decision,
                workflow=WorkflowDocument(prompt="authored"),
                work=work,
            )

        assert witnesses == []  # tool #2 never called; no overlay returned

    def test_empty_contribution_discarded_with_warning_silent_tool_ok(
        self,
        pin_package_environment,
        install_tool_package,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """An empty buffer is a discard with one warning; no buffer is silent."""
        pin_package_environment({"goga_tool_demo": ["demo-dist"], "goga_tool_second": ["second-dist"]})

        def register_empty(hooks: object) -> None:
            def empty(self: object, context: object) -> None:
                context.contribute(WorkflowDocument())

            hooks.subscribe("pipeline", "amend_workflow", "empty", empty)  # type: ignore[attr-defined]

        def register_silent(hooks: object) -> None:
            def silent(self: object, context: object) -> None:
                return None

            hooks.subscribe("pipeline", "amend_workflow", "silent", silent)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_demo", register_hooks=register_empty)
        install_tool_package("goga_tool_second", register_hooks=register_silent)

        pipeline, decision, work = _facts()
        base = WorkflowDocument(prompt="a")

        with caplog.at_level(logging.WARNING, logger="goga.pipeline.hooks.events"):
            overlay = PipelineHooks().amend_workflow(
                pipeline=pipeline,
                decision=decision,
                workflow=base,
                work=work,
            )

        assert overlay.workflow is base  # the passthrough — nothing committed
        assert overlay.provenance == []

        discards = [record.getMessage() for record in caplog.records if "discarded" in record.getMessage()]
        assert len(discards) == 1
        assert "demo" in discards[0]
