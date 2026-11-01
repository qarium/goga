"""Tests for the ``parse_workflow`` assistants authoring surfaces.

Covers the three authoring surfaces of the assistants contract: the TOP-LEVEL
``assistants:`` catalog and ``delegation:`` block (steps 6.5/6.6 — entry
validation, name grammar/reserved/within-catalog duplicate rules, the
at-least-one-of-prompt-or-skills rule, materialized defaults, the depth/
max_tasks int checks with the materialized ``max_tasks: 50`` default and the
authored-zero value), the PER-STAGE attachment grammar (step 6.7 — the three
entry forms, the eight-key declaration set, the ``gate``/``when`` parameter
domains), the extend-entry prohibition (step 6.8), and the document-wide
duplicate-name pass.
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
        """The design's full YAML parses with every default materialized on both surfaces."""
        document = parse_workflow(
            "assistants:\n"
            "  - name: reviewer\n"
            "    agent: claude\n"
            "    delegate: true\n"
            "    skills:\n"
            "      - code-audit\n"
            "    prompt: |\n"
            "      Review the stage changes.\n"
            "stages:\n"
            "  build:\n"
            "    assistants:\n"
            "      - name: reviewer\n"
            "        gate: true\n"
            "        when: finish\n",
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

        attachment = document.stages["build"].assistants[0]
        assert attachment.name == "reviewer"
        assert attachment.gate is True
        assert attachment.when == "finish"
        assert attachment.prompt is None

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


class TestStageAttachments:
    """Contract and logic tests — the per-stage attachment grammar (steps 6.7/6.8) and the namespace."""

    def test_parse_stage_assistants_parse_into_the_stage(self) -> None:
        """A stage carrying ``assistants:`` parses its list into the stage model."""
        document = parse_workflow(
            "assistants:\n"
            "  - name: reviewer\n"
            "    prompt: Review.\n"
            "stages:\n"
            "  build:\n"
            "    assistants:\n"
            "      - reviewer\n",
        )

        attachments = document.stages["build"].assistants
        assert attachments is not None
        assert [entry.name for entry in attachments] == ["reviewer"]
        assert document.stages["build"].assistants[0].prompt is None

    def test_parse_unknown_stage_key_message_lists_twelve_valid_keys(self) -> None:
        """The unknown stage key error enumerates all twelve valid keys with ``assistants`` last."""
        with pytest.raises(WorkflowSyntaxError) as exc_info:
            parse_workflow("stages:\n  build:\n    bogus: 1\n")

        message = str(exc_info.value)
        assert "unknown key in workflow.stages.build: bogus" in message
        assert (
            "valid keys: agent, env, prompt, loop, skills, skip, approve, manual, notes, reflect, memory, assistants"
            in message
        )

    def test_parse_assistants_on_extend_entry_raises_prohibition(self) -> None:
        """``assistants`` inside an extend-entry raises the pinned prohibition (step 6.8)."""
        with pytest.raises(WorkflowSyntaxError) as exc_info:
            parse_workflow(
                "stages:\n  b:\n    agent: codex\nextend:\n  n:\n    assistants: []\n    before: [b]\n",
            )

        assert str(exc_info.value) == "assistants is forbidden in workflow.extend.n"

    def test_parse_attachment_three_entry_forms(self) -> None:
        """The design's attachment YAML parses the three entry forms with materialized defaults."""
        document = parse_workflow(
            "assistants:\n"
            "  - name: reviewer\n"
            "    prompt: Review.\n"
            "  - name: reviewer2\n"
            "    prompt: Review again.\n"
            "stages:\n"
            "  build:\n"
            "    assistants:\n"
            "      - reviewer\n"
            "      - name: reviewer2\n"
            "        gate: true\n"
            "      - name: security\n"
            "        agent: codex\n"
            "        prompt: Audit.\n"
            "        when: start\n",
        )

        assert [(a.name, a.gate, a.when, a.prompt) for a in document.stages["build"].assistants] == [
            ("reviewer", False, "checkpoints", None),
            ("reviewer2", True, "checkpoints", None),
            ("security", False, "start", "Audit."),
        ]

    @pytest.mark.parametrize(
        ("workflow_yaml", "match"),
        [
            ("stages:\n  b:\n    assistants: {}\n", r"non-list assistants in workflow\.stages\.b"),
            ("stages:\n  b:\n    assistants: [42]\n", r"invalid assistant entry in workflow\.stages\.b\.assistants"),
            (
                "stages:\n  b:\n    assistants:\n      - gate: true\n",
                r"name is required in workflow\.stages\.b\.assistants entry",
            ),
            (
                "stages:\n  b:\n    assistants:\n      - prompt: p\n",
                r"name is required in workflow\.stages\.b\.assistants entry",
            ),
            (
                "stages:\n  b:\n    assistants:\n      - name: 3\n        prompt: p\n",
                r"non-str name in workflow\.stages\.b\.assistants entry",
            ),
            (
                "stages:\n  b:\n    assistants:\n      - name: r\n        prompt: p\n        bogus: 1\n",
                r"unknown key in workflow\.stages\.b\.assistants\.r: bogus; "
                r"valid keys: name, prompt, skills, agent, delegate, env, gate, when",
            ),
            (
                "stages:\n  b:\n    assistants:\n      - name: r\n        prompt: p\n        when: later\n",
                r"when must be one of: start, checkpoints, finish in workflow\.stages\.b\.assistants\.r",
            ),
            (
                "stages:\n  b:\n    assistants:\n      - name: r\n        prompt: p\n        gate: x\n",
                r"non-bool value in workflow\.stages\.b\.assistants\.r\.gate",
            ),
            (
                "stages:\n  b:\n    agent: codex\nextend:\n  n:\n    assistants: []\n    before: [b]\n",
                r"assistants is forbidden in workflow\.extend\.n",
            ),
            (
                "assistants:\n  - name: r\n    prompt: p\n"
                "stages:\n  b:\n    assistants:\n      - name: r\n        prompt: q\n",
                r"duplicate assistant name: r",
            ),
            (
                "stages:\n"
                "  b:\n    assistants:\n      - name: r\n        prompt: p\n"
                "  c:\n    assistants:\n      - name: r\n        skills: [s]\n",
                r"duplicate assistant name: r",
            ),
            (
                "stages:\n  b:\n    assistants:\n      - name: r\n        prompt: p\n"
                "      - name: r\n        skills: [s]\n",
                r"duplicate assistant name: r",
            ),
            ('stages:\n  b:\n    assistants:\n      - "a b"\n', r"invalid assistant name: a b"),
            (
                'stages:\n  b:\n    assistants:\n      - name: "a b"\n        gate: true\n',
                r"invalid assistant name: a b",
            ),
            (
                "stages:\n  b:\n    assistants:\n      - name: assistant\n        prompt: p\n",
                r"assistant name is reserved",
            ),
        ],
    )
    def test_parse_attachment_rejects_structural_defects(self, workflow_yaml: str, match: str) -> None:
        """Each single-defect attachment file raises WorkflowSyntaxError with the pinned message."""
        with pytest.raises(WorkflowSyntaxError, match=match):
            parse_workflow(workflow_yaml)

    @pytest.mark.parametrize(
        ("workflow_yaml", "fragment"),
        [
            (
                "stages:\n  b:\n    assistants:\n      - name: r\n        prompt: 3\n",
                "non-str value in workflow.stages.b.assistants.r.prompt",
            ),
            (
                "stages:\n  b:\n    assistants:\n      - name: r\n        skills: [1]\n",
                "non-list-of-str skills in workflow.stages.b.assistants.r",
            ),
            (
                "stages:\n  b:\n    assistants:\n      - name: r\n        prompt: p\n        delegate: 3\n",
                "non-bool value in workflow.stages.b.assistants.r.delegate",
            ),
            (
                "stages:\n  b:\n    assistants:\n      - name: r\n        prompt: p\n        env: not-a-map\n",
                "non-mapping env in workflow.stages.b.assistants.r",
            ),
            (
                "stages:\n  b:\n    assistants:\n      - name: r\n        prompt: p\n        env:\n          A: 1\n",
                "non-str value in workflow.stages.b.assistants.r.env.A",
            ),
            (
                "stages:\n  b:\n    assistants:\n      - name: r\n        prompt: p\n        when: 3\n",
                "non-str value in workflow.stages.b.assistants.r.when",
            ),
        ],
    )
    def test_parse_attachment_rejects_wrong_typed_declaration_fields(
        self,
        workflow_yaml: str,
        fragment: str,
    ) -> None:
        """Each wrong-typed declaration field raises WorkflowSyntaxError carrying a stable fragment."""
        with pytest.raises(WorkflowSyntaxError) as exc_info:
            parse_workflow(workflow_yaml)

        assert fragment in str(exc_info.value)

    def test_parse_empty_assistants_list_equals_absence(self) -> None:
        """A stage's empty ``assistants: []`` list builds the stage with assistants=None."""
        document = parse_workflow("stages:\n  b:\n    agent: codex\n    assistants: []\n")

        assert document.stages["b"].assistants is None

    def test_parse_empty_env_and_empty_skills_forms(self) -> None:
        """An inline declaration's empty env map equals absence; an authored empty skills list is a declaration."""
        document = parse_workflow(
            "stages:\n  b:\n    assistants:\n      - name: r\n        env: {}\n        skills: []\n",
        )

        entry = document.stages["b"].assistants[0]
        assert entry.env is None
        assert entry.skills == []
        assert entry.prompt is None

    def test_parse_duplicate_reference_on_one_stage_list_is_legal(self) -> None:
        """Two identical bare-string references parse — the per-stage duplicate check is the compiler's."""
        document = parse_workflow(
            "assistants:\n"
            "  - name: reviewer\n"
            "    prompt: p\n"
            "stages:\n"
            "  b:\n"
            "    assistants:\n"
            "      - reviewer\n"
            "      - reviewer\n",
        )

        assert [entry.name for entry in document.stages["b"].assistants] == ["reviewer", "reviewer"]
