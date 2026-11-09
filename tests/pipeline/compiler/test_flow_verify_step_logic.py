"""Logic tests for the ``FlowVerifyStep`` dataclass.

Covers construction behavior beyond the contract surface: the two emitted
step forms (:func:`compile_flow` builds a shell step carrying ``run`` and an
AI step carrying ``command`` — the wrapper path), the verbatim carriage of
``timeout``/``prompt`` (value grammar is engine-owned), and the model's
deliberate purity — the exactly-one-of-``run``/``command`` exclusivity is a
COMPILE-time guarantee threaded by :func:`compile_flow`, so the dataclass
itself performs no exclusivity check and raises nothing on a degenerate
instance.
"""

from __future__ import annotations

import pytest
from goga.pipeline.compiler import FlowVerifyStep


class TestFlowVerifyStepLogic:
    """Logic tests — construction behavior of the ``FlowVerifyStep`` dataclass."""

    def test_flow_verify_step_shell_form_carries_run(self) -> None:
        """A shell step — what ``compile_flow`` builds from ``script:`` — stores the command verbatim.

        ``command`` and ``prompt`` stay ``None``: a shell instance never
        carries an AI launch command or a review instruction.
        """
        step = FlowVerifyStep(name="compile", run="make all", timeout="1h")

        assert step.name == "compile"
        assert step.run == "make all"
        assert step.command is None
        assert step.timeout == "1h"
        assert step.prompt is None

    def test_flow_verify_step_ai_form_carries_command_and_prompt(self) -> None:
        """An AI step — what ``compile_flow`` builds from ``agent:`` — stores the composed command and prompt."""
        step = FlowVerifyStep(
            name="Check",
            command="/home/goga/bin/codex-as-claude.sh",
            timeout="15m",
            prompt="Be strict.",
        )

        assert step.name == "Check"
        assert step.command == "/home/goga/bin/codex-as-claude.sh"
        assert step.run is None
        assert step.timeout == "15m"
        assert step.prompt == "Be strict."

    def test_flow_verify_step_values_pass_verbatim(self) -> None:
        """Timeout and prompt round-trip unvalidated — no grammar check at the model level."""
        step = FlowVerifyStep(name="t", run="make check", timeout="30x")

        assert step.timeout == "30x"

    def test_flow_verify_step_model_performs_no_exclusivity_check(self) -> None:
        """The dataclass raises nothing on a degenerate instance — the exclusivity is compile-time.

        Exactly one of ``run``/``command`` not ``None`` is guaranteed by
        :func:`compile_flow` BEFORE construction; the model itself is pure
        data, so both-set and neither-set instances construct without error
        (the compiler never threads them — this pin documents the boundary).
        """
        both = FlowVerifyStep(name="both", run="pytest", command="/home/goga/bin/codex-as-claude.sh")
        neither = FlowVerifyStep(name="neither")

        assert (both.run, both.command) == ("pytest", "/home/goga/bin/codex-as-claude.sh")
        assert (neither.run, neither.command) == (None, None)

    def test_flow_verify_step_name_required(self) -> None:
        """``name`` has no default — construction without it raises TypeError."""
        with pytest.raises(TypeError):
            FlowVerifyStep(run="pytest -q")  # type: ignore[call-arg]

    def test_equality_of_identical_constructions(self) -> None:
        """Two steps with identical fields compare equal; a differing field does not."""
        assert FlowVerifyStep(name="t", run="pytest") == FlowVerifyStep(name="t", run="pytest")
        assert FlowVerifyStep(name="t", run="pytest") != FlowVerifyStep(name="t", command="/x/y.sh")
