"""Contract and logic tests for the entities declared in
``goga/pipeline/hooks/CODEMANIFEST`` with ``location: overlay.py``:

- ``ToolContribution(tool, document)`` — one tool's committed contribution
- ``WorkflowOverlay(workflow, provenance)`` — the composed effective workflow
- ``merge_workflow_overlay(base, contributions)`` — the authored-wins merge

Supported data and pure functions only — no mocks, no filesystem: the merge is
pure (inputs never mutated, new instances returned), deterministic, and stays
declarative (the result compiles through the unchanged ``compile_flow``).
"""

from __future__ import annotations

import dataclasses
import inspect

import pytest
from goga.pipeline.hooks import ToolContribution, WorkflowOverlay, merge_workflow_overlay
from goga.pipeline.workflow import (
    WorkflowDocument,
    WorkflowExtendStage,
    WorkflowMemory,
    WorkflowStage,
)

from tests.conftest import is_kw_only_dataclass


def _field_defaults(cls: type) -> list[tuple[str, object]]:
    """(name, default) per declared field — ``MISSING`` for required fields."""
    return [(field.name, field.default) for field in dataclasses.fields(cls)]


# --- Contract tests ---


class TestOverlayContract:
    def test_entities_are_importable_from_the_zone_facade(self) -> None:
        """All three names live on the zone package and its ``__all__``."""
        import goga.pipeline.hooks as zone

        assert zone.ToolContribution is ToolContribution
        assert zone.WorkflowOverlay is WorkflowOverlay
        assert zone.merge_workflow_overlay is merge_workflow_overlay
        for name in ("ToolContribution", "WorkflowOverlay", "merge_workflow_overlay"):
            assert name in zone.__all__

    def test_models_are_kw_only_dataclasses(self) -> None:
        """Positional construction raises ``TypeError`` for both models."""
        for cls in (ToolContribution, WorkflowOverlay):
            assert dataclasses.is_dataclass(cls)
            assert is_kw_only_dataclass(cls)

        with pytest.raises(TypeError):
            ToolContribution("t1", WorkflowDocument())  # type: ignore[misc]

        with pytest.raises(TypeError):
            WorkflowOverlay(None, [])  # type: ignore[misc]

    def test_models_carry_exactly_the_declared_fields(self) -> None:
        """``tool, document`` and ``workflow, provenance`` — no defaults."""
        assert _field_defaults(ToolContribution) == [
            ("tool", dataclasses.MISSING),
            ("document", dataclasses.MISSING),
        ]
        assert _field_defaults(WorkflowOverlay) == [
            ("workflow", dataclasses.MISSING),
            ("provenance", dataclasses.MISSING),
        ]

    def test_merge_signature_matches_the_contract(self) -> None:
        """Parameters ``base, contributions``; return annotation ``WorkflowOverlay``."""
        signature = inspect.signature(merge_workflow_overlay)

        assert list(signature.parameters) == ["base", "contributions"]
        # With `from __future__ import annotations` the annotation is a string;
        # without it, it is the evaluated class. Accept either form.
        assert signature.return_annotation in ("WorkflowOverlay", WorkflowOverlay)


# --- Logic tests (the design's scenarios, verbatim) ---


class TestMergeWorkflowOverlay:
    def test_merge_prompt_concatenates_authored_first_then_tools(self) -> None:
        """Non-empty texts join with a single blank line, authored first, tools in order."""
        base = WorkflowDocument(prompt="authored")
        contributions = [
            ToolContribution(tool="t1", document=WorkflowDocument(prompt="one")),
            ToolContribution(tool="t2", document=WorkflowDocument(prompt="two")),
        ]

        overlay = merge_workflow_overlay(base, contributions)

        assert overlay.workflow is not None
        assert overlay.workflow.prompt == "authored\n\none\n\ntwo"
        assert overlay.provenance == ["t1", "t2"]

    def test_merge_stage_fields_fill_only_unset_later_tool_wins(self) -> None:
        """Authored-set fields block every tool; unset fields take the later tool's value."""
        base = WorkflowDocument(stages={"build": WorkflowStage(agent="author-agent", loop=2)})
        contributions = [
            ToolContribution(
                tool="t1",
                document=WorkflowDocument(stages={"build": WorkflowStage(agent="t1-agent", skills=["s1"])}),
            ),
            ToolContribution(
                tool="t2",
                document=WorkflowDocument(stages={"build": WorkflowStage(agent="t2-agent", loop=5)}),
            ),
        ]

        overlay = merge_workflow_overlay(base, contributions)

        assert overlay.workflow is not None
        assert overlay.workflow.stages["build"].agent == "author-agent"
        assert overlay.workflow.stages["build"].loop == 2
        assert overlay.workflow.stages["build"].skills == ["s1"]
        assert base.stages["build"].skills is None  # purity — input untouched

    def test_merge_skip_false_overrides_nothing_authored_skip_unbeatable(self) -> None:
        """Only a positive skip is authored intent; a fresh name is fully tool-defined."""
        base = WorkflowDocument(stages={"build": WorkflowStage(skip=True)})
        contributions = [
            ToolContribution(
                tool="t1",
                document=WorkflowDocument(
                    stages={"build": WorkflowStage(skip=False), "deploy": WorkflowStage(skip=True)},
                ),
            ),
        ]

        overlay = merge_workflow_overlay(base, contributions)

        assert overlay.workflow is not None
        assert overlay.workflow.stages["build"].skip is True
        assert overlay.workflow.stages["deploy"].skip is True

    def test_merge_memory_authored_block_unbeatable_and_later_tool_wins(self) -> None:
        """Memory is whole-block: authored kept; else the later tool's block."""
        case_a = merge_workflow_overlay(
            WorkflowDocument(memory=WorkflowMemory(max_rules=5)),
            [ToolContribution(tool="t1", document=WorkflowDocument(memory=WorkflowMemory(max_rules=99)))],
        )
        case_b = merge_workflow_overlay(
            WorkflowDocument(prompt="authored"),
            [
                ToolContribution(tool="t1", document=WorkflowDocument(memory=WorkflowMemory(max_rules=7))),
                ToolContribution(tool="t2", document=WorkflowDocument(memory=WorkflowMemory(max_rules=9))),
            ],
        )

        assert case_a.workflow is not None
        assert case_a.workflow.memory is not None
        assert case_a.workflow.memory.max_rules == 5
        assert case_b.workflow is not None
        assert case_b.workflow.memory is not None
        assert case_b.workflow.memory.max_rules == 9

    def test_merge_extend_authored_names_win_and_later_tool_wins(self) -> None:
        """A contribution under an authored name is dropped; fresh names: later tool wins."""
        base = WorkflowDocument(extend={"audit": WorkflowExtendStage(after=["build"], body={"title": "Audit"})})
        contributions = [
            ToolContribution(
                tool="t1",
                document=WorkflowDocument(
                    extend={
                        "audit": WorkflowExtendStage(before=["build"], body={"title": "X"}),
                        "notify": WorkflowExtendStage(after=["deploy"], body={"title": "N1"}),
                    },
                ),
            ),
            ToolContribution(
                tool="t2",
                document=WorkflowDocument(
                    extend={"notify": WorkflowExtendStage(after=["audit"], body={"title": "N2"})},
                ),
            ),
        ]

        overlay = merge_workflow_overlay(base, contributions)

        assert overlay.workflow is not None
        assert overlay.workflow.extend["audit"].after == ["build"]
        assert overlay.workflow.extend["notify"].after == ["audit"]
        assert len(overlay.workflow.extend) == 2
        assert base.extend["audit"].after == ["build"]  # purity — input untouched

    def test_merge_empty_base_tools_build_the_document(self) -> None:
        """A None base with committed contributions produces a real document."""
        contributions = [
            ToolContribution(
                tool="t1",
                document=WorkflowDocument(prompt="one", stages={"build": WorkflowStage(agent="a")}),
            ),
            ToolContribution(tool="t2", document=WorkflowDocument(prompt="two")),
        ]

        overlay = merge_workflow_overlay(None, contributions)

        assert overlay.workflow is not None
        assert overlay.workflow.prompt == "one\n\ntwo"
        assert overlay.workflow.stages["build"].agent == "a"
        assert overlay.provenance == ["t1", "t2"]

    def test_merge_passthrough_short_circuit_returns_base_object(self) -> None:
        """Empty contributions return the passed workflow object itself — no rebuild."""
        base = WorkflowDocument(prompt="x")

        overlay = merge_workflow_overlay(base, [])

        assert overlay.workflow is base
        assert overlay.provenance == []
        assert merge_workflow_overlay(None, []).workflow is None

    def test_merge_builds_new_instances_and_never_mutates_inputs(self) -> None:
        """Purity — the result is new objects; base and contributions are untouched."""
        base_stage = WorkflowStage(agent="author-agent")
        base = WorkflowDocument(prompt="authored", stages={"build": base_stage})
        contribution_stage = WorkflowStage(agent="t1-agent")
        contribution = ToolContribution(
            tool="t1",
            document=WorkflowDocument(prompt="one", stages={"build": contribution_stage}),
        )

        overlay = merge_workflow_overlay(base, [contribution])

        assert overlay.workflow is not None
        assert overlay.workflow is not base
        assert overlay.workflow.stages["build"] is not base_stage
        assert overlay.workflow.stages["build"] is not contribution_stage
        assert base.prompt == "authored"
        assert base.stages == {"build": base_stage}
        assert base_stage.agent == "author-agent"
        assert contribution.document.prompt == "one"
        assert contribution.document.stages == {"build": contribution_stage}

    def test_merge_authored_names_order_first_then_fresh_names_in_order(self) -> None:
        """Deterministic stage order — authored names first, fresh names in appearance order."""
        base = WorkflowDocument(stages={"build": WorkflowStage(agent="author")})
        contributions = [
            ToolContribution(tool="t1", document=WorkflowDocument(stages={"scan": WorkflowStage(loop=1)})),
            ToolContribution(
                tool="t2",
                document=WorkflowDocument(stages={"audit": WorkflowStage(loop=2), "scan": WorkflowStage(loop=3)}),
            ),
        ]

        overlay = merge_workflow_overlay(base, contributions)

        assert overlay.workflow is not None
        assert list(overlay.workflow.stages) == ["build", "scan", "audit"]
        assert overlay.workflow.stages["scan"].loop == 3  # later tool wins on the fresh name
        assert overlay.workflow.stages["audit"].loop == 2

    def test_merge_manual_three_state_both_states_are_authored_intent(self) -> None:
        """Authored ``manual=True`` and ``manual=False`` both block tools; unset takes the tool's value.

        ``manual`` is three-state — True (force) and False (explicit cancel)
        are BOTH set — so a tool cannot flip an authored decision in either
        direction, but it fills an authored absence.
        """
        base = WorkflowDocument(
            stages={
                "force": WorkflowStage(manual=True),
                "cancel": WorkflowStage(manual=False),
                "open": WorkflowStage(agent="author-agent"),
            }
        )
        contributions = [
            ToolContribution(
                tool="t1",
                document=WorkflowDocument(
                    stages={
                        "force": WorkflowStage(manual=False),
                        "cancel": WorkflowStage(manual=True),
                        "open": WorkflowStage(manual=True),
                    }
                ),
            ),
        ]

        overlay = merge_workflow_overlay(base, contributions)

        assert overlay.workflow is not None
        assert overlay.workflow.stages["force"].manual is True  # authored True unbeatable
        assert overlay.workflow.stages["cancel"].manual is False  # authored False unbeatable
        assert overlay.workflow.stages["open"].manual is True  # unset — the tool fills

    def test_merge_empty_prompt_texts_are_dropped(self) -> None:
        """An empty-string prompt contributes nothing — the join drops empties."""
        overlay = merge_workflow_overlay(
            WorkflowDocument(prompt="authored"),
            [ToolContribution(tool="t1", document=WorkflowDocument(prompt=""))],
        )

        assert overlay.workflow is not None
        assert overlay.workflow.prompt == "authored"

    def test_merge_prompt_none_when_no_text_survives(self) -> None:
        """No authored prompt and no tool prompt — the merged prompt is ``None``."""
        overlay = merge_workflow_overlay(
            None,
            [ToolContribution(tool="t1", document=WorkflowDocument(stages={"build": WorkflowStage(agent="a")}))],
        )

        assert overlay.workflow is not None
        assert overlay.workflow.prompt is None
