"""Tests for the ``parse_workflow`` assistants catalog and delegation block.

Covers the two TOP-LEVEL authoring surfaces of contract steps 6.5/6.6: the
``assistants:`` catalog (entry validation, name grammar/reserved/within-catalog
duplicate rules, the at-least-one-of-prompt-or-skills rule, materialized
defaults) and the ``delegation:`` block (depth/max_tasks int checks, the
materialized ``max_tasks: 50`` default, the authored-zero value). The stage
attachment grammar (6.7), the extend prohibition (6.8), and the document-wide
duplicate-name pass live in later tasks — this module pins the top-level
surfaces only.
"""

from __future__ import annotations

import pytest
from goga.pipeline.workflow import (
    WorkflowAssistant,
    WorkflowDelegation,
    WorkflowDocument,
    WorkflowSyntaxError,
    parse_workflow,
)


class TestAssistantCatalog:
    """Contract and logic tests — the top-level ``assistants:`` catalog (step 6.5)."""

    def test_parse_workflow_accepts_assistants_and_delegation_top_level_keys(self) -> None:
        """A workflow carrying both new top-level keys parses into the document."""
        document = parse_workflow(
            "assistants:\n"
            "  - name: reviewer\n"
            "    prompt: Review the changes.\n"
            "delegation:\n"
            "  depth: 3\n"
            "stages:\n"
            "  build:\n"
            "    agent: codex\n",
        )

        assert isinstance(document, WorkflowDocument)
        assert isinstance(document.assistants["reviewer"], WorkflowAssistant)
        assert isinstance(document.delegation, WorkflowDelegation)

    def test_parse_workflow_unknown_top_level_key_message_lists_eight_valid_keys(self) -> None:
        """The unknown top-level key error enumerates all eight valid keys."""
        with pytest.raises(WorkflowSyntaxError) as exc_info:
            parse_workflow("unknown_key: value\nprompt: hello\n")

        message = str(exc_info.value)
        assert "unknown key in workflow: unknown_key" in message
        assert "valid keys: prompt, stages, extend, memory, profile, build, assistants, delegation" in message

    def test_parse_workflow_extended_empty_message_fires_for_empty_mapping(self) -> None:
        """``{}`` raises the extended empty-workflow message naming both new blocks."""
        with pytest.raises(WorkflowSyntaxError) as exc_info:
            parse_workflow("{}\n")

        assert str(exc_info.value) == (
            "empty workflow — provide at least prompt, one stage, one extend entry, "
            "the memory block, the build block, the assistants block, or the delegation block"
        )

    def test_parse_assistants_catalog_full_form_materializes_defaults(self) -> None:
        """The design's catalog YAML parses with every default materialized."""
        document = parse_workflow(
            "assistants:\n"
            "  - name: reviewer\n"
            "    agent: claude\n"
            "    delegate: true\n"
            "    skills:\n"
            "      - code-audit\n"
            "    prompt: |\n"
            "      Review the stage changes.\n",
        )

        assert list(document.assistants.keys()) == ["reviewer"]
        reviewer = document.assistants["reviewer"]
        assert reviewer.prompt == "Review the stage changes.\n"
        assert reviewer.skills == ["code-audit"]
        assert reviewer.agent == "claude"
        assert reviewer.delegate is True
        assert reviewer.env is None
        assert reviewer.gate is False
        assert reviewer.when == "checkpoints"
        assert document.delegation is None

    def test_parse_assistants_catalog_preserves_authored_order(self) -> None:
        """The catalog map keeps the authored entry order (not name-sorted)."""
        document = parse_workflow(
            "assistants:\n  - name: zed\n    prompt: Z.\n  - name: alpha\n    prompt: A.\n",
        )

        assert list(document.assistants.keys()) == ["zed", "alpha"]

    def test_parse_assistants_catalog_empty_skills_satisfies_at_least_one(self) -> None:
        """An authored ``skills: []`` satisfies the at-least-one rule (presence, not truthiness)."""
        document = parse_workflow("assistants:\n  - name: r\n    skills: []\n")

        reviewer = document.assistants["r"]
        assert reviewer.skills == []
        assert reviewer.prompt is None

    def test_parse_assistants_catalog_empty_env_map_equals_absence(self) -> None:
        """An authored ``env: {}`` builds the entry with env=None."""
        document = parse_workflow("assistants:\n  - name: r\n    prompt: p\n    env: {}\n")

        assert document.assistants["r"].env is None

    def test_parse_assistants_catalog_empty_list_equals_no_catalog(self) -> None:
        """``assistants: []`` parses to an empty dict and does not rescue an empty workflow."""
        document = parse_workflow("assistants: []\nstages:\n  build:\n    agent: codex\n")

        assert document.assistants == {}

        with pytest.raises(WorkflowSyntaxError, match="empty workflow"):
            parse_workflow("assistants: []\n")

    def test_parse_assistants_only_workflow_is_valid(self) -> None:
        """A workflow consisting of the catalog alone parses (content, not activation)."""
        document = parse_workflow("assistants:\n  - name: r\n    prompt: p\n")

        assert list(document.assistants.keys()) == ["r"]
        assert document.stages == {}

    @pytest.mark.parametrize(
        ("workflow_yaml", "match"),
        [
            ("assistants:\n  a: 1\n", "non-list assistants block in workflow"),
            ("assistants: [x]\n", "non-mapping assistant entry in workflow.assistants"),
            ("assistants:\n  - prompt: p\n", "name is required in workflow.assistants entry"),
            ("assistants:\n  - name: 3\n    prompt: p\n", "non-str name in workflow.assistants entry"),
            (
                "assistants:\n  - name: r\n    gate: true\n",
                r"unknown key in workflow\.assistants\.r: gate; "
                r"valid keys: name, prompt, skills, agent, delegate, env",
            ),
            (
                "assistants:\n  - name: r\n    when: start\n",
                r"unknown key in workflow\.assistants\.r: when; "
                r"valid keys: name, prompt, skills, agent, delegate, env",
            ),
            ("assistants:\n  - name: r\n    agent: c\n", "assistant r requires at least one of prompt or skills"),
            ('assistants:\n  - name: "a b"\n    prompt: p\n', "invalid assistant name: a b"),
            ("assistants:\n  - name: assistant\n    prompt: p\n", "assistant name is reserved"),
            (
                "assistants:\n  - name: r\n    prompt: p\n  - name: r\n    prompt: q\n",
                "duplicate assistant name: r",
            ),
        ],
    )
    def test_parse_assistants_catalog_rejects_structural_defects(self, workflow_yaml: str, match: str) -> None:
        """Each single-defect catalog file raises WorkflowSyntaxError with the pinned message."""
        with pytest.raises(WorkflowSyntaxError, match=match):
            parse_workflow(workflow_yaml)

    @pytest.mark.parametrize(
        ("workflow_yaml", "fragment"),
        [
            ("assistants:\n  - name: r\n    prompt: 3\n", "non-str value in workflow.assistants.r.prompt"),
            ("assistants:\n  - name: r\n    skills: [1]\n", "non-list-of-str skills in workflow.assistants.r"),
            (
                "assistants:\n  - name: r\n    prompt: p\n    delegate: 3\n",
                "non-bool value in workflow.assistants.r.delegate",
            ),
            (
                "assistants:\n  - name: r\n    prompt: p\n    env: not-a-map\n",
                "non-mapping env in workflow.assistants.r",
            ),
            (
                "assistants:\n  - name: r\n    prompt: p\n    env:\n      A: 1\n",
                "non-str value in workflow.assistants.r.env.A",
            ),
        ],
    )
    def test_parse_assistants_catalog_rejects_wrong_typed_fields(
        self,
        workflow_yaml: str,
        fragment: str,
    ) -> None:
        """Each wrong-typed catalog field raises WorkflowSyntaxError carrying a stable fragment."""
        with pytest.raises(WorkflowSyntaxError) as exc_info:
            parse_workflow(workflow_yaml)

        assert fragment in str(exc_info.value)


class TestDelegationBlock:
    """Logic tests — the top-level ``delegation:`` block (step 6.6)."""

    def test_parse_delegation_block_materializes_max_tasks(self) -> None:
        """``depth`` alone materializes ``max_tasks: 50``; an authored ``max_tasks`` wins."""
        document = parse_workflow("delegation:\n  depth: 3\nstages:\n  build:\n    agent: codex\n")

        assert document.delegation is not None
        assert document.delegation.depth == 3
        assert document.delegation.max_tasks == 50

        document = parse_workflow("delegation:\n  depth: 3\n  max_tasks: 7\nstages:\n  build:\n    agent: codex\n")

        assert document.delegation is not None
        assert document.delegation.depth == 3
        assert document.delegation.max_tasks == 7

    def test_parse_delegation_empty_block_alone_is_valid(self) -> None:
        """``delegation: {}`` alone yields ``(None, 50)`` and does not fire the empty rule."""
        document = parse_workflow("delegation: {}\n")

        assert document.delegation is not None
        assert document.delegation.depth is None
        assert document.delegation.max_tasks == 50

    def test_parse_delegation_depth_zero_is_an_authored_value(self) -> None:
        """The boundary row: an authored ``depth: 0`` survives as the int 0, never as absence."""
        document = parse_workflow("delegation:\n  depth: 0\nstages:\n  build:\n    agent: codex\n")

        assert document.delegation is not None
        assert document.delegation.depth == 0
        assert document.delegation.max_tasks == 50

    @pytest.mark.parametrize(
        ("workflow_yaml", "match"),
        [
            ("delegation: [1]\n", "non-mapping delegation block in workflow"),
            ("delegation:\n  x: 1\n", r"unknown key in workflow\.delegation: x; valid keys: depth, max_tasks"),
            ("delegation:\n  depth: -1\n", "depth must be >= 0 in workflow.delegation"),
            ("delegation:\n  depth: true\n", "non-int value in workflow.delegation.depth"),
            ("delegation:\n  max_tasks: 0\n", "max_tasks must be >= 1 in workflow.delegation"),
            ("delegation:\n  max_tasks: true\n", "non-int value in workflow.delegation.max_tasks"),
        ],
    )
    def test_parse_delegation_rejects_structural_defects(self, workflow_yaml: str, match: str) -> None:
        """Each single-defect delegation file raises WorkflowSyntaxError with the pinned message."""
        with pytest.raises(WorkflowSyntaxError, match=match):
            parse_workflow(workflow_yaml)
