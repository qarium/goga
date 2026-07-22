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
from goga.pipeline.workflow import (
    WorkflowSyntaxError,
    parse_workflow,
)


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

    def test_parse_workflow_skills_field_accepted(self, tmp_path: Path) -> None:
        """A stages entry with a ``skills`` list builds a WorkflowStage carrying it."""
        workflow_path = _write(
            tmp_path,
            "workflow.yml",
            "stages:\n  propose:\n    agent: codex\n    skills: [web-search, goga-propose]\n",
        )

        document = parse_workflow(workflow_path)

        propose = document.stages["propose"]
        assert propose.agent == "codex"
        assert propose.skills == ["web-search", "goga-propose"]
        # skills is independent of the other fields; they stay None.
        assert propose.prompt is None
        assert propose.loop is None

    def test_parse_workflow_extend_populates_document(self, tmp_path: Path) -> None:
        """A workflow-file with an extend block parses each entry into WorkflowExtendStage."""
        workflow_path = _write(
            tmp_path,
            "workflow.yml",
            "extend:\n"
            "  warmup:\n"
            "    before: [propose]\n"
            "    title: Warmup\n"
            "    prompt: Bootstrap\n"
            "  extra:\n"
            "    after: [review]\n"
            "    title: Extra\n"
            "    skills: [goga-review]\n",
        )

        document = parse_workflow(workflow_path)

        assert set(document.extend) == {"warmup", "extra"}

        warmup = document.extend["warmup"]
        assert warmup.before == ["propose"]
        assert warmup.after is None
        assert warmup.body == {"title": "Warmup", "prompt": "Bootstrap"}

        extra = document.extend["extra"]
        assert extra.before is None
        assert extra.after == ["review"]
        assert extra.body == {"title": "Extra", "skills": ["goga-review"]}

    def test_parse_workflow_extend_inline_agent_loop_extracted(self, tmp_path: Path) -> None:
        """An extend entry's inline ``agent``/``loop`` are extracted into the model, not the body."""
        workflow_path = _write(
            tmp_path,
            "workflow.yml",
            "extend:\n"
            "  warmup:\n"
            "    before: [propose]\n"
            "    title: Warmup\n"
            "    prompt: Bootstrap\n"
            "    agent: codex\n"
            "    loop: 3\n",
        )

        document = parse_workflow(workflow_path)

        warmup = document.extend["warmup"]
        assert warmup.agent == "codex"
        assert warmup.loop == 3
        # Inline agent/loop are extracted out of the body — they must not leak
        # into it (the compiler applies them, the flow-file never sees them).
        assert warmup.body == {"title": "Warmup", "prompt": "Bootstrap"}
        assert "agent" not in warmup.body
        assert "loop" not in warmup.body

    def test_parse_workflow_extend_only_is_valid_not_empty(self, tmp_path: Path) -> None:
        """A workflow-file with only an extend block is valid (not an empty workflow)."""
        workflow_path = _write(
            tmp_path,
            "workflow.yml",
            "extend:\n  warmup:\n    before: [propose]\n    title: Warmup\n",
        )

        document = parse_workflow(workflow_path)

        assert document.prompt is None
        assert document.stages == {}
        assert set(document.extend) == {"warmup"}

    def test_parse_workflow_extend_body_passes_through_unknown_fields(self, tmp_path: Path) -> None:
        """An extend-entry body carries arbitrary stage fields verbatim; before/after are stripped."""
        workflow_path = _write(
            tmp_path,
            "workflow.yml",
            "extend:\n"
            "  extra:\n"
            "    after: [review]\n"
            "    before: [propose]\n"
            "    title: Extra\n"
            "    prompt: Run extra checks\n"
            "    skills: [goga-review]\n"
            "    agents: [codex]\n"
            "    interactive: true\n"
            "    custom:\n"
            "      deep: 1\n"
            "      nested:\n"
            "        leaf: value\n",
        )

        document = parse_workflow(workflow_path)

        extra = document.extend["extra"]
        assert extra.before == ["propose"]
        assert extra.after == ["review"]
        # before/after are removed from the body; everything else passes through.
        assert "before" not in extra.body
        assert "after" not in extra.body
        assert extra.body["title"] == "Extra"
        assert extra.body["prompt"] == "Run extra checks"
        assert extra.body["skills"] == ["goga-review"]
        assert extra.body["agents"] == ["codex"]
        assert extra.body["interactive"] is True
        assert extra.body["custom"] == {"deep": 1, "nested": {"leaf": "value"}}

    def test_parse_workflow_extend_before_empty_list_passes(self, tmp_path: Path) -> None:
        """A before: [] (empty list) satisfies list[str]; semantics are deferred to the compiler."""
        workflow_path = _write(
            tmp_path,
            "workflow.yml",
            "extend:\n  warmup:\n    before: []\n    after: [propose]\n    title: Warmup\n",
        )

        document = parse_workflow(workflow_path)

        warmup = document.extend["warmup"]
        assert warmup.before == []
        assert warmup.after == ["propose"]


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
        # Strengthened: the exact valid-keys list now includes ``extend``; the
        # substring ``prompt, stages`` alone would pass even without ``extend``,
        # so assert the full trailing fragment.
        assert "valid keys: prompt, stages, extend" in message

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
        # The full valid-keys list now includes ``skills``; the substring
        # ``agent, prompt, loop`` alone would pass even without ``skills``, so
        # assert the full trailing fragment.
        assert "valid keys: agent, prompt, loop, skills" in message

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

    def test_parse_workflow_skills_non_list_of_str_rejected(self, tmp_path: Path) -> None:
        """A non-list[str] skills raises WorkflowSyntaxError('non-list-of-str skills ...')."""
        workflow_path = _write(tmp_path, "workflow.yml", "stages:\n  x:\n    skills: web-search\n")

        with pytest.raises(WorkflowSyntaxError, match=r"non-list-of-str skills in workflow\.stages\.x"):
            parse_workflow(workflow_path)

    def test_parse_workflow_rejects_empty_workflow(self, tmp_path: Path) -> None:
        """A workflow with empty stages and no prompt raises WorkflowSyntaxError('empty workflow')."""
        workflow_path = _write(tmp_path, "workflow.yml", "stages: {}\n")

        with pytest.raises(WorkflowSyntaxError, match="empty workflow"):
            parse_workflow(workflow_path)

    def test_parse_workflow_rejects_non_mapping_extend_block(self, tmp_path: Path) -> None:
        """A non-mapping extend block raises WorkflowSyntaxError('non-mapping extend block')."""
        workflow_path = _write(tmp_path, "workflow.yml", "extend: not-a-mapping\n")

        with pytest.raises(WorkflowSyntaxError, match="non-mapping extend block in workflow"):
            parse_workflow(workflow_path)

    def test_parse_workflow_rejects_non_mapping_extend_entry(self, tmp_path: Path) -> None:
        """A non-mapping extend entry value raises WorkflowSyntaxError naming the entry."""
        workflow_path = _write(tmp_path, "workflow.yml", "extend:\n  x: codex\n")

        with pytest.raises(WorkflowSyntaxError, match=r"non-mapping extend entry x in workflow\.extend"):
            parse_workflow(workflow_path)

    def test_parse_workflow_rejects_extend_depends_on_forbidden(self, tmp_path: Path) -> None:
        """A depends_on key inside an extend entry raises WorkflowSyntaxError naming the entry."""
        workflow_path = _write(
            tmp_path,
            "workflow.yml",
            "extend:\n  x:\n    after: [review]\n    depends_on: [propose]\n",
        )

        with pytest.raises(WorkflowSyntaxError, match=r"depends_on is forbidden in workflow\.extend\.x"):
            parse_workflow(workflow_path)

    @pytest.mark.parametrize(
        "before_yaml",
        ["codex", "[1, 2]", "[true]"],
        ids=["scalar", "list-of-int", "list-of-bool"],
    )
    def test_parse_workflow_rejects_extend_before_non_list_of_str(self, tmp_path: Path, before_yaml: str) -> None:
        """A non-list[str] before raises WorkflowSyntaxError('non-list-of-str before ...')."""
        workflow_path = _write(
            tmp_path,
            "workflow.yml",
            f"extend:\n  x:\n    before: {before_yaml}\n    title: X\n",
        )

        with pytest.raises(WorkflowSyntaxError, match=r"non-list-of-str before in workflow\.extend\.x"):
            parse_workflow(workflow_path)

    @pytest.mark.parametrize(
        "after_yaml",
        ["codex", "[1, 2]", "[true]"],
        ids=["scalar", "list-of-int", "list-of-bool"],
    )
    def test_parse_workflow_rejects_extend_after_non_list_of_str(self, tmp_path: Path, after_yaml: str) -> None:
        """A non-list[str] after raises WorkflowSyntaxError('non-list-of-str after ...')."""
        workflow_path = _write(
            tmp_path,
            "workflow.yml",
            f"extend:\n  x:\n    after: {after_yaml}\n    title: X\n",
        )

        with pytest.raises(WorkflowSyntaxError, match=r"non-list-of-str after in workflow\.extend\.x"):
            parse_workflow(workflow_path)

    def test_parse_workflow_rejects_extend_neither_before_nor_after(self, tmp_path: Path) -> None:
        """An extend entry with neither before nor after raises WorkflowSyntaxError."""
        workflow_path = _write(
            tmp_path,
            "workflow.yml",
            "extend:\n  x:\n    title: Just a body\n",
        )

        with pytest.raises(WorkflowSyntaxError, match=r"extend entry x requires at least one of before/after"):
            parse_workflow(workflow_path)

    def test_parse_workflow_extend_inline_agent_non_str_rejected(self, tmp_path: Path) -> None:
        """A non-str inline extend agent raises WorkflowSyntaxError naming the entry and field."""
        workflow_path = _write(
            tmp_path,
            "workflow.yml",
            "extend:\n  warmup:\n    before: [propose]\n    agent: 5\n",
        )

        with pytest.raises(WorkflowSyntaxError, match=r"non-str value in workflow\.extend\.warmup\.agent"):
            parse_workflow(workflow_path)

    @pytest.mark.parametrize(
        ("loop_yaml", "expected"),
        [
            ("0", r"loop must be >= 1 in workflow\.extend\.warmup"),
            ("true", r"non-int value in workflow\.extend\.warmup\.loop"),
        ],
        ids=["below-one", "bool"],
    )
    def test_parse_workflow_extend_inline_loop_invalid_rejected(
        self,
        tmp_path: Path,
        loop_yaml: str,
        expected: str,
    ) -> None:
        """An invalid inline extend loop (< 1 or bool) raises WorkflowSyntaxError."""
        workflow_path = _write(
            tmp_path,
            "workflow.yml",
            f"extend:\n  warmup:\n    before: [propose]\n    loop: {loop_yaml}\n",
        )

        with pytest.raises(WorkflowSyntaxError, match=expected):
            parse_workflow(workflow_path)

    @pytest.mark.parametrize(
        ("field", "expected"),
        [
            ("agent", r"non-str value in workflow\.extend\.warmup\.agent"),
            ("loop", r"non-int value in workflow\.extend\.warmup\.loop"),
        ],
        ids=["agent-null", "loop-null"],
    )
    def test_parse_workflow_extend_inline_null_rejected(self, tmp_path: Path, field: str, expected: str) -> None:
        """An explicit ``null`` inline extend agent/loop is a structural type error, not absence.

        Symmetric with the per-stage agent/loop and the extend loop: presence of
        the key forces a type check (no ``is not None`` guard), so ``null`` is
        rejected. Absence is expressed by omitting the key.
        """
        workflow_path = _write(
            tmp_path,
            "workflow.yml",
            f"extend:\n  warmup:\n    before: [propose]\n    {field}: ~\n",
        )

        with pytest.raises(WorkflowSyntaxError, match=expected):
            parse_workflow(workflow_path)

    @pytest.mark.parametrize(
        ("field_yaml", "expected"),
        [
            ("agent: 5", r"non-str value in workflow\.extend\.warmup\.agent"),
            ("loop: 0", r"loop must be >= 1 in workflow\.extend\.warmup"),
            ("loop: true", r"non-int value in workflow\.extend\.warmup\.loop"),
        ],
        ids=["bad-agent", "below-one-loop", "bool-loop"],
    )
    def test_parse_workflow_extend_multi_defect_surfaces_type_error_first(
        self,
        tmp_path: Path,
        field_yaml: str,
        expected: str,
    ) -> None:
        """A multi-defect entry surfaces the type error, not the positional one.

        An extend entry with NEITHER ``before`` nor ``after`` AND a bad inline
        ``agent``/``loop`` carries two structural defects. The CODEMANIFEST
        algorithm (step 6b) validates ``agent``/``loop`` (e/f) BEFORE the
        at-least-one-of-before/after check (g), so the more specific type error
        must win over ``extend entry NAME requires at least one of before/after``.
        """
        workflow_path = _write(
            tmp_path,
            "workflow.yml",
            f"extend:\n  warmup:\n    title: Just a body\n    {field_yaml}\n",
        )

        with pytest.raises(WorkflowSyntaxError, match=expected):
            parse_workflow(workflow_path)

    def test_parse_workflow_rejects_empty_workflow_with_empty_extend(self, tmp_path: Path) -> None:
        """A workflow with empty extend map, empty stages, and no prompt is still empty."""
        workflow_path = _write(tmp_path, "workflow.yml", "extend: {}\n")

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
