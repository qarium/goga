"""Logic tests for the ``WorkflowGates`` dataclass.

Covers construction behavior beyond the contract surface: the defaults carry
no authored key (``None`` on every field — the model materializes nothing),
the verbatim round-trip of an authored block, and the authored-zero boundary
— ``patience: 0`` and ``max_iterations: 0`` are VALUES, never absences, so
the consumers can distinguish "no bound" (``None``) from "zero" (``0``)
without a falsy trap.
"""

from __future__ import annotations

from goga.pipeline.workflow import WorkflowGates


class TestWorkflowGatesLogic:
    """Logic tests — construction behavior of the ``WorkflowGates`` dataclass."""

    def test_workflow_gates_defaults_carry_no_authored_key(self) -> None:
        """Constructing with no arguments yields pure absence on every field.

        An empty settings block parses to ``None`` (the parser normalizes
        emptiness), so a default construction is exactly "no authored key" —
        every downstream "authored any key" decision keys on ``is None``.
        """
        gates = WorkflowGates()

        assert gates.patience is None
        assert gates.max_iterations is None
        assert gates.fresh_correction is None

    def test_workflow_gates_stores_authored_values_verbatim(self) -> None:
        """Every field round-trips an authored block verbatim (no translation, no rewrite)."""
        gates = WorkflowGates(patience=2, max_iterations=5, fresh_correction=True)

        assert gates.patience == 2
        assert gates.max_iterations == 5
        assert gates.fresh_correction is True

    def test_workflow_gates_authored_zero_is_a_value(self) -> None:
        """Authored ``0`` on the two int fields survives as the integer zero, not absence.

        The falsy-zero boundary: the consumer translating into the engine
        vocabulary must key on ``is None``, never on truthiness — this pin
        keeps the authored zero distinguishable from an unauthored field.
        """
        gates = WorkflowGates(patience=0, max_iterations=0)

        assert gates.patience == 0
        assert gates.patience is not None
        assert gates.max_iterations == 0
        assert gates.max_iterations is not None

    def test_workflow_gates_authored_false_is_a_value(self) -> None:
        """An authored ``fresh_correction: false`` stays ``False`` — distinct from absence.

        The bool twin of the zero boundary: ``False`` (explicitly authored
        off) and ``None`` (not authored) carry different meanings downstream.
        """
        gates = WorkflowGates(fresh_correction=False)

        assert gates.fresh_correction is False
        assert gates.fresh_correction is not None

    def test_equality_of_identical_constructions(self) -> None:
        """Two blocks with identical fields compare equal; a differing field does not."""
        assert WorkflowGates() == WorkflowGates(patience=None, max_iterations=None, fresh_correction=None)
        assert WorkflowGates(patience=1) != WorkflowGates(patience=2)
