"""Contract and logic tests for the run-cycle arm of the overlay merge — the
``repeat`` vocabulary of ``goga/pipeline/hooks/CODEMANIFEST`` with ``location:
overlay.py`` / ``events.py``:

- ``merge_workflow_overlay`` step 4c — the whole-block repeat merge
  (authored unbeatable, else the later contributing tool wins) and the
  rebuild carry (the ninth field rides the rebuilt document verbatim)
- ``PipelineHooks.amend_workflow`` — the emptiness discard counts ``repeat``:
  a repeat-only contribution is content, it commits and merges

Supported data and pure functions only — no mocks, no filesystem: the merge
is pure (inputs never mutated, new instances returned) and the block rides
the merge whole (no field-level merging, no interpretation).
"""

from __future__ import annotations

from goga.pipeline.hooks import ToolContribution, merge_workflow_overlay
from goga.pipeline.workflow import WorkflowDocument, WorkflowRepeat

# --- Contract tests ---


class TestOverlayRepeatContract:
    def test_authored_repeat_passthrough_with_no_contributions(self) -> None:
        """Empty contributions return the passed workflow itself — its repeat intact."""
        base = WorkflowDocument(prompt="authored", repeat=WorkflowRepeat(max_cycles=2))

        overlay = merge_workflow_overlay(base, [])

        assert overlay.workflow is base
        assert overlay.workflow.repeat is not None
        assert overlay.workflow.repeat.max_cycles == 2

    def test_repeat_only_contribution_builds_the_document(self) -> None:
        """A None base with a repeat-carrying contribution yields a real workflow."""
        overlay = merge_workflow_overlay(
            None,
            [ToolContribution(tool="t1", document=WorkflowDocument(repeat=WorkflowRepeat(max_cycles=4)))],
        )

        assert overlay.workflow is not None
        assert overlay.workflow.repeat is not None
        assert overlay.workflow.repeat.max_cycles == 4

    def test_authored_repeat_survives_the_rebuild(self) -> None:
        """A rebuilt document with an authored repeat keeps the authored block whole."""
        base = WorkflowDocument(prompt="authored", repeat=WorkflowRepeat(max_cycles=2))
        contributions = [
            ToolContribution(
                tool="t1",
                document=WorkflowDocument(prompt="one", repeat=WorkflowRepeat(max_cycles=9)),
            ),
        ]

        overlay = merge_workflow_overlay(base, contributions)

        assert overlay.workflow is not None
        assert overlay.workflow is not base
        assert overlay.workflow.repeat is not None
        assert overlay.workflow.repeat.max_cycles == 2


# --- Logic tests (the design's scenarios, verbatim) ---


class TestMergeRepeat:
    def test_overlay_authored_repeat_wins_and_contribution_fills(self) -> None:
        """The whole-block rule — authored unbeatable, else the later tool fills.

        Scenario 1: an authored block keeps every field and blocks the
        contributions entirely (no field-level merging — the authored
        ``keep_runs`` absence stays absent). Scenario 2: with no authored
        block the later contributing tool's block wins whole.
        """
        scenario_one = merge_workflow_overlay(
            WorkflowDocument(prompt="authored", repeat=WorkflowRepeat(max_cycles=2)),
            [
                ToolContribution(tool="t1", document=WorkflowDocument(repeat=WorkflowRepeat(keep_runs=9))),
                ToolContribution(tool="t2", document=WorkflowDocument(repeat=WorkflowRepeat(max_cycles=7))),
            ],
        )
        scenario_two = merge_workflow_overlay(
            WorkflowDocument(prompt="authored"),
            [
                ToolContribution(tool="t1", document=WorkflowDocument(repeat=WorkflowRepeat(keep_runs=9))),
                ToolContribution(tool="t2", document=WorkflowDocument(repeat=WorkflowRepeat(max_cycles=7))),
            ],
        )

        assert scenario_one.workflow is not None
        assert scenario_one.workflow.repeat is not None
        assert scenario_one.workflow.repeat.max_cycles == 2  # authored wins
        assert scenario_one.workflow.repeat.keep_runs is None  # contribution NOT merged in — whole-block
        assert scenario_two.workflow is not None
        assert scenario_two.workflow.repeat is not None
        assert scenario_two.workflow.repeat.max_cycles == 7  # later tool wins
        assert scenario_two.workflow.repeat.keep_runs is None

    def test_overlay_repeat_rides_the_rebuild_verbatim(self) -> None:
        """The effective repeat is the SAME object — carried whole, never rebuilt."""
        authored = WorkflowRepeat(max_cycles=2, keep_runs=5)

        overlay = merge_workflow_overlay(
            WorkflowDocument(prompt="authored", repeat=authored),
            [ToolContribution(tool="t1", document=WorkflowDocument(prompt="one"))],
        )

        assert overlay.workflow is not None
        assert overlay.workflow.repeat is authored  # verbatim — the same object
        assert authored.max_cycles == 2  # purity — the input block untouched
        assert authored.keep_runs == 5

    def test_overlay_tool_repeat_survives_a_later_non_carrying_tool(self) -> None:
        """A later tool without a block never clobbers an earlier tool's block.

        The assignment into the slot happens only for a carrying
        contribution — a later prompt-only tool must leave an earlier
        tool's authored cycle bound intact, not reset the slot to ``None``.
        """
        overlay = merge_workflow_overlay(
            WorkflowDocument(prompt="authored"),
            [
                ToolContribution(tool="t1", document=WorkflowDocument(repeat=WorkflowRepeat(max_cycles=4))),
                ToolContribution(tool="t2", document=WorkflowDocument(prompt="two")),
            ],
        )

        assert overlay.workflow is not None
        assert overlay.workflow.repeat is not None
        assert overlay.workflow.repeat.max_cycles == 4

    def test_overlay_repeat_absent_when_no_one_authors_one(self) -> None:
        """Neither the base nor any contribution carries a block — the slot stays ``None``."""
        overlay = merge_workflow_overlay(
            WorkflowDocument(prompt="authored"),
            [ToolContribution(tool="t1", document=WorkflowDocument(prompt="one"))],
        )

        assert overlay.workflow is not None
        assert overlay.workflow.repeat is None
