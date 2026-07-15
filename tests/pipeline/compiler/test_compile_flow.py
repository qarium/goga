"""Contract and logic tests for the ``compile_flow`` entry point.

Covers the entry-point half of the compiler cell: reading a goga DSL pipeline-file
via ``parse_dsl``, applying per-format ``depends_on`` rules (PHASES:
position-derived; STAGES: pass-through), reordering step bodies into canonical
key order via the internal ``_canonical_fields`` helper, and writing the canonical
afm flow-file. I/O and structural errors propagate unchanged; an empty body is
rejected here with ``StructuralError("empty body")``.
"""

from __future__ import annotations

import inspect
from itertools import pairwise
from pathlib import Path

import pytest
import yaml
from goga.pipeline.compiler import StructuralError, compile_flow

_REPO_ROOT = Path(__file__).resolve().parents[3]
_FEATURE_PHASES = _REPO_ROOT / "goga" / "assets" / "pipelines" / "feature-phases.yml"
_FEATURE_STAGES = _REPO_ROOT / "goga" / "assets" / "pipelines" / "feature-stages.yml"


class TestCompileFlowContract:
    """Contract tests — the public API declared by the compiler-cell CODEMANIFEST."""

    def test_compile_flow_importable_from_facade(self) -> None:
        """``compile_flow`` must be importable from the facade."""
        assert compile_flow is not None

    def test_compile_flow_signature(self) -> None:
        """``compile_flow`` takes exactly two parameters: ``pipeline_path``, ``flow_path``."""
        parameters = list(inspect.signature(compile_flow).parameters)

        assert parameters == ["pipeline_path", "flow_path"]

    def test_compile_flow_returns_none_on_minimal_valid_input(self, tmp_path: Path) -> None:
        """A minimal valid phases input compiles and the return value is ``None``."""
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text("name: N\ndescription: D\n---\n\n- name: a\n  description: A\n")
        flow_path = tmp_path / "flow.yml"

        result = compile_flow(pipeline_path, flow_path)

        assert result is None

    def test_private_helpers_not_on_facade(self) -> None:
        """``_canonical_fields`` and ``_CANONICAL_KEY_ORDER`` are module-internal, not facade names."""
        from goga.pipeline.compiler import __all__ as facade_all

        assert "_canonical_fields" not in facade_all
        assert "_CANONICAL_KEY_ORDER" not in facade_all


class TestCompileFlowLogic:
    """Behavioral tests against the documented algorithm and edge cases."""

    def test_compile_flow_phases_to_flow_document(self, tmp_path: Path) -> None:
        """A 2-step phases input yields a flow-file with position-derived depends_on."""
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text(
            "name: T\n"
            "description: T\n"
            "---\n"
            "\n"
            "- name: a\n"
            "  description: A\n"
            "  prompt: Do A\n"
            "- name: b\n"
            "  description: B\n"
            "  prompt: Do B\n",
        )
        flow_path = tmp_path / "flow.yml"

        compile_flow(pipeline_path, flow_path)

        loaded = yaml.safe_load(flow_path.read_text())

        assert loaded["name"] == "T"
        assert loaded["description"] == "T"
        assert [stage["id"] for stage in loaded["stages"]] == ["a", "b"]
        # First step has no depends_on (position 0); second depends on the first.
        assert "depends_on" not in loaded["stages"][0]
        assert loaded["stages"][1]["depends_on"] == ["a"]

    def test_compile_flow_stages_passes_through_depends_on(self, tmp_path: Path) -> None:
        """A 3-step stages input preserves the null / empty / list tristate verbatim."""
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text(
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
            "  depends_on: [a]\n",
        )
        flow_path = tmp_path / "flow.yml"

        compile_flow(pipeline_path, flow_path)

        stages = yaml.safe_load(flow_path.read_text())["stages"]

        # None (absent in source) → no depends_on key; [] → explicit empty; [a] → list.
        assert stages[0]["id"] == "a"
        assert "depends_on" not in stages[0]
        assert stages[1]["depends_on"] == []
        assert stages[2]["depends_on"] == ["a"]

    def test_compile_flow_idempotent(self, tmp_path: Path) -> None:
        """Compiling the same input twice produces byte-identical output."""
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text(_FEATURE_PHASES.read_text())
        flow_path = tmp_path / "flow.yml"

        compile_flow(pipeline_path, flow_path)
        first = flow_path.read_text()

        compile_flow(pipeline_path, flow_path)
        second = flow_path.read_text()

        assert first == second

    def test_compile_flow_empty_body_raises(self, tmp_path: Path) -> None:
        """An empty body segment (zero steps) raises StructuralError("empty body")."""
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text("name: T\ndescription: T\n---\n\n")
        flow_path = tmp_path / "flow.yml"

        with pytest.raises(StructuralError, match="empty body"):
            compile_flow(pipeline_path, flow_path)

    def test_compile_flow_pipeline_file_not_found_propagates(self, tmp_path: Path) -> None:
        """A missing pipeline_path raises FileNotFoundError unwrapped (no try/except)."""
        pipeline_path = tmp_path / "missing.yml"
        flow_path = tmp_path / "flow.yml"

        with pytest.raises(FileNotFoundError):
            compile_flow(pipeline_path, flow_path)

    def test_compile_flow_canonical_order_with_unknown_fields(self, tmp_path: Path) -> None:
        """Extras sort alphabetically after the known canonical keys."""
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text(
            "name: T\n"
            "description: T\n"
            "---\n"
            "\n"
            "- name: a\n"
            "  description: A\n"
            "  zebra: 1\n"
            "  apple: 2\n"
            "  interactive: true\n",
        )
        flow_path = tmp_path / "flow.yml"

        compile_flow(pipeline_path, flow_path)

        text = flow_path.read_text()

        # Canonical order: interactive (known), then apple, zebra (extras sorted).
        idx_interactive = text.index("interactive: true")
        idx_apple = text.index("apple: 2")
        idx_zebra = text.index("zebra: 1")

        assert idx_interactive < idx_apple < idx_zebra

    def test_compile_flow_phases_fixture_depends_on_chains(self, tmp_path: Path) -> None:
        """The canonical phases fixture compiles to a position-derived dependency chain."""
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text(_FEATURE_PHASES.read_text())
        flow_path = tmp_path / "flow.yml"

        compile_flow(pipeline_path, flow_path)

        stages = yaml.safe_load(flow_path.read_text())["stages"]

        # First stage carries no depends_on; every later stage depends on its predecessor's id.
        assert "depends_on" not in stages[0]
        for prev, curr in pairwise(stages):
            assert curr["depends_on"] == [prev["id"]]

    def test_compile_flow_stages_fixture_preserves_authored_depends_on(self, tmp_path: Path) -> None:
        """The canonical stages fixture passes authored depends_on through unchanged."""
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text(_FEATURE_STAGES.read_text())
        flow_path = tmp_path / "flow.yml"

        compile_flow(pipeline_path, flow_path)

        stages = yaml.safe_load(flow_path.read_text())["stages"]

        # First stage (propose) authored no depends_on; second (propose-review) depends on propose.
        assert stages[0]["id"] == "propose"
        assert "depends_on" not in stages[0]
        assert stages[1]["depends_on"] == ["propose"]

    def test_compile_flow_deep_copies_fields(self, tmp_path: Path) -> None:
        """``_canonical_fields`` deep-copies values — mutating the source body cannot reach the fields.

        Verified directly on the helper because ``compile_flow`` reads from disk and
        discards its parsed body before returning, so the isolation is not observable
        through the public ``compile_flow`` return value.
        """
        from goga.pipeline.compiler.compile_flow import _canonical_fields

        source_body = {"agents": ["planning"], "nested": {"k": 1}}
        fields = _canonical_fields(source_body)

        # Canonical order is established (``agents`` is a known key) and values match.
        assert list(fields.keys()) == ["agents", "nested"]
        assert fields["agents"] == ["planning"]

        # Mutating the ordered fields must not reach back into the source body
        # (genuine deep-copy isolation, not an alias to the source values).
        fields["agents"].append("hacked")
        fields["nested"]["extra"] = True

        assert source_body["agents"] == ["planning"]
        assert source_body["nested"] == {"k": 1}

    def test_compile_flow_missing_flow_path_parent_raises(self, tmp_path: Path) -> None:
        """A flow_path whose parent directory does not exist raises FileNotFoundError."""
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text("name: T\ndescription: T\n---\n\n- name: a\n  description: A\n")
        flow_path = tmp_path / "nonexistent_dir" / "flow.yml"

        with pytest.raises(FileNotFoundError):
            compile_flow(pipeline_path, flow_path)
