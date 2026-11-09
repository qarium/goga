"""Contract and logic tests for the ``gates`` authoring surface of ``parse_workflow``.

Covers the quality-gate vocabulary the workflow-cell CODEMANIFEST declares:
the optional top-level ``gates`` settings block (``patience``/
``max_iterations`` non-negative ints — bools are non-ints —, a bool
``fresh_correction``, authored keys only, the empty block equals absence),
the per-stage ``gates`` check-step list (a required ``name``, exactly one of
``script``/``agent`` — a ``script`` payload is a non-empty string or a
non-empty list of non-empty strings joined with newlines into one script,
an ``agent`` alias a single string —, optional ``timeout``/``prompt`` with
``prompt`` forbidden on a script step, the empty list equals absence), the
extend-entry prohibition, and the gates-only workflow validity (the block
counts as content). The contract class pins the surface; the logic classes
exercise every documented message verbatim.
"""

from __future__ import annotations

import re

import pytest
from goga.pipeline.workflow import (
    WorkflowGateStep,
    WorkflowSyntaxError,
    parse_workflow,
)


class TestParseWorkflowGatesContract:
    """Contract tests — the gates blocks on the ``parse_workflow`` surface."""

    def test_gates_settings_block_alone_is_valid(self) -> None:
        """A workflow consisting of the gates block alone parses (the block counts as content)."""
        document = parse_workflow("gates:\n  patience: 1\n")

        assert document.gates is not None
        assert document.gates.patience == 1
        assert document.gates.max_iterations is None
        assert document.gates.fresh_correction is None
        assert document.prompt is None
        assert document.stages == {}

    def test_stage_gates_steps_built_in_authored_order(self) -> None:
        """A stage's gates list builds one ``WorkflowGateStep`` per entry, in authored order."""
        document = parse_workflow(
            "stages:\n"
            "  implement:\n"
            "    prompt: Implement the change.\n"
            "    gates:\n"
            "      - name: Unit tests\n"
            "        script: pytest -q\n"
            "        timeout: 30m\n"
            "      - name: Code review\n"
            "        agent: codex\n"
            "        prompt: Review the diff for correctness.\n"
        )

        gates = document.stages["implement"].gates

        assert gates is not None
        assert len(gates) == 2

        first, second = gates

        assert isinstance(first, WorkflowGateStep)
        assert first.name == "Unit tests"
        assert first.script == "pytest -q"
        assert first.timeout == "30m"
        assert first.agent is None
        assert first.prompt is None

        assert isinstance(second, WorkflowGateStep)
        assert second.name == "Code review"
        assert second.agent == "codex"
        assert second.prompt == "Review the diff for correctness."
        assert second.script is None
        assert second.timeout is None

    def test_empty_settings_block_and_empty_list_equal_absence(self) -> None:
        """An empty gates block and an empty per-stage list both normalize to ``None``."""
        document = parse_workflow("gates: {}\nstages:\n  a:\n    gates: []\n    prompt: x\n")

        assert document.gates is None
        assert document.stages["a"].gates is None

    def test_authored_zero_is_a_value(self) -> None:
        """An authored ``0`` on either bound is a VALUE, never an absence."""
        document = parse_workflow("gates: {patience: 0, max_iterations: 0}\n")

        assert document.gates is not None
        assert document.gates.patience == 0
        assert document.gates.max_iterations == 0
        assert document.gates.patience is not None
        assert document.gates.max_iterations is not None

    def test_step_list_script_joined_into_one_multiline_string(self) -> None:
        """A list-form ``script`` payload joins with newlines into one script string.

        Each element is one line of the shell check — shell-identical to
        authoring the same text as a block scalar. The step keeps the plain
        ``str`` type (the model carries no list form).
        """
        document = parse_workflow(
            "stages:\n"
            "  a:\n"
            "    gates:\n"
            "      - name: checks\n"
            "        script:\n"
            "          - pytest -q\n"
            "          - ruff check .\n",
        )

        step = document.stages["a"].gates[0]

        assert isinstance(step.script, str)
        assert step.script == "pytest -q\nruff check ."
        assert step.agent is None

    def test_step_single_element_list_script_joins_to_the_element(self) -> None:
        """A one-element list joins to the element itself — no newline is invented."""
        document = parse_workflow("stages:\n  a:\n    gates: [{name: x, script: [pytest -q]}]\n")

        assert document.stages["a"].gates[0].script == "pytest -q"

    def test_step_agent_list_stays_a_structural_error(self) -> None:
        """An ``agent`` alias is a single string — the list form is rejected with the scalar message."""
        with pytest.raises(
            WorkflowSyntaxError,
            match=re.escape("agent must be a non-empty string in workflow.stages.a.gates[0]"),
        ):
            parse_workflow("stages:\n  a:\n    gates: [{name: x, agent: [codex]}]\n")

    def test_step_env_carried_on_both_step_kinds_in_authored_order(self) -> None:
        """A step env map parses onto script and agent steps alike, in authored order."""
        document = parse_workflow(
            "stages:\n"
            "  implement:\n"
            "    gates:\n"
            "      - name: Unit tests\n"
            "        script: pytest -q\n"
            "        env:\n"
            "          FOO: bar\n"
            "          BAZ: qux\n"
            "      - name: Code review\n"
            "        agent: codex\n"
            "        prompt: Review.\n"
            "        env:\n"
            "          MODEL: gpt\n"
        )

        first, second = document.stages["implement"].gates

        assert first.env == {"FOO": "bar", "BAZ": "qux"}
        assert list(first.env) == ["FOO", "BAZ"]
        assert second.env == {"MODEL": "gpt"}

    def test_step_empty_env_map_equals_absence(self) -> None:
        """An authored empty step env map normalizes to ``None`` — no wrapper, no patch."""
        document = parse_workflow("stages:\n  a:\n    gates: [{name: x, script: pytest, env: {}}]\n")

        assert document.stages["a"].gates[0].env is None


class TestParseWorkflowGatesLogic:
    """Logic tests — the gates blocks' authored-values carry and normalizations."""

    def test_parse_gates_block_carries_authored_keys(self) -> None:
        """A gates block with every key parses the values verbatim onto the document."""
        document = parse_workflow("gates:\n  patience: 2\n  max_iterations: 5\n  fresh_correction: true\nprompt: x\n")

        assert document.gates is not None
        assert document.gates.patience == 2
        assert document.gates.max_iterations == 5
        assert document.gates.fresh_correction is True

    def test_parse_gates_block_single_key(self) -> None:
        """Each settings key authors alone; the un-authored keys stay ``None``."""
        document = parse_workflow("gates:\n  fresh_correction: false\nprompt: x\n")

        assert document.gates is not None
        assert document.gates.patience is None
        assert document.gates.max_iterations is None
        assert document.gates.fresh_correction is False

    def test_ungated_stage_and_workflow_carry_none(self) -> None:
        """A gate-free stage and a gate-free workflow both carry ``gates is None``."""
        document = parse_workflow("prompt: x\nstages:\n  a:\n    prompt: y\n")

        assert document.gates is None
        assert document.stages["a"].gates is None


class TestParseWorkflowGatesRejections:
    """Negative logic tests — every structural defect of the two gates blocks."""

    @pytest.mark.parametrize(
        ("workflow_text", "message"),
        [
            ("gates: 5\n", "non-mapping gates block in workflow"),
            ("gates: true\n", "non-mapping gates block in workflow"),
            ("gates: [1]\n", "non-mapping gates block in workflow"),
            (
                "gates: {patiance: 1}\n",
                "unknown key in workflow.gates: patiance; valid keys: patience, max_iterations, fresh_correction",
            ),
            ("gates: {patience: true}\n", "non-int value in workflow.gates.patience"),
            ('gates: {patience: "2"}\n', "non-int value in workflow.gates.patience"),
            ("gates: {max_iterations: -1}\n", "max_iterations must be >= 0 in workflow.gates"),
            ("gates: {patience: -3}\n", "patience must be >= 0 in workflow.gates"),
            ("gates: {fresh_correction: 1}\n", "non-bool value in workflow.gates.fresh_correction"),
            ("stages: {a: {gates: {name: x}}}\n", "non-list gates in workflow.stages.a"),
            ("stages: {a: {gates: pytest}}\n", "non-list gates in workflow.stages.a"),
            ("stages: {a: {gates: [pytest]}}\n", "non-mapping gate step in workflow.stages.a.gates[0]"),
            ("stages: {a: {gates: [{script: x}]}}\n", "gates step without name in workflow.stages.a.gates[0]"),
            (
                "stages: {a: {gates: [{name: 1, script: x}]}}\n",
                "non-str value in workflow.stages.a.gates[0].name",
            ),
            (
                "stages: {a: {gates: [{name: x}]}}\n",
                "gates step must carry exactly one of script/agent in workflow.stages.a.gates[0]",
            ),
            (
                "stages: {a: {gates: [{name: x, script: y, agent: z}]}}\n",
                "gates step must carry exactly one of script/agent in workflow.stages.a.gates[0]",
            ),
            (
                'stages: {a: {gates: [{name: x, script: ""}]}}\n',
                "script must be a non-empty string in workflow.stages.a.gates[0]",
            ),
            (
                "stages: {a: {gates: [{name: x, script: []}]}}\n",
                "script must be a non-empty list of non-empty strings in workflow.stages.a.gates[0]",
            ),
            (
                "stages: {a: {gates: [{name: x, script: [pytest, '']}]}}\n",
                "script must be a non-empty list of non-empty strings in workflow.stages.a.gates[0]",
            ),
            (
                "stages: {a: {gates: [{name: x, script: [pytest, 2]}]}}\n",
                "script must be a non-empty list of non-empty strings in workflow.stages.a.gates[0]",
            ),
            (
                'stages: {a: {gates: [{name: x, agent: ""}]}}\n',
                "agent must be a non-empty string in workflow.stages.a.gates[0]",
            ),
            (
                "stages: {a: {gates: [{name: x, script: y, timeout: 5}]}}\n",
                "non-str value in workflow.stages.a.gates[0].timeout",
            ),
            (
                "stages: {a: {gates: [{name: x, agent: y, prompt: 5}]}}\n",
                "non-str value in workflow.stages.a.gates[0].prompt",
            ),
            (
                "stages: {a: {gates: [{name: x, script: y, prompt: z}]}}\n",
                "prompt is forbidden on a script gate step in workflow.stages.a.gates[0]",
            ),
            (
                "stages: {a: {gates: [{name: x, agent: y, extra: 1}]}}\n",
                "unknown key in workflow.stages.a.gates[0]: extra; "
                "valid keys: name, script, agent, timeout, prompt, env",
            ),
            (
                "stages: {a: {gates: [{name: x, script: y, env: 5}]}}\n",
                "non-mapping env in workflow.stages.a.gates[0]",
            ),
            (
                "stages: {a: {gates: [{name: x, script: y, env: {1: v}}]}}\n",
                "non-str key in workflow.stages.a.gates[0].env",
            ),
            (
                "stages: {a: {gates: [{name: x, agent: y, env: {K: 2}}]}}\n",
                "non-str value in workflow.stages.a.gates[0].env.K",
            ),
            (
                "stages: {a: {gates: [{name: x, agent: y}, 5]}}\n",
                "non-mapping gate step in workflow.stages.a.gates[1]",
            ),
            (
                "extend: {n: {after: [a], gates: [{name: g, script: pytest}]}}\n",
                "gates is forbidden in workflow.extend.n",
            ),
        ],
    )
    def test_parse_gates_structural_defects(self, workflow_text: str, message: str) -> None:
        """Every structural defect of the gates surfaces raises its documented one-line message."""
        with pytest.raises(WorkflowSyntaxError, match=re.escape(message)):
            parse_workflow(workflow_text)

    def test_parse_unknown_top_level_key_enumeration_includes_gates(self) -> None:
        """The unknown top-level key message enumerates the ten valid keys ending with ``gates``."""
        with pytest.raises(WorkflowSyntaxError) as excinfo:
            parse_workflow("gatess: {}\n")

        message = str(excinfo.value)
        expected = "valid keys: prompt, stages, extend, memory, profile, build, assistants, delegation, repeat, gates"
        assert expected in message

    def test_parse_unknown_stage_key_enumeration_includes_gates(self) -> None:
        """The unknown per-stage key message enumerates the twelve valid keys ending with ``gates``."""
        with pytest.raises(WorkflowSyntaxError) as excinfo:
            parse_workflow("stages:\n  a:\n    gate: []\n")

        assert "valid keys: agent, env, prompt, loop, skills, skip, approve, manual, notes, reflect, memory, " in str(
            excinfo.value
        )
        assert "assistants, gates" in str(excinfo.value)
