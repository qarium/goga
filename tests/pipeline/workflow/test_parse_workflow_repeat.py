"""Contract and logic tests for the ``repeat`` authoring surface of ``parse_workflow``.

Covers the run-cycle tuning vocabulary the workflow-cell CODEMANIFEST
declares: the optional top-level ``repeat`` block (a mapping with at most
``max_cycles``/``keep_runs``, both non-negative ints — bools and floats are
non-ints), the empty-block-equals-absence normalization, the repeat-only
workflow validity (the block counts as content), and the nine-key top-level
grammar. The contract class pins the API shape; the logic classes exercise
every documented message verbatim.
"""

from __future__ import annotations

import re

import pytest
from goga.pipeline.workflow import (
    WorkflowDocument,
    WorkflowSyntaxError,
    parse_workflow,
)


class TestParseWorkflowRepeatContract:
    """Contract tests — the repeat block on the ``parse_workflow`` surface."""

    def test_parse_repeat_only_workflow_is_valid(self) -> None:
        """A workflow consisting of the repeat block alone parses (the block counts as content)."""
        document = parse_workflow("repeat:\n  max_cycles: 2\n")

        assert isinstance(document, WorkflowDocument)
        assert document.prompt is None
        assert not document.stages
        assert document.repeat is not None
        assert document.repeat.max_cycles == 2

    def test_parse_repeat_top_level_key_accepted_on_empty_workflow(self) -> None:
        """A ``repeat`` top-level key on an otherwise-empty workflow is ACCEPTED."""
        document = parse_workflow("repeat:\n  keep_runs: 1\n")

        assert document.repeat is not None
        assert document.repeat.keep_runs == 1
        assert document.repeat.max_cycles is None


class TestParseWorkflowRepeatLogic:
    """Logic tests — the repeat block's authored-values carry and normalizations."""

    def test_parse_repeat_block_carries_authored_keys(self) -> None:
        """A repeat block with both keys parses them verbatim onto the document."""
        document = parse_workflow("repeat:\n  max_cycles: 3\n  keep_runs: 5\nprompt: x\n")

        assert document.repeat is not None
        assert document.repeat.max_cycles == 3
        assert document.repeat.keep_runs == 5

    def test_parse_repeat_block_single_key_and_zero_values(self) -> None:
        """Each key authors alone; an authored zero is a VALUE, never an absence."""
        zero_cycles = parse_workflow("repeat:\n  max_cycles: 0\nprompt: x\n")
        zero_runs = parse_workflow("repeat:\n  keep_runs: 0\nprompt: x\n")
        one_cycle = parse_workflow("repeat:\n  max_cycles: 1\nprompt: x\n")

        assert zero_cycles.repeat is not None
        assert zero_cycles.repeat.max_cycles == 0
        assert zero_cycles.repeat.keep_runs is None

        assert zero_runs.repeat is not None
        assert zero_runs.repeat.max_cycles is None
        assert zero_runs.repeat.keep_runs == 0

        assert one_cycle.repeat is not None
        assert one_cycle.repeat.max_cycles == 1
        assert one_cycle.repeat.keep_runs is None

    def test_parse_repeat_empty_block_equals_absence(self) -> None:
        """``repeat: {}`` normalizes to ``None`` (the workflow stays valid via prompt)."""
        document = parse_workflow("repeat: {}\nprompt: x\n")

        assert document.repeat is None
        assert document.prompt == "x"

    def test_parse_empty_workflow_still_rejects_profile_only(self) -> None:
        """A profile-only workflow stays empty — activation is not content."""
        with pytest.raises(
            WorkflowSyntaxError,
            match=re.escape(
                "empty workflow — provide at least prompt, one stage, one extend entry, "
                "the memory block, the build block, the assistants block, the delegation block, "
                "or the repeat block"
            ),
        ):
            parse_workflow("profile: dev\n")


class TestParseWorkflowRepeatRejections:
    """Negative logic tests — every structural defect of the ``repeat`` block."""

    @pytest.mark.parametrize(
        "block_yaml",
        [
            "repeat: true\n",
            "repeat: false\n",
            "repeat: 5\n",
            "repeat: [1, 2]\n",
            "repeat: soon\n",
        ],
    )
    def test_parse_repeat_non_mapping_block(self, block_yaml: str) -> None:
        """A non-mapping repeat block (scalar, list, or string) is rejected."""
        with pytest.raises(WorkflowSyntaxError, match=re.escape("non-mapping repeat block in workflow")):
            parse_workflow(f"{block_yaml}prompt: x\n")

    def test_parse_repeat_unknown_key(self) -> None:
        """An unknown repeat key is rejected listing the two valid keys."""
        with pytest.raises(
            WorkflowSyntaxError,
            match=re.escape("unknown key in workflow.repeat: cycles; valid keys: max_cycles, keep_runs"),
        ):
            parse_workflow("repeat:\n  max_cycles: 1\n  cycles: 3\nprompt: x\n")

    @pytest.mark.parametrize(
        ("block_yaml", "message"),
        [
            ("repeat:\n  max_cycles: true\n", "non-int value in workflow.repeat.max_cycles"),
            ("repeat:\n  keep_runs: true\n", "non-int value in workflow.repeat.keep_runs"),
            ('repeat:\n  keep_runs: "3"\n', "non-int value in workflow.repeat.keep_runs"),
            ("repeat:\n  max_cycles: 1.5\n", "non-int value in workflow.repeat.max_cycles"),
            ("repeat:\n  max_cycles: -1\n", "max_cycles must be >= 0 in workflow.repeat"),
            ("repeat:\n  keep_runs: -2\n", "keep_runs must be >= 0 in workflow.repeat"),
        ],
    )
    def test_parse_repeat_non_int_and_negative_values(self, block_yaml: str, message: str) -> None:
        """A non-int bound (bool, str, float) or a negative one is rejected."""
        with pytest.raises(WorkflowSyntaxError, match=re.escape(message)):
            parse_workflow(f"{block_yaml}prompt: x\n")
