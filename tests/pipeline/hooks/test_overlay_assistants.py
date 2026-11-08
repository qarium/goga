"""Contract and logic tests for the collaboration arms of the overlay merge —
the ``assistants`` / ``delegation`` vocabulary of
``goga/pipeline/hooks/CODEMANIFEST`` with ``location: overlay.py`` /
``events.py``:

- ``merge_workflow_overlay`` steps 4a / 4b / 5a — the catalog merge, the
  whole-block delegation, and the per-stage append-with-dedup under the
  document-wide assistant-namespace invariant
- ``PipelineHooks.amend_workflow`` — the buffer-shape guard and the
  empty-contribution vocabulary gain the two new facts

Supported data and pure functions only for the merge — no mocks, no
filesystem: inputs are never mutated, collisions are silent drops, and the
merged document stays declarative (compilable through ``compile_flow``).
"""

from __future__ import annotations

import dataclasses
import logging

import pytest
from goga.pipeline.hooks import (
    PipelineHooks,
    PipelineIdentity,
    ToolContribution,
    WorkflowDecision,
    WorkIdentity,
    merge_workflow_overlay,
)
from goga.pipeline.workflow import (
    WorkflowAssistant,
    WorkflowDelegation,
    WorkflowDocument,
    WorkflowStage,
)

# --- Contract tests ---


class _DuckDocument:
    """A buffer carrying the four legacy facts and no collaboration attributes."""

    def __init__(self) -> None:
        self.prompt = "duck"
        self.stages: dict[str, WorkflowStage] = {}
        self.extend: dict[str, object] = {}
        self.memory = None


class _DuckDocumentNoRepeat:
    """A buffer carrying every fact except ``repeat`` — the ninth-fact guard probe."""

    def __init__(self) -> None:
        self.prompt = "duck"
        self.stages: dict[str, WorkflowStage] = {}
        self.extend: dict[str, object] = {}
        self.memory = None
        self.assistants: dict[str, WorkflowAssistant] = {}
        self.delegation = None


class TestOverlayAssistantsContract:
    def test_collaboration_fields_merge_base_with_contributions(self) -> None:
        """A base carrying ``assistants``/``delegation`` merges with contributions that do."""
        base = WorkflowDocument(
            prompt="authored",
            assistants={"reviewer": WorkflowAssistant(name="reviewer", prompt="Review.")},
            delegation=WorkflowDelegation(depth=1),
        )
        contributions = [
            ToolContribution(
                tool="t1",
                document=WorkflowDocument(
                    assistants={"qa": WorkflowAssistant(name="qa", prompt="Check.")},
                    delegation=WorkflowDelegation(max_tasks=9),
                ),
            ),
        ]

        overlay = merge_workflow_overlay(base, contributions)

        assert overlay.workflow is not None
        assert list(overlay.workflow.assistants) == ["reviewer", "qa"]
        assert overlay.workflow.delegation is not None
        assert overlay.workflow.delegation.max_tasks == 50  # authored block unbeatable

    def test_collaboration_fields_survive_collaboration_free_contributions(self) -> None:
        """A tool without collaboration content leaves the base fields intact."""
        base = WorkflowDocument(
            prompt="authored",
            assistants={"reviewer": WorkflowAssistant(name="reviewer", prompt="Review.")},
            delegation=WorkflowDelegation(depth=2),
        )

        overlay = merge_workflow_overlay(base, [ToolContribution(tool="t1", document=WorkflowDocument(prompt="one"))])

        assert overlay.workflow is not None
        assert overlay.workflow.assistants["reviewer"].prompt == "Review."
        assert overlay.workflow.delegation is not None
        assert overlay.workflow.delegation.depth == 2

    def test_empty_contributions_passthrough_keeps_base_object(self) -> None:
        """``contributions=[]`` is the unchanged passthrough — the same object returns."""
        base = WorkflowDocument(
            assistants={"reviewer": WorkflowAssistant(name="reviewer", prompt="Review.")},
            delegation=WorkflowDelegation(),
        )

        overlay = merge_workflow_overlay(base, [])

        assert overlay.workflow is base
        assert overlay.provenance == []

    def test_duck_buffer_missing_collaboration_attributes_fails_that_hook_hard(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """A buffer without ``assistants``/``delegation`` fails the guard inside the intercept.

        The shape guard runs per hook inside the try block, so a duck-typed
        buffer missing the new attributes surfaces as the hook's own hard
        ``ValueError`` — never as an ``AttributeError`` escaping to
        ``merge_workflow_overlay``.
        """
        pin_package_environment({"goga_tool_demo": ["demo-dist"]})

        def register_duck(hooks: object) -> None:
            def duck(self: object, context: object) -> None:
                context.contribute(_DuckDocument())

            hooks.subscribe("pipeline", "amend_workflow", "duck", duck)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_demo", register_hooks=register_duck)

        registry = PipelineHooks()

        with pytest.raises(
            ValueError,
            match=r"pipeline\.amend_workflow: '_DuckDocument' object has no attribute 'assistants'",
        ):
            registry.amend_workflow(
                pipeline=PipelineIdentity(name="deploy", display_name="Deploy", description="Ships", source="project"),
                decision=WorkflowDecision(kind="auto-match", workflow_name="deploy"),
                workflow=WorkflowDocument(prompt="authored"),
                work=WorkIdentity(branch="feature-demo", slug="feature-demo", year="2026"),
            )

    def test_duck_buffer_missing_repeat_attribute_fails_that_hook_hard(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """A buffer without ``repeat`` fails the guard inside the intercept, not after it.

        The fact walk is the only place a duck-typed buffer missing the
        ninth fact produces the pinned hard ``ValueError`` — the emptiness
        check that also reads ``repeat`` runs OUTSIDE the try, so without
        the walk term the same buffer would escape as a raw
        ``AttributeError``.
        """
        pin_package_environment({"goga_tool_demo": ["demo-dist"]})

        def register_duck(hooks: object) -> None:
            def duck(self: object, context: object) -> None:
                context.contribute(_DuckDocumentNoRepeat())

            hooks.subscribe("pipeline", "amend_workflow", "duck", duck)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_demo", register_hooks=register_duck)

        registry = PipelineHooks()

        with pytest.raises(
            ValueError,
            match=r"pipeline\.amend_workflow: '_DuckDocumentNoRepeat' object has no attribute 'repeat'",
        ):
            registry.amend_workflow(
                pipeline=PipelineIdentity(name="deploy", display_name="Deploy", description="Ships", source="project"),
                decision=WorkflowDecision(kind="auto-match", workflow_name="deploy"),
                workflow=WorkflowDocument(prompt="authored"),
                work=WorkIdentity(branch="feature-demo", slug="feature-demo", year="2026"),
            )

    def test_delegation_only_contribution_is_content_and_reaches_the_merge(
        self,
        pin_package_environment,
        install_tool_package,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """A delegation-only buffer is not a no-op — it commits and merges."""
        pin_package_environment({"goga_tool_demo": ["demo-dist"]})

        def register_delegate(hooks: object) -> None:
            def delegate(self: object, context: object) -> None:
                context.contribute(WorkflowDocument(delegation=WorkflowDelegation(max_tasks=7)))

            hooks.subscribe("pipeline", "amend_workflow", "delegate", delegate)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_demo", register_hooks=register_delegate)

        with caplog.at_level(logging.WARNING, logger="goga.pipeline.hooks.events"):
            overlay = PipelineHooks().amend_workflow(
                pipeline=PipelineIdentity(name="deploy", display_name="Deploy", description="Ships", source="project"),
                decision=WorkflowDecision(kind="auto-match", workflow_name="deploy"),
                workflow=WorkflowDocument(prompt="authored"),
                work=WorkIdentity(branch="feature-demo", slug="feature-demo", year="2026"),
            )

        assert overlay.provenance == ["demo"]  # committed — not discarded
        assert overlay.workflow is not None
        assert overlay.workflow.delegation is not None
        assert overlay.workflow.delegation.max_tasks == 7
        assert not [record for record in caplog.records if "discarded" in record.message]

    def test_catalog_only_contribution_is_content_and_reaches_the_merge(
        self,
        pin_package_environment,
        install_tool_package,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """An assistants-catalog-only buffer is not a no-op — it commits and merges."""
        pin_package_environment({"goga_tool_demo": ["demo-dist"]})

        def register_delegate(hooks: object) -> None:
            def delegate(self: object, context: object) -> None:
                context.contribute(WorkflowDocument(assistants={"qa": WorkflowAssistant(name="qa", prompt="QA.")}))

            hooks.subscribe("pipeline", "amend_workflow", "delegate", delegate)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_demo", register_hooks=register_delegate)

        with caplog.at_level(logging.WARNING, logger="goga.pipeline.hooks.events"):
            overlay = PipelineHooks().amend_workflow(
                pipeline=PipelineIdentity(name="deploy", display_name="Deploy", description="Ships", source="project"),
                decision=WorkflowDecision(kind="auto-match", workflow_name="deploy"),
                workflow=WorkflowDocument(prompt="authored"),
                work=WorkIdentity(branch="feature-demo", slug="feature-demo", year="2026"),
            )

        assert overlay.provenance == ["demo"]  # committed — not discarded
        assert overlay.workflow is not None
        assert list(overlay.workflow.assistants) == ["qa"]
        assert overlay.workflow.assistants["qa"].prompt == "QA."
        assert not [record for record in caplog.records if "discarded" in record.message]

    def test_catalog_override_is_field_level_not_displacement(self) -> None:
        """A same-name delivered entry merges field by field under the authored entry."""
        base = WorkflowDocument(
            prompt="authored",
            assistants={"x": WorkflowAssistant(name="x", agent="my-agent")},
        )
        contributions = [
            ToolContribution(
                tool="t1",
                document=WorkflowDocument(
                    assistants={
                        "x": WorkflowAssistant(
                            name="x",
                            prompt="tool-prompt",
                            skills=["s1"],
                            agent="tool-agent",
                            delegate=True,
                            env={"K": "V"},
                        ),
                    },
                ),
            ),
        ]

        overlay = merge_workflow_overlay(base, contributions)

        assert overlay.workflow is not None
        merged = overlay.workflow.assistants["x"]
        assert merged is not base.assistants["x"]  # a fresh composition, never displacement
        assert merged.agent == "my-agent"  # the authored field wins
        assert merged.prompt == "tool-prompt"  # the omitted field flows from the delivered base

    def test_merge_inputs_survive_the_call_unchanged(self) -> None:
        """The merge is pure — every input document field survives the call (deep comparison)."""
        base = WorkflowDocument(
            prompt="authored",
            assistants={"x": WorkflowAssistant(name="x", agent="my-agent")},
            stages={
                "build": WorkflowStage(
                    agent="a",
                    assistants={"y": WorkflowAssistant(name="y", when="start", agent="my-agent")},
                ),
            },
        )
        document = WorkflowDocument(
            assistants={
                "x": WorkflowAssistant(
                    name="x",
                    prompt="tool-prompt",
                    skills=["s1"],
                    agent="tool-agent",
                    delegate=True,
                    env={"K": "V"},
                ),
                "y": WorkflowAssistant(name="y", prompt="Watch the build."),
            },
            stages={
                "build": WorkflowStage(agent="a", assistants={"z": WorkflowAssistant(name="z", prompt="Late.")}),
            },
        )
        contributions = [ToolContribution(tool="t1", document=document)]
        base_snapshot = dataclasses.asdict(base)
        tool_snapshot = dataclasses.asdict(document)

        overlay = merge_workflow_overlay(base, contributions)

        assert dataclasses.asdict(base) == base_snapshot  # deep — no input field mutated
        assert dataclasses.asdict(document) == tool_snapshot
        assert overlay.workflow is not None


def _declaration_names(document: WorkflowDocument) -> list[str]:
    """Every declaration-source name of a document — catalog then stage declarations."""
    names = list(document.assistants)

    for stage in document.stages.values():
        for entry in (stage.assistants or {}).values():
            if (
                entry.prompt is not None
                or entry.skills is not None
                or entry.agent is not None
                or entry.delegate is not None
                or entry.env is not None
            ):
                names.append(entry.name)

    return names


# --- Logic tests (the design's scenarios, verbatim) ---


class TestOverlayAssistants:
    def test_overlay_catalog_merge_authored_fields_win_fresh_names_later_tool(self) -> None:
        """Authored catalog fields override the delivered base; fresh names take the later tool's entry."""
        reviewer_base = WorkflowAssistant(name="reviewer", prompt="Review (authored).")
        base = WorkflowDocument(prompt="authored", assistants={"reviewer": reviewer_base})
        contributions = [
            ToolContribution(
                tool="t1",
                document=WorkflowDocument(
                    assistants={
                        "reviewer": WorkflowAssistant(name="reviewer", prompt="Review (t1).", agent="agent (t1)."),
                        "qa": WorkflowAssistant(name="qa", prompt="QA (t1)."),
                    },
                ),
            ),
            ToolContribution(
                tool="t2",
                document=WorkflowDocument(
                    assistants={
                        "reviewer": WorkflowAssistant(name="reviewer", prompt="Review (t2).", agent="agent (t2)."),
                        "qa": WorkflowAssistant(name="qa", prompt="QA (t2)."),
                        "ops": WorkflowAssistant(name="ops", prompt="Ops (t2)."),
                    },
                ),
            ),
        ]

        overlay = merge_workflow_overlay(base, contributions)

        assert overlay.workflow is not None
        assert list(overlay.workflow.assistants) == ["reviewer", "qa", "ops"]
        reviewer = overlay.workflow.assistants["reviewer"]
        assert reviewer is not reviewer_base  # the override composes a fresh entry
        assert reviewer.prompt == "Review (authored)."  # the authored field wins
        assert reviewer.agent == "agent (t2)."  # omitted fields flow from the winning base (t2's whole entry)
        assert overlay.workflow.assistants["qa"].prompt == "QA (t2)."  # later tool wins per fresh name
        assert overlay.workflow.assistants["ops"].prompt == "Ops (t2)."
        assert base.assistants == {"reviewer": reviewer_base}  # purity — input untouched

    def test_overlay_stage_assistants_append_with_dedup(self) -> None:
        """Authored attachments first; tools append with the on-stage and namespace dedup."""
        authored_reviewer = WorkflowAssistant(name="reviewer", gate=True)
        base = WorkflowDocument(
            prompt="authored",
            assistants={"qa": WorkflowAssistant(name="qa", prompt="QA.")},
            stages={
                "build": WorkflowStage(agent="a", assistants={"reviewer": authored_reviewer}),
                "gate-check": WorkflowStage(
                    agent="a", assistants={"sec": WorkflowAssistant(name="sec", prompt="Check gates.")}
                ),
            },
        )
        contributions = [
            ToolContribution(
                tool="t1",
                document=WorkflowDocument(
                    stages={
                        "build": WorkflowStage(
                            agent="a",
                            assistants={
                                "reviewer": WorkflowAssistant(name="reviewer"),
                                "security": WorkflowAssistant(name="security", prompt="Watch the build."),
                            },
                        ),
                        "scan": WorkflowStage(agent="a", assistants={"qa": WorkflowAssistant(name="qa")}),
                    },
                ),
            ),
            ToolContribution(
                tool="t2",
                document=WorkflowDocument(
                    stages={
                        "build": WorkflowStage(
                            agent="a",
                            assistants={
                                "security": WorkflowAssistant(name="security", prompt="Watch (t2)."),
                                "audit": WorkflowAssistant(name="audit"),
                            },
                        ),
                        "deploy": WorkflowStage(
                            agent="a", assistants={"sec": WorkflowAssistant(name="sec", prompt="Sneak in.")}
                        ),
                    },
                ),
            ),
        ]

        overlay = merge_workflow_overlay(base, contributions)

        workflow = overlay.workflow
        assert workflow is not None
        build = workflow.stages["build"].assistants
        assert build is not None
        # Authored order first, then the accepted appends in enumeration order.
        assert list(build) == ["reviewer", "security", "audit"]
        assert build["reviewer"] is authored_reviewer  # authored entry verbatim
        assert build["security"].prompt == "Watch the build."  # t1's declaration — t2's dropped on-stage
        assert build["audit"].prompt is None  # a reference carries no declaration fields
        # References are immune to the namespace rule — "qa" is cataloged, the
        # bare reference on "scan" still attaches.
        scan = workflow.stages["scan"].assistants
        assert scan is not None
        assert list(scan) == ["qa"]
        # The sibling rule — an authored declaration on "gate-check" blocks the
        # tool's same-name declaration on "deploy".
        assert workflow.stages["deploy"].assistants is None
        # The merged namespace holds each name exactly once.
        names = _declaration_names(workflow)
        assert names == ["qa", "security", "sec"]  # catalog, then stage-declaration order
        assert len(names) == len(set(names))
        # Purity — the contribution documents are untouched.
        t1_build = contributions[0].document.stages["build"].assistants
        assert t1_build is not None
        assert list(t1_build) == ["reviewer", "security"]

    def test_overlay_catalog_entry_displaces_earlier_inline_declaration(self) -> None:
        """The pinned cross-kind collision — a later catalog entry displaces an earlier declaration."""
        declaration = WorkflowAssistant(name="sec", prompt="Audit the stage (t1 inline).")
        catalog_entry = WorkflowAssistant(name="sec", prompt="Audit the stage (t2 catalog).")
        base = WorkflowDocument(prompt="authored", stages={"build": WorkflowStage(agent="a")})
        contributions = [
            ToolContribution(
                tool="t1",
                document=WorkflowDocument(stages={"build": WorkflowStage(agent="a", assistants={"sec": declaration})}),
            ),
            ToolContribution(tool="t2", document=WorkflowDocument(assistants={"sec": catalog_entry})),
        ]

        overlay = merge_workflow_overlay(base, contributions)

        workflow = overlay.workflow
        assert workflow is not None
        assert list(workflow.assistants) == ["sec"]
        assert workflow.assistants["sec"] is catalog_entry  # the catalog entry is accepted
        assert workflow.stages["build"].assistants is None  # the declaration dropped — the stage loses it
        names = _declaration_names(workflow)
        assert names == ["sec"]  # the name lives on exactly once — as the catalog entry
        assert contributions[0].document.stages["build"].assistants == {"sec": declaration}  # purity

    def test_overlay_passthrough_unchanged_and_no_contributions(self) -> None:
        """The passthrough returns the same object; contributions keep the namespace duplicate-free."""
        base = WorkflowDocument(
            prompt="authored",
            assistants={"reviewer": WorkflowAssistant(name="reviewer", prompt="Review.")},
            delegation=WorkflowDelegation(depth=1),
        )

        passthrough = merge_workflow_overlay(base, [])

        assert passthrough.workflow is base
        assert passthrough.provenance == []

        # The same inline name contributed to two stages keeps the namespace
        # duplicate-free — the second stage's declaration drops.
        shared = WorkflowAssistant(name="sec", prompt="Shared.")
        contributions = [
            ToolContribution(
                tool="t1",
                document=WorkflowDocument(
                    stages={
                        "a": WorkflowStage(agent="x", assistants={"sec": shared}),
                        "b": WorkflowStage(
                            agent="x", assistants={"sec": WorkflowAssistant(name="sec", prompt="Again.")}
                        ),
                    },
                ),
            ),
        ]

        overlay = merge_workflow_overlay(base, contributions)

        workflow = overlay.workflow
        assert workflow is not None
        stage_a = workflow.stages["a"].assistants
        assert stage_a is not None
        assert list(stage_a) == ["sec"]
        assert stage_a["sec"] is shared
        assert workflow.stages["b"].assistants is None
        names = _declaration_names(workflow)
        assert names == ["reviewer", "sec"]
        assert len(names) == len(set(names))

    def test_overlay_delegation_authored_unbeatable_later_tool_wins(self) -> None:
        """The delegation arms — whole-block like memory: authored kept, else the later block."""
        authored = merge_workflow_overlay(
            WorkflowDocument(prompt="authored", delegation=WorkflowDelegation(depth=1)),
            [ToolContribution(tool="t1", document=WorkflowDocument(delegation=WorkflowDelegation(max_tasks=9)))],
        )
        later = merge_workflow_overlay(
            WorkflowDocument(prompt="authored"),
            [
                ToolContribution(tool="t1", document=WorkflowDocument(delegation=WorkflowDelegation(max_tasks=7))),
                ToolContribution(tool="t2", document=WorkflowDocument(delegation=WorkflowDelegation(max_tasks=9))),
            ],
        )
        none_carried = merge_workflow_overlay(
            WorkflowDocument(prompt="authored", delegation=WorkflowDelegation(depth=2)),
            [ToolContribution(tool="t1", document=WorkflowDocument(prompt="one"))],
        )
        only_contribution = merge_workflow_overlay(
            None,
            [ToolContribution(tool="t1", document=WorkflowDocument(delegation=WorkflowDelegation(max_tasks=7)))],
        )

        assert authored.workflow is not None
        assert authored.workflow.delegation is not None
        assert (authored.workflow.delegation.depth, authored.workflow.delegation.max_tasks) == (1, 50)
        assert later.workflow is not None
        assert later.workflow.delegation is not None
        assert later.workflow.delegation.max_tasks == 9  # the last contribution carrying a block wins
        assert none_carried.workflow is not None
        assert none_carried.workflow.delegation is not None
        assert none_carried.workflow.delegation.depth == 2  # carried when no tool carries a block
        assert only_contribution.workflow is not None
        assert only_contribution.workflow.delegation is not None
        assert only_contribution.workflow.delegation.max_tasks == 7  # a delegation-only contribution is content

    def test_overlay_collaboration_free_documents_unchanged_by_the_new_arms(self) -> None:
        """A base and tools without collaboration content merge to the absent defaults."""
        overlay = merge_workflow_overlay(
            WorkflowDocument(prompt="authored", stages={"build": WorkflowStage(agent="author")}),
            [ToolContribution(tool="t1", document=WorkflowDocument(prompt="one"))],
        )

        workflow = overlay.workflow
        assert workflow is not None
        assert workflow.assistants == {}
        assert workflow.delegation is None
        assert workflow.stages["build"].assistants is None

    def test_merge_overlay_catalog_entry_overrides_agent_only(self) -> None:
        """SC4 — an agent-only authored entry overrides the agent, inherits the rest."""
        base = WorkflowDocument(
            prompt="authored",
            assistants={"X": WorkflowAssistant(name="X", agent="my-agent")},
        )
        contributions = [
            ToolContribution(
                tool="t",
                document=WorkflowDocument(
                    assistants={
                        "X": WorkflowAssistant(
                            name="X",
                            prompt="tool-prompt",
                            skills=["s1"],
                            agent="tool-agent",
                            delegate=True,
                            env={"K": "V"},
                        ),
                    },
                ),
            ),
        ]

        overlay = merge_workflow_overlay(base, contributions)

        assert overlay.workflow is not None
        merged = overlay.workflow.assistants["X"]
        assert merged.prompt == "tool-prompt"
        assert merged.skills == ["s1"]
        assert merged.agent == "my-agent"  # authored
        assert merged.delegate is True  # inherited
        assert merged.env == {"K": "V"}

    def test_merge_override_authored_empty_env_clears_tool_env(self) -> None:
        """R2.1 — an authored ``env: {}`` is a clear, not an absence."""
        base = WorkflowDocument(
            prompt="authored",
            assistants={"X": WorkflowAssistant(name="X", agent="a", env={})},
        )
        contributions = [
            ToolContribution(
                tool="t",
                document=WorkflowDocument(
                    assistants={"X": WorkflowAssistant(name="X", prompt="p", env={"K": "V"})},
                ),
            ),
        ]

        overlay = merge_workflow_overlay(base, contributions)

        assert overlay.workflow is not None
        merged = overlay.workflow.assistants["X"]
        assert merged.env == {}  # the clear wins
        assert merged.prompt == "p"  # omitted fields flow

    def test_merge_override_authored_empty_skills_clears_tool_skills(self) -> None:
        """R2.1 — an authored ``skills: []`` is a clear, not an absence (the env twin).

        The presence discipline covers both explicit empties: an authored
        empty skills list wins over the delivered base's skills instead of
        letting them flow — an omitted field flows, an authored empty
        replaces whole.
        """
        base = WorkflowDocument(
            prompt="authored",
            assistants={"X": WorkflowAssistant(name="X", agent="a", skills=[])},
        )
        contributions = [
            ToolContribution(
                tool="t",
                document=WorkflowDocument(
                    assistants={"X": WorkflowAssistant(name="X", prompt="p", skills=["s1"])},
                ),
            ),
        ]

        overlay = merge_workflow_overlay(base, contributions)

        assert overlay.workflow is not None
        merged = overlay.workflow.assistants["X"]
        assert merged.skills == []  # the clear wins
        assert merged.prompt == "p"  # omitted fields flow

    def test_merge_override_delegate_false_opts_out_and_none_inherits(self) -> None:
        """The tri-state discipline end to end — authored False opts out, absent inherits."""
        base = WorkflowDocument(
            prompt="authored",
            assistants={
                "A": WorkflowAssistant(name="A", prompt="q", delegate=False),
                "B": WorkflowAssistant(name="B", prompt="q"),
            },
        )
        contributions = [
            ToolContribution(
                tool="t",
                document=WorkflowDocument(
                    assistants={
                        "A": WorkflowAssistant(name="A", delegate=True),
                        "B": WorkflowAssistant(name="B", delegate=True),
                    },
                ),
            ),
        ]

        overlay = merge_workflow_overlay(base, contributions)

        assert overlay.workflow is not None
        assert overlay.workflow.assistants["A"].delegate is False  # the authored opt-out wins
        assert overlay.workflow.assistants["B"].delegate is True  # absent delegates inherit

    def test_merge_no_collision_passthrough_verbatim(self) -> None:
        """C8 — collision-free authoring: authored entries survive verbatim, tools still commit."""
        reviewer = WorkflowAssistant(name="reviewer", prompt="Review.")
        sec = WorkflowAssistant(name="sec", prompt="Audit.", when="start")
        base = WorkflowDocument(
            prompt="authored",
            assistants={"reviewer": reviewer},
            stages={"build": WorkflowStage(agent="a", assistants={"sec": sec})},
        )
        contributions = [
            ToolContribution(
                tool="t1",
                document=WorkflowDocument(assistants={"qa": WorkflowAssistant(name="qa", prompt="QA.")}),
            ),
            ToolContribution(
                tool="t2",
                document=WorkflowDocument(
                    stages={
                        "build": WorkflowStage(
                            agent="a", assistants={"ops": WorkflowAssistant(name="ops", prompt="Ops.")}
                        ),
                    },
                ),
            ),
        ]

        overlay = merge_workflow_overlay(base, contributions)

        workflow = overlay.workflow
        assert workflow is not None
        assert workflow.assistants["reviewer"] is reviewer  # field-equal and instance-reused
        build = workflow.stages["build"].assistants
        assert build is not None
        assert build["sec"] is sec  # no delivered entry under the name — verbatim
        assert overlay.provenance == ["t1", "t2"]

    def test_merge_inline_override_stays_on_stage(self) -> None:
        """Position preservation — an inline override lands on its stage, never in the catalog."""
        inline = WorkflowAssistant(name="X", when="start", agent="my-agent")
        base = WorkflowDocument(
            prompt="authored",
            stages={"s1": WorkflowStage(agent="a", assistants={"X": inline})},
        )
        contributions = [
            ToolContribution(
                tool="t",
                document=WorkflowDocument(assistants={"X": WorkflowAssistant(name="X", prompt="p", skills=["s"])}),
            ),
        ]

        overlay = merge_workflow_overlay(base, contributions)

        workflow = overlay.workflow
        assert workflow is not None
        assert "X" not in workflow.assistants  # the catalog does not own the name
        merged = workflow.stages["s1"].assistants
        assert merged is not None
        assert merged["X"].prompt == "p"  # inherited content
        assert merged["X"].when == "start"  # the attachment parameter is kept
        assert merged["X"].agent == "my-agent"  # the authored override
