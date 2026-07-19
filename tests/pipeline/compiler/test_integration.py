"""Compiler-cell integration tests — end-to-end coverage across all entities.

These tests drive the full pipeline-file → flow-file transformation with the two
canonical fixtures (``feature-phases.yml``, ``feature-stages.yml``). They validate
the output both as round-tripped Python data (via ``yaml.safe_load``) and as
canonical YAML text (key order, flow/block styles). The integration surface is
``compile_flow`` only — it internally exercises ``parse_dsl``, ``serialize_flow``,
and the data models, so a passing suite here means the three routines compose
correctly.
"""

from __future__ import annotations

from itertools import pairwise
from pathlib import Path

import pytest
import yaml
from goga.pipeline.compiler import StructuralError, compile_flow

_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "integration"
_FEATURE_PHASES = _FIXTURES / "phases.yml"
_FEATURE_STAGES = _FIXTURES / "stages.yml"

# Canonical field-key order that ``compile_flow`` must establish before serialization.
# Known keys first in this fixed order; any extras follow alphabetically.
_CANONICAL_KEY_ORDER = [
    "interactive",
    "command",
    "prompt",
    "description",
    "agents",
    "supervisor",
    "supervisor_prompt",
    "skills",
]


def _split_header_body(fixture_path: Path) -> tuple[dict, object]:
    """Load a fixture's header (dict) and body (list | dict) by splitting on ``---``."""
    text = fixture_path.read_text()
    header_text, body_text = text.split("---", 1)

    return yaml.safe_load(header_text), yaml.safe_load(body_text)


def _stage_field_keys_in_text_order(text: str, stage_id: str) -> list[str]:
    """Return one stage's field keys (excluding id/name/depends_on) in textual order.

    Walks the serialized YAML text line by line, isolating the block for ``stage_id``
    (from ``- id: <stage_id>`` up to the next ``- id:`` or end-of-file), and collects
    the field keys in the order they appear. Used to assert canonical key ordering.
    """
    lines = text.splitlines()
    start = next(i for i, line in enumerate(lines) if line == f"- id: {stage_id}")

    keys: list[str] = []
    for line in lines[start + 1 :]:
        # The next stage begins at a top-level ``- id:`` line.
        if line.startswith("- id: "):
            break
        # Field keys sit at exactly two-space indent, are not sequence items, and
        # contain a colon (e.g. ``  interactive: true``).
        stripped = line[2:]
        if (
            line.startswith("  ")
            and not line.startswith("   ")
            and not stripped.startswith("-")
            and ":" in stripped
        ):
            key = stripped.split(":", 1)[0]
            if key not in ("id", "name", "depends_on"):
                keys.append(key)

    return keys


class TestCompileFlowIntegrationPhases:
    """End-to-end coverage for the canonical phases (list-body) fixture."""

    def test_phases_fixture_end_to_end(self, tmp_path: Path) -> None:
        """The phases fixture compiles to a position-derived dependency chain.

        Asserts the output file exists, has exactly the three top-level keys, the
        stage ids match the fixture's authored step names in order, and the
        ``depends_on`` values form a position-derived chain (first stage has none,
        each subsequent stage depends on its predecessor's id).
        """
        flow_path = tmp_path / "flow.yml"
        compile_flow(_FEATURE_PHASES, flow_path)

        assert flow_path.exists()

        header, _body = _split_header_body(_FEATURE_PHASES)
        loaded = yaml.safe_load(flow_path.read_text())

        # Top-level shape: exactly name, description, stages.
        assert list(loaded.keys()) == ["name", "description", "stages"]
        assert loaded["name"] == header["name"]
        assert loaded["description"] == header["description"]

        stages = loaded["stages"]

        # Stage ids preserve the fixture's authored step order.
        _, body = _split_header_body(_FEATURE_PHASES)
        expected_ids = [item["name"] for item in body]
        assert [stage["id"] for stage in stages] == expected_ids

        # First stage has no depends_on; every later stage depends on its predecessor.
        assert "depends_on" not in stages[0]
        for prev, curr in pairwise(stages):
            assert curr["depends_on"] == [prev["id"]]


class TestCompileFlowIntegrationStages:
    """End-to-end coverage for the canonical stages (map-body) fixture."""

    def test_stages_fixture_depends_on_matches_authored(self, tmp_path: Path) -> None:
        """The stages fixture passes authored depends_on through unchanged.

        An absent ``depends_on`` in the source is emitted as no key; a present list
        is emitted verbatim. Every stage's compiled depends_on matches the fixture.
        """
        flow_path = tmp_path / "flow.yml"
        compile_flow(_FEATURE_STAGES, flow_path)

        stages = yaml.safe_load(flow_path.read_text())["stages"]

        _, body = _split_header_body(_FEATURE_STAGES)
        authored = {name: value.get("depends_on") for name, value in body.items()}

        for stage in stages:
            expected = authored[stage["id"]]
            if expected is None:
                assert "depends_on" not in stage
            else:
                assert stage["depends_on"] == expected

    def test_stages_fixture_canonical_key_order(self, tmp_path: Path) -> None:
        """Every stage's fields serialize in canonical key order (textual)."""
        flow_path = tmp_path / "flow.yml"
        compile_flow(_FEATURE_STAGES, flow_path)

        text = flow_path.read_text()

        for stage in yaml.safe_load(text)["stages"]:
            keys = _stage_field_keys_in_text_order(text, stage["id"])

            # Known canonical keys must appear in their fixed relative order...
            known = [k for k in keys if k in _CANONICAL_KEY_ORDER]
            assert known == [k for k in _CANONICAL_KEY_ORDER if k in known]

            # ...and any extras must follow, sorted alphabetically among themselves.
            extras = [k for k in keys if k not in _CANONICAL_KEY_ORDER]
            assert extras == sorted(extras)

    def test_stages_fixture_flow_and_block_styles(self, tmp_path: Path) -> None:
        """``agents`` serialize in flow-style; ``skills`` and ``depends_on`` in block-style."""
        flow_path = tmp_path / "flow.yml"
        compile_flow(_FEATURE_STAGES, flow_path)

        text = flow_path.read_text()

        # A flow-style agents list renders on one line as ``agents: [...]``.
        assert "agents: [planning, implementation]" in text
        # A block-style skills list renders as a nested sequence.
        assert "skills:\n  - goga-propose" in text
        # A block-style depends_on list renders as a nested sequence.
        assert "depends_on:\n  - propose" in text


class TestCompileFlowIntegrationIdempotency:
    """Compiling the same input twice produces byte-identical output."""

    @pytest.mark.parametrize("fixture", [_FEATURE_PHASES, _FEATURE_STAGES], ids=["phases", "stages"])
    def test_compile_twice_is_byte_identical(self, fixture: Path, tmp_path: Path) -> None:
        flow_path = tmp_path / "flow.yml"

        compile_flow(fixture, flow_path)
        first = flow_path.read_text()

        compile_flow(fixture, flow_path)
        second = flow_path.read_text()

        assert first == second

    def test_single_trailing_newline(self, tmp_path: Path) -> None:
        """The serialized output ends with exactly one trailing newline (both fixtures)."""
        for fixture in (_FEATURE_PHASES, _FEATURE_STAGES):
            flow_path = tmp_path / "flow.yml"
            compile_flow(fixture, flow_path)
            text = flow_path.read_text()

            assert text.endswith("\n")
            assert not text.endswith("\n\n")


class TestCompileFlowIntegrationErrorPropagation:
    """Structural errors from parse_dsl surface through compile_flow unchanged."""

    def test_scalar_body_raises_structural_error(self, tmp_path: Path) -> None:
        """A scalar body (neither list nor mapping) raises StructuralError through compile_flow."""
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text("name: T\ndescription: T\n---\n\njust a string\n")
        flow_path = tmp_path / "flow.yml"

        with pytest.raises(StructuralError, match="unsupported body format"):
            compile_flow(pipeline_path, flow_path)
