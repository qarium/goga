"""Contract and logic tests for the memory authoring surface of ``parse_workflow``.

Covers the memory vocabulary the workflow-cell CODEMANIFEST declares: the
optional top-level ``memory`` block (key set, value domains, path shapes,
materialized defaults), the per-stage ``reflect`` / ``memory`` instructions,
the prohibition of both keys in an extend-entry, the correspondence between
the materialized method and the per-stage instructions, and the new
empty-workflow rule that counts the block. The contract class pins the API
shape; the logic classes exercise every documented message verbatim.
"""

from __future__ import annotations

import inspect
import re
from pathlib import Path

import pytest
from goga.pipeline.workflow import (
    WorkflowDocument,
    WorkflowMemory,
    WorkflowReflect,
    WorkflowStage,
    WorkflowSyntaxError,
    parse_workflow,
)


def _write(tmp_path: Path, name: str, text: str) -> Path:
    """Write ``text`` to ``tmp_path / name`` and return the path."""
    workflow_path = tmp_path / name

    workflow_path.write_text(text)

    return workflow_path


def _parse(tmp_path: Path, text: str) -> WorkflowDocument:
    """Parse ``text`` as a workflow-file and return the built document."""
    return parse_workflow(_write(tmp_path, "workflow.yml", text))


class TestParseWorkflowMemoryContract:
    """Contract tests — the memory surface of the ``parse_workflow`` routine."""

    def test_parse_workflow_signature_unchanged(self) -> None:
        """``parse_workflow`` still takes exactly one parameter (``workflow_path``)."""
        parameters = list(inspect.signature(parse_workflow).parameters)

        assert parameters == ["workflow_path"]

    def test_parse_workflow_document_memory_is_optional_workflow_memory(self, tmp_path: Path) -> None:
        """The parsed document carries ``memory`` as a ``WorkflowMemory | None``."""
        with_block = _parse(tmp_path, "memory:\n  max_rules: 40\n")
        without_block = _parse(tmp_path, "prompt: guidance\n")

        assert isinstance(with_block.memory, WorkflowMemory)
        assert without_block.memory is None

    def test_parse_workflow_stage_reflect_is_optional_workflow_reflect(self, tmp_path: Path) -> None:
        """A parsed stage carries ``reflect`` as a ``WorkflowReflect | None``."""
        document = _parse(tmp_path, "stages:\n  brainstorm:\n    reflect:\n      file: shared.md\n")

        assert isinstance(document.stages["brainstorm"].reflect, WorkflowReflect)
        assert WorkflowStage().reflect is None

    def test_parse_workflow_stage_memory_is_optional_bool(self, tmp_path: Path) -> None:
        """A parsed stage carries ``memory`` as a ``bool | None`` (never ``False``)."""
        document = _parse(
            tmp_path,
            "memory:\n  method: alignment\nstages:\n  brainstorm:\n    memory: true\n  review:\n    agent: codex\n",
        )

        assert document.stages["brainstorm"].memory is True
        assert isinstance(document.stages["brainstorm"].memory, bool)
        assert document.stages["review"].memory is None


class TestParseWorkflowMemoryPositive:
    """Positive logic tests — valid memory authoring parses to the expected models."""

    def test_parse_workflow_memory_block_only_is_valid_not_empty(self, tmp_path: Path) -> None:
        """A workflow of the memory block alone is valid — the block counts as content."""
        document = _parse(tmp_path, "memory:\n  max_rules: 40\n")

        assert document.prompt is None
        assert document.stages == {}
        assert document.extend == {}
        assert isinstance(document.memory, WorkflowMemory)
        assert document.memory.max_rules == 40
        assert document.memory.method == "reflect"
        assert document.memory.commit is False
        assert document.memory.mode is None

    def test_parse_workflow_empty_memory_block_materializes_defaults(self, tmp_path: Path) -> None:
        """An empty ``memory: {}`` block builds the model with every default materialized."""
        document = _parse(tmp_path, "memory: {}\n")

        assert isinstance(document.memory, WorkflowMemory)
        assert document.memory == WorkflowMemory()
        assert document.memory.method == "reflect"
        assert document.memory.path is None
        assert document.memory.max_rules == 25
        assert document.memory.commit is False
        assert document.memory.mode is None

    def test_parse_workflow_max_rules_accepts_lower_boundary(self, tmp_path: Path) -> None:
        """``max_rules: 1`` — the inclusive lower boundary — parses."""
        document = _parse(tmp_path, "memory:\n  max_rules: 1\n")

        assert document.memory is not None
        assert document.memory.max_rules == 1

    def test_parse_workflow_memory_block_absent_leaves_memory_none(self, tmp_path: Path) -> None:
        """A workflow-file without a ``memory`` block yields ``document.memory is None``."""
        document = _parse(tmp_path, "prompt: guidance\nstages:\n  build:\n    agent: codex\n")

        assert document.memory is None

    def test_parse_workflow_alignment_block_materializes_mode_rw(self, tmp_path: Path) -> None:
        """The alignment method materializes ``mode`` to ``rw`` when the block omits it."""
        document = _parse(
            tmp_path,
            "memory:\n  method: alignment\n  path: goga-development\nstages:\n  brainstorm:\n    memory: true\n",
        )

        assert document.memory is not None
        assert document.memory.method == "alignment"
        assert document.memory.mode == "rw"
        assert document.memory.path == "goga-development"
        assert document.stages["brainstorm"].memory is True

    def test_parse_workflow_stage_reflect_builds_workflow_reflect(self, tmp_path: Path) -> None:
        """Per-stage reflect instructions build WorkflowReflect with the mode materialized."""
        document = _parse(
            tmp_path,
            "memory:\n"
            "  max_rules: 40\n"
            "stages:\n"
            "  brainstorm:\n"
            "    reflect:\n"
            "      file: shared.md\n"
            "      mode: r\n"
            "  review:\n"
            "    reflect:\n"
            "      file: shared.md\n",
        )

        assert document.stages["brainstorm"].reflect == WorkflowReflect(file="shared.md", mode="r")
        assert document.stages["review"].reflect == WorkflowReflect(file="shared.md", mode="rw")

    def test_parse_workflow_stage_reflect_without_memory_block_is_valid(self, tmp_path: Path) -> None:
        """A reflect instruction with no authored block is valid — the default method is reflect."""
        document = _parse(tmp_path, "stages:\n  brainstorm:\n    reflect:\n      file: shared.md\n")

        assert document.memory is None
        assert document.stages["brainstorm"].reflect == WorkflowReflect(file="shared.md", mode="rw")

    def test_parse_workflow_stage_memory_false_equals_absence(self, tmp_path: Path) -> None:
        """An explicit ``memory: false`` is normalized to ``None`` — absence, not False."""
        document = _parse(
            tmp_path,
            "memory:\n  method: alignment\nstages:\n  build:\n    memory: false\n",
        )

        assert document.stages["build"].memory is None


class TestParseWorkflowMemoryBlockRejections:
    """Negative logic tests — every structural defect of the ``memory`` block."""

    @pytest.mark.parametrize(
        ("block_yaml", "message"),
        [
            ("memory: [1]", "non-mapping memory block in workflow"),
            ("memory: text", "non-mapping memory block in workflow"),
            (
                "memory: {bad: 1}",
                "unknown key in workflow.memory: bad; valid keys: method, path, max_rules, commit, mode",
            ),
            ("memory: {method: 3}", "non-str value in workflow.memory.method"),
            ("memory: {method: sync}", "method must be one of: reflect, alignment in workflow.memory"),
            ("memory: {path: 4}", "non-str value in workflow.memory.path"),
            ("memory: {path: ''}", "invalid path in workflow.memory.path: "),
            ("memory: {path: /abs}", "invalid path in workflow.memory.path: /abs"),
            ("memory: {path: ../x}", "invalid path in workflow.memory.path: ../x"),
            ("memory: {max_rules: '9'}", "non-int value in workflow.memory.max_rules"),
            ("memory: {max_rules: 0}", "max_rules must be >= 1 in workflow.memory"),
            ("memory: {max_rules: -3}", "max_rules must be >= 1 in workflow.memory"),
            ("memory: {max_rules: true}", "non-int value in workflow.memory.max_rules"),
            ("memory: {commit: 'yes'}", "non-bool value in workflow.memory.commit"),
            ("memory: {commit: 1}", "non-bool value in workflow.memory.commit"),
            ("memory: {mode: 1}", "non-str value in workflow.memory.mode"),
            ("memory: {mode: x}", "mode must be one of: r, w, rw in workflow.memory"),
            ("memory: {method: reflect, mode: rw}", "mode is forbidden in workflow.memory with method: reflect"),
        ],
        ids=[
            "list-block",
            "scalar-block",
            "unknown-key",
            "non-str-method",
            "method-outside-domain",
            "non-str-path",
            "empty-path",
            "absolute-path",
            "parent-segment-path",
            "non-int-max-rules",
            "zero-max-rules",
            "negative-max-rules",
            "bool-max-rules",
            "non-bool-commit",
            "int-commit",
            "non-str-mode",
            "mode-outside-domain",
            "mode-under-reflect",
        ],
    )
    def test_parse_workflow_rejects_memory_block_shape_errors(
        self,
        tmp_path: Path,
        block_yaml: str,
        message: str,
    ) -> None:
        """A structurally malformed memory block raises WorkflowSyntaxError with the documented message."""
        with pytest.raises(WorkflowSyntaxError, match=re.escape(message)):
            _parse(tmp_path, f"{block_yaml}\n")

    def test_parse_workflow_unknown_top_level_message_lists_memory(self, tmp_path: Path) -> None:
        """The unknown top-level key message now lists ``memory`` in the valid-keys fragment."""
        with pytest.raises(WorkflowSyntaxError) as exc_info:
            _parse(tmp_path, "bogus: 1\n")

        message = str(exc_info.value)
        assert "unknown key in workflow: bogus" in message
        assert "valid keys: prompt, stages, extend, memory" in message

    def test_parse_workflow_unknown_stage_key_message_lists_reflect_and_memory(
        self,
        tmp_path: Path,
    ) -> None:
        """The unknown per-stage key message now lists ``reflect, memory`` in the valid-keys fragment."""
        with pytest.raises(WorkflowSyntaxError) as exc_info:
            _parse(tmp_path, "stages:\n  build:\n    bogus: 1\n")

        message = str(exc_info.value)
        assert "unknown key in workflow.stages.build: bogus" in message
        assert "valid keys: agent, prompt, loop, skills, skip, approve, manual, notes, reflect, memory" in message


class TestParseWorkflowReflectRejections:
    """Negative logic tests — every structural defect of a per-stage ``reflect`` instruction."""

    @pytest.mark.parametrize(
        ("stage_yaml", "block_yaml", "message"),
        [
            ("    reflect: [1]", "", "non-mapping reflect in workflow.stages.brainstorm"),
            (
                "    reflect:\n      file: a.md\n      bad: 1",
                "",
                "unknown key in workflow.stages.brainstorm.reflect: bad; valid keys: file, mode",
            ),
            ("    reflect: {}", "", "file is required in workflow.stages.brainstorm.reflect"),
            ("    reflect:\n      mode: r", "", "file is required in workflow.stages.brainstorm.reflect"),
            (
                "    reflect:\n      file: 3",
                "",
                "non-str value in workflow.stages.brainstorm.reflect.file",
            ),
            (
                "    reflect:\n      file: ../x",
                "",
                "invalid path in workflow.stages.brainstorm.reflect.file: ../x",
            ),
            (
                "    reflect:\n      file: a.md\n      mode: 3",
                "",
                "non-str value in workflow.stages.brainstorm.reflect.mode",
            ),
            (
                "    reflect:\n      file: a.md\n      mode: x",
                "",
                "mode must be one of: r, w, rw in workflow.stages.brainstorm.reflect",
            ),
            ("    memory: 1", "memory:\n  method: alignment\n", "non-bool value in workflow.stages.brainstorm.memory"),
        ],
        ids=[
            "list-reflect",
            "unknown-key",
            "empty-map",
            "missing-file",
            "non-str-file",
            "bad-path-shape",
            "non-str-mode",
            "mode-outside-domain",
            "non-bool-memory",
        ],
    )
    def test_parse_workflow_rejects_reflect_instruction_errors(
        self,
        tmp_path: Path,
        stage_yaml: str,
        block_yaml: str,
        message: str,
    ) -> None:
        """A malformed per-stage instruction raises WorkflowSyntaxError with the documented message."""
        text = f"stages:\n  brainstorm:\n{stage_yaml}\n"

        if block_yaml:
            text = f"{block_yaml}{text}"

        with pytest.raises(WorkflowSyntaxError, match=re.escape(message)):
            _parse(tmp_path, text)


class TestParseWorkflowMethodInstructionMismatch:
    """Negative logic tests — the method ↔ instruction correspondence and the extend prohibition."""

    @pytest.mark.parametrize(
        ("text", "message"),
        [
            (
                "memory:\n  method: alignment\nstages:\n  x:\n    reflect:\n      file: a.md\n",
                "reflect is forbidden in workflow.stages.x with method: alignment",
            ),
            (
                "memory: {}\nstages:\n  x:\n    memory: true\n",
                "memory is forbidden in workflow.stages.x with method: reflect",
            ),
            (
                "stages:\n  x:\n    memory: true\n",
                "memory is forbidden in workflow.stages.x with method: reflect",
            ),
            (
                "extend:\n  extra:\n    after: [build]\n    title: Extra\n    reflect:\n      file: a.md\n",
                "reflect is forbidden in workflow.extend.extra",
            ),
            (
                "extend:\n  extra:\n    after: [build]\n    title: Extra\n    memory: true\n",
                "memory is forbidden in workflow.extend.extra",
            ),
        ],
        ids=[
            "reflect-under-alignment",
            "memory-under-reflect-with-block",
            "memory-under-reflect-without-block",
            "reflect-in-extend-entry",
            "memory-in-extend-entry",
        ],
    )
    def test_parse_workflow_rejects_method_instruction_mismatch(
        self,
        tmp_path: Path,
        text: str,
        message: str,
    ) -> None:
        """A method/instruction mismatch or an extend-entry instruction raises the documented message."""
        with pytest.raises(WorkflowSyntaxError, match=re.escape(message)):
            _parse(tmp_path, text)

    def test_parse_workflow_alignment_accepts_authored_mode_and_path(self, tmp_path: Path) -> None:
        """An alignment block with an authored mode carries it verbatim alongside the suffix."""
        document = _parse(
            tmp_path,
            "memory:\n  method: alignment\n  path: p\n  mode: r\nstages:\n  build:\n    memory: true\n",
        )

        assert document.memory is not None
        assert document.memory.mode == "r"
        assert document.memory.path == "p"
        assert document.stages["build"].memory is True

    def test_parse_workflow_empty_workflow_message_mentions_memory_block(self, tmp_path: Path) -> None:
        """The empty-workflow message now offers the memory block as a fourth alternative."""
        with pytest.raises(WorkflowSyntaxError) as exc_info:
            _parse(tmp_path, "stages: {}\n")

        assert str(exc_info.value) == (
            "empty workflow — provide at least prompt, one stage, one extend entry, or the memory block"
        )
