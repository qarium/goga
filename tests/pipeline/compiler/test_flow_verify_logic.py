"""Logic tests for the ``FlowVerify`` dataclass.

Covers construction behavior beyond the contract surface: the list emission
form (a gate carrying no authored setting — the serializer writes the steps
alone), the container form (steps plus authored retry settings under the
engine vocabulary), the authored-zero boundary (``max_failures: 0`` and
``review_patience: 0`` are VALUES, never absences, so the serializer keys on
``is None``, never on truthiness), and the required ``steps`` field.
"""

from __future__ import annotations

import pytest
from goga.pipeline.compiler import FlowVerify, FlowVerifyStep


class TestFlowVerifyLogic:
    """Logic tests — construction behavior of the ``FlowVerify`` dataclass."""

    def test_flow_verify_defaults_carry_no_authored_setting(self) -> None:
        """A steps-only gate carries no authored setting — it IS the list emission form.

        Every downstream "authored any setting" decision keys on ``is None``
        checks across the three settings; the serializer picks the emission
        form from exactly this shape.
        """
        gate = FlowVerify(steps=[FlowVerifyStep(name="t", run="pytest")])

        assert gate.max_failures is None
        assert gate.review_patience is None
        assert gate.fresh_correction is None

    def test_flow_verify_stores_authored_settings_verbatim(self) -> None:
        """Every setting round-trips an authored block verbatim (no translation, no rewrite)."""
        gate = FlowVerify(
            steps=[FlowVerifyStep(name="t", run="pytest")],
            max_failures=2,
            review_patience=1,
            fresh_correction=True,
        )

        assert gate.max_failures == 2
        assert gate.review_patience == 1
        assert gate.fresh_correction is True

    def test_flow_verify_authored_zero_is_a_value(self) -> None:
        """Authored ``0`` on the two int settings survives as the integer zero, not absence.

        The falsy-zero boundary: the serializer deciding list vs container
        form must key on ``is None``, never on truthiness — this pin keeps
        the authored zero distinguishable from an unauthored setting.
        """
        gate = FlowVerify(steps=[], max_failures=0, review_patience=0)

        assert gate.max_failures == 0
        assert gate.max_failures is not None
        assert gate.review_patience == 0
        assert gate.review_patience is not None

    def test_flow_verify_authored_false_is_a_value(self) -> None:
        """An authored ``fresh_correction: false`` stays ``False`` — distinct from absence.

        The bool twin of the zero boundary: ``False`` (explicitly authored
        off) and ``None`` (not authored) carry different meanings downstream
        — the latter is the list form, the former the container form.
        """
        gate = FlowVerify(steps=[], fresh_correction=False)

        assert gate.fresh_correction is False
        assert gate.fresh_correction is not None

    def test_flow_verify_steps_has_no_default(self) -> None:
        """``steps`` is required — construction without it raises TypeError."""
        with pytest.raises(TypeError):
            FlowVerify(max_failures=1)  # type: ignore[call-arg]

    def test_flow_verify_steps_carried_in_authored_order(self) -> None:
        """The steps list keeps the authored order — the compiler threads it, the model stores it."""
        first = FlowVerifyStep(name="Unit tests", run="pytest -q")
        second = FlowVerifyStep(name="Code review", command="/home/goga/bin/codex-as-claude.sh")

        gate = FlowVerify(steps=[first, second])

        assert gate.steps == [first, second]

    def test_equality_of_identical_constructions(self) -> None:
        """Two gates with identical fields compare equal; a differing setting does not."""
        steps = [FlowVerifyStep(name="t", run="pytest")]

        assert FlowVerify(steps=steps) == FlowVerify(steps=steps)
        assert FlowVerify(steps=steps) != FlowVerify(steps=steps, max_failures=1)
