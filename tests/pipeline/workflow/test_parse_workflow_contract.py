"""Contract tests for the ``parse_workflow`` routine.

Verifies the public API declared by the workflow-cell CODEMANIFEST:
importability of ``parse_workflow`` from the facade, callability with a single
``str`` argument (the rendered text — the caller owns reading and rendering),
and that a valid workflow text yields a ``WorkflowDocument``. These tests pin
the contract surface — behavior lives in the logic test module.
"""

from __future__ import annotations

import inspect

import pytest
from goga.pipeline.workflow import (
    WorkflowBuild,
    WorkflowDocument,
    WorkflowExtendStage,
    WorkflowStage,
    WorkflowSyntaxError,
    parse_workflow,
)


class TestParseWorkflowContract:
    """Contract tests — the public API declared by the workflow-cell CODEMANIFEST."""

    def test_parse_workflow_importable_from_facade(self) -> None:
        """parse_workflow must be importable from the goga.pipeline.workflow facade."""
        assert parse_workflow is not None

    def test_parse_workflow_signature_is_rendered_text(self) -> None:
        """parse_workflow declares exactly one parameter — the rendered ``text`` str."""
        signature = inspect.signature(parse_workflow)

        assert list(signature.parameters) == ["text"]

    def test_parse_workflow_callable_with_single_text_argument(self) -> None:
        """parse_workflow accepts a single str positional argument."""
        document = parse_workflow("prompt: top-level guidance\n")

        assert isinstance(document, WorkflowDocument)

    def test_parse_workflow_returns_workflow_document_for_valid_input(self) -> None:
        """parse_workflow returns a WorkflowDocument for a valid workflow text."""
        document = parse_workflow("prompt: top-level guidance\nstages:\n  propose:\n    agent: codex\n")

        assert isinstance(document, WorkflowDocument)
        assert document.prompt == "top-level guidance"
        assert "propose" in document.stages
        assert document.stages["propose"].agent == "codex"

    def test_parse_workflow_populates_extend_for_valid_workflow_text(self) -> None:
        """A workflow text with an extend block yields a non-empty extend map of WorkflowExtendStage.

        Pins the contract: the extend block is part of the parse_workflow Return
        value, populated as ``dict[str, WorkflowExtendStage]``.
        """
        document = parse_workflow("extend:\n  warmup:\n    before: [propose]\n    title: Warmup\n")

        assert isinstance(document, WorkflowDocument)
        assert isinstance(document.extend, dict)
        assert set(document.extend) == {"warmup"}
        assert isinstance(document.extend["warmup"], WorkflowExtendStage)

    def test_parse_workflow_skills_is_accepted_stage_key(self) -> None:
        """``skills`` is part of the accepted per-stage key set (contract surface).

        Pins the contract: ``skills`` is a valid stage key, so a stage carrying it
        parses successfully and surfaces on the ``WorkflowStage`` model. The full
        valid-keys enumeration is pinned in the logic test module.
        """
        document = parse_workflow("stages:\n  propose:\n    agent: codex\n    skills: [web-search]\n")

        assert isinstance(document, WorkflowDocument)
        assert document.stages["propose"].skills == ["web-search"]

    def test_parse_workflow_env_is_accepted_stage_key(self) -> None:
        """``env`` is part of the accepted per-stage key set (contract surface).

        Pins the contract: ``env`` is a valid stage key (second, right after
        ``agent``), so a stage carrying a string map parses successfully and
        surfaces on the ``WorkflowStage`` model as the ``env`` field.
        """
        document = parse_workflow("stages:\n  propose:\n    env:\n      MODEL: sonnet\n")

        assert isinstance(document, WorkflowDocument)
        assert isinstance(document.stages["propose"], WorkflowStage)
        assert document.stages["propose"].env == {"MODEL": "sonnet"}

    def test_parse_workflow_accepts_skip_key(self) -> None:
        """``skip`` is part of the accepted per-stage key set (contract surface).

        Pins the contract: ``skip`` is a valid stage key, so a stage carrying
        ``skip: true`` parses successfully, the facade ``WorkflowDocument`` shape
        is unchanged, and the entry surfaces as a ``WorkflowStage``. The bool
        check, the false/absent equivalence, and the extend-prohibition are
        pinned in the logic test module.
        """
        document = parse_workflow("stages:\n  propose:\n    skip: true\n")

        assert isinstance(document, WorkflowDocument)
        assert "propose" in document.stages
        assert isinstance(document.stages["propose"], WorkflowStage)

    def test_parse_workflow_extend_exposes_agent_and_loop_fields(self) -> None:
        """An extend entry's inline ``agent``/``loop`` surface on the model (contract surface).

        Pins the contract: the extend model exposes ``agent`` and ``loop`` fields,
        extracted from the extend entry (and therefore absent from ``body``).
        """
        document = parse_workflow(
            "extend:\n  warmup:\n    before: [propose]\n    title: Warmup\n    agent: codex\n    loop: 3\n",
        )

        warmup = document.extend["warmup"]
        assert isinstance(warmup, WorkflowExtendStage)
        assert warmup.agent == "codex"
        assert warmup.loop == 3
        assert "agent" not in warmup.body
        assert "loop" not in warmup.body

    def test_parse_workflow_approve_is_accepted_stage_key(self) -> None:
        """``approve`` is part of the accepted per-stage key set (contract surface).

        Pins the contract: ``approve`` is a valid per-stage key, so a stage
        carrying ``approve: auto`` parses successfully and surfaces on the
        ``WorkflowStage`` model. The full valid-keys enumeration, the
        domain check, and the extend inline extraction are pinned in the logic
        test module.
        """
        document = parse_workflow("stages:\n  propose:\n    approve: auto\n")

        assert isinstance(document, WorkflowDocument)
        assert document.stages["propose"].approve == "auto"

    def test_parse_workflow_stage_keys_includes_env(self) -> None:
        """The internal ``_STAGE_KEYS`` tuple includes ``env`` (contract surface).

        Pins the contract: ``_STAGE_KEYS`` is the single source of the accepted
        per-stage key set and of the unknown-key ``valid keys`` message fragment,
        so it must carry ``env`` (right after ``agent``), then ``prompt``,
        ``loop``, ``skills``, ``skip``, ``approve``, ``manual``, ``notes``,
        ``reflect``, ``memory``, ``assistants``, and ``gates`` last — the fixed
        canonical order.
        """
        from goga.pipeline.workflow.parse_workflow import _STAGE_KEYS

        assert "env" in _STAGE_KEYS
        assert _STAGE_KEYS == (
            "agent",
            "env",
            "prompt",
            "loop",
            "skills",
            "skip",
            "approve",
            "manual",
            "notes",
            "reflect",
            "memory",
            "assistants",
            "gates",
        )

    def test_parse_workflow_top_level_keys_includes_profile_and_build(self) -> None:
        """The internal ``_TOP_LEVEL_KEYS`` tuple carries the ten accepted keys (contract surface).

        Pins the contract: the unknown top-level key message is generated from
        ``_TOP_LEVEL_KEYS`` and therefore lists ``profile`` and ``build`` after
        the four original keys, then ``assistants``, ``delegation``,
        ``repeat``, and ``gates`` last.
        """
        from goga.pipeline.workflow.parse_workflow import _TOP_LEVEL_KEYS

        assert _TOP_LEVEL_KEYS == (
            "prompt",
            "stages",
            "extend",
            "memory",
            "profile",
            "build",
            "assistants",
            "delegation",
            "repeat",
            "gates",
        )

    def test_parse_workflow_manual_is_accepted_stage_key(self) -> None:
        """``manual`` is part of the accepted per-stage key set (contract surface).

        Pins the contract: ``manual`` is a valid stage key, so a stage carrying
        ``manual: true`` parses successfully and surfaces on the ``WorkflowStage``
        model as the tri-state ``manual`` field. The bool check, the
        absent→``None`` (not ``False``) build, and the extend-prohibition are
        pinned in the logic test module.
        """
        document = parse_workflow("stages:\n  propose:\n    manual: true\n")

        assert isinstance(document, WorkflowDocument)
        assert document.stages["propose"].manual is True

    def test_parse_workflow_unknown_stage_key_message_lists_env(self) -> None:
        """The unknown per-stage key error message lists ``env`` in the valid-keys fragment.

        Pins the contract: the ``valid keys`` fragment of the unknown-key message
        is generated from ``_STAGE_KEYS`` and therefore includes ``env`` right
        after ``agent``.
        """
        with pytest.raises(WorkflowSyntaxError) as exc_info:
            parse_workflow("stages:\n  propose:\n    bad: value\n")

        message = str(exc_info.value)
        assert "unknown key in workflow.stages.propose: bad" in message
        assert "valid keys: agent, env, prompt, loop, skills, skip, approve, manual, notes" in message

    def test_parse_workflow_unknown_top_level_key_message_lists_profile_and_build(self) -> None:
        """The unknown top-level key error message lists all nine valid keys.

        Pins the contract: ``profile`` and ``build`` are accepted top-level keys,
        so the unknown-key message's valid-keys fragment enumerates all nine —
        including ``assistants``, ``delegation``, and ``repeat`` last.
        """
        with pytest.raises(WorkflowSyntaxError) as exc_info:
            parse_workflow("unknown_key: value\nprompt: hello\n")

        message = str(exc_info.value)
        assert "unknown key in workflow: unknown_key" in message
        assert "valid keys: prompt, stages, extend, memory, profile, build, assistants, delegation, repeat" in message

    def test_parse_workflow_build_block_surfaces_on_document(self) -> None:
        """A workflow ``build:`` block parses into the document's ``build`` field (contract surface).

        Pins the contract: the built ``WorkflowBuild`` is carried by
        ``WorkflowDocument.build`` — the parser builds the six-field model, the
        layering lives elsewhere.
        """
        document = parse_workflow(
            "build:\n"
            "  agent: codex\n"
            "  env:\n"
            '    A: "1"\n'
            "  review:\n"
            "    agent: claude\n"
            "    env:\n"
            '      C: "3"\n'
            "    additional:\n"
            "      agent: gemini\n"
            "      env:\n"
            '        E: "5"\n',
        )

        assert isinstance(document, WorkflowDocument)
        assert isinstance(document.build, WorkflowBuild)
        assert document.build.agent == "codex"
        assert document.build.env == {"A": "1"}
        assert document.build.review_agent == "claude"
        assert document.build.review_env == {"C": "3"}
        assert document.build.review_additional_agent == "gemini"
        assert document.build.review_additional_env == {"E": "5"}
