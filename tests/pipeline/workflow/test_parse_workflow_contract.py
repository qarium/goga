"""Contract tests for the ``parse_workflow`` routine.

Verifies the public API declared by the workflow-cell CODEMANIFEST:
importability of ``parse_workflow`` from the facade, callability with a single
``Path`` argument, and that a valid workflow-file yields a ``WorkflowDocument``.
These tests pin the contract surface — behavior lives in the logic test module.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from goga.pipeline.workflow import (
    WorkflowDocument,
    WorkflowExtendStage,
    WorkflowSyntaxError,
    parse_workflow,
)


class TestParseWorkflowContract:
    """Contract tests — the public API declared by the workflow-cell CODEMANIFEST."""

    def test_parse_workflow_importable_from_facade(self) -> None:
        """parse_workflow must be importable from the goga.pipeline.workflow facade."""
        assert parse_workflow is not None

    def test_parse_workflow_callable_with_single_path_argument(self, tmp_path: Path) -> None:
        """parse_workflow accepts a single Path positional argument."""
        workflow_path = tmp_path / "workflow.yml"
        workflow_path.write_text("prompt: top-level guidance\n")

        document = parse_workflow(workflow_path)

        assert isinstance(document, WorkflowDocument)

    def test_parse_workflow_returns_workflow_document_for_valid_input(self, tmp_path: Path) -> None:
        """parse_workflow returns a WorkflowDocument for a valid workflow-file."""
        workflow_path = tmp_path / "workflow.yml"
        workflow_path.write_text("prompt: top-level guidance\nstages:\n  propose:\n    agent: codex\n")

        document = parse_workflow(workflow_path)

        assert isinstance(document, WorkflowDocument)
        assert document.prompt == "top-level guidance"
        assert "propose" in document.stages
        assert document.stages["propose"].agent == "codex"

    def test_parse_workflow_populates_extend_for_valid_workflow_file(self, tmp_path: Path) -> None:
        """A workflow-file with an extend block yields a non-empty extend map of WorkflowExtendStage.

        Pins the contract: the extend block is part of the parse_workflow Return
        value, populated as ``dict[str, WorkflowExtendStage]``.
        """
        workflow_path = tmp_path / "workflow.yml"
        workflow_path.write_text(
            "extend:\n  warmup:\n    before: [propose]\n    title: Warmup\n",
        )

        document = parse_workflow(workflow_path)

        assert isinstance(document, WorkflowDocument)
        assert isinstance(document.extend, dict)
        assert set(document.extend) == {"warmup"}
        assert isinstance(document.extend["warmup"], WorkflowExtendStage)

    def test_parse_workflow_skills_is_accepted_stage_key(self, tmp_path: Path) -> None:
        """``skills`` is part of the accepted per-stage key set (contract surface).

        Pins the contract: ``skills`` is a valid stage key, so a stage carrying it
        parses successfully and surfaces on the ``WorkflowStage`` model. The full
        valid-keys enumeration is pinned in the logic test module.
        """
        workflow_path = tmp_path / "workflow.yml"
        workflow_path.write_text(
            "stages:\n  propose:\n    agent: codex\n    skills: [web-search]\n",
        )

        document = parse_workflow(workflow_path)

        assert isinstance(document, WorkflowDocument)
        assert document.stages["propose"].skills == ["web-search"]

    def test_parse_workflow_accepts_skip_key(self, tmp_path: Path) -> None:
        """``skip`` is part of the accepted per-stage key set (contract surface).

        Pins the contract: ``skip`` is a valid stage key (5th key, after
        ``skills``), so a stage carrying ``skip: true`` parses successfully, the
        facade ``WorkflowDocument`` shape is unchanged, and the entry surfaces as a
        ``WorkflowStage``. The bool check, the false/absent equivalence, and the
        extend-prohibition are pinned in the logic test module.
        """
        from goga.pipeline.workflow import WorkflowStage

        workflow_path = tmp_path / "workflow.yml"
        workflow_path.write_text("stages:\n  propose:\n    skip: true\n")

        document = parse_workflow(workflow_path)

        assert isinstance(document, WorkflowDocument)
        assert "propose" in document.stages
        assert isinstance(document.stages["propose"], WorkflowStage)

    def test_parse_workflow_extend_exposes_agent_and_loop_fields(self, tmp_path: Path) -> None:
        """An extend entry's inline ``agent``/``loop`` surface on the model (contract surface).

        Pins the contract: the extend model exposes ``agent`` and ``loop`` fields,
        extracted from the extend entry (and therefore absent from ``body``).
        """
        workflow_path = tmp_path / "workflow.yml"
        workflow_path.write_text(
            "extend:\n  warmup:\n    before: [propose]\n    title: Warmup\n    agent: codex\n    loop: 3\n",
        )

        document = parse_workflow(workflow_path)

        warmup = document.extend["warmup"]
        assert isinstance(warmup, WorkflowExtendStage)
        assert warmup.agent == "codex"
        assert warmup.loop == 3
        assert "agent" not in warmup.body
        assert "loop" not in warmup.body

    def test_parse_workflow_approve_is_accepted_stage_key(self, tmp_path: Path) -> None:
        """``approve`` is part of the accepted per-stage key set (contract surface).

        Pins the contract: ``approve`` is a valid per-stage key (6th key, after
        ``skip``), so a stage carrying ``approve: auto`` parses successfully and
        surfaces on the ``WorkflowStage`` model. The full valid-keys enumeration,
        the ``"auto"``-only check, and the extend inline extraction are pinned in
        the logic test module.
        """
        workflow_path = tmp_path / "workflow.yml"
        workflow_path.write_text("stages:\n  propose:\n    approve: auto\n")

        document = parse_workflow(workflow_path)

        assert isinstance(document, WorkflowDocument)
        assert document.stages["propose"].approve == "auto"

    def test_parse_workflow_stage_keys_includes_approve(self) -> None:
        """The internal ``_STAGE_KEYS`` tuple includes ``approve`` (contract surface).

        Pins the contract: ``_STAGE_KEYS`` is the single source of the accepted
        per-stage key set and of the unknown-key ``valid keys`` message fragment,
        so it must carry ``approve`` (after ``skip``).
        """
        from goga.pipeline.workflow.parse_workflow import _STAGE_KEYS

        assert "approve" in _STAGE_KEYS
        # Fixed canonical order: agent, prompt, loop, skills, skip, approve.
        assert _STAGE_KEYS == ("agent", "prompt", "loop", "skills", "skip", "approve")

    def test_parse_workflow_unknown_stage_key_message_lists_approve(self, tmp_path: Path) -> None:
        """The unknown per-stage key error message lists ``approve`` in the valid-keys fragment.

        Pins the contract: the ``valid keys`` fragment of the unknown-key message
        is generated from ``_STAGE_KEYS`` and therefore includes ``approve``.
        """
        workflow_path = tmp_path / "workflow.yml"
        workflow_path.write_text("stages:\n  propose:\n    bad: value\n")

        with pytest.raises(WorkflowSyntaxError) as exc_info:
            parse_workflow(workflow_path)

        message = str(exc_info.value)
        assert "unknown key in workflow.stages.propose: bad" in message
        assert "valid keys: agent, prompt, loop, skills, skip, approve" in message
