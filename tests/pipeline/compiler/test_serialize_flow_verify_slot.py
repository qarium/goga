"""Logic tests for the stage ``verify`` slot + ``serialize_flow`` emission.

Covers the verify serializer arm: a ``FlowVerify`` in a stage's ``fields`` is
rebuilt by ``_verify_repr`` — an instance carrying no authored setting IS the
list emission form (the steps list written directly under ``verify:``);
any authored setting switches to the container form (the ordered ``steps``
key first, then the present settings in the fixed order ``max_failures,
review_patience, fresh_correction`` — plain scalars, step fields never at the
container top level). Each step is rebuilt by ``_verify_step_repr`` in the
fixed key order ``name, run xor command, timeout, prompt``; multi-line
``run``/``command``/``timeout``/``prompt`` strings wrap in
``_BlockLiteralScript``. A stage without a gate never enters the arm — no
``verify`` key, byte-identical text.
"""

from __future__ import annotations

from goga.pipeline.compiler import FlowDocument, FlowStage, FlowVerify, FlowVerifyStep, serialize_flow


def _stage_with(fields: dict[str, object]) -> FlowStage:
    """Build one ``FlowStage`` whose fields carry a ``prompt`` plus the given extras."""
    merged: dict[str, object] = {"prompt": "Do"}
    merged.update(fields)

    return FlowStage(id="a", name="A", depends_on=None, fields=merged)


def _doc(stage: FlowStage) -> FlowDocument:
    """Build a minimal single-stage ``FlowDocument`` around the given stage."""
    return FlowDocument(name="n", description="d", stages=[stage])


class TestSerializeFlowVerifyListForm:
    """The list emission form — no authored setting writes the steps list alone."""

    def test_verify_list_form_is_the_steps_list(self) -> None:
        """A settings-free ``FlowVerify`` writes the steps directly under ``verify:``."""
        gate = FlowVerify(steps=[FlowVerifyStep(name="t", run="pytest")])

        text = serialize_flow(_doc(_stage_with({"verify": gate})))

        assert "verify:\n" in text
        assert "steps:" not in text
        assert "- name: t\n" in text

    def test_verify_list_form_indentation_pinned(self) -> None:
        """Dashes align with ``verify:`` at 2 spaces; step fields sit at 4."""
        gate = FlowVerify(steps=[FlowVerifyStep(name="t", run="pytest")])

        text = serialize_flow(_doc(_stage_with({"verify": gate})))

        assert "  verify:\n" in text
        assert "  - name: t\n" in text
        assert "    run: pytest\n" in text

    def test_verify_list_form_shell_step_emits_no_command_key(self) -> None:
        """A shell step writes ``run`` and never a ``command`` key."""
        gate = FlowVerify(steps=[FlowVerifyStep(name="t", run="pytest", timeout="1h")])

        text = serialize_flow(_doc(_stage_with({"verify": gate})))

        assert "run: pytest\n" in text
        assert "timeout: 1h\n" in text
        assert "command:" not in text

    def test_verify_list_form_ai_step_emits_no_run_key(self) -> None:
        """An AI step writes ``command`` and never a ``run`` key."""
        gate = FlowVerify(steps=[FlowVerifyStep(name="r", command="/x/y.sh", prompt="Be strict.")])

        text = serialize_flow(_doc(_stage_with({"verify": gate})))

        assert "command: /x/y.sh\n" in text
        assert "run:" not in text

    def test_verify_list_form_multiline_run_is_block_literal(self) -> None:
        """A multi-line ``run`` string wraps in ``_BlockLiteralScript`` (block-literal style)."""
        gate = FlowVerify(steps=[FlowVerifyStep(name="t", run="pytest -q\nruff check .")])

        text = serialize_flow(_doc(_stage_with({"verify": gate})))

        assert "    run: |-\n" in text
        assert "      pytest -q\n" in text
        assert "      ruff check .\n" in text

    def test_verify_list_form_authored_false_setting_switches_to_container(self) -> None:
        """An authored ``fresh_correction=False`` is a setting — the container form fires."""
        gate = FlowVerify(steps=[FlowVerifyStep(name="t", run="pytest")], fresh_correction=False)

        text = serialize_flow(_doc(_stage_with({"verify": gate})))

        assert "steps:\n" in text
        assert "fresh_correction: false\n" in text


class TestSerializeFlowVerifyContainerForm:
    """The container emission form — any authored setting writes the ordered block."""

    def test_verify_container_form_fixed_order_and_multiline_prompt(self) -> None:
        """``steps`` first, then settings in fixed order; multi-line prompt block-literal."""
        gate = FlowVerify(
            steps=[FlowVerifyStep(name="r", command="/x/y.sh", prompt="line1\nline2\n")],
            max_failures=3,
            review_patience=1,
        )

        text = serialize_flow(_doc(_stage_with({"verify": gate})))

        assert "verify:\n    steps:\n" in text
        assert "    max_failures: 3\n" in text
        assert "    review_patience: 1\n" in text
        assert text.index("steps:") < text.index("max_failures:") < text.index("review_patience:")
        assert "      prompt: |\n" in text

    def test_verify_container_form_multiline_prompt_without_trailing_newline(self) -> None:
        """A multi-line prompt with no trailing newline renders the strip-chomping ``|-``."""
        gate = FlowVerify(
            steps=[FlowVerifyStep(name="r", command="/x/y.sh", prompt="line1\nline2")],
            max_failures=3,
            review_patience=1,
        )

        text = serialize_flow(_doc(_stage_with({"verify": gate})))

        assert "      prompt: |-\n" in text
        assert "        line1\n" in text
        assert "        line2\n" in text

    def test_verify_container_form_present_settings_only(self) -> None:
        """Absent settings drop entirely; present keys keep the fixed order."""
        gate = FlowVerify(steps=[FlowVerifyStep(name="t", run="pytest")], max_failures=2)

        text = serialize_flow(_doc(_stage_with({"verify": gate})))

        assert "    max_failures: 2\n" in text
        assert "review_patience" not in text
        assert "fresh_correction" not in text

    def test_verify_container_form_all_settings_fixed_order(self) -> None:
        """All three settings write in the fixed order, ``False`` as the plain scalar."""
        gate = FlowVerify(
            steps=[FlowVerifyStep(name="t", run="pytest")],
            max_failures=0,
            review_patience=0,
            fresh_correction=True,
        )

        text = serialize_flow(_doc(_stage_with({"verify": gate})))

        assert "    max_failures: 0\n" in text
        assert "    review_patience: 0\n" in text
        assert "    fresh_correction: true\n" in text
        assert text.index("steps:") < text.index("max_failures:") < text.index("review_patience:")
        assert text.index("review_patience:") < text.index("fresh_correction:")

    def test_verify_container_form_settings_are_plain_scalars(self) -> None:
        """The settings render as plain scalars (no quoting, no flow style)."""
        gate = FlowVerify(steps=[FlowVerifyStep(name="t", run="pytest")], max_failures=3)

        text = serialize_flow(_doc(_stage_with({"verify": gate})))

        assert "max_failures: 3" in text
        assert "max_failures: '3'" not in text
        assert "verify: {steps" not in text


class TestSerializeFlowVerifyOmission:
    """A stage without a gate never enters the arm — byte-identical output."""

    def test_gate_free_stage_emits_no_verify_key_byte_identical(self) -> None:
        """A plain stage keeps the exact pre-feature serialized text."""
        expected = "name: n\ndescription: d\nstages:\n- id: a\n  name: A\n  prompt: Do\n"

        text = serialize_flow(_doc(FlowStage(id="a", name="A", depends_on=None, fields={"prompt": "Do"})))

        assert text == expected
        assert "verify" not in text
