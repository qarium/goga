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

    def test_parse_dsl_deep_copies_body_dicts(self) -> None:
        """Step bodies are deep copies — mutating a parsed body does not touch the source list."""
        text = (
            "name: X\n"
            "description: Y\n"
            "---\n"
            "\n"
            "- name: a\n"
            "  description: A\n"
            "  agents:\n"
            "    - planning\n"
            "  nested:\n"
            "    key: value\n"
        )

        _header, _fmt, body = parse_dsl(text)

        step_body = body.steps[0].body

        # Mutating the returned body (including nested structures) must not reach back into
        # any parsed structure the parser still holds.
        step_body["agents"].append("hacked")
        step_body["nested"]["extra"] = True

        # A second parse of the same text must be unaffected by the first's mutation.
        _header2, _fmt2, body2 = parse_dsl(text)

        assert body2.steps[0].body["agents"] == ["planning"]
        assert body2.steps[0].body["nested"] == {"key": "value"}

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
