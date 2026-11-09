"""Logic tests for the ``WorkflowGateStep`` dataclass.

Covers construction behavior beyond the contract surface: the two step forms
the parser threads (a shell step carrying ``script``, an AI-review step
carrying ``agent`` — possibly with ``prompt``), the verbatim carriage of
``timeout``/``prompt`` (value grammar is engine-owned), and the model's
deliberate purity — the exactly-one-of-``script``/``agent`` exclusivity is a
PARSE-time guarantee, so the dataclass itself performs no exclusivity check
and raises nothing on a degenerate instance.
"""

from __future__ import annotations

import pytest
from goga.pipeline.workflow import WorkflowGateStep


class TestWorkflowGateStepLogic:
    """Logic tests — construction behavior of the ``WorkflowGateStep`` dataclass."""

    def test_workflow_gate_step_shell_form_carries_script(self) -> None:
        """A shell step — what the parser threads for ``script:`` — stores the command verbatim.

        ``agent`` and ``prompt`` stay ``None``: ``prompt`` is forbidden on a
        script gate step at parse time, so a shell instance never carries
        one.
        """
        step = WorkflowGateStep(name="Unit tests", script="pytest -q", timeout="30m")

        assert step.name == "Unit tests"
        assert step.script == "pytest -q"
        assert step.agent is None
        assert step.timeout == "30m"
        assert step.prompt is None

    def test_workflow_gate_step_ai_form_carries_agent_and_prompt(self) -> None:
        """An AI-review step — what the parser threads for ``agent:`` — stores both verbatim."""
        step = WorkflowGateStep(name="Code review", agent="codex", prompt="Review the diff for correctness.")

        assert step.name == "Code review"
        assert step.agent == "codex"
        assert step.script is None
        assert step.prompt == "Review the diff for correctness."
        assert step.timeout is None

    def test_workflow_gate_step_values_pass_verbatim(self) -> None:
        """Timeout and prompt round-trip unvalidated — no grammar check at the model level."""
        step = WorkflowGateStep(name="t", script="make check", timeout="30x", prompt=None)

        assert step.timeout == "30x"

    def test_workflow_gate_step_model_performs_no_exclusivity_check(self) -> None:
        """The dataclass raises nothing on a degenerate instance — the exclusivity is parse-time.

        Exactly one of ``script``/``agent`` not ``None`` is guaranteed by
        :func:`parse_workflow` BEFORE construction; the model itself is pure
        data, so both-set and neither-set instances construct without error
        (the parser never threads them — this pin documents the boundary).
        """
        both = WorkflowGateStep(name="both", script="pytest", agent="codex")
        neither = WorkflowGateStep(name="neither")

        assert (both.script, both.agent) == ("pytest", "codex")
        assert (neither.script, neither.agent) == (None, None)

    def test_workflow_gate_step_name_required(self) -> None:
        """``name`` has no default — construction without it raises TypeError."""
        with pytest.raises(TypeError):
            WorkflowGateStep(script="pytest -q")  # type: ignore[call-arg]

    def test_equality_of_identical_constructions(self) -> None:
        """Two steps with identical fields compare equal; a differing field does not."""
        assert WorkflowGateStep(name="t", script="pytest") == WorkflowGateStep(name="t", script="pytest")
        assert WorkflowGateStep(name="t", script="pytest") != WorkflowGateStep(name="t", agent="codex")
