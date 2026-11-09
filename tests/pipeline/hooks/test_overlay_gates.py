"""Contract and logic tests for the quality-gate arm of the overlay merge — the
``gates`` vocabulary of ``goga/pipeline/hooks/CODEMANIFEST`` with ``location:
overlay.py``:

- ``merge_workflow_overlay`` step 4d — the whole-block gates settings merge
  (authored unbeatable, else the later contributing tool wins) and the
  rebuild carry (the settings block rides the rebuilt document verbatim)
- step 5b — the per-stage ``gates`` field of the field-set-complete stage
  merge: an authored check-step list is never overwritten, an unset one
  takes the later contributing tool that sets it

Supported data and pure functions only — no mocks, no filesystem: the merge
is pure (inputs never mutated, new instances returned) and both gate
surfaces ride the merge whole (no field-level merging, no interpretation,
no rebuild).
"""

from __future__ import annotations

from goga.pipeline.hooks import ToolContribution, merge_workflow_overlay
from goga.pipeline.workflow import (
    WorkflowDocument,
    WorkflowGates,
    WorkflowGateStep,
    WorkflowStage,
)

# --- Contract tests ---


class TestOverlayGatesContract:
    def test_authored_gates_passthrough_with_no_contributions(self) -> None:
        """Empty contributions return the passed workflow itself — its gates intact."""
        base = WorkflowDocument(prompt="authored", gates=WorkflowGates(patience=2))

        overlay = merge_workflow_overlay(base, [])

        assert overlay.workflow is base
        assert overlay.workflow.gates is not None
        assert overlay.workflow.gates.patience == 2

    def test_gates_only_contribution_builds_the_document(self) -> None:
        """A None base with a gates-carrying contribution yields a real workflow."""
        overlay = merge_workflow_overlay(
            None,
            [ToolContribution(tool="t1", document=WorkflowDocument(gates=WorkflowGates(max_iterations=4)))],
        )

        assert overlay.workflow is not None
        assert overlay.workflow.gates is not None
        assert overlay.workflow.gates.max_iterations == 4

    def test_authored_gates_survives_the_rebuild(self) -> None:
        """A rebuilt document with an authored gates block keeps the authored block whole."""
        base = WorkflowDocument(prompt="authored", gates=WorkflowGates(patience=2))
        contributions = [
            ToolContribution(
                tool="t1",
                document=WorkflowDocument(prompt="one", gates=WorkflowGates(max_iterations=9)),
            ),
        ]

        overlay = merge_workflow_overlay(base, contributions)

        assert overlay.workflow is not None
        assert overlay.workflow is not base
        assert overlay.workflow.gates is not None
        assert overlay.workflow.gates.patience == 2


# --- Logic tests (the design's scenarios, verbatim) ---


class TestMergeGates:
    def test_authored_settings_block_unbeatable_and_stage_gates_fill(self) -> None:
        """The settings block is whole-block; the stage field is authored-wins field.

        Scenario one: an authored settings block keeps every key and blocks
        the contributions entirely (no field-level merging — the authored
        ``max_iterations`` absence stays absent) while the per-stage lists
        ride their own field merge — the authored list of ``a`` stands, the
        tool's fresh stage ``b`` arrives with its list whole.
        """
        step = WorkflowGateStep(name="compile", script="make all")
        other_step = WorkflowGateStep(name="Check", agent="codex")
        base = WorkflowDocument(
            gates=WorkflowGates(patience=1),
            stages={"a": WorkflowStage(prompt="do", gates=[step])},
        )

        overlay = merge_workflow_overlay(
            base,
            [
                ToolContribution(
                    tool="t1",
                    document=WorkflowDocument(
                        gates=WorkflowGates(max_iterations=9),
                        stages={"b": WorkflowStage(prompt="fill", gates=[other_step])},
                    ),
                ),
            ],
        )

        assert overlay.workflow is not None
        assert overlay.workflow.gates is not None
        assert overlay.workflow.gates.patience == 1  # authored wins
        assert overlay.workflow.gates.max_iterations is None  # contribution NOT merged in — whole-block
        assert overlay.workflow.stages["a"].gates == [step]  # authored list never overwritten
        assert overlay.workflow.stages["b"].gates == [other_step]  # the fresh stage carries its list

    def test_gates_only_contribution_rides_the_merge(self) -> None:
        """A gates-only contribution is content — it commits and rides the merge."""
        overlay = merge_workflow_overlay(
            None,
            [ToolContribution(tool="t", document=WorkflowDocument(gates=WorkflowGates(max_iterations=1)))],
        )

        assert overlay.workflow is not None
        assert overlay.workflow.gates is not None
        assert overlay.workflow.gates.max_iterations == 1

    def test_overlay_gates_settings_rides_the_rebuild_verbatim(self) -> None:
        """The effective settings block is the SAME object — carried whole, never rebuilt."""
        authored = WorkflowGates(patience=2, fresh_correction=True)

        overlay = merge_workflow_overlay(
            WorkflowDocument(prompt="authored", gates=authored),
            [ToolContribution(tool="t1", document=WorkflowDocument(prompt="one"))],
        )

        assert overlay.workflow is not None
        assert overlay.workflow.gates is authored  # verbatim — the same object
        assert authored.patience == 2  # purity — the input block untouched
        assert authored.fresh_correction is True

    def test_overlay_later_tool_settings_wins_when_unset(self) -> None:
        """With no authored block the later contributing tool's block wins whole."""
        overlay = merge_workflow_overlay(
            WorkflowDocument(prompt="authored"),
            [
                ToolContribution(tool="t1", document=WorkflowDocument(gates=WorkflowGates(patience=9))),
                ToolContribution(tool="t2", document=WorkflowDocument(gates=WorkflowGates(max_iterations=7))),
            ],
        )

        assert overlay.workflow is not None
        assert overlay.workflow.gates is not None
        assert overlay.workflow.gates.max_iterations == 7  # later tool wins
        assert overlay.workflow.gates.patience is None  # whole-block — no field merge between tools

    def test_overlay_tool_gates_survives_a_later_non_carrying_tool(self) -> None:
        """A later tool without a block never clobbers an earlier tool's block.

        The assignment into the slot happens only for a carrying
        contribution — a later prompt-only tool must leave an earlier
        tool's contributed gate setting intact, not reset the slot to
        ``None``.
        """
        overlay = merge_workflow_overlay(
            WorkflowDocument(prompt="authored"),
            [
                ToolContribution(tool="t1", document=WorkflowDocument(gates=WorkflowGates(max_iterations=4))),
                ToolContribution(tool="t2", document=WorkflowDocument(prompt="two")),
            ],
        )

        assert overlay.workflow is not None
        assert overlay.workflow.gates is not None
        assert overlay.workflow.gates.max_iterations == 4

    def test_overlay_gates_absent_when_no_one_authors_one(self) -> None:
        """Neither the base nor any contribution carries a block — the slot stays ``None``."""
        overlay = merge_workflow_overlay(
            WorkflowDocument(prompt="authored"),
            [ToolContribution(tool="t1", document=WorkflowDocument(prompt="one"))],
        )

        assert overlay.workflow is not None
        assert overlay.workflow.gates is None


class TestMergeStageGates:
    def test_authored_stage_gates_unbeatable_by_a_tool_list(self) -> None:
        """An authored check-step list is never overwritten — the field, whole."""
        authored = [WorkflowGateStep(name="compile", script="make all")]
        base = WorkflowDocument(
            stages={"build": WorkflowStage(prompt="do", gates=authored)},
        )

        overlay = merge_workflow_overlay(
            base,
            [
                ToolContribution(
                    tool="t1",
                    document=WorkflowDocument(
                        stages={"build": WorkflowStage(gates=[WorkflowGateStep(name="tool", script="pytest")])},
                    ),
                ),
            ],
        )

        assert overlay.workflow is not None
        assert overlay.workflow.stages["build"].gates is authored  # the same list, verbatim

    def test_unset_stage_gates_take_the_later_setting_tool(self) -> None:
        """A field the author left unset takes the later contributing tool that sets it."""
        base = WorkflowDocument(stages={"build": WorkflowStage(prompt="do")})

        overlay = merge_workflow_overlay(
            base,
            [
                ToolContribution(
                    tool="t1",
                    document=WorkflowDocument(
                        stages={"build": WorkflowStage(gates=[WorkflowGateStep(name="first", script="a")])},
                    ),
                ),
                ToolContribution(
                    tool="t2",
                    document=WorkflowDocument(
                        stages={"build": WorkflowStage(gates=[WorkflowGateStep(name="second", script="b")])},
                    ),
                ),
            ],
        )

        assert overlay.workflow is not None
        gates = overlay.workflow.stages["build"].gates

        assert gates is not None
        assert [step.name for step in gates] == ["second"]  # the later tool wins — no list concatenation

    def test_stage_gates_absent_when_no_one_sets_them(self) -> None:
        """No authored list, no contributing list — the rebuilt stage keeps ``gates=None``."""
        base = WorkflowDocument(stages={"build": WorkflowStage(prompt="do")})

        overlay = merge_workflow_overlay(
            base,
            [ToolContribution(tool="t1", document=WorkflowDocument(prompt="one"))],
        )

        assert overlay.workflow is not None
        assert overlay.workflow.stages["build"].gates is None

    def test_stage_gates_inputs_never_mutated(self) -> None:
        """Purity — the authored and contributing stage objects keep their own lists."""
        authored = [WorkflowGateStep(name="compile", script="make all")]
        tool_list = [WorkflowGateStep(name="tool", script="pytest")]
        base = WorkflowDocument(stages={"build": WorkflowStage(prompt="do", gates=authored)})
        contribution = ToolContribution(
            tool="t1",
            document=WorkflowDocument(stages={"build": WorkflowStage(prompt="tool", gates=tool_list)}),
        )

        merge_workflow_overlay(base, [contribution])

        assert authored == [WorkflowGateStep(name="compile", script="make all")]
        assert tool_list == [WorkflowGateStep(name="tool", script="pytest")]
        assert contribution.document.stages["build"].gates is tool_list
