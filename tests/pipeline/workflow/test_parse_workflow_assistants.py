"""Tests for the ``parse_workflow`` assistants authoring surfaces.

Covers the three authoring surfaces of the assistants contract: the TOP-LEVEL
``assistants:`` catalog and ``delegation:`` block (steps 6.5/6.6 — the
name-keyed entry-map grammar, the name grammar/reserved rules, the
override-style entries that carry none of the five declaration fields, the
presence-preserving field discipline, the depth/max_tasks int checks with the
materialized ``max_tasks: 50`` default and the authored-zero value), the
PER-STAGE attachment map grammar (step 6.7 — the map-keyed reference and full
inline declaration forms, the required ``when``, the seven-key declaration
set, the ``gate``/``when`` parameter domains), the extend-entry prohibition
(step 6.8), and the document-wide duplicate-name pass under the five-field
declaration discriminator. Both surfaces are name-keyed maps — the retired
list-of-mappings forms are hard-rejected with rename errors naming the map
form.
"""

from __future__ import annotations

import pytest
from goga.pipeline.workflow import (
    WorkflowAssistant,
    WorkflowDelegation,
    WorkflowDocument,
    WorkflowStage,
    WorkflowSyntaxError,
    parse_workflow,
)


class TestAssistantMapContract:
    """Contract tests — the map-form data model both authoring surfaces build into."""

    def test_workflow_stage_constructs_with_assistants_map(self) -> None:
        """``WorkflowStage(assistants=...)`` takes a name-keyed map of WorkflowAssistant."""
        attachment = WorkflowAssistant(name="reviewer", when="start")

        stage = WorkflowStage(assistants={"reviewer": attachment})

        assert stage.assistants == {"reviewer": attachment}

    def test_workflow_assistant_import_surface_unchanged(self) -> None:
        """The WorkflowAssistant model stays importable from the workflow facade."""
        assert WorkflowAssistant(name="x", when="finish").name == "x"


class TestAssistantCatalog:
    """Contract and logic tests — the top-level ``assistants:`` catalog map (step 6.5)."""

    def test_parse_workflow_accepts_assistants_and_delegation_top_level_keys(self) -> None:
        """A workflow carrying both new top-level keys parses into the document."""
        document = parse_workflow(
            "assistants:\n"
            "  reviewer:\n"
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

    def test_parse_workflow_unknown_top_level_key_message_lists_nine_valid_keys(self) -> None:
        """The unknown top-level key error enumerates all nine valid keys."""
        with pytest.raises(WorkflowSyntaxError) as exc_info:
            parse_workflow("unknown_key: value\nprompt: hello\n")

        message = str(exc_info.value)
        assert "unknown key in workflow: unknown_key" in message
        assert "valid keys: prompt, stages, extend, memory, profile, build, assistants, delegation, repeat" in message

    def test_parse_workflow_extended_empty_message_fires_for_empty_mapping(self) -> None:
        """``{}`` raises the extended empty-workflow message naming the content blocks."""
        with pytest.raises(WorkflowSyntaxError) as exc_info:
            parse_workflow("{}\n")

        assert str(exc_info.value) == (
            "empty workflow — provide at least prompt, one stage, one extend entry, "
            "the memory block, the build block, the assistants block, the delegation block, "
            "the repeat block, or the gates block"
        )

    def test_parse_assistant_catalog_map_form(self) -> None:
        """The design's canonical map-form YAML parses with every default materialized."""
        document = parse_workflow(
            "assistants:\n"
            "  reviewer:\n"
            "    agent: claude\n"
            "    delegate: true\n"
            "    skills:\n"
            "      - code-audit\n"
            "    prompt: |\n"
            "      Review the stage changes.\n"
            "stages:\n"
            "  build:\n"
            "    assistants:\n"
            "      reviewer:\n"
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

        attachment = document.stages["build"].assistants["reviewer"]
        assert attachment.name == "reviewer"
        assert attachment.gate is False
        assert attachment.when == "finish"
        assert attachment.prompt is None

    def test_parse_assistants_catalog_preserves_authored_order(self) -> None:
        """The catalog map keeps the authored key order (not name-sorted)."""
        document = parse_workflow(
            "assistants:\n  zed:\n    prompt: Z.\n  alpha:\n    prompt: A.\n",
        )

        assert list(document.assistants.keys()) == ["zed", "alpha"]

    def test_parse_assistants_catalog_empty_skills_is_explicit_override(self) -> None:
        """An authored ``skills: []`` parses as a declaration carrying the explicit empty list."""
        document = parse_workflow("assistants:\n  r:\n    skills: []\n")

        reviewer = document.assistants["r"]
        assert reviewer.skills == []
        assert reviewer.prompt is None

    def test_parse_assistants_catalog_empty_env_map_is_explicit_override(self) -> None:
        """An authored ``env: {}`` builds the entry with env={} (an override that clears)."""
        document = parse_workflow("assistants:\n  r:\n    prompt: p\n    env: {}\n")

        assert document.assistants["r"].env == {}

    def test_parse_empty_assistants_catalog_equals_absence(self) -> None:
        """``assistants: {}`` parses to an empty dict and does not rescue an empty workflow."""
        document = parse_workflow("assistants: {}\nstages:\n  build:\n    agent: codex\n")

        assert document.assistants == {}

        with pytest.raises(WorkflowSyntaxError, match="empty workflow"):
            parse_workflow("assistants: {}\n")

    def test_parse_assistants_only_workflow_is_valid(self) -> None:
        """A workflow consisting of the catalog alone parses (content, not activation)."""
        document = parse_workflow("assistants:\n  r:\n    prompt: p\n")

        assert list(document.assistants.keys()) == ["r"]
        assert document.stages == {}

    def test_parse_workflow_preserves_explicit_empty_env_and_skills(self) -> None:
        """An assistant's authored ``skills: []``/``env: {}`` stay explicit; the stage env rule is untouched.

        The catalog entry carries ``prompt: p, skills: [], env: {}`` and a
        stage carries ``env: {}`` — the assistant fields parse as the
        explicit empty overrides the overlay merge keys on, while the
        per-STAGE env keeps its empty-equals-absence rule (the presence
        discipline applies to the assistant fields only).
        """
        document = parse_workflow(
            "assistants:\n"
            "  X:\n"
            "    prompt: p\n"
            "    skills: []\n"
            "    env: {}\n"
            "stages:\n"
            "  s1:\n"
            "    prompt: go\n"
            "    env: {}\n",
        )

        assert document.assistants["X"].skills == []
        assert document.assistants["X"].env == {}
        assert document.stages["s1"].env is None

    def test_parse_workflow_delegate_default_is_none(self) -> None:
        """A catalog entry without ``delegate`` parses with delegate None (was False before).

        Absent and explicit-``false`` must stay distinguishable to the
        overlay merge — None is the inheritable not-authored value.
        """
        document = parse_workflow("assistants:\n  X:\n    prompt: p\n")

        assert document.assistants["X"].delegate is None

        authored = parse_workflow("assistants:\n  X:\n    prompt: p\n    delegate: false\n")

        assert authored.assistants["X"].delegate is False

    def test_parse_workflow_empty_catalog_entry_parses_as_override_style(self) -> None:
        """A catalog ``X: {}`` parses with every field None and joins the namespace.

        The degenerate override — legal parse (the compile content check
        owns the failure); the entry counts for the duplicate-name rule via
        the five-field discriminator, while a pure reference still repeats
        freely.
        """
        document = parse_workflow("assistants:\n  X: {}\nstages:\n  s1:\n    prompt: p\n")

        entry = document.assistants["X"]
        assert entry.prompt is None
        assert entry.skills is None
        assert entry.agent is None
        assert entry.delegate is None
        assert entry.env is None

        with pytest.raises(WorkflowSyntaxError, match="duplicate assistant name: X"):
            parse_workflow(
                "assistants:\n"
                "  X: {}\n"
                "stages:\n"
                "  s1:\n"
                "    prompt: p\n"
                "    assistants:\n"
                "      X:\n"
                "        prompt: q\n"
                "        when: start\n",
            )

        reference_repeat = parse_workflow(
            "assistants:\n  X: {}\nstages:\n  s1:\n    prompt: p\n    assistants:\n      X:\n        when: start\n",
        )

        assert list(reference_repeat.stages["s1"].assistants) == ["X"]

    def test_parse_workflow_agent_only_entry_parses_as_override_style(self) -> None:
        """An ``agent``-only catalog entry parses — the at-least-one raise is gone for it.

        The entry configures delivery fields and inherits its content from
        a tool-delivered entry of the same name at the overlay merge; the
        effective-content requirement is enforced at compilation.
        """
        document = parse_workflow("assistants:\n  r:\n    agent: c\n")

        reviewer = document.assistants["r"]
        assert reviewer.agent == "c"
        assert reviewer.prompt is None
        assert reviewer.skills is None
        assert reviewer.delegate is None
        assert reviewer.env is None

    def test_parse_workflow_rejects_non_bool_delegate(self) -> None:
        """A non-bool ``delegate`` value still raises the pinned type error after the relaxation."""
        with pytest.raises(WorkflowSyntaxError) as exc_info:
            parse_workflow("assistants:\n  X:\n    delegate: yes-please\n    prompt: p\n")

        assert str(exc_info.value) == "non-bool value in workflow.assistants.X.delegate"

    def test_parse_list_form_catalog_rejected_naming_map_form(self) -> None:
        """The retired list-of-mappings catalog is hard-rejected with the rename error."""
        with pytest.raises(WorkflowSyntaxError) as exc_info:
            parse_workflow(
                "assistants:\n  - name: reviewer\n    prompt: Review the changes.\n",
            )

        assert str(exc_info.value) == (
            "non-mapping assistants block in workflow; author the map form keyed by assistant name"
        )

    def test_parse_assistant_name_grammar_and_reserved(self) -> None:
        """The name grammar accepts the full character class; the map key carries the name.

        ``good.name-1_X`` exercises every accepted character class of
        ``[A-Za-z0-9._-]``; the reserved name and the invalid names die on
        their pinned messages (the parametrized defects below carry those
        rows, including the non-str YAML key guard).
        """
        document = parse_workflow("assistants:\n  good.name-1_X:\n    prompt: p\n")

        assert list(document.assistants) == ["good.name-1_X"]
        assert document.assistants["good.name-1_X"].name == "good.name-1_X"

    @pytest.mark.parametrize(
        ("workflow_yaml", "match"),
        [
            (
                "assistants: [x]\n",
                "non-mapping assistants block in workflow; author the map form keyed by assistant name",
            ),
            ("assistants:\n  a: 1\n", r"non-mapping assistant entry in workflow\.assistants\.a"),
            ("assistants:\n  a: [x]\n", r"non-mapping assistant entry in workflow\.assistants\.a"),
            (
                "assistants:\n  r:\n    name: x\n    prompt: p\n",
                r"unknown key in workflow\.assistants\.r: name; "
                r"valid keys: prompt, skills, agent, delegate, env",
            ),
            (
                "assistants:\n  r:\n    gate: true\n",
                r"unknown key in workflow\.assistants\.r: gate; "
                r"valid keys: prompt, skills, agent, delegate, env",
            ),
            (
                "assistants:\n  r:\n    when: start\n",
                r"unknown key in workflow\.assistants\.r: when; "
                r"valid keys: prompt, skills, agent, delegate, env",
            ),
            ('assistants:\n  "bad name!":\n    prompt: p\n', "invalid assistant name: bad name!"),
            ("assistants:\n  assistant:\n    prompt: p\n", "assistant name is reserved"),
            ("assistants:\n  123:\n    prompt: p\n", "invalid assistant name: 123"),
        ],
    )
    def test_parse_assistants_catalog_rejects_structural_defects(self, workflow_yaml: str, match: str) -> None:
        """Each single-defect catalog file raises WorkflowSyntaxError with the pinned message."""
        with pytest.raises(WorkflowSyntaxError, match=match):
            parse_workflow(workflow_yaml)

    @pytest.mark.parametrize(
        ("workflow_yaml", "fragment"),
        [
            ("assistants:\n  r:\n    prompt: 3\n", "non-str value in workflow.assistants.r.prompt"),
            ("assistants:\n  r:\n    skills: [1]\n", "non-list-of-str skills in workflow.assistants.r"),
            (
                "assistants:\n  r:\n    prompt: p\n    delegate: 3\n",
                "non-bool value in workflow.assistants.r.delegate",
            ),
            (
                "assistants:\n  r:\n    prompt: p\n    env: not-a-map\n",
                "non-mapping env in workflow.assistants.r",
            ),
            (
                "assistants:\n  r:\n    prompt: p\n    env:\n      A: 1\n",
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

    def test_parse_duplicate_assistant_name_across_surfaces(self) -> None:
        """A catalog name repeated as a stage inline declaration raises the duplicate error."""
        with pytest.raises(WorkflowSyntaxError, match="duplicate assistant name: r"):
            parse_workflow(
                "assistants:\n"
                "  r:\n"
                "    prompt: p\n"
                "stages:\n"
                "  b:\n"
                "    assistants:\n"
                "      r:\n"
                "        prompt: q\n"
                "        when: start\n",
            )

    def test_parse_workflow_override_style_inline_counts_for_duplicate_name(self) -> None:
        """An override-style inline declaration counts for the duplicate rule via its ``agent``.

        The five-field discriminator: the inline entry ``{when: start,
        agent: y}`` is a DECLARATION (``agent is not None``), so repeating
        the catalog name raises — under the OLD prompt/skills-only rule it
        parsed as a reference and its ``agent`` was silently dropped.
        """
        with pytest.raises(WorkflowSyntaxError) as exc_info:
            parse_workflow(
                "assistants:\n"
                "  X:\n"
                "    prompt: p\n"
                "stages:\n"
                "  s1:\n"
                "    prompt: go\n"
                "    assistants:\n"
                "      X:\n"
                "        when: start\n"
                "        agent: y\n",
            )

        assert str(exc_info.value) == "duplicate assistant name: X"


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
    """Contract and logic tests — the per-stage attachment map (steps 6.7/6.8) and the namespace."""

    def test_parse_stage_attachment_map_parses_into_stage(self) -> None:
        """A stage carrying a map-form ``assistants:`` parses its entries keyed by name."""
        document = parse_workflow(
            "assistants:\n"
            "  reviewer:\n"
            "    prompt: Review.\n"
            "stages:\n"
            "  build:\n"
            "    assistants:\n"
            "      reviewer:\n"
            "        when: checkpoints\n",
        )

        attachments = document.stages["build"].assistants
        assert attachments is not None
        assert list(attachments.keys()) == ["reviewer"]
        assert attachments["reviewer"].prompt is None

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
                "stages:\n  b:\n    agent: codex\nextend:\n  n:\n    assistants: {}\n    before: [b]\n",
            )

        assert str(exc_info.value) == "assistants is forbidden in workflow.extend.n"

    def test_parse_attachment_full_inline_declaration(self) -> None:
        """The design's full inline declaration parses with every authored field carried."""
        document = parse_workflow(
            "stages:\n"
            "  build:\n"
            "    assistants:\n"
            "      security:\n"
            "        agent: codex\n"
            "        prompt: Audit the diff.\n"
            "        gate: true\n"
            "        when: checkpoints\n",
        )

        entry = document.stages["build"].assistants["security"]
        assert entry.prompt == "Audit the diff."
        assert entry.agent == "codex"
        assert entry.gate is True
        assert entry.when == "checkpoints"
        assert entry.skills is None
        assert entry.delegate is None
        assert entry.env is None

    def test_parse_attachment_reference_with_when_only(self) -> None:
        """A reference with only ``when`` authored parses — gate materializes False."""
        document = parse_workflow(
            "assistants:\n"
            "  reviewer:\n"
            "    prompt: Review.\n"
            "stages:\n"
            "  build:\n"
            "    assistants:\n"
            "      reviewer:\n"
            "        when: start\n",
        )

        entry = document.stages["build"].assistants["reviewer"]
        assert entry.prompt is None
        assert entry.skills is None
        assert entry.gate is False
        assert entry.when == "start"

    def test_parse_attachment_when_message_is_accepted(self) -> None:
        """``when: message`` — the resting engagement — parses and is carried verbatim."""
        document = parse_workflow(
            "assistants:\n"
            "  reviewer:\n"
            "    prompt: Review.\n"
            "stages:\n"
            "  build:\n"
            "    assistants:\n"
            "      reviewer:\n"
            "        gate: true\n"
            "        when: message\n",
        )

        entry = document.stages["build"].assistants["reviewer"]
        assert entry.when == "message"
        assert entry.gate is True

    def test_parse_attachment_list_and_string_forms_rejected(self) -> None:
        """The retired list and scalar attachment forms are hard-rejected naming the map form."""
        with pytest.raises(WorkflowSyntaxError) as exc_info:
            parse_workflow("stages:\n  build:\n    assistants: [reviewer]\n")

        assert str(exc_info.value) == (
            "non-mapping assistants in workflow.stages.build; author the map form keyed by assistant name"
        )

        with pytest.raises(WorkflowSyntaxError) as exc_info:
            parse_workflow("stages:\n  build:\n    assistants: reviewer\n")

        assert str(exc_info.value) == (
            "non-mapping assistants in workflow.stages.build; author the map form keyed by assistant name"
        )

    def test_parse_attachment_missing_when(self) -> None:
        """An attachment without ``when`` raises the required-when error naming the entry."""
        with pytest.raises(WorkflowSyntaxError) as exc_info:
            parse_workflow(
                "stages:\n  build:\n    assistants:\n      reviewer:\n        gate: true\n",
            )

        assert str(exc_info.value) == "when is required in workflow.stages.build.assistants.reviewer"

    def test_parse_attachment_empty_map_equals_absence(self) -> None:
        """A stage's empty ``assistants: {}`` map builds the stage with assistants=None."""
        document = parse_workflow("stages:\n  b:\n    agent: codex\n    assistants: {}\n")

        assert document.stages["b"].assistants is None

    def test_parse_inline_empty_env_and_empty_skills_forms(self) -> None:
        """An inline declaration preserves authored ``env: {}`` and ``skills: []`` as explicit overrides."""
        document = parse_workflow(
            "stages:\n  b:\n    assistants:\n      r:\n        env: {}\n        skills: []\n        when: start\n",
        )

        entry = document.stages["b"].assistants["r"]
        assert entry.env == {}
        assert entry.skills == []
        assert entry.prompt is None

    def test_parse_attachment_declaration_keeps_authored_gate(self) -> None:
        """A full inline declaration keeps its authored bool ``gate`` — not the materialized default."""
        document = parse_workflow(
            "stages:\n  b:\n    assistants:\n      r:\n        prompt: p\n        gate: true\n        when: finish\n",
        )

        entry = document.stages["b"].assistants["r"]
        assert entry.gate is True
        assert entry.when == "finish"

    @pytest.mark.parametrize(
        ("workflow_yaml", "match"),
        [
            (
                "stages:\n  b:\n    assistants: [x]\n",
                r"non-mapping assistants in workflow\.stages\.b; author the map form keyed by assistant name",
            ),
            (
                "stages:\n  b:\n    assistants: r\n",
                r"non-mapping assistants in workflow\.stages\.b; author the map form keyed by assistant name",
            ),
            (
                "stages:\n  b:\n    assistants:\n      r: 5\n",
                r"non-mapping assistant attachment in workflow\.stages\.b\.r",
            ),
            (
                "stages:\n  b:\n    assistants:\n      r: [x]\n",
                r"non-mapping assistant attachment in workflow\.stages\.b\.r",
            ),
            (
                "stages:\n  b:\n    assistants:\n      r: {}\n",
                r"when is required in workflow\.stages\.b\.assistants\.r",
            ),
            (
                "stages:\n  b:\n    assistants:\n      r:\n        gate: true\n",
                r"when is required in workflow\.stages\.b\.assistants\.r",
            ),
            (
                "stages:\n  b:\n    assistants:\n      r:\n        prompt: p\n",
                r"when is required in workflow\.stages\.b\.assistants\.r",
            ),
            (
                "stages:\n  b:\n    assistants:\n      r:\n        when: start\n        bogus: 1\n",
                r"unknown key in workflow\.stages\.b\.assistants\.r: bogus; "
                r"valid keys: prompt, skills, agent, delegate, env, gate, when",
            ),
            (
                "stages:\n  b:\n    assistants:\n      r:\n        when: later\n",
                r"when must be one of: start, checkpoints, finish, message in workflow\.stages\.b\.assistants\.r",
            ),
            (
                "stages:\n  b:\n    assistants:\n      r:\n        when: start\n        gate: x\n",
                r"non-bool value in workflow\.stages\.b\.assistants\.r\.gate",
            ),
            (
                "stages:\n  b:\n    agent: codex\nextend:\n  n:\n    assistants: {}\n    before: [b]\n",
                r"assistants is forbidden in workflow\.extend\.n",
            ),
            (
                "stages:\n"
                "  b:\n    assistants:\n      r:\n        prompt: p\n        when: start\n"
                "  c:\n    assistants:\n      r:\n        skills: [s]\n        when: start\n",
                r"duplicate assistant name: r",
            ),
            (
                'stages:\n  b:\n    assistants:\n      "bad name!":\n        when: start\n',
                r"invalid assistant name: bad name!",
            ),
            ("stages:\n  b:\n    assistants:\n      123:\n        when: start\n", r"invalid assistant name: 123"),
            (
                "stages:\n  b:\n    assistants:\n      assistant:\n        prompt: p\n        when: start\n",
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
                "stages:\n  b:\n    assistants:\n      r:\n        when: start\n        prompt: 3\n",
                "non-str value in workflow.stages.b.assistants.r.prompt",
            ),
            (
                "stages:\n  b:\n    assistants:\n      r:\n        when: start\n        skills: [1]\n",
                "non-list-of-str skills in workflow.stages.b.assistants.r",
            ),
            (
                "stages:\n  b:\n    assistants:\n      r:\n        when: start\n        prompt: p\n"
                "        delegate: 3\n",
                "non-bool value in workflow.stages.b.assistants.r.delegate",
            ),
            (
                "stages:\n  b:\n    assistants:\n      r:\n        when: start\n        prompt: p\n"
                "        env: not-a-map\n",
                "non-mapping env in workflow.stages.b.assistants.r",
            ),
            (
                "stages:\n  b:\n    assistants:\n      r:\n        when: start\n        prompt: p\n"
                "        env:\n          A: 1\n",
                "non-str value in workflow.stages.b.assistants.r.env.A",
            ),
            (
                "stages:\n  b:\n    assistants:\n      r:\n        when: 3\n",
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
