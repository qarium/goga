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

    def test_parse_workflow_skip_true_carried_through(self, tmp_path: Path) -> None:
        """``skip: true`` on a stage flows through to the WorkflowStage.skip field."""
        workflow_path = _write(tmp_path, "workflow.yml", "stages:\n  propose:\n    skip: true\n")

        document = parse_workflow(workflow_path)

        propose = document.stages["propose"]
        assert propose.skip is True
        # skip is independent of the other fields; they stay None.
        assert propose.agent is None

    def test_parse_workflow_skip_false_and_absent_equivalent(self, tmp_path: Path) -> None:
        """``skip: false`` and an omitted ``skip`` are equivalent (both yield False)."""
        workflow_path = _write(
            tmp_path,
            "workflow.yml",
            "stages:\n  a:\n    skip: false\n  b: {}\n",
        )

        document = parse_workflow(workflow_path)

        assert document.stages["a"].skip is False
        assert document.stages["b"].skip is False

    def test_skip_in_stage_with_other_fields(self, tmp_path: Path) -> None:
        """``skip`` coexists with ``agent`` and ``skills`` in one stage entry."""
        workflow_path = _write(
            tmp_path,
            "workflow.yml",
            "stages:\n  propose:\n    agent: codex\n    skills: [web-search]\n    skip: true\n",
        )

        document = parse_workflow(workflow_path)

        propose = document.stages["propose"]
        assert propose.skip is True
        assert propose.agent == "codex"
        assert propose.skills == ["web-search"]

    def test_parse_workflow_approve_auto_stages(self, tmp_path: Path) -> None:
        """``approve: auto`` on a stages entry flows through to WorkflowStage.approve."""
        workflow_path = _write(
            tmp_path,
            "workflow.yml",
            "stages:\n  deploy:\n    approve: auto\n",
        )

        document = parse_workflow(workflow_path)

        deploy = document.stages["deploy"]
        assert deploy.approve == "auto"
        # approve is independent of the other fields; they stay None.
        assert deploy.agent is None
        assert deploy.loop is None
        assert deploy.skip is False

    def test_parse_workflow_approve_plan_stages(self, tmp_path: Path) -> None:
        """``approve: plan`` on a stages entry flows through to WorkflowStage.approve."""
        workflow_path = _write(
            tmp_path,
            "workflow.yml",
            "stages:\n  deploy:\n    approve: plan\n",
        )

        document = parse_workflow(workflow_path)

        deploy = document.stages["deploy"]
        assert deploy.approve == "plan"
        assert deploy.agent is None
        assert deploy.skip is False

    def test_parse_workflow_approve_dialog_stages(self, tmp_path: Path) -> None:
        """``approve: dialog`` on a stages entry flows through to WorkflowStage.approve."""
        workflow_path = _write(
            tmp_path,
            "workflow.yml",
            "stages:\n  deploy:\n    approve: dialog\n",
        )

        document = parse_workflow(workflow_path)

        deploy = document.stages["deploy"]
        assert deploy.approve == "dialog"
        assert deploy.agent is None
        assert deploy.skip is False

    def test_parse_workflow_approve_auto_stages_coexists_with_other_fields(self, tmp_path: Path) -> None:
        """``approve`` coexists with ``agent``/``loop``/``skills``/``skip`` in one entry."""
        workflow_path = _write(
            tmp_path,
            "workflow.yml",
            "stages:\n"
            "  deploy:\n"
            "    agent: codex\n"
            "    loop: 2\n"
            "    skills: [goga-deploy]\n"
            "    skip: false\n"
            "    approve: auto\n",
        )

        document = parse_workflow(workflow_path)

        deploy = document.stages["deploy"]
        assert deploy.approve == "auto"
        assert deploy.agent == "codex"
        assert deploy.loop == 2
        assert deploy.skills == ["goga-deploy"]
        assert deploy.skip is False

    def test_parse_workflow_manual_true_stages(self, tmp_path: Path) -> None:
        """``manual: true`` on a stages entry builds WorkflowStage(manual=True).

        Trace: parse_workflow → _extract_top_level → _build_stages →
        _build_stage("deploy", {"manual": True}) → _validate_stage_field (the
        manual branch: bool ok, returns True) → WorkflowStage(manual=True).
        manual is independent of the other fields — they keep their defaults
        (agent None, skip False).
        """
        workflow_path = _write(tmp_path, "workflow.yml", "stages:\n  deploy:\n    manual: true\n")

        document = parse_workflow(workflow_path)

        deploy = document.stages["deploy"]
        assert deploy.manual is True
        # manual is independent of the other fields; they stay at their defaults.
        assert deploy.agent is None
        assert deploy.skip is False

    def test_parse_workflow_manual_false_stages(self, tmp_path: Path) -> None:
        """``manual: false`` on a stages entry builds WorkflowStage(manual=False).

        An explicit ``manual: false`` is the cancel instruction — it must build
        exactly ``False``, NOT ``None`` (losing the False → None distinction
        would silently drop the cancel semantics for the compiler).
        """
        workflow_path = _write(tmp_path, "workflow.yml", "stages:\n  deploy:\n    manual: false\n")

        document = parse_workflow(workflow_path)

        assert document.stages["deploy"].manual is False

    def test_parse_workflow_manual_absent_yields_none(self, tmp_path: Path) -> None:
        """An absent ``manual`` key yields None (NOT False) — three distinguishable states.

        Anchors the tri-state contract (6.1.10): absence is ``None``, so an
        absent key and an explicit ``manual: false`` remain DIFFERENT
        instructions.
        """
        workflow_path = _write(tmp_path, "workflow.yml", "stages:\n  deploy:\n    agent: codex\n")

        document = parse_workflow(workflow_path)

        assert document.stages["deploy"].manual is None

    def test_parse_workflow_manual_coexists_with_other_fields(self, tmp_path: Path) -> None:
        """``manual`` coexists with ``agent``/``loop``/``skills``/``approve`` in one entry."""
        workflow_path = _write(
            tmp_path,
            "workflow.yml",
            "stages:\n"
            "  deploy:\n"
            "    agent: codex\n"
            "    loop: 2\n"
            "    skills: [web-search]\n"
            "    approve: auto\n"
            "    manual: true\n",
        )

        document = parse_workflow(workflow_path)

        deploy = document.stages["deploy"]
        assert deploy.manual is True
        assert deploy.approve == "auto"
        assert deploy.loop == 2

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

    def test_parse_workflow_approve_auto_extend_extracted(self, tmp_path: Path) -> None:
        """An extend entry's inline ``approve`` is extracted into the model, not the body."""
        workflow_path = _write(
            tmp_path,
            "workflow.yml",
            "extend:\n  extra:\n    after: [deploy]\n    approve: auto\n    prompt: do extra\n",
        )

        document = parse_workflow(workflow_path)

        extra = document.extend["extra"]
        assert extra.approve == "auto"
        # Inline approve is extracted out of the body — it must not leak into it
        # (the compiler applies it, the flow-file never sees it as a body key).
        assert extra.body == {"prompt": "do extra"}
        assert "approve" not in extra.body

    def test_parse_workflow_approve_plan_extend_extracted(self, tmp_path: Path) -> None:
        """An extend entry's inline ``approve: plan`` is extracted into the model, not the body."""
        workflow_path = _write(
            tmp_path,
            "workflow.yml",
            "extend:\n  extra:\n    after: [deploy]\n    approve: plan\n    prompt: do extra\n",
        )

        document = parse_workflow(workflow_path)

        extra = document.extend["extra"]
        assert extra.approve == "plan"
        assert extra.body == {"prompt": "do extra"}
        assert "approve" not in extra.body

    def test_parse_workflow_approve_dialog_extend_extracted(self, tmp_path: Path) -> None:
        """An extend entry's inline ``approve: dialog`` is extracted into the model, not the body."""
        workflow_path = _write(
            tmp_path,
            "workflow.yml",
            "extend:\n  extra:\n    after: [deploy]\n    approve: dialog\n    prompt: do extra\n",
        )

        document = parse_workflow(workflow_path)

        extra = document.extend["extra"]
        assert extra.approve == "dialog"
        assert extra.body == {"prompt": "do extra"}
        assert "approve" not in extra.body

    def test_parse_workflow_approve_auto_extend_alongside_agent_loop(self, tmp_path: Path) -> None:
        """An extend entry carries inline ``agent``/``loop``/``approve`` together."""
        workflow_path = _write(
            tmp_path,
            "workflow.yml",
            "extend:\n"
            "  extra:\n"
            "    before: [propose]\n"
            "    agent: codex\n"
            "    loop: 3\n"
            "    approve: auto\n"
            "    title: Extra\n",
        )

        document = parse_workflow(workflow_path)

        extra = document.extend["extra"]
        assert extra.agent == "codex"
        assert extra.loop == 3
        assert extra.approve == "auto"
        assert extra.body == {"title": "Extra"}
        assert "agent" not in extra.body
        assert "loop" not in extra.body
        assert "approve" not in extra.body

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

    def test_parse_workflow_trigger_in_extend_body_passes_verbatim(self, tmp_path: Path) -> None:
        """A ``trigger`` key in an extend-entry body passes through to ``body`` verbatim.

        Trace: _build_extend_stage: trigger is neither a validated positioning
        key nor an excluded/forbidden key, so it lands in
        ``body = {key: value for key not in _EXTEND_BODY_EXCLUDED}``. The
        workflow cell does not know the stage field schema — ``trigger`` is a
        full stage-body field whose value the compiler validates at compile
        time, not here.
        """
        workflow_path = _write(
            tmp_path,
            "workflow.yml",
            "extend:\n  extra:\n    after: [deploy]\n    trigger: manual\n    prompt: do extra\n",
        )

        document = parse_workflow(workflow_path)

        extra = document.extend["extra"]
        assert "trigger" in extra.body
        assert extra.body["trigger"] == "manual"
        assert extra.body["prompt"] == "do extra"

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
            "    communication: true\n"
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
        assert extra.body["communication"] is True
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
        # The full valid-keys list now includes ``skip`` (5th), ``approve``
        # (6th), and ``manual`` (7th); the substring ``agent, prompt, loop,
        # skills`` alone would pass even without them, so assert the full
        # trailing fragment.
        assert "valid keys: agent, prompt, loop, skills, skip, approve, manual" in message

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

    @pytest.mark.parametrize(
        "skip_yaml",
        ['"yes"', "1"],
        ids=["str", "int"],
    )
    def test_parse_workflow_rejects_non_bool_skip(self, tmp_path: Path, skip_yaml: str) -> None:
        """A non-bool skip raises WorkflowSyntaxError('non-bool value ... skip').

        A quoted ``"yes"`` is a ``str`` (note: the unquoted ``yes`` would parse
        as a YAML bool, so it must be quoted to exercise the non-bool path); an
        int ``1`` is also rejected because ``isinstance(1, bool)`` is ``False``.
        """
        workflow_path = _write(
            tmp_path,
            "workflow.yml",
            f"stages:\n  x:\n    skip: {skip_yaml}\n",
        )

        with pytest.raises(WorkflowSyntaxError, match=r"non-bool value in workflow\.stages\.x\.skip"):
            parse_workflow(workflow_path)

    def test_skip_explicit_null_rejected(self, tmp_path: Path) -> None:
        """An explicit ``null`` skip is a non-bool, rejected as a structural type error.

        Symmetric with the per-stage agent/prompt and the extend agent/loop:
        presence of the key forces a type check, so ``null`` is rejected.
        Absence is expressed by omitting the key (``skip`` then defaults to
        ``False``).
        """
        workflow_path = _write(tmp_path, "workflow.yml", "stages:\n  x:\n    skip: ~\n")

        with pytest.raises(WorkflowSyntaxError, match=r"non-bool value in workflow\.stages\.x\.skip"):
            parse_workflow(workflow_path)

    def test_parse_workflow_rejects_skip_in_extend(self, tmp_path: Path) -> None:
        """A skip key inside an extend entry raises WorkflowSyntaxError naming the entry."""
        workflow_path = _write(
            tmp_path,
            "workflow.yml",
            "extend:\n  x:\n    after: [review]\n    skip: true\n",
        )

        with pytest.raises(WorkflowSyntaxError, match=r"skip is forbidden in workflow\.extend\.x"):
            parse_workflow(workflow_path)

    @pytest.mark.parametrize(
        "manual_yaml",
        ['"yes"', "1", "~"],
        ids=["str", "int", "explicit-null"],
    )
    def test_parse_workflow_rejects_non_bool_manual(self, tmp_path: Path, manual_yaml: str) -> None:
        """A non-bool ``manual`` raises WorkflowSyntaxError('non-bool value ... manual').

        Trace: ``isinstance("yes", bool)`` is False → the manual branch in
        ``_validate_stage_field`` raises. The strict bool check (contract
        6.1.9) cuts off int/str values that YAML could otherwise coerce; an
        unquoted ``yes`` would parse as a bool, so it is quoted to exercise the
        non-bool path. An explicit ``null`` is likewise a non-bool structural
        type error — symmetric with ``skip: ~``: presence of the key forces the
        type check, and an absent-vs-null distinction must NOT collapse the
        tri-state (``None`` means "no instruction", the compiler's no-op).
        """
        workflow_path = _write(
            tmp_path,
            "workflow.yml",
            f"stages:\n  deploy:\n    manual: {manual_yaml}\n",
        )

        with pytest.raises(WorkflowSyntaxError, match=r"non-bool value in workflow\.stages\.deploy\.manual"):
            parse_workflow(workflow_path)

    def test_parse_workflow_manual_forbidden_in_extend(self, tmp_path: Path) -> None:
        """A ``manual`` key inside an extend entry raises WorkflowSyntaxError naming the entry.

        The launch mode of a NEW stage is authored in its body via ``trigger``,
        not via a workflow instruction. The check sits at contract position
        6.2.4 — right after the skip check (6.2.3) and BEFORE the
        before/after checks (6.2.5-6.2.6) — so the more specific manual error
        is primary over the positional one. The entry deliberately carries NO
        ``before``/``after``: both defects (the forbidden key and the missing
        positioning) are present, so only the documented ordering surfaces the
        ``manual`` error rather than the at-least-one positional error (6.2.10).
        """
        workflow_path = _write(
            tmp_path,
            "workflow.yml",
            "extend:\n  extra:\n    manual: true\n",
        )

        with pytest.raises(WorkflowSyntaxError, match=r"manual is forbidden in workflow\.extend\.extra"):
            parse_workflow(workflow_path)

    def test_parse_workflow_trigger_in_stages_is_unknown_key(self, tmp_path: Path) -> None:
        """A ``trigger`` key in the stages block is an unknown-key structural error.

        ``trigger`` is a full stage-body field, not a workflow modifier: in the
        ``stages`` block it lands in the unknown-key branch of
        ``_validate_stage_field`` (its extend-body counterpart passes through
        verbatim instead). The valid-keys fragment comes from ``_STAGE_KEYS``,
        so it must now include ``manual`` — pinning the tuple itself, not just
        a prefix of the message.
        """
        workflow_path = _write(tmp_path, "workflow.yml", "stages:\n  deploy:\n    trigger: manual\n")

        with pytest.raises(WorkflowSyntaxError, match=r"unknown key in workflow\.stages\.deploy: trigger"):
            parse_workflow(workflow_path)

    def test_parse_workflow_trigger_unknown_key_message_lists_manual(self, tmp_path: Path) -> None:
        """The unknown-key message for ``trigger`` lists the full valid-keys fragment with ``manual``."""
        workflow_path = _write(tmp_path, "workflow.yml", "stages:\n  deploy:\n    trigger: manual\n")

        with pytest.raises(WorkflowSyntaxError) as exc_info:
            parse_workflow(workflow_path)

        message = str(exc_info.value)
        assert "unknown key in workflow.stages.deploy: trigger" in message
        assert "valid keys: agent, prompt, loop, skills, skip, approve, manual" in message

    def test_parse_workflow_approve_non_auto_rejected(self, tmp_path: Path) -> None:
        """An ``approve`` value outside the accepted set is rejected (stages entry).

        ``"manual"`` parses as a str (passes the type check) but is not one of
        ``auto``/``plan``/``dialog``, surfacing the ``approve must be one of:
        auto, plan, dialog`` message naming the stage.
        """
        workflow_path = _write(
            tmp_path,
            "workflow.yml",
            "stages:\n  deploy:\n    approve: manual\n",
        )

        with pytest.raises(
            WorkflowSyntaxError, match=r"approve must be one of: auto, plan, dialog in workflow\.stages\.deploy"
        ):
            parse_workflow(workflow_path)

    def test_parse_workflow_approve_non_auto_rejected_extend(self, tmp_path: Path) -> None:
        """An extend inline ``approve`` outside the accepted set is rejected."""
        workflow_path = _write(
            tmp_path,
            "workflow.yml",
            "extend:\n  x:\n    after: [deploy]\n    approve: manual\n",
        )

        with pytest.raises(
            WorkflowSyntaxError, match=r"approve must be one of: auto, plan, dialog in workflow\.extend\.x"
        ):
            parse_workflow(workflow_path)

    def test_parse_workflow_approve_non_str_rejected(self, tmp_path: Path) -> None:
        """A non-str ``approve`` (int) is rejected as a structural type error (stages entry)."""
        workflow_path = _write(
            tmp_path,
            "workflow.yml",
            "stages:\n  deploy:\n    approve: 5\n",
        )

        with pytest.raises(WorkflowSyntaxError, match=r"non-str value in workflow\.stages\.deploy\.approve"):
            parse_workflow(workflow_path)

    def test_parse_workflow_approve_null_rejected_extend(self, tmp_path: Path) -> None:
        """An explicit ``null`` extend ``approve`` is a non-str, rejected (symmetric with inline agent).

        Presence of the key forces a type check (no ``is not None`` guard), so an
        explicit ``null`` is rejected rather than treated as absence. Absence is
        expressed by omitting the key.
        """
        workflow_path = _write(
            tmp_path,
            "workflow.yml",
            "extend:\n  x:\n    after: [deploy]\n    approve: ~\n",
        )

        with pytest.raises(WorkflowSyntaxError, match=r"non-str value in workflow\.extend\.x\.approve"):
            parse_workflow(workflow_path)

    def test_parse_workflow_approve_null_rejected_stages(self, tmp_path: Path) -> None:
        """An explicit ``null`` stages ``approve`` is a non-str, rejected."""
        workflow_path = _write(
            tmp_path,
            "workflow.yml",
            "stages:\n  deploy:\n    approve: ~\n",
        )

        with pytest.raises(WorkflowSyntaxError, match=r"non-str value in workflow\.stages\.deploy\.approve"):
            parse_workflow(workflow_path)

    def test_parse_workflow_approve_in_extend_unknown_position(self, tmp_path: Path) -> None:
        """An extend entry with ``approve`` but no before/after surfaces the at-least-one error.

        The at-least-one-of-before/after check stays the LAST structural check
        (contract step 6.2.9): a valid inline ``approve: auto`` passes its check,
        so the positional ``requires at least one of before/after`` error wins.
        """
        workflow_path = _write(
            tmp_path,
            "workflow.yml",
            "extend:\n  x:\n    approve: auto\n",
        )

        with pytest.raises(WorkflowSyntaxError, match=r"extend entry x requires at least one of before/after"):
            parse_workflow(workflow_path)

    def test_parse_workflow_approve_extend_multi_defect_surfaces_approve_error_first(self, tmp_path: Path) -> None:
        """A multi-defect entry surfaces the approve type error, not the positional one.

        An extend entry with NEITHER ``before``/``after`` AND a bad inline
        ``approve`` carries two structural defects; the ``approve`` check runs
        before the at-least-one check, so the more specific type error wins.
        """
        workflow_path = _write(
            tmp_path,
            "workflow.yml",
            "extend:\n  x:\n    title: Just a body\n    approve: manual\n",
        )

        with pytest.raises(
            WorkflowSyntaxError, match=r"approve must be one of: auto, plan, dialog in workflow\.extend\.x"
        ):
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
        algorithm (step 6.2) validates ``agent``/``loop`` (6.2.6/6.2.7) BEFORE the
        at-least-one-of-before/after check (6.2.9), so the more specific type error
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
