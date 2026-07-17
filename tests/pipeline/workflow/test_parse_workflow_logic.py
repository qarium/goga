"""Logic tests for the ``parse_workflow`` routine.

Covers the 8-step CODEMANIFEST algorithm: positive parsing of prompt + stages,
the ``prompt``-only and ``stages``-only single-directive shapes, every
structural rejection (invalid YAML, non-mapping root, unknown top-level and
per-stage keys, wrong-typed fields, ``loop`` below one, empty workflow), and
the OSError-propagation / YAML-error edges. Each rejection asserts both the
``WorkflowSyntaxError`` type and the documented message substring.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from goga.pipeline.workflow import WorkflowSyntaxError, parse_workflow


def _write(tmp_path: Path, name: str, text: str) -> Path:
    """Write ``text`` to ``tmp_path / name`` and return the path."""
    workflow_path = tmp_path / name

    workflow_path.write_text(text)

    return workflow_path


class TestParseWorkflowPositive:
    """Positive logic tests — valid workflow-files parse to the expected document."""

    def test_parse_workflow_top_level_prompt_and_stages(self, tmp_path: Path) -> None:
        """A full workflow-file with prompt and two stages parses verbatim."""
        workflow_path = _write(
            tmp_path,
            "workflow.yml",
            "prompt: top-level guidance\n"
            "stages:\n"
            "  propose:\n"
            "    agent: codex\n"
            "    prompt: Additional prompt\n"
            "  propose-review:\n"
            "    loop: 2\n"
            "    agent: claude\n",
        )

        document = parse_workflow(workflow_path)

        assert document.prompt == "top-level guidance"
        assert set(document.stages) == {"propose", "propose-review"}
        assert document.stages["propose"].agent == "codex"
        assert document.stages["propose"].prompt == "Additional prompt"
        assert document.stages["propose"].loop is None
        assert document.stages["propose-review"].agent == "claude"
        assert document.stages["propose-review"].loop == 2
        assert document.stages["propose-review"].prompt is None

    def test_parse_workflow_only_top_level_prompt(self, tmp_path: Path) -> None:
        """A workflow with only a top-level prompt succeeds with an empty stages map."""
        workflow_path = _write(tmp_path, "workflow.yml", "prompt: guidance only\n")

        document = parse_workflow(workflow_path)

        assert document.prompt == "guidance only"
        assert document.stages == {}

    def test_parse_workflow_only_stages_no_prompt(self, tmp_path: Path) -> None:
        """A workflow with only stages (no prompt) succeeds with prompt None."""
        workflow_path = _write(
            tmp_path,
            "workflow.yml",
            "stages:\n  propose:\n    agent: codex\n",
        )

        document = parse_workflow(workflow_path)

        assert document.prompt is None
        assert set(document.stages) == {"propose"}
        assert document.stages["propose"].agent == "codex"

    def test_parse_workflow_stage_with_no_fields(self, tmp_path: Path) -> None:
        """A stage entry with no fields builds an all-None WorkflowStage."""
        workflow_path = _write(tmp_path, "workflow.yml", "stages:\n  propose: {}\n")

        document = parse_workflow(workflow_path)

        assert document.stages["propose"].agent is None
        assert document.stages["propose"].prompt is None
        assert document.stages["propose"].loop is None


class TestParseWorkflowNegative:
    """Negative logic tests — structural defects raise WorkflowSyntaxError with the documented message."""

    def test_parse_workflow_rejects_unknown_top_level_key(self, tmp_path: Path) -> None:
        """An unknown top-level key raises WorkflowSyntaxError listing the valid keys."""
        workflow_path = _write(
            tmp_path,
            "workflow.yml",
            "unknown_key: value\nprompt: hello\n",
        )

        with pytest.raises(WorkflowSyntaxError) as exc_info:
            parse_workflow(workflow_path)

        message = str(exc_info.value)
        assert "unknown key in workflow: unknown_key" in message
        assert "valid keys: prompt, stages" in message

    def test_parse_workflow_rejects_non_mapping_root(self, tmp_path: Path) -> None:
        """A non-mapping YAML root raises WorkflowSyntaxError('workflow must be a mapping')."""
        workflow_path = _write(tmp_path, "workflow.yml", "- just\n- a\n- list\n")

        with pytest.raises(WorkflowSyntaxError, match="workflow must be a mapping"):
            parse_workflow(workflow_path)

    def test_parse_workflow_rejects_non_str_top_level_prompt(self, tmp_path: Path) -> None:
        """A non-str top-level prompt raises WorkflowSyntaxError('non-str value in workflow.prompt')."""
        workflow_path = _write(tmp_path, "workflow.yml", "prompt: 123\n")

        with pytest.raises(WorkflowSyntaxError, match=r"non-str value in workflow\.prompt"):
            parse_workflow(workflow_path)

    def test_parse_workflow_rejects_non_mapping_stages(self, tmp_path: Path) -> None:
        """A non-mapping stages block raises WorkflowSyntaxError('non-mapping stages block')."""
        workflow_path = _write(tmp_path, "workflow.yml", "stages: not-a-mapping\n")

        with pytest.raises(WorkflowSyntaxError, match="non-mapping stages block in workflow"):
            parse_workflow(workflow_path)

    def test_parse_workflow_rejects_non_mapping_stage_value(self, tmp_path: Path) -> None:
        """A non-mapping stage value raises WorkflowSyntaxError naming the stage."""
        workflow_path = _write(tmp_path, "workflow.yml", "stages:\n  propose: codex\n")

        with pytest.raises(WorkflowSyntaxError, match=r"non-mapping stage propose in workflow\.stages"):
            parse_workflow(workflow_path)

    def test_parse_workflow_rejects_unknown_stage_key(self, tmp_path: Path) -> None:
        """An unknown per-stage key raises WorkflowSyntaxError listing the valid per-stage keys."""
        workflow_path = _write(
            tmp_path,
            "workflow.yml",
            "stages:\n  propose:\n    bad: value\n",
        )

        with pytest.raises(WorkflowSyntaxError) as exc_info:
            parse_workflow(workflow_path)

        message = str(exc_info.value)
        assert "unknown key in workflow.stages.propose: bad" in message
        assert "valid keys: agent, prompt, loop" in message

    def test_parse_workflow_rejects_non_str_agent(self, tmp_path: Path) -> None:
        """A non-str agent raises WorkflowSyntaxError naming the stage and field."""
        workflow_path = _write(tmp_path, "workflow.yml", "stages:\n  propose:\n    agent: 123\n")

        with pytest.raises(WorkflowSyntaxError, match=r"non-str value in workflow\.stages\.propose\.agent"):
            parse_workflow(workflow_path)

    def test_parse_workflow_rejects_non_str_stage_prompt(self, tmp_path: Path) -> None:
        """A non-str stage prompt raises WorkflowSyntaxError naming the stage and field."""
        workflow_path = _write(tmp_path, "workflow.yml", "stages:\n  propose:\n    prompt: 123\n")

        with pytest.raises(WorkflowSyntaxError, match=r"non-str value in workflow\.stages\.propose\.prompt"):
            parse_workflow(workflow_path)

    @pytest.mark.parametrize(
        "loop_yaml",
        ["true", "2.5", "two"],
        ids=["bool", "float", "str"],
    )
    def test_parse_workflow_rejects_non_int_loop(self, tmp_path: Path, loop_yaml: str) -> None:
        """A non-int loop (bool, float, or str) raises WorkflowSyntaxError('non-int value')."""
        workflow_path = _write(
            tmp_path,
            "workflow.yml",
            f"stages:\n  propose:\n    loop: {loop_yaml}\n",
        )

        with pytest.raises(WorkflowSyntaxError, match=r"non-int value in workflow\.stages\.propose\.loop"):
            parse_workflow(workflow_path)

    def test_parse_workflow_rejects_loop_below_one(self, tmp_path: Path) -> None:
        """A loop of zero raises WorkflowSyntaxError('loop must be >= 1')."""
        workflow_path = _write(tmp_path, "workflow.yml", "stages:\n  propose:\n    loop: 0\n")

        with pytest.raises(WorkflowSyntaxError, match=r"loop must be >= 1 in workflow\.stages\.propose"):
            parse_workflow(workflow_path)

    def test_parse_workflow_rejects_negative_loop(self, tmp_path: Path) -> None:
        """A negative loop raises WorkflowSyntaxError('loop must be >= 1')."""
        workflow_path = _write(tmp_path, "workflow.yml", "stages:\n  propose:\n    loop: -3\n")

        with pytest.raises(WorkflowSyntaxError, match=r"loop must be >= 1 in workflow\.stages\.propose"):
            parse_workflow(workflow_path)

    def test_parse_workflow_rejects_empty_workflow(self, tmp_path: Path) -> None:
        """A workflow with empty stages and no prompt raises WorkflowSyntaxError('empty workflow')."""
        workflow_path = _write(tmp_path, "workflow.yml", "stages: {}\n")

        with pytest.raises(WorkflowSyntaxError, match="empty workflow"):
            parse_workflow(workflow_path)


class TestParseWorkflowEdgeCases:
    """Edge-case logic tests — file I/O and YAML parsing boundaries."""

    def test_parse_workflow_missing_file_propagates_oserror(self, tmp_path: Path) -> None:
        """A missing file propagates FileNotFoundError unchanged (no WorkflowSyntaxError wrapping)."""
        workflow_path = tmp_path / "absent.yml"

        with pytest.raises(FileNotFoundError):
            parse_workflow(workflow_path)

    def test_parse_workflow_invalid_yaml_raises_syntax_error(self, tmp_path: Path) -> None:
        """Invalid YAML raises WorkflowSyntaxError('invalid YAML in workflow-file')."""
        # An unquoted mapping value with a stray colon is a YAML scanner error.
        workflow_path = _write(tmp_path, "workflow.yml", "prompt: hello: world\n")

        with pytest.raises(WorkflowSyntaxError, match="invalid YAML in workflow-file"):
            parse_workflow(workflow_path)
