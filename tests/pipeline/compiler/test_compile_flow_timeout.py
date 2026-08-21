"""Contract and logic tests for the ``compile_flow`` stage timeout directive.

Covers the timeout half of step 5 (``_canonical_fields``): the authoring-side
string ``timeout`` stage-body directive (pipeline-file stage OR embedded
extend-stage body, including every loop-expanded copy) is validated and
translated into the output ``script_timeout`` slot of the assembled
``FlowStage``:

- ``timeout: "30m"`` with ``script`` in the same body → the flow stage carries
  ``script_timeout: 30m`` in the canonical slot immediately after
  ``script_after``;
- a non-string value (int/bool/null/list) → ``StructuralError`` naming the
  stage (``timeout: null`` counts as PRESENT non-string — unlike ``trigger``,
  whose null counts as absent);
- ``timeout`` without ``script`` (``before_script``/``after_script`` do not
  open the directive — ``script_timeout`` scopes to the script action) →
  ``StructuralError`` naming the stage;
- the value passes verbatim with no Go-duration grammar validation (a
  malformed string like ``"3 min"`` reaches the flow-file as-is; afm fails at
  runtime);
- the authoring key is consumed, never passed through as an unknown key; the
  output key is emitted only when authored (omitempty) — a pipeline without
  ``timeout`` compiles byte-identically;
- direct authoring of ``script_timeout`` is legal; when both ``timeout`` and a
  direct ``script_timeout`` are authored, the translated ``timeout`` value
  wins;
- loop-expanded copies inherit the translated value verbatim; the
  ``PipelineDocument`` mirror keeps the authored body (output-side only).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml
from goga.pipeline.compiler import StructuralError, compile_flow
from goga.pipeline.compiler.compile_flow import _CANONICAL_KEY_ORDER
from goga.pipeline.workflow import (
    WorkflowDocument,
    WorkflowExtendStage,
    parse_workflow,
)

_HEADER = "name: Feature\ndescription: Feature implementation\n---\n"


def _write(tmp_path: Path, body: str) -> Path:
    """Write a STAGES pipeline (or a PHASES list body) to a temp file and return its path."""
    pipeline_path = tmp_path / "pipeline.yml"
    pipeline_path.write_text(_HEADER + body)

    return pipeline_path


def _compile(tmp_path: Path, pipeline_text: str, workflow_text: str | None = None) -> str:
    """Write the pipeline (and optional workflow), compile, return the flow-file text."""
    pipeline_path = tmp_path / "pipeline.yml"
    pipeline_path.write_text(pipeline_text)
    flow_path = tmp_path / "flow.yml"

    workflow = None

    if workflow_text is not None:
        workflow_path = tmp_path / "workflow.yml"
        workflow_path.write_text(workflow_text)
        workflow = parse_workflow(workflow_path)

    compile_flow(pipeline_path, flow_path, workflow=workflow)

    return flow_path.read_text()


class TestTimeoutContract:
    """Contract tests — the timeout translation surface declared by the CODEMANIFEST."""

    def test_canonical_key_order_has_script_timeout_after_script_after(self) -> None:
        """``script_timeout`` occupies the canonical slot immediately after ``script_after``."""
        assert "script_timeout" in _CANONICAL_KEY_ORDER
        assert _CANONICAL_KEY_ORDER.index("script_timeout") == _CANONICAL_KEY_ORDER.index("script_after") + 1

    def test_compile_timeout_translates_to_script_timeout(self, tmp_path: Path) -> None:
        """A ``{script, timeout}`` body compiles to a ``script_timeout`` field.

        The authoring ``timeout`` key is consumed by the translation — it never
        reaches ``FlowStage.fields`` (nor the flow-file) as an unknown key.
        """
        pipeline_path = _write(tmp_path, "build:\n  title: Build\n  script: make test\n  timeout: 30m\n")
        flow_path = tmp_path / "flow.yml"

        _pipeline_doc, flow_doc = compile_flow(pipeline_path, flow_path)

        assert flow_doc.stages[0].fields["script_timeout"] == "30m"
        assert "timeout" not in flow_doc.stages[0].fields


class TestTimeoutTranslation:
    """Step 5 — timeout validation and ``script_timeout`` translation across body sources."""

    def test_timeout_translates_to_script_timeout_in_canonical_slot(self, tmp_path: Path) -> None:
        """The translated value lands in the canonical slot right after the script family.

        ``agents`` is injected by default and sits BEFORE the script family, so
        a minimal ``{title, script, timeout}`` body assembles
        ``[agents, script, script_timeout]`` and the flow-file prints the
        script before its timeout.
        """
        flow_text = _compile(
            tmp_path,
            _HEADER + "build:\n" + "  title: Build\n" + "  script: make test\n" + "  timeout: 30m\n",
        )

        assert "script: make test" in flow_text
        assert "script_timeout: 30m" in flow_text
        assert flow_text.index("script:") < flow_text.index("script_timeout:")

        _pipeline_doc, flow_doc = compile_flow(
            _write(tmp_path, "build:\n  title: Build\n  script: make test\n  timeout: 30m\n"),
            tmp_path / "flow2.yml",
        )

        assert flow_doc.stages[0].fields == {"script": "make test", "script_timeout": "30m"}
        assert list(flow_doc.stages[0].fields) == ["script", "script_timeout"]

    def test_timeout_full_script_family_canonical_order(self, tmp_path: Path) -> None:
        """The whole script family sits contiguously, immediately after ``agents``.

        ``before_script``/``script``/``after_script``/``timeout`` in one body
        assembles ``[agents, script_before, script, script_after,
        script_timeout]`` — the translated timeout closes the family.
        """
        _pipeline_doc, flow_doc = compile_flow(
            _write(
                tmp_path,
                "build:\n"
                "  title: Build\n"
                "  before_script: echo a\n"
                "  script: make\n"
                "  after_script: echo b\n"
                "  timeout: 5m\n",
            ),
            tmp_path / "flow.yml",
        )

        assert list(flow_doc.stages[0].fields) == [
            "script_before",
            "script",
            "script_after",
            "script_timeout",
        ]

    def test_timeout_loop_expansion_every_copy_inherits(self, tmp_path: Path) -> None:
        """Every loop-expanded copy ``NAME-i`` carries its own ``script_timeout``.

        The body is deep-copied per copy, so each expanded stage re-runs the
        translation on an identical body and inherits the value verbatim.
        """
        flow_text = _compile(
            tmp_path,
            _HEADER + "test:\n" + "  title: Test\n" + "  script: go test ./...\n" + "  timeout: 10m\n",
            "stages:\n  test:\n    loop: 2\n",
        )

        stages = yaml.safe_load(flow_text)["stages"]

        assert [stage["id"] for stage in stages] == ["test-1", "test-2"]
        assert stages[0]["script_timeout"] == "10m"
        assert stages[1]["script_timeout"] == "10m"

    def test_timeout_loop_copy_structural_error_names_expanded_stage(self, tmp_path: Path) -> None:
        """A structural error inside a loop-expanded copy names the copy
        (``test-1``), not the base stage — the validation re-runs per copy."""
        with pytest.raises(StructuralError, match=r"timeout must be a string in stage test-1"):
            _compile(
                tmp_path,
                _HEADER + "test:\n" + "  title: Test\n" + "  script: go test ./...\n" + "  timeout: 5\n",
                "stages:\n  test:\n    loop: 2\n",
            )

    def test_compile_timeout_multiline_value_block_literal_in_flow_file(self, tmp_path: Path) -> None:
        """A multi-line timeout travels through the compile→serialize seam and
        takes the script-family block-literal style in the written flow-file
        (the authored `|` block keeps its trailing newline — verbatim)."""
        flow_text = _compile(
            tmp_path,
            _HEADER + "build:\n  title: Build\n  script: make\n  timeout: |\n    a\n    b\n",
        )

        assert "script_timeout: |" in flow_text
        assert yaml.safe_load(flow_text)["stages"][0]["script_timeout"] == "a\nb\n"

    def test_timeout_extend_stage_body_translates(self, tmp_path: Path) -> None:
        """An embedded extend-stage body runs through the same translation pass.

        ``_canonical_fields`` is the single translation site: the extend body's
        ``timeout`` is consumed and its ``script`` keeps its authored value.
        """
        _pipeline_doc, flow_doc = compile_flow(
            _write(tmp_path, "build:\n  title: Build\n  script: make\n"),
            tmp_path / "flow.yml",
            workflow=WorkflowDocument(
                extend={
                    "lint": WorkflowExtendStage(
                        after=["build"],
                        body={"title": "Lint", "script": "ruff check .", "timeout": "3m"},
                    ),
                },
            ),
        )

        lint = next(stage for stage in flow_doc.stages if stage.id == "lint")

        assert lint.fields["script_timeout"] == "3m"
        assert lint.fields["script"] == "ruff check ."

    def test_compile_timeout_phases_format_translates(self, tmp_path: Path) -> None:
        """The PHASES list body translates identically — the directive is format-agnostic."""
        _pipeline_doc, flow_doc = compile_flow(
            _write(
                tmp_path,
                "- name: build\n  title: Build\n  script: make\n  timeout: 20m\n",
            ),
            tmp_path / "flow.yml",
        )

        assert flow_doc.stages[0].fields["script_timeout"] == "20m"

    def test_compile_timeout_without_script_raises(self, tmp_path: Path) -> None:
        """``timeout`` without ``script`` is a structural error naming the stage.

        ``script_timeout`` scopes to the script action — a prompt-only stage
        cannot carry it.
        """
        with pytest.raises(StructuralError, match=r"timeout requires script in stage build"):
            compile_flow(
                _write(tmp_path, "build:\n  title: Build\n  prompt: do\n  timeout: 30m\n"),
                tmp_path / "flow.yml",
            )

    def test_compile_timeout_before_script_only_raises(self, tmp_path: Path) -> None:
        """``before_script`` does not open the directive — only ``script`` does."""
        with pytest.raises(StructuralError, match=r"timeout requires script in stage"):
            compile_flow(
                _write(tmp_path, "build:\n  title: Build\n  before_script: echo\n  timeout: 1m\n"),
                tmp_path / "flow.yml",
            )

    @pytest.mark.parametrize("timeout_value", ["30", "true", '["30m"]'])
    def test_compile_timeout_non_string_raises(self, tmp_path: Path, timeout_value: str) -> None:
        """A non-string ``timeout`` (int/bool/list) is a structural error naming the stage."""
        with pytest.raises(StructuralError, match=r"timeout must be a string in stage build"):
            compile_flow(
                _write(tmp_path, f"build:\n  title: Build\n  script: s\n  timeout: {timeout_value}\n"),
                tmp_path / "flow.yml",
            )

    def test_compile_timeout_null_raises_non_string(self, tmp_path: Path) -> None:
        """``timeout:`` (YAML-null) counts as PRESENT non-string — unlike ``trigger``.

        The trigger directive gates on the VALUE (null ⇒ absent); the timeout
        directive gates on key PRESENCE — a null is a present non-string and
        raises, mirroring the divergence pinned by the contract.
        """
        with pytest.raises(StructuralError, match=r"timeout must be a string in stage build"):
            compile_flow(
                _write(tmp_path, "build:\n  title: Build\n  script: s\n  timeout:\n"),
                tmp_path / "flow.yml",
            )

    def test_compile_timeout_authoring_key_not_leaked(self, tmp_path: Path) -> None:
        """The authoring ``timeout`` key never reaches the flow-file as a stage key.

        The raw text check needs a negative lookbehind: ``timeout:`` is a
        substring of ``script_timeout:``, so a plain substring test would
        always fail. An unknown key still passes through alphabetically.
        """
        flow_text = _compile(
            tmp_path,
            _HEADER + "build:\n" + "  title: Build\n" + "  script: s\n" + "  timeout: 30m\n" + "  custom: u\n",
        )

        stage = yaml.safe_load(flow_text)["stages"][0]

        assert "timeout" not in stage
        assert "script_timeout" in stage
        assert re.search(r"(?<![\w])timeout:", flow_text) is None
        # Unknown keys keep flowing through alphabetically, as before.
        assert stage["custom"] == "u"

    def test_compile_timeout_omitempty_and_byte_identical_without_directive(self, tmp_path: Path) -> None:
        """A pipeline without ``timeout`` compiles without any ``script_timeout`` key.

        The omitempty contract: no directive ⇒ no key anywhere in the output,
        so timeout-free pipelines compile byte-identically to before the
        feature (the shipped-pipelines guard covers the full asset set).
        """
        flow_text = _compile(
            tmp_path,
            _HEADER + "build:\n" + "  title: Build\n" + "  script: make\n" + "  after_script: echo done\n",
        )

        assert "script_timeout" not in flow_text
        stage = yaml.safe_load(flow_text)["stages"][0]
        assert list(stage) == ["id", "name", "script", "script_after"]

    @pytest.mark.parametrize(
        ("body", "expected"),
        [
            ("build:\n  title: Build\n  script: s\n  script_timeout: 1h\n", "1h"),
            ("build:\n  title: Build\n  script: s\n  timeout: 30m\n  script_timeout: 1h\n", "30m"),
        ],
    )
    def test_compile_direct_script_timeout_passes_and_timeout_wins(
        self,
        tmp_path: Path,
        body: str,
        expected: str,
    ) -> None:
        """Direct ``script_timeout`` authoring is legal; a translated ``timeout`` wins.

        Case (a) — a direct key passes into the canonical slot unvalidated (the
        same stance as direct ``script_before``). Case (b) — when both are
        authored, the translated ``timeout`` value overwrites the direct one.
        """
        _pipeline_doc, flow_doc = compile_flow(_write(tmp_path, body), tmp_path / "flow.yml")

        assert flow_doc.stages[0].fields["script_timeout"] == expected

    def test_compile_timeout_malformed_duration_passes_verbatim(self, tmp_path: Path) -> None:
        """The Go duration grammar is afm's concern — a malformed string passes as-is."""
        _pipeline_doc, flow_doc = compile_flow(
            _write(tmp_path, "build:\n  title: Build\n  script: s\n  timeout: 3 min\n"),
            tmp_path / "flow.yml",
        )

        assert flow_doc.stages[0].fields["script_timeout"] == "3 min"
        assert "script_timeout: 3 min" in (tmp_path / "flow.yml").read_text()

    def test_compile_timeout_empty_string_translates_verbatim(self, tmp_path: Path) -> None:
        """``timeout: ""`` is a present string — the gate is presence, not truthiness.

        The empty string survives the round-trip through the flow-file, pinning
        the ``has_timeout`` check against an accidental ``if timeout_value:``.
        """
        _pipeline_doc, flow_doc = compile_flow(
            _write(tmp_path, 'build:\n  title: Build\n  script: s\n  timeout: ""\n'),
            tmp_path / "flow.yml",
        )

        assert flow_doc.stages[0].fields["script_timeout"] == ""
        assert yaml.safe_load((tmp_path / "flow.yml").read_text())["stages"][0]["script_timeout"] == ""

    def test_compile_timeout_script_exclusivity_error_precedes_timeout_error(self, tmp_path: Path) -> None:
        """With two violations, the exclusivity check fires first — deterministic order.

        ``script + prompt`` and a non-string ``timeout`` both fail; the
        contract fixes exclusivity as the first check, so its message is the
        one raised.
        """
        with pytest.raises(StructuralError, match=r"script is mutually exclusive with prompt/skills"):
            compile_flow(
                _write(tmp_path, "build:\n  title: Build\n  script: s\n  prompt: p\n  timeout: 5\n"),
                tmp_path / "flow.yml",
            )

    def test_timeout_pipeline_document_body_untouched(self, tmp_path: Path) -> None:
        """The ``PipelineDocument`` mirror keeps the authored body verbatim.

        ``timeout`` stays, ``script_timeout`` never appears — the translation
        is local to ``FlowStage.fields`` assembly (output-side only).
        """
        pipeline_doc, flow_doc = compile_flow(
            _write(tmp_path, "build:\n  title: Build\n  script: s\n  timeout: 30m\n"),
            tmp_path / "flow.yml",
        )

        assert pipeline_doc.body.steps[0].body["timeout"] == "30m"
        assert "script_timeout" not in pipeline_doc.body.steps[0].body
        assert flow_doc.stages[0].fields["script_timeout"] == "30m"
        assert "timeout" not in flow_doc.stages[0].fields
