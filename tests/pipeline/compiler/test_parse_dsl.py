"""Contract and logic tests for the ``parse_dsl`` pure parser and ``StructuralError``.

Covers the parser half of the compiler cell: structural validation of a goga DSL
pipeline-file (header segment + body segment split on a literal ``---`` line) and
the typed 3-tuple it returns. Content of step fields is passed through verbatim;
``depends_on`` references are not resolved. A stage body's ``assistants`` map is
extracted into the steps' typed field (step 4a) with its vocabulary enforced at
parse time — the verbatim body excludes the key.
"""

from __future__ import annotations

import dataclasses
import inspect
import re
from pathlib import Path

import pytest
from goga.pipeline.compiler import (
    BodyFormat,
    PhasesBody,
    PipelineAssistant,
    PipelineHeader,
    PipelineRoles,
    StagesBody,
    StructuralError,
    parse_dsl,
)

_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "parse_dsl"
_FEATURE_PHASES = _FIXTURES / "phases.yml"
_FEATURE_STAGES = _FIXTURES / "stages.yml"


class TestParseDslContract:
    """Contract tests — the public API declared by the compiler-cell CODEMANIFEST."""

    def test_parse_dsl_and_structural_error_importable_from_facade(self) -> None:
        """``parse_dsl`` and ``StructuralError`` must be importable from the facade."""
        assert parse_dsl is not None
        assert StructuralError is not None

    def test_structural_error_is_value_error_subclass(self) -> None:
        """``StructuralError`` subclasses ``ValueError`` so callers can catch it broadly."""
        assert issubclass(StructuralError, ValueError)

    def test_parse_dsl_signature(self) -> None:
        """``parse_dsl`` takes exactly one parameter named ``text``."""
        parameters = list(inspect.signature(parse_dsl).parameters)

        assert parameters == ["text"]

    def test_parse_dsl_returns_three_tuple_on_minimal_phases(self) -> None:
        """A minimal valid phases text yields (PipelineHeader, PHASES, PhasesBody)."""
        text = "name: X\ndescription: Y\n---\n\n- name: a\n  title: A\n"

        header, fmt, body = parse_dsl(text)

        assert isinstance(header, PipelineHeader)
        assert fmt is BodyFormat.PHASES
        assert isinstance(body, PhasesBody)

    def test_parse_dsl_returns_stages_on_minimal_stages(self) -> None:
        """A minimal valid stages text yields (PipelineHeader, STAGES, StagesBody)."""
        text = "name: X\ndescription: Y\n---\n\na:\n  title: A\n"

        header, fmt, body = parse_dsl(text)

        assert isinstance(header, PipelineHeader)
        assert fmt is BodyFormat.STAGES
        assert isinstance(body, StagesBody)

    def test_parse_dsl_steps_carry_assistants_field_both_formats(self) -> None:
        """Both body formats produce steps with the declared trailing ``assistants`` field.

        The field is annotated ``dict[str, PipelineAssistant] | None`` and
        defaults to ``None``; a step whose source body carries no
        ``assistants`` key parses with ``assistants is None`` (absence).
        """
        phases_text = "name: X\ndescription: Y\n---\n\n- name: a\n  title: A\n"
        stages_text = "name: X\ndescription: Y\n---\n\na:\n  title: A\n"

        _header, _fmt, phases_body = parse_dsl(phases_text)
        _header, _fmt, stages_body = parse_dsl(stages_text)

        for step in (*phases_body.steps, *stages_body.steps):
            field = next(field for field in dataclasses.fields(step) if field.name == "assistants")

            assert field.type == "dict[str, PipelineAssistant] | None"
            assert field.default is None
            assert step.assistants is None


class TestParseDslLogic:
    """Behavioral tests against the real fixtures and the documented edge cases."""

    def test_parse_dsl_phases_basic(self) -> None:
        """The canonical phases fixture parses to 3 steps with bodies excluding name/title."""
        text = _FEATURE_PHASES.read_text()

        header, fmt, body = parse_dsl(text)

        assert header.name == "Goga feature"
        assert header.description == "Feature implementation"
        assert fmt is BodyFormat.PHASES
        assert isinstance(body, PhasesBody)

        assert len(body.steps) == 3

        first = body.steps[0]
        assert first.name == "propose"
        assert first.title == "Propose"

        # name/title are separate fields; everything else is verbatim body.
        assert "name" not in first.body
        assert "title" not in first.body
        assert first.body["communication"] is True
        assert first.body["agents"] == ["planning", "implementation"]
        assert "prompt" in first.body

    def test_parse_dsl_stages_basic(self) -> None:
        """The canonical stages fixture parses to 3 steps with pass-through depends_on."""
        text = _FEATURE_STAGES.read_text()

        header, fmt, body = parse_dsl(text)

        assert header.name == "Goga feature"
        assert fmt is BodyFormat.STAGES
        assert isinstance(body, StagesBody)

        assert len(body.steps) == 3

        # First stage has no authored depends_on.
        assert body.steps[0].name == "propose"
        assert body.steps[0].depends_on is None

        # Second stage depends on the first; the map key becomes the step name.
        assert body.steps[1].name == "propose-review"
        assert body.steps[1].depends_on == ["propose"]

    def test_parse_dsl_missing_separator_raises(self) -> None:
        """An already-afm-format file (no ``---`` line) is rejected."""
        text = "name: X\ndescription: Y\n\nstages:\n  - id: a\n"

        with pytest.raises(StructuralError, match="missing body separator"):
            parse_dsl(text)

    def test_parse_dsl_header_missing_name_raises(self) -> None:
        """A header lacking a string name is rejected before the body is inspected."""
        text = "description: Y\n---\n\n- name: a\n  title: A\n"

        with pytest.raises(StructuralError, match="header missing name"):
            parse_dsl(text)

    def test_parse_dsl_unsupported_body_format_raises(self) -> None:
        """A scalar body segment is neither list nor mapping and is rejected."""
        text = "name: X\ndescription: Y\n---\n\njust a scalar\n"

        with pytest.raises(StructuralError, match="unsupported body format"):
            parse_dsl(text)

    def test_parse_dsl_stages_depends_on_null_vs_empty(self) -> None:
        """depends_on distinguishes null (None), explicit empty ([]), and absent (None)."""
        text = (
            "name: T\n"
            "description: T\n"
            "---\n"
            "\n"
            "a:\n"
            "  title: A\n"
            "  depends_on:\n"
            "b:\n"
            "  title: B\n"
            "  depends_on: []\n"
            "c:\n"
            "  title: C\n"
        )

        _header, fmt, body = parse_dsl(text)

        assert fmt is BodyFormat.STAGES

        assert body.steps[0].depends_on is None
        assert body.steps[1].depends_on == []
        assert body.steps[2].depends_on is None

    def test_parse_dsl_stages_depends_on_string_rejected(self) -> None:
        """A non-list, non-None depends_on (a bare string) is a structural type error."""
        text = "name: T\ndescription: T\n---\n\na:\n  title: A\n  depends_on: b\n"

        with pytest.raises(StructuralError, match="depends_on must be a list"):
            parse_dsl(text)

    def test_parse_dsl_stages_depends_on_non_string_element_rejected(self) -> None:
        """A depends_on list with a non-string element is a structural type error."""
        text = "name: T\ndescription: T\n---\n\na:\n  title: A\n  depends_on: [1, 2]\n"

        with pytest.raises(StructuralError, match="depends_on must contain only strings"):
            parse_dsl(text)

    def test_parse_dsl_phase_item_missing_title_raises(self) -> None:
        """A phases list item without a string title is rejected."""
        text = "name: X\ndescription: Y\n---\n\n- name: a\n  interactive: true\n"

        with pytest.raises(StructuralError, match="phase item missing name/title"):
            parse_dsl(text)

    def test_parse_dsl_stage_value_must_be_mapping_raises(self) -> None:
        """A stages body whose value is not a mapping is rejected."""
        text = "name: X\ndescription: Y\n---\n\na: just a scalar\n"

        with pytest.raises(StructuralError, match="stage value must be a mapping"):
            parse_dsl(text)

    def test_parse_dsl_header_not_a_mapping_raises(self) -> None:
        """A header segment that YAML-parses to a non-mapping (e.g. a scalar) is rejected."""
        text = "42\n---\n\n- name: a\n  title: A\n"

        with pytest.raises(StructuralError, match="header missing name/description"):
            parse_dsl(text)

    def test_parse_dsl_phase_item_not_a_mapping_raises(self) -> None:
        """A phases list element that is not a mapping (e.g. a scalar) is rejected."""
        text = "name: X\ndescription: Y\n---\n\n- just a scalar\n"

        with pytest.raises(StructuralError, match="phase item must be a mapping"):
            parse_dsl(text)

    def test_parse_dsl_stage_value_missing_title_raises(self) -> None:
        """A stages value mapping without a string title is rejected."""
        text = "name: X\ndescription: Y\n---\n\na:\n  agents: [planning]\n"

        with pytest.raises(StructuralError, match="stage value missing title"):
            parse_dsl(text)

    def test_parse_dsl_deep_copies_body_dicts(self) -> None:
        """``_deep_copy_without`` drops excluded keys and deep-copies the rest.

        The parser deep-copies each step body so a caller mutating the returned
        objects cannot alias the source mapping. Verified directly on the helper
        because the source mapping is local to ``parse_dsl`` and discarded before
        it returns, so the isolation is not observable through the public return
        value alone.
        """
        from goga.pipeline.compiler.parse_dsl import _deep_copy_without

        source = {"name": "a", "title": "A", "agents": ["planning"], "nested": {"k": 1}}

        copied = _deep_copy_without(source, excluded={"name", "title"})

        # Excluded keys (carried as separate fields) are dropped from the body.
        assert "name" not in copied
        assert "title" not in copied
        assert copied["agents"] == ["planning"]
        assert copied["nested"] == {"k": 1}

        # Mutating the returned body — including nested structures — must not reach
        # back into the source mapping (genuine deep-copy isolation).
        copied["agents"].append("hacked")
        copied["nested"]["extra"] = True

        assert source["agents"] == ["planning"]
        assert source["nested"] == {"k": 1}

    def test_parse_dsl_empty_body_segment_passes_through(self) -> None:
        """An empty body segment (None after parse) is not a structural error here."""
        text = "name: X\ndescription: Y\n---\n\n"

        _header, fmt, body = parse_dsl(text)

        assert fmt is BodyFormat.PHASES
        assert isinstance(body, PhasesBody)
        assert body.steps == []

    def test_parse_dsl_header_int_name_rejected(self) -> None:
        """A non-string name (e.g. an int) is rejected as a missing name/description."""
        text = "name: 5\ndescription: Y\n---\n\na:\n  title: A\n"

        with pytest.raises(StructuralError, match="header missing name/description"):
            parse_dsl(text)

    def test_parse_dsl_stages_body_excludes_depends_on_and_title(self) -> None:
        """The stages step body excludes title and depends_on (separate fields)."""
        text = "name: X\ndescription: Y\n---\n\na:\n  title: A\n  depends_on: []\n  agents:\n    - planning\n"

        _header, _fmt, body = parse_dsl(text)

        step_body = body.steps[0].body

        assert "title" not in step_body
        assert "depends_on" not in step_body
        assert step_body["agents"] == ["planning"]
        assert body.steps[0].depends_on == []

    def test_parse_dsl_stages_non_string_key_rejected(self) -> None:
        """A non-string stage map key (int/bool/float) is rejected — ids must be strings.

        YAML parses unquoted numeric/boolean keys as int/bool/float; these would otherwise
        flow through ``StageStep.name`` -> ``FlowStage.id`` and produce a malformed flow-file
        with a non-string id (afm expects string ids for depends_on references).
        """
        for key in ("1", "true", "3.14"):
            text = f"name: X\ndescription: Y\n---\n\n{key}:\n  title: A\n"

            with pytest.raises(StructuralError, match="stage name must be a string"):
                parse_dsl(text)

    def test_parse_dsl_phases_strips_authored_depends_on(self) -> None:
        """An authored ``depends_on`` in a phase item is dropped — phases derive it from position.

        Without this, the authored value leaks into ``PhaseStep.body`` and (for the first step,
        whose position-derived depends_on is None) survives into the output as a dangling
        dependency. Stripping it makes phases consistent with the position-derived contract.
        """
        text = "name: X\ndescription: Y\n---\n\n- name: a\n  title: A\n  depends_on: [zzz]\n  prompt: Do A\n"

        _header, fmt, body = parse_dsl(text)

        assert fmt is BodyFormat.PHASES
        assert "depends_on" not in body.steps[0].body
        assert body.steps[0].body["prompt"] == "Do A"

    def test_parse_dsl_phases_strips_authored_id(self) -> None:
        """An authored ``id`` in a phase item is dropped — the output id derives from ``name``.

        Without this, the authored value leaks into ``PhaseStep.body`` and clobbers the
        serializer's seeded stage id, breaking the position-derived depends_on chain.
        """
        text = "name: X\ndescription: Y\n---\n\n- name: a\n  title: A\n  id: collision-a\n  prompt: Do A\n"

        _header, fmt, body = parse_dsl(text)

        assert fmt is BodyFormat.PHASES
        assert "id" not in body.steps[0].body
        assert body.steps[0].body["prompt"] == "Do A"

    def test_parse_dsl_stages_strips_authored_name_and_id(self) -> None:
        """Authored ``name``/``id`` in a stage value are dropped — reserved output keys.

        The display label derives from ``title`` and the id from the map key; an
        authored value would otherwise leak into ``StageStep.body`` and clobber the
        serializer's seeded ``name``/``id``.
        """
        text = (
            "name: X\n"
            "description: Y\n"
            "---\n"
            "\n"
            "a:\n"
            "  title: A\n"
            "  name: Collision Name\n"
            "  id: collision\n"
            "  agents:\n"
            "    - planning\n"
        )

        _header, fmt, body = parse_dsl(text)

        assert fmt is BodyFormat.STAGES
        assert "name" not in body.steps[0].body
        assert "id" not in body.steps[0].body
        assert body.steps[0].body["agents"] == ["planning"]

    def test_parse_dsl_accepts_crlf_line_endings(self) -> None:
        """A pipeline file with CRLF (Windows) line endings still splits on ``---``."""
        text = "name: X\r\ndescription: Y\r\n---\r\n\r\n- name: a\r\n  title: A\r\n"

        header, fmt, body = parse_dsl(text)

        assert header.name == "X"
        assert fmt is BodyFormat.PHASES
        assert body.steps[0].name == "a"

    def test_parse_dsl_rejects_four_dash_separator(self) -> None:
        """A ``----`` line is not the separator — it must be exactly three dashes."""
        text = "name: X\ndescription: Y\n----\n\n- name: a\n  title: A\n"

        with pytest.raises(StructuralError, match="missing body separator"):
            parse_dsl(text)


class TestParseDslStageAssistants:
    """Logic tests for the stage-body ``assistants`` map extraction (step 4a).

    A step body (both formats) may declare the stage's helper assistants —
    a name-keyed map whose entries carry the four value keys ``prompt``/
    ``skills``/``when``/``gate``. ``parse_dsl`` extracts it into the typed
    ``assistants`` field (the verbatim body excludes the key) and enforces
    the vocabulary at parse time: ``when`` is required (checked before the
    key loop — an empty entry dies as when-required), the delivery keys
    carry the workflow-file clause, the name rules match the workflow
    surface, and every declaration resolves ``prompt`` or ``skills``. An
    absent key and an empty map both equal absence.
    """

    def test_stage_body_assistant_parses_into_typed_field(self) -> None:
        """A stage-body declaration parses into the typed field; the body excludes the key.

        Both body formats produce the same shape: the declaration carries
        every authored value, an un-authored ``gate`` materializes ``False``,
        and the map preserves authored order.
        """
        stages_text = (
            "name: demo\n"
            "description: Demo pipeline\n"
            "---\n"
            "build:\n"
            "  title: Build\n"
            "  prompt: Make\n"
            "  assistants:\n"
            "    auditor:\n"
            "      prompt: Audit.\n"
            "      skills: [code-audit]\n"
            "      when: finish\n"
            "      gate: true\n"
            "    watcher:\n"
            "      prompt: Watch.\n"
            "      when: checkpoints\n"
        )
        phases_text = (
            "name: demo\n"
            "description: Demo pipeline\n"
            "---\n"
            "- name: build\n"
            "  title: Build\n"
            "  prompt: Make\n"
            "  assistants:\n"
            "    auditor:\n"
            "      prompt: Audit.\n"
            "      skills: [code-audit]\n"
            "      when: finish\n"
            "      gate: true\n"
        )

        _header, stages_fmt, stages_body = parse_dsl(stages_text)
        _header, phases_fmt, phases_body = parse_dsl(phases_text)

        assert stages_fmt is BodyFormat.STAGES
        assert phases_fmt is BodyFormat.PHASES

        stages_step = stages_body.steps[0]

        assert list(stages_step.assistants) == ["auditor", "watcher"]
        assert stages_step.assistants["auditor"] == PipelineAssistant(
            name="auditor", prompt="Audit.", skills=["code-audit"], when="finish", gate=True
        )

        watcher = stages_step.assistants["watcher"]

        assert watcher.prompt == "Watch."
        assert watcher.skills is None
        assert watcher.when == "checkpoints"
        assert watcher.gate is False

        # The verbatim body excludes the extracted key; other keys stay verbatim.
        assert "assistants" not in stages_step.body
        assert stages_step.body["prompt"] == "Make"

        phases_step = phases_body.steps[0]

        assert phases_step.assistants["auditor"] == PipelineAssistant(
            name="auditor", prompt="Audit.", skills=["code-audit"], when="finish", gate=True
        )
        assert "assistants" not in phases_step.body
        assert phases_step.body["prompt"] == "Make"

    def test_stage_body_assistants_map_is_deep_copied(self) -> None:
        """The extracted map is deep-copied — mutating it cannot reach the parsed source.

        Verified directly on the helper (the suite's established pattern):
        the yaml-parsed item is local to ``parse_dsl`` and discarded before
        it returns, so the isolation is not observable through the public
        return value alone.
        """
        from goga.pipeline.compiler.parse_dsl import _extract_step_assistants

        item = {
            "title": "Build",
            "assistants": {"watcher": {"prompt": "Watch.", "skills": ["lint"], "when": "checkpoints"}},
        }

        assistants = _extract_step_assistants("build", item)

        # Sentinel mutations on the returned map must not reach the source.
        assistants["watcher"].skills.append("hacked")
        assistants["watcher"].prompt = "hacked"
        assistants["extra"] = None

        assert item["assistants"]["watcher"]["skills"] == ["lint"]
        assert item["assistants"]["watcher"]["prompt"] == "Watch."
        assert "extra" not in item["assistants"]

    def test_delivery_key_in_stage_declaration_rejected(self) -> None:
        """A delivery key in a declaration is the unknown-key error with the workflow-file clause.

        ``agent``/``env``/``delegate`` are workflow-file territory — the
        vocabulary boundary is enforced at parse time, strictly before any
        run (the delivery keys never enter the model).
        """
        text = (
            "name: demo\n"
            "description: Demo pipeline\n"
            "---\n"
            "build:\n"
            "  title: Build\n"
            "  assistants:\n"
            "    auditor:\n"
            "      prompt: X\n"
            "      when: start\n"
            "      agent: codex\n"
        )

        with pytest.raises(
            StructuralError,
            match=re.escape(
                "unknown key in stage build.assistants.auditor: agent; valid keys: prompt, skills, when, gate; "
                "agent, env, delegate are workflow-file territory"
            ),
        ):
            parse_dsl(text)

    def test_content_free_stage_declaration_rejected(self) -> None:
        """A declaration resolving neither prompt nor skills is rejected (the content rule)."""
        text = (
            "name: demo\n"
            "description: Demo pipeline\n"
            "---\n"
            "build:\n"
            "  title: Build\n"
            "  assistants:\n"
            "    auditor:\n"
            "      when: start\n"
        )

        with pytest.raises(
            StructuralError,
            match=re.escape("assistant declaration auditor in stage build resolves neither prompt nor skills"),
        ):
            parse_dsl(text)

    @pytest.mark.parametrize(
        ("assistants_literal", "case", "expected"),
        [
            (
                '    auditor:\n      prompt: X\n      when: start\n      gate: "yes"\n',
                "non-bool gate",
                "non-bool value in stage build.assistants.auditor.gate",
            ),
            (
                "    auditor:\n      prompt: X\n      when: daily\n",
                "invalid when",
                "when must be one of: start, checkpoints, finish, message in stage build.assistants.auditor",
            ),
            (
                "    auditor:\n      prompt: X\n      when: start\n      env:\n        A: B\n",
                "delivery key env",
                "unknown key in stage build.assistants.auditor: env; valid keys: prompt, skills, when, gate; "
                "agent, env, delegate are workflow-file territory",
            ),
            (
                "    bad name!:\n      prompt: X\n      when: start\n",
                "invalid name",
                "invalid assistant name in stage build.assistants.bad name!: bad name!",
            ),
            (
                "    123:\n      prompt: X\n      when: start\n",
                "non-str name",
                "invalid assistant name in stage build.assistants.123: 123",
            ),
            (
                "    assistant:\n      prompt: X\n      when: start\n",
                "reserved name",
                "assistant name is reserved",
            ),
            (
                "    auditor: not a map\n",
                "non-mapping entry",
                "non-mapping assistant declaration in stage build.assistants.auditor",
            ),
            (
                "    - profile: goga-x\n",
                "non-mapping map",
                "non-mapping assistants in stage build; author the map form keyed by assistant name",
            ),
        ],
    )
    def test_pipeline_declaration_vocabulary_rejections(
        self, assistants_literal: str, case: str, expected: str
    ) -> None:
        """Each vocabulary violation dies in its own branch with the exact contract text.

        Every rejection fires strictly before any ``PipelineAssistant`` is
        built — the vocabulary of the new authoring surface is guarded
        character-for-character.
        """
        text = (
            "name: demo\ndescription: Demo pipeline\n---\nbuild:\n  title: Build\n  assistants:\n" + assistants_literal
        )

        with pytest.raises(StructuralError, match=re.escape(expected)):
            parse_dsl(text)

    @pytest.mark.parametrize(
        ("entry_literal", "expected"),
        [
            (
                "    auditor:\n      prompt: 5\n      when: start\n",
                "non-str value in stage build.assistants.auditor.prompt",
            ),
            (
                "    auditor:\n      skills: lint\n      when: start\n",
                "non-list-of-str skills in stage build.assistants.auditor",
            ),
        ],
    )
    def test_declaration_value_type_rejections(self, entry_literal: str, expected: str) -> None:
        """A non-str ``prompt`` and a non-list-of-str ``skills`` die on their contract texts.

        Completes the four-key loop's boundary table alongside the gate and
        ``when`` rows of the vocabulary rejections above.
        """
        text = "name: demo\ndescription: Demo pipeline\n---\nbuild:\n  title: Build\n  assistants:\n" + entry_literal

        with pytest.raises(StructuralError, match=re.escape(expected)):
            parse_dsl(text)

    @pytest.mark.parametrize(
        "entry_literal",
        [
            "    auditor:\n      prompt: X\n",
            "    auditor: {}\n",
        ],
    )
    def test_pipeline_declaration_when_missing_rejected(self, entry_literal: str) -> None:
        """A declaration without ``when`` — field-less or empty — dies on the same branch.

        The ``when`` presence check runs before the key loop, so an empty
        entry dies as when-required, never as an unknown key.
        """
        text = "name: demo\ndescription: Demo pipeline\n---\nbuild:\n  title: Build\n  assistants:\n" + entry_literal

        with pytest.raises(
            StructuralError,
            match=re.escape("when is required in stage build.assistants.auditor"),
        ):
            parse_dsl(text)

    def test_empty_stage_assistants_map_equals_absence(self) -> None:
        """An authored empty ``assistants: {}`` map equals absence — ``step.assistants is None``."""
        text = "name: demo\ndescription: Demo pipeline\n---\nbuild:\n  title: Build\n  assistants: {}\n"

        _header, _fmt, body = parse_dsl(text)

        assert body.steps[0].assistants is None
        assert "assistants" not in body.steps[0].body


class TestParseDslRolesBlock:
    """Contract and logic tests for the optional header-level ``roles`` block.

    The ``roles`` block carries three optional inline prompt overrides
    (planner, executor, reviewer). ``parse_dsl`` extracts and structurally
    validates it: the legacy ``agents`` header key is a hard-rename error,
    unknown keys (incl. ``summary`` — a separate, non-role channel), non-str
    values, and non-mapping blocks are structural errors; an absent or
    empty-mapping block yields ``header.roles is None``.
    """

    def test_parse_dsl_extracts_roles_overrides(self) -> None:
        """A partial override (planner, reviewer) is extracted; executor stays None; no summary."""
        text = (
            "name: Goga feature\n"
            "description: Feature implementation\n"
            "roles:\n"
            "  planner: |\n"
            "    plan prompt\n"
            "  reviewer: |\n"
            "    review prompt\n"
            "---\n"
            "\n"
            "- name: propose\n"
            "  title: Propose\n"
        )

        header, fmt, _body = parse_dsl(text)

        assert header.name == "Goga feature"
        assert header.description == "Feature implementation"
        assert header.roles is not None
        assert header.roles.planner == "plan prompt\n"
        assert header.roles.executor is None
        assert header.roles.reviewer == "review prompt\n"
        # summary is NOT a role — the carrier has no such attribute at all.
        assert not hasattr(header.roles, "summary")
        assert fmt is BodyFormat.PHASES

    def test_parse_dsl_header_roles_is_typed_pipeline_roles_or_none(self) -> None:
        """``header.roles`` is either a ``PipelineRoles`` or ``None`` — never a raw mapping."""
        text_without_roles = "name: X\ndescription: Y\n---\n\n- name: a\n  title: A\n"
        text_with_roles = "name: X\ndescription: Y\nroles:\n  planner: P\n---\n\n- name: a\n  title: A\n"

        header_none, _fmt, _body = parse_dsl(text_without_roles)
        header_typed, _fmt, _body = parse_dsl(text_with_roles)

        # Absent block → None (not an empty dict).
        assert header_none.roles is None

        # Present block → a typed PipelineRoles, never the raw YAML dict.
        assert isinstance(header_typed.roles, PipelineRoles)
        assert header_typed.roles.planner == "P"

    def test_parse_dsl_rejects_legacy_agents_header_key(self) -> None:
        """The legacy ``agents`` header key is forbidden — a hard-rename error.

        A user copying the old ``agents:`` header shape is caught with a clear
        message pointing at the replacement directive (``roles``), rather than
        the block being silently dropped.
        """
        text = (
            "name: Goga feature\n"
            "description: Feature implementation\n"
            "agents:\n"
            "  planning: x\n"
            "---\n"
            "\n"
            "- name: propose\n"
            "  title: Propose\n"
        )

        with pytest.raises(StructuralError, match="agents key is forbidden in header; use roles"):
            parse_dsl(text)

    def test_parse_dsl_rejects_unknown_role_including_summary(self) -> None:
        """An unknown role key (e.g. ``summary``) is rejected — summary is NOT an overridable role."""
        text = (
            "name: Goga feature\n"
            "description: Feature implementation\n"
            "roles:\n"
            "  planner: x\n"
            "  summary: s\n"
            "---\n"
            "\n"
            "- name: propose\n"
            "  title: Propose\n"
        )

        with pytest.raises(
            StructuralError,
            match=r"unknown role in header\.roles: summary; valid keys: planner, executor, reviewer",
        ):
            parse_dsl(text)

    @pytest.mark.parametrize(
        ("roles_value", "case"),
        [
            ('"not a mapping"\n', "scalar string"),
            ("42\n", "scalar number"),
            ("\n  - planner\n", "list"),
        ],
    )
    def test_parse_dsl_rejects_non_mapping_roles_block(self, roles_value: str, case: str) -> None:
        """A non-mapping ``roles`` value (scalar/string/list) is rejected.

        The list case is the most likely real-world mistake: step-level
        ``roles`` in this same DSL IS a list (``roles: [planner]``), so a user
        copying that shape into the header block must be caught as non-mapping.
        """
        text = (
            "name: Goga feature\n"
            "description: Feature implementation\n"
            f"roles: {roles_value}"
            "---\n"
            "\n"
            "- name: propose\n"
            "  title: Propose\n"
        )

        with pytest.raises(StructuralError, match="non-mapping roles block in header"):
            parse_dsl(text)

    @pytest.mark.parametrize(
        ("role_value_line", "case"),
        [
            ("  planner: 42\n", "int"),
            ("  planner: true\n", "bool"),
            ("  planner: 3.14\n", "float"),
            ("  planner:\n", "null value"),
            ("  planner:\n    nested: x\n", "nested mapping"),
        ],
    )
    def test_parse_dsl_rejects_non_str_role_value(self, role_value_line: str, case: str) -> None:
        """A non-str value for a known role key is rejected — no silent type coercion.

        Covers the full non-str surface: scalar types (int/bool/float), a null
        value (``planner:`` with nothing — a plausible omission), and a nested
        mapping (``planner:\\n  nested: x`` — step-level keys mis-nested under
        the header block). All hit the ``not isinstance(value, str)`` branch and
        raise; none are silently coerced or treated as "no override".
        """
        text = (
            "name: Goga feature\n"
            "description: Feature implementation\n"
            "roles:\n"
            f"{role_value_line}"
            "---\n"
            "\n"
            "- name: propose\n"
            "  title: Propose\n"
        )

        with pytest.raises(StructuralError, match=r"non-str value in header\.roles\.planner"):
            parse_dsl(text)

    def test_parse_dsl_empty_roles_block_equals_none(self) -> None:
        """An empty ``roles: {}`` mapping is treated identically to an absent block (None)."""
        text = (
            "name: Goga feature\n"
            "description: Feature implementation\n"
            "roles: {}\n"
            "---\n"
            "\n"
            "- name: propose\n"
            "  title: Propose\n"
        )

        header, _fmt, _body = parse_dsl(text)

        assert header.roles is None

    def test_parse_dsl_roles_null_value_treated_as_none(self) -> None:
        """A null ``roles:`` value (no body) is treated identically to an absent block (None)."""
        text = (
            "name: Goga feature\n"
            "description: Feature implementation\n"
            "roles:\n"
            "---\n"
            "\n"
            "- name: propose\n"
            "  title: Propose\n"
        )

        header, _fmt, _body = parse_dsl(text)

        assert header.roles is None


class TestParseDslRepeatableFlag:
    """Contract and logic tests for the optional header-level ``repeatable`` flag.

    The flag declares the pipeline's repeat capability. ``parse_dsl`` extracts
    it after the ``roles`` block: a present value must be strictly bool
    (an explicit ``null``, an int, or a string raise one clean structural
    error); an absent key equals ``False``. The flag is carried into
    ``PipelineHeader`` and never enters the compiled flow-file directly —
    the compiled ``repeat`` directive is derived from it by ``compile_flow``.
    """

    def test_parse_dsl_extracts_repeatable_true(self) -> None:
        """An explicit ``repeatable: true`` parses to ``header.repeatable is True``."""
        text = (
            "name: Goga feature\n"
            "description: Feature implementation\n"
            "repeatable: true\n"
            "---\n"
            "\n"
            "- name: propose\n"
            "  title: Propose\n"
        )

        header, _fmt, _body = parse_dsl(text)

        assert header.repeatable is True

    def test_parse_dsl_repeatable_absent_equals_false(self) -> None:
        """A header without the flag parses to ``header.repeatable is False``."""
        text = "name: X\ndescription: Y\n---\n\n- name: a\n  title: A\n"

        header, _fmt, _body = parse_dsl(text)

        assert header.repeatable is False

    def test_parse_dsl_repeatable_explicit_false_equals_false(self) -> None:
        """An explicit ``repeatable: false`` parses to ``header.repeatable is False``."""
        text = "name: X\ndescription: Y\nrepeatable: false\n---\n\n- name: a\n  title: A\n"

        header, _fmt, _body = parse_dsl(text)

        assert header.repeatable is False

    def test_parse_dsl_repeatable_after_roles(self) -> None:
        """The flag parses alongside a ``roles`` block (checked last, after roles)."""
        text = "name: X\ndescription: Y\nroles:\n  planner: P\nrepeatable: true\n---\n\n- name: a\n  title: A\n"

        header, _fmt, _body = parse_dsl(text)

        assert header.roles is not None
        assert header.roles.planner == "P"
        assert header.repeatable is True

    @pytest.mark.parametrize(
        ("flag_line", "case"),
        [
            ("repeatable: 1\n", "int one"),
            ('repeatable: "yes"\n', "quoted string"),
            ("repeatable: null\n", "explicit null"),
        ],
    )
    def test_parse_dsl_repeatable_non_bool(self, flag_line: str, case: str) -> None:
        """A present non-bool value raises one clean structural error.

        ``1`` equals ``True`` in Python but is an ``int``, not a ``bool``; the
        quoted ``"yes"`` is a string (a BARE ``yes`` parses as bool ``True``
        under PyYAML's YAML 1.1 and must not be used as a negative case); an
        explicit ``null`` is PRESENT and non-bool — the same error.
        """
        text = f"name: X\ndescription: Y\n{flag_line}---\n\n- name: a\n  title: A\n"

        with pytest.raises(StructuralError, match=r"non-bool value in header\.repeatable"):
            parse_dsl(text)


class TestParseDslAnchors:
    """Behavioral tests for YAML links — anchor carriage across the separator and hidden keys."""

    def test_header_anchor_merged_into_stages_stage(self) -> None:
        """An anchor declared in the header segment merges into a STAGES body stage."""
        text = (
            "name: demo\ndescription: demo\n"
            ".defaults: &shared\n"
            "  agent: claude\n"
            "---\n"
            "build:\n"
            "  <<: *shared\n"
            "  title: Build\n"
        )

        _header, fmt, body = parse_dsl(text)

        assert fmt is BodyFormat.STAGES

        step = body.steps[0]
        assert step.name == "build"
        assert step.title == "Build"
        assert step.body["agent"] == "claude"

    def test_hidden_body_key_with_merge(self) -> None:
        """A hidden ``.defaults`` body key merges into stages and never becomes one."""
        text = (
            "name: demo\ndescription: demo\n"
            "---\n"
            ".defaults: &shared\n"
            "  agent: claude\n"
            "build:\n"
            "  <<: *shared\n"
            "  title: Build\n"
        )

        _header, fmt, body = parse_dsl(text)

        assert fmt is BodyFormat.STAGES
        assert [step.name for step in body.steps] == ["build"]
        assert body.steps[0].body["agent"] == "claude"

    def test_hidden_body_key_alone_is_dropped(self) -> None:
        """A hidden body key without use sites is dropped, not compiled into a stage."""
        text = "name: demo\ndescription: demo\n---\n.anchor: &a\n  q: 1\nbuild:\n  title: Build\n"

        _header, _fmt, body = parse_dsl(text)

        assert [step.name for step in body.steps] == ["build"]

    def test_header_anchor_merged_into_phases_item(self) -> None:
        """A header anchor merges into a PHASES list item mapping."""
        text = (
            "name: demo\ndescription: demo\n"
            ".defaults: &shared\n"
            "  agent: claude\n"
            "---\n"
            "- name: s1\n"
            "  title: T1\n"
            "  <<: *shared\n"
        )

        _header, fmt, body = parse_dsl(text)

        assert fmt is BodyFormat.PHASES
        assert body.steps[0].body["agent"] == "claude"

    def test_alias_within_body_segment(self) -> None:
        """An anchor and its alias inside one body segment work without a hidden key."""
        text = "name: demo\ndescription: demo\n---\nbuild: &b\n  title: Build\ncopy: *b\n"

        _header, _fmt, body = parse_dsl(text)

        assert [step.name for step in body.steps] == ["build", "copy"]
        assert body.steps[1].title == "Build"

    def test_alias_before_anchor_raises_wrapped(self) -> None:
        """An alias authored before its anchor fails as the clean structural error."""
        text = "name: *a\n---\n.x: &a\n  q: 1\n"

        with pytest.raises(StructuralError, match="invalid YAML in pipeline-file"):
            parse_dsl(text)

    def test_duplicate_anchor_across_segments_raises_wrapped(self) -> None:
        """Re-declaring the same anchor name in both segments fails as a structural error."""
        text = "name: d\ndescription: d\n.x: &a\n  q: 1\n---\n.y: &a\n  q: 2\nbuild:\n  <<: *a\n  title: B\n"

        with pytest.raises(StructuralError, match="invalid YAML in pipeline-file"):
            parse_dsl(text)

    def test_invalid_yaml_raises_structural_error(self) -> None:
        """A damaged body YAML raises the wrapped structural error, never a raw YAMLError."""
        text = "name: Deploy\ndescription: d\n---\n:\n  [broken\n"

        with pytest.raises(StructuralError, match="invalid YAML in pipeline-file"):
            parse_dsl(text)

    def test_extra_separator_raises(self) -> None:
        """A third document (an extra ``---`` line inside the body) is a structural error."""
        text = "name: d\ndescription: d\n---\nbuild:\n  title: B\n---\nextra: 1\n"

        with pytest.raises(StructuralError, match="extra body separator"):
            parse_dsl(text)

    def test_crlf_file_parses(self) -> None:
        """A CRLF pipeline file parses through the stream loader with anchors intact."""
        text = "name: d\r\ndescription: d\r\n.x: &a\r\n  agent: claude\r\n---\r\nbuild:\r\n  <<: *a\r\n  title: B\r\n"

        header, _fmt, body = parse_dsl(text)

        assert header.name == "d"
        assert body.steps[0].body["agent"] == "claude"

    def test_empty_header_segment_keeps_message(self) -> None:
        """A whitespace-only header segment keeps the empty-header error of the split era."""
        text = "\n---\nbuild:\n  title: B\n"

        with pytest.raises(StructuralError, match="header missing name/description"):
            parse_dsl(text)

    def test_leading_separator_keeps_message(self) -> None:
        """A file starting with the separator line keeps the empty-header error."""
        text = "---\nname: d\ndescription: d\n---\nbuild:\n  title: B\n"

        with pytest.raises(StructuralError, match="header missing name/description"):
            parse_dsl(text)
