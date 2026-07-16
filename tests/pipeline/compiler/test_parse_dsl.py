"""Contract and logic tests for the ``parse_dsl`` pure parser and ``StructuralError``.

Covers the parser half of the compiler cell: structural validation of a goga DSL
pipeline-file (header segment + body segment split on a literal ``---`` line) and
the typed 3-tuple it returns. Content of step fields is passed through verbatim;
``depends_on`` references are not resolved.
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest
from goga.pipeline.compiler import (
    BodyFormat,
    PhasesBody,
    PipelineAgents,
    PipelineHeader,
    StagesBody,
    StructuralError,
    parse_dsl,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_FEATURE_PHASES = _REPO_ROOT / "goga" / "assets" / "pipelines" / "feature-phases.yml"
_FEATURE_STAGES = _REPO_ROOT / "goga" / "assets" / "pipelines" / "feature-stages.yml"


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
        text = "name: X\ndescription: Y\n---\n\n- name: a\n  description: A\n"

        header, fmt, body = parse_dsl(text)

        assert isinstance(header, PipelineHeader)
        assert fmt is BodyFormat.PHASES
        assert isinstance(body, PhasesBody)

    def test_parse_dsl_returns_stages_on_minimal_stages(self) -> None:
        """A minimal valid stages text yields (PipelineHeader, STAGES, StagesBody)."""
        text = "name: X\ndescription: Y\n---\n\na:\n  description: A\n"

        header, fmt, body = parse_dsl(text)

        assert isinstance(header, PipelineHeader)
        assert fmt is BodyFormat.STAGES
        assert isinstance(body, StagesBody)


class TestParseDslLogic:
    """Behavioral tests against the real fixtures and the documented edge cases."""

    def test_parse_dsl_phases_basic(self) -> None:
        """The canonical phases fixture parses to 11 steps with bodies excluding name/description."""
        text = _FEATURE_PHASES.read_text()

        header, fmt, body = parse_dsl(text)

        assert header.name == "Goga feature"
        assert header.description == "Feature implementation"
        assert fmt is BodyFormat.PHASES
        assert isinstance(body, PhasesBody)

        assert len(body.steps) == 11

        first = body.steps[0]
        assert first.name == "propose"
        assert first.description == "Propose"

        # name/description are separate fields; everything else is verbatim body.
        assert "name" not in first.body
        assert "description" not in first.body
        assert first.body["interactive"] is True
        assert first.body["agents"] == ["planning", "implementation"]
        assert "prompt" in first.body

    def test_parse_dsl_stages_basic(self) -> None:
        """The canonical stages fixture parses to 11 steps with pass-through depends_on."""
        text = _FEATURE_STAGES.read_text()

        header, fmt, body = parse_dsl(text)

        assert header.name == "Goga feature"
        assert fmt is BodyFormat.STAGES
        assert isinstance(body, StagesBody)

        assert len(body.steps) == 11

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
        text = "description: Y\n---\n\n- name: a\n  description: A\n"

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
            "  description: A\n"
            "  depends_on:\n"
            "b:\n"
            "  description: B\n"
            "  depends_on: []\n"
            "c:\n"
            "  description: C\n"
        )

        _header, fmt, body = parse_dsl(text)

        assert fmt is BodyFormat.STAGES

        assert body.steps[0].depends_on is None
        assert body.steps[1].depends_on == []
        assert body.steps[2].depends_on is None

    def test_parse_dsl_stages_depends_on_string_rejected(self) -> None:
        """A non-list, non-None depends_on (a bare string) is a structural type error."""
        text = "name: T\ndescription: T\n---\n\na:\n  description: A\n  depends_on: b\n"

        with pytest.raises(StructuralError, match="depends_on must be a list"):
            parse_dsl(text)

    def test_parse_dsl_stages_depends_on_non_string_element_rejected(self) -> None:
        """A depends_on list with a non-string element is a structural type error."""
        text = "name: T\ndescription: T\n---\n\na:\n  description: A\n  depends_on: [1, 2]\n"

        with pytest.raises(StructuralError, match="depends_on must contain only strings"):
            parse_dsl(text)

    def test_parse_dsl_phase_item_missing_description_raises(self) -> None:
        """A phases list item without a string description is rejected."""
        text = "name: X\ndescription: Y\n---\n\n- name: a\n  interactive: true\n"

        with pytest.raises(StructuralError, match="phase item missing name/description"):
            parse_dsl(text)

    def test_parse_dsl_stage_value_must_be_mapping_raises(self) -> None:
        """A stages body whose value is not a mapping is rejected."""
        text = "name: X\ndescription: Y\n---\n\na: just a scalar\n"

        with pytest.raises(StructuralError, match="stage value must be a mapping"):
            parse_dsl(text)

    def test_parse_dsl_header_not_a_mapping_raises(self) -> None:
        """A header segment that YAML-parses to a non-mapping (e.g. a scalar) is rejected."""
        text = "42\n---\n\n- name: a\n  description: A\n"

        with pytest.raises(StructuralError, match="header missing name/description"):
            parse_dsl(text)

    def test_parse_dsl_phase_item_not_a_mapping_raises(self) -> None:
        """A phases list element that is not a mapping (e.g. a scalar) is rejected."""
        text = "name: X\ndescription: Y\n---\n\n- just a scalar\n"

        with pytest.raises(StructuralError, match="phase item must be a mapping"):
            parse_dsl(text)

    def test_parse_dsl_stage_value_missing_description_raises(self) -> None:
        """A stages value mapping without a string description is rejected."""
        text = "name: X\ndescription: Y\n---\n\na:\n  agents: [planning]\n"

        with pytest.raises(StructuralError, match="stage value missing description"):
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

        source = {"name": "a", "description": "A", "agents": ["planning"], "nested": {"k": 1}}

        copied = _deep_copy_without(source, excluded={"name", "description"})

        # Excluded keys (carried as separate fields) are dropped from the body.
        assert "name" not in copied
        assert "description" not in copied
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
        text = "name: 5\ndescription: Y\n---\n\na:\n  description: A\n"

        with pytest.raises(StructuralError, match="header missing name/description"):
            parse_dsl(text)

    def test_parse_dsl_stages_body_excludes_depends_on_and_description(self) -> None:
        """The stages step body excludes description and depends_on (separate fields)."""
        text = (
            "name: X\n"
            "description: Y\n"
            "---\n"
            "\n"
            "a:\n"
            "  description: A\n"
            "  depends_on: []\n"
            "  agents:\n"
            "    - planning\n"
        )

        _header, _fmt, body = parse_dsl(text)

        step_body = body.steps[0].body

        assert "description" not in step_body
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
            text = f"name: X\ndescription: Y\n---\n\n{key}:\n  description: A\n"

            with pytest.raises(StructuralError, match="stage name must be a string"):
                parse_dsl(text)

    def test_parse_dsl_phases_strips_authored_depends_on(self) -> None:
        """An authored ``depends_on`` in a phase item is dropped — phases derive it from position.

        Without this, the authored value leaks into ``PhaseStep.body`` and (for the first step,
        whose position-derived depends_on is None) survives into the output as a dangling
        dependency. Stripping it makes phases consistent with the position-derived contract.
        """
        text = (
            "name: X\n"
            "description: Y\n"
            "---\n"
            "\n"
            "- name: a\n"
            "  description: A\n"
            "  depends_on: [zzz]\n"
            "  prompt: Do A\n"
        )

        _header, fmt, body = parse_dsl(text)

        assert fmt is BodyFormat.PHASES
        assert "depends_on" not in body.steps[0].body
        assert body.steps[0].body["prompt"] == "Do A"

    def test_parse_dsl_phases_strips_authored_id(self) -> None:
        """An authored ``id`` in a phase item is dropped — the output id derives from ``name``.

        Without this, the authored value leaks into ``PhaseStep.body`` and clobbers the
        serializer's seeded stage id, breaking the position-derived depends_on chain.
        """
        text = (
            "name: X\n"
            "description: Y\n"
            "---\n"
            "\n"
            "- name: a\n"
            "  description: A\n"
            "  id: collision-a\n"
            "  prompt: Do A\n"
        )

        _header, fmt, body = parse_dsl(text)

        assert fmt is BodyFormat.PHASES
        assert "id" not in body.steps[0].body
        assert body.steps[0].body["prompt"] == "Do A"

    def test_parse_dsl_stages_strips_authored_name_and_id(self) -> None:
        """Authored ``name``/``id`` in a stage value are dropped — reserved output keys.

        The display label derives from ``description`` and the id from the map key; an
        authored value would otherwise leak into ``StageStep.body`` and clobber the
        serializer's seeded ``name``/``id``.
        """
        text = (
            "name: X\n"
            "description: Y\n"
            "---\n"
            "\n"
            "a:\n"
            "  description: A\n"
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
        text = "name: X\r\ndescription: Y\r\n---\r\n\r\n- name: a\r\n  description: A\r\n"

        header, fmt, body = parse_dsl(text)

        assert header.name == "X"
        assert fmt is BodyFormat.PHASES
        assert body.steps[0].name == "a"

    def test_parse_dsl_rejects_four_dash_separator(self) -> None:
        """A ``----`` line is not the separator — it must be exactly three dashes."""
        text = "name: X\ndescription: Y\n----\n\n- name: a\n  description: A\n"

        with pytest.raises(StructuralError, match="missing body separator"):
            parse_dsl(text)


class TestParseDslAgentsBlock:
    """Contract and logic tests for the optional header-level ``agents`` block.

    The ``agents`` block carries four optional inline prompt overrides
    (planning, implementation, review, summary). ``parse_dsl`` extracts and
    structurally validates it: unknown keys, non-str values, and non-mapping
    blocks are structural errors; an absent or empty-mapping block yields
    ``header.agents is None``.
    """

    def test_parse_dsl_extracts_agents_planning_only(self) -> None:
        """A partial override (planning only) is extracted; the other three fields stay None."""
        text = (
            "name: Goga feature\n"
            "description: Feature implementation\n"
            "agents:\n"
            "  planning: |\n"
            "    Custom planning prompt.\n"
            "---\n"
            "\n"
            "- name: propose\n"
            "  description: Propose\n"
        )

        header, fmt, _body = parse_dsl(text)

        assert header.name == "Goga feature"
        assert header.description == "Feature implementation"
        assert header.agents is not None
        assert header.agents.planning == "Custom planning prompt.\n"
        assert header.agents.implementation is None
        assert header.agents.review is None
        assert header.agents.summary is None
        assert fmt is BodyFormat.PHASES

    def test_parse_dsl_header_agents_is_typed_pipeline_agents_or_none(self) -> None:
        """``header.agents`` is either a ``PipelineAgents`` or ``None`` — never a raw mapping."""
        text_without_agents = "name: X\ndescription: Y\n---\n\n- name: a\n  description: A\n"
        text_with_agents = (
            "name: X\n"
            "description: Y\n"
            "agents:\n"
            "  planning: P\n"
            "---\n"
            "\n"
            "- name: a\n"
            "  description: A\n"
        )

        header_none, _fmt, _body = parse_dsl(text_without_agents)
        header_typed, _fmt, _body = parse_dsl(text_with_agents)

        # Absent block → None (not an empty dict).
        assert header_none.agents is None

        # Present block → a typed PipelineAgents, never the raw YAML dict.
        assert isinstance(header_typed.agents, PipelineAgents)
        assert header_typed.agents.planning == "P"

    def test_parse_dsl_rejects_unknown_agent_key(self) -> None:
        """An unknown agent key (e.g. ``researcher``) is rejected with a readable error."""
        text = (
            "name: Goga feature\n"
            "description: Feature implementation\n"
            "agents:\n"
            "  researcher: Should fail\n"
            "---\n"
            "\n"
            "- name: propose\n"
            "  description: Propose\n"
        )

        with pytest.raises(StructuralError, match=r"unknown agent in header\.agents: researcher"):
            parse_dsl(text)

    def test_parse_dsl_rejects_non_str_agent_value(self) -> None:
        """A non-str agent value (e.g. an int) is rejected — no silent type coercion."""
        text = (
            "name: Goga feature\n"
            "description: Feature implementation\n"
            "agents:\n"
            "  planning: 42\n"
            "---\n"
            "\n"
            "- name: propose\n"
            "  description: Propose\n"
        )

        with pytest.raises(StructuralError, match=r"non-str value in header\.agents\.planning"):
            parse_dsl(text)

    def test_parse_dsl_rejects_non_mapping_agents_block(self) -> None:
        """A scalar/string ``agents`` value (not a mapping) is rejected."""
        text = (
            "name: Goga feature\n"
            "description: Feature implementation\n"
            'agents: "not a mapping"\n'
            "---\n"
            "\n"
            "- name: propose\n"
            "  description: Propose\n"
        )

        with pytest.raises(StructuralError, match="non-mapping agents block in header"):
            parse_dsl(text)

    def test_parse_dsl_treats_empty_agents_mapping_as_none(self) -> None:
        """An empty ``agents: {}`` mapping is treated identically to an absent block (None)."""
        text = (
            "name: Goga feature\n"
            "description: Feature implementation\n"
            "agents: {}\n"
            "---\n"
            "\n"
            "- name: propose\n"
            "  description: Propose\n"
        )

        header, _fmt, _body = parse_dsl(text)

        assert header.agents is None

    def test_parse_dsl_agents_null_value_treated_as_none(self) -> None:
        """A null ``agents:`` value (no body) is treated identically to an absent block (None)."""
        text = (
            "name: Goga feature\n"
            "description: Feature implementation\n"
            "agents:\n"
            "---\n"
            "\n"
            "- name: propose\n"
            "  description: Propose\n"
        )

        header, _fmt, _body = parse_dsl(text)

        assert header.agents is None
