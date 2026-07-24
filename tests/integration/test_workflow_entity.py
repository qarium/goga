"""End-to-end integration tests for the ``workflow-entity`` feature.

These stitch together the full cross-cell chain introduced by
``workflow-entity``:

    goga/pipeline/workflow/parse_workflow.py  (leaf — declarative parser)
        -> goga/pipeline/compiler/compile_flow.py  (body reconstruction)
            -> goga/commands/pipeline/...           (host-side CLI + launcher)

The boundary exercised is the workflow contract surfaced through the facades:
``parse_workflow`` reads a project workflow-file into a pure declarative
``WorkflowDocument``; ``compile_flow`` consumes that document to reconstruct the
parsed pipeline body (per-stage ``command``/``description`` overrides,
``NAME-1``..``NAME-N`` loop-expansion, and external ``depends_on`` rewrite to
the LAST expanded id); and the ``goga pipeline`` click command + real launcher
turn an explicit ``--workflow`` flag into the in-container env-file entry
(``GOGA_WORKFLOW_NAME``) plus the host-side workflow log line.

The tests reference the project fixtures under ``.goga/`` directly (read-only)
so the integration scenarios exercise the real authored pipeline/workflow files.
The docker/subprocess boundary is mocked per
``[[feedback_mock_patch_module_shadowing]]``: the package ``__init__`` re-exports
submodule functions, which shadows string-based ``mock.patch`` paths on Python
3.10, so the real modules are resolved via ``sys.modules`` and patched by
attribute.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest
import yaml
from click.testing import CliRunner
from goga.commands.pipeline import pipeline
from goga.config import BuildConfig, PipelineConfig, ProjectConfig, TaskExecutorConfig
from goga.pipeline.compiler import StructuralError, compile_flow
from goga.pipeline.workflow import WorkflowDocument, WorkflowStage, parse_workflow

# The reference fixtures live under tests/integration/fixtures/ — authored
# pipeline/workflow YAML reused across the integration scenarios below.
_FIXTURES = Path(__file__).resolve().parent / "fixtures"
_FEATURE_PHASES_PIPELINE = _FIXTURES / "feature-phases.yml"
_FEATURE_STAGES_PIPELINE = _FIXTURES / "feature-stages.yml"
_FEATURE_WORKFLOW = _FIXTURES / "feature-phases.workflow.yml"

# goga.commands.pipeline.run_pipeline_container shadows its submodule name in the
# package __init__, so resolve the real module via sys.modules for attribute
# monkeypatching of the host-side helpers (mirrors the sibling test modules).
_rpc_mod = sys.modules["goga.commands.pipeline.run_pipeline_container"]


def _stage_by_id(stages: list[dict[str, object]], stage_id: str) -> dict[str, object]:
    """Return the single flow stage whose ``id`` equals ``stage_id``.

    Args:
        stages: The deserialized ``stages`` list from a compiled flow-file.
        stage_id: The stage id to match.

    Returns:
        The matching stage dict.

    Raises:
        AssertionError: If no stage or more than one stage matches (an
            ambiguous match would silently mask a miscompile).
    """
    matches = [stage for stage in stages if stage["id"] == stage_id]
    assert len(matches) == 1, f"expected exactly one stage {stage_id!r}, got {len(matches)}"
    return matches[0]


# --- Item 1 — feature-phases end-to-end compile (workflow -> compiler) ---


class TestFeaturePhasesEndToEndCompile:
    """The reference ``feature-phases`` fixtures compiled together end-to-end."""

    def test_feature_phases_compile_applies_overrides_and_loop_expansion(self, tmp_path: Path) -> None:
        """``parse_workflow`` + ``compile_flow`` apply overrides, expansion, and rewriting.

        The reference ``feature-phases`` workflow sets a top-level ``prompt``, an
        ``agent``+``prompt`` override on ``propose`` (→ ``command`` +
        ``description`` slots), and a ``loop: 2`` + ``agent`` on ``propose-review``.
        Compiling the reference PHASES pipeline with it yields:

        - ``propose`` gains ``command: /home/goga/bin/codex-as-claude.sh`` and a
          ``description`` slot carrying the workflow prompt;
        - ``propose-review`` expands into ``propose-review-1`` / ``propose-review-2``,
          each carrying the ``claude`` wrapper path in ``command``;
        - the PHASES position chain makes the next original step (``brainstorm``)
          depend on the LAST expanded id (``propose-review-2``);
        - the workflow top-level ``prompt`` is emitted as the first flow-file key.
        """
        flow_path = tmp_path / "flow.yml"
        workflow = parse_workflow(_FEATURE_WORKFLOW)

        pipeline_doc, flow_doc = compile_flow(_FEATURE_PHASES_PIPELINE, flow_path, workflow=workflow)

        # The ORIGINAL pipeline body is untouched — reconstruction lives only in
        # FlowDocument.stages.
        original_names = [step.name for step in pipeline_doc.body.steps]
        assert "propose-review" in original_names
        assert "propose-review-1" not in original_names

        # The workflow top-level prompt is carried through and serialized first.
        assert flow_doc.prompt is not None
        assert "Example prompt" in flow_doc.prompt

        text = flow_path.read_text()
        assert text.startswith("prompt: |")

        stages = yaml.safe_load(text)["stages"]
        ids = [stage["id"] for stage in stages]

        # Per-stage override on `propose`.
        propose = _stage_by_id(stages, "propose")
        assert propose["command"] == "/home/goga/bin/codex-as-claude.sh"
        assert propose["description"] == "Additional prompt\n"

        # Loop-expansion of `propose-review` (loop=2).
        assert "propose-review" not in ids
        assert "propose-review-1" in ids
        assert "propose-review-2" in ids
        propose_review_1 = _stage_by_id(stages, "propose-review-1")
        propose_review_2 = _stage_by_id(stages, "propose-review-2")
        # The agent override applies to every expanded copy.
        assert propose_review_1["command"] == "/home/goga/bin/claude-as-claude.sh"
        assert propose_review_2["command"] == "/home/goga/bin/claude-as-claude.sh"

        # PHASES position-derived chain — the copies and the next original step
        # chain to the LAST expanded id.
        assert propose_review_1["depends_on"] == ["propose"]
        assert propose_review_2["depends_on"] == ["propose-review-1"]
        brainstorm = _stage_by_id(stages, "brainstorm")
        assert brainstorm["depends_on"] == ["propose-review-2"]


# --- Item 2 — feature-stages STAGES-format loop-expansion + external rewrite ---


class TestFeatureStagesLoopExpansion:
    """STAGES-format loop-expansion rewrites external refs to the LAST id (5c)."""

    def test_feature_stages_loop_expansion_rewrites_to_last_expanded_id(self, tmp_path: Path) -> None:
        """STAGES loop-expansion rewrites downstream external refs to the LAST id.

        The reference ``feature-stages`` pipeline is STAGES-format with authored
        ``depends_on`` (``brainstorm`` → ``propose-review``). Expanding
        ``propose-review`` (loop=2) yields ``propose-review-1`` / ``propose-review-2``
        with the first copy inheriting the original external dep and the second
        chaining to it; every downstream reference to ``propose-review`` is
        rewritten to the LAST expanded id ``propose-review-2`` — the STAGES-only
        5c rewrite that distinguishes this format from PHASES position chaining.
        """
        flow_path = tmp_path / "flow.yml"
        workflow = WorkflowDocument(stages={"propose-review": WorkflowStage(loop=2)})

        compile_flow(_FEATURE_STAGES_PIPELINE, flow_path, workflow=workflow)

        stages = yaml.safe_load(flow_path.read_text())["stages"]
        ids = [stage["id"] for stage in stages]

        # The looped stage is expanded; non-looped stages keep their original ids.
        assert "propose-review" not in ids
        assert "propose-review-1" in ids
        assert "propose-review-2" in ids

        # The FIRST expanded copy inherits the original external depends_on.
        propose_review_1 = _stage_by_id(stages, "propose-review-1")
        assert propose_review_1["depends_on"] == ["propose"]
        # The second copy chains to the previous copy (internal chain).
        propose_review_2 = _stage_by_id(stages, "propose-review-2")
        assert propose_review_2["depends_on"] == ["propose-review-1"]

        # The downstream `brainstorm` (authored depends_on: [propose-review]) is
        # rewritten to the LAST expanded id — the STAGES-only 5c external rewrite.
        brainstorm = _stage_by_id(stages, "brainstorm")
        assert brainstorm["depends_on"] == ["propose-review-2"]
        # A non-expanded predecessor reference is kept as-is (no spurious rewrite).
        brainstorm_review = _stage_by_id(stages, "brainstorm-review")
        assert brainstorm_review["depends_on"] == ["brainstorm"]


# --- Item 4 — ``extend`` directive end-to-end (workflow-file -> compiler) ---


def _write_stages_pipeline(tmp_path: Path) -> Path:
    """Write a minimal STAGES pipeline (propose -> review) and return its path.

    Args:
        tmp_path: Project root used as the working directory for the test.

    Returns:
        The path to the freshly written pipeline-file.
    """
    pipeline_path = tmp_path / "pipeline-stages.yml"
    pipeline_path.write_text(
        "name: T\n"
        "description: T\n"
        "---\n"
        "\n"
        "propose:\n"
        "  title: Propose\n"
        "review:\n"
        "  title: Review\n"
        "  depends_on: [propose]\n",
    )
    return pipeline_path


def _write_phases_pipeline(tmp_path: Path) -> Path:
    """Write a 3-step PHASES pipeline (a, b, c) and return its path.

    Args:
        tmp_path: Project root used as the working directory for the test.

    Returns:
        The path to the freshly written pipeline-file.
    """
    pipeline_path = tmp_path / "pipeline-phases.yml"
    pipeline_path.write_text(
        "name: T\ndescription: T\n---\n\n- name: a\n  title: A\n- name: b\n  title: B\n- name: c\n  title: C\n",
    )
    return pipeline_path


def _write_workflow(tmp_path: Path, body: str) -> Path:
    """Write a workflow-file carrying ``body`` and return its path.

    Args:
        tmp_path: Project root used as the working directory for the test.
        body: The raw YAML body of the workflow-file.

    Returns:
        The path to the freshly written workflow-file.
    """
    workflow_path = tmp_path / "workflow.yml"
    workflow_path.write_text(body)
    return workflow_path


class TestExtendDirectiveEndToEnd:
    """The ``extend`` directive exercised across the workflow -> compiler boundary.

    An authored workflow-file carries an ``extend`` map; ``parse_workflow``
    materialises it into ``WorkflowDocument.extend`` and ``compile_flow`` embeds
    the extend-stages into ``FlowDocument.stages`` (never the original
    ``PipelineDocument.body``). Unlike the cell-local logic tests (which build a
    ``WorkflowDocument`` in memory), these scenarios drive the full chain through
    real workflow-files so the parser-to-compiler handoff is exercised on authored
    YAML.
    """

    def test_stages_extend_after_compiles_depends_on(self, tmp_path: Path) -> None:
        """A STAGES extend ``after`` entry reaches the flow-file as a dependency.

        A workflow-file ``extend: {extra: {after: [review], title: Extra}}`` parsed
        and compiled against the STAGES propose->review pipeline yields a flow-file
        whose stages are [propose, review, extra] with ``extra`` depending on
        ``review`` and the authored review->propose dependency preserved.
        """
        pipeline_path = _write_stages_pipeline(tmp_path)
        workflow_path = _write_workflow(
            tmp_path,
            "extend:\n  extra:\n    after: [review]\n    title: Extra\n",
        )
        flow_path = tmp_path / "flow.yml"

        workflow = parse_workflow(workflow_path)
        compile_flow(pipeline_path, flow_path, workflow=workflow)

        stages = yaml.safe_load(flow_path.read_text())["stages"]
        ids = [stage["id"] for stage in stages]
        assert ids == ["propose", "review", "extra"]
        extra = _stage_by_id(stages, "extra")
        assert extra["depends_on"] == ["review"]
        review = _stage_by_id(stages, "review")
        assert review["depends_on"] == ["propose"]

    def test_stages_extend_before_appends_to_target(self, tmp_path: Path) -> None:
        """A STAGES extend ``before`` entry appends the new stage to the target's deps.

        A workflow-file ``extend: {warmup: {before: [propose], title: Warmup}}``
        yields a flow-file where ``propose`` depends on ``warmup``.
        """
        pipeline_path = _write_stages_pipeline(tmp_path)
        workflow_path = _write_workflow(
            tmp_path,
            "extend:\n  warmup:\n    before: [propose]\n    title: Warmup\n",
        )
        flow_path = tmp_path / "flow.yml"

        workflow = parse_workflow(workflow_path)
        compile_flow(pipeline_path, flow_path, workflow=workflow)

        stages = yaml.safe_load(flow_path.read_text())["stages"]
        propose = _stage_by_id(stages, "propose")
        assert propose["depends_on"] == ["warmup"]

    def test_phases_extend_after_inserts_positionally(self, tmp_path: Path) -> None:
        """A PHASES extend ``after`` entry inserts positionally with derived deps.

        A workflow-file ``extend: {x: {after: [b], title: X}}`` parsed and compiled
        against the PHASES [a, b, c] pipeline yields [a, b, x, c] where x depends on
        b and c depends on x by list position.
        """
        pipeline_path = _write_phases_pipeline(tmp_path)
        workflow_path = _write_workflow(
            tmp_path,
            "extend:\n  x:\n    after: [b]\n    title: X\n",
        )
        flow_path = tmp_path / "flow.yml"

        workflow = parse_workflow(workflow_path)
        compile_flow(pipeline_path, flow_path, workflow=workflow)

        stages = yaml.safe_load(flow_path.read_text())["stages"]
        ids = [stage["id"] for stage in stages]
        assert ids == ["a", "b", "x", "c"]
        x = _stage_by_id(stages, "x")
        c = _stage_by_id(stages, "c")
        assert x["depends_on"] == ["b"]
        assert c["depends_on"] == ["x"]

    def test_title_fallback_uses_extend_stage_name(self, tmp_path: Path) -> None:
        """An extend-entry without ``title`` falls back to its name as display label.

        A workflow-file ``extend: {warmup: {before: [propose]}}`` (no title) yields
        a flow-file stage ``warmup`` whose display ``name`` is the extend-stage name.
        """
        pipeline_path = _write_stages_pipeline(tmp_path)
        workflow_path = _write_workflow(
            tmp_path,
            "extend:\n  warmup:\n    before: [propose]\n",
        )
        flow_path = tmp_path / "flow.yml"

        workflow = parse_workflow(workflow_path)
        compile_flow(pipeline_path, flow_path, workflow=workflow)

        stages = yaml.safe_load(flow_path.read_text())["stages"]
        warmup = _stage_by_id(stages, "warmup")
        assert warmup["name"] == "warmup"

    def test_workflow_without_extend_matches_no_workflow_stages(self, tmp_path: Path) -> None:
        """A workflow-file with no ``extend`` compiles to the same stages as workflow=None.

        Parsing a workflow-file that carries no ``extend`` key yields a
        ``WorkflowDocument.extend`` that is the empty default map; compiling it
        embeds no extend-stage and the resulting stages match the no-workflow path.
        Only the ``stages`` list is compared — the workflow path additionally emits
        its top-level ``prompt``, which the no-workflow path does not.
        """
        pipeline_path = _write_stages_pipeline(tmp_path)
        workflow_path = _write_workflow(tmp_path, "prompt: |\n  Drive the pipeline\n")
        flow_path = tmp_path / "flow.yml"
        flow_path_none = tmp_path / "flow-none.yml"

        workflow = parse_workflow(workflow_path)
        assert workflow.extend == {}

        compile_flow(pipeline_path, flow_path, workflow=workflow)
        compile_flow(pipeline_path, flow_path_none)

        stages = yaml.safe_load(flow_path.read_text())["stages"]
        stages_none = yaml.safe_load(flow_path_none.read_text())["stages"]
        ids = [stage["id"] for stage in stages]
        assert ids == [stage["id"] for stage in stages_none] == ["propose", "review"]
        review = _stage_by_id(stages, "review")
        review_none = _stage_by_id(stages_none, "review")
        assert review["depends_on"] == review_none["depends_on"] == ["propose"]
        assert all("extend" not in stage for stage in stages)

    def test_extend_populates_document_and_embeds_only_in_flow(self, tmp_path: Path) -> None:
        """Cross-entity: parsed extend reaches FlowDocument.stages, not PipelineDocument.body.

        A workflow-file with an ``extend`` block parses into a ``WorkflowDocument``
        whose ``extend`` map is populated with the authored entry;
        ``compile_flow`` embeds the extend-stage into ``FlowDocument.stages`` while
        the ``PipelineDocument.body`` carries only the original parsed steps.
        """
        pipeline_path = _write_stages_pipeline(tmp_path)
        workflow_path = _write_workflow(
            tmp_path,
            "extend:\n  extra:\n    after: [review]\n    title: Extra\n",
        )
        flow_path = tmp_path / "flow.yml"

        workflow = parse_workflow(workflow_path)
        assert set(workflow.extend) == {"extra"}
        assert workflow.extend["extra"].after == ["review"]

        pipeline_doc, flow_doc = compile_flow(pipeline_path, flow_path, workflow=workflow)

        # The ORIGINAL parsed body never carries the extend-stage.
        assert [step.name for step in pipeline_doc.body.steps] == ["propose", "review"]
        # The extend-stage is embedded only in the compiled FlowDocument.stages.
        assert [stage.id for stage in flow_doc.stages] == ["propose", "review", "extra"]

    def test_stages_extend_dangling_after_ref_rejected_at_compile(self, tmp_path: Path) -> None:
        """A dangling STAGES extend ``after`` ref is rejected at compile time.

        A workflow-file ``extend: {x: {after: [ghost], title: X}}`` (ghost unknown)
        raises a ``StructuralError`` from ``compile_flow`` — strict validation
        (4a0-pre) rejects the dangling ref up front; it no longer reaches the
        flow-file verbatim. End-to-end: ``parse_workflow`` → ``compile_flow``.
        """
        pipeline_path = _write_stages_pipeline(tmp_path)
        workflow_path = _write_workflow(
            tmp_path,
            "extend:\n  x:\n    after: [ghost]\n    title: X\n",
        )
        flow_path = tmp_path / "flow.yml"

        workflow = parse_workflow(workflow_path)
        with pytest.raises(
            StructuralError,
            match=r"unknown stage name in workflow\.extend\.x\.after: ghost",
        ):
            compile_flow(pipeline_path, flow_path, workflow=workflow)


# --- Item 3 — full CLI invocation -> launcher workflow layer + env-file ---


def _make_config(
    *,
    pipeline_agent: str = "claude",
) -> ProjectConfig:
    """Build a minimal ProjectConfig with a pipeline section for run-mode dispatch."""
    return ProjectConfig(
        lang="python",
        image="qarium/goga:latest",
        dockerfile=None,
        build=BuildConfig(task_executor=TaskExecutorConfig(agent="claude")),
        pipeline=PipelineConfig(agent=pipeline_agent, env={}),
    )


def _write_project(tmp_path: Path) -> None:
    """Materialize a minimal ``.goga`` tree: config.yml + the feature-phases workflow.

    Args:
        tmp_path: Project root used as the working directory for the test.
    """
    goga_dir = tmp_path / ".goga"
    goga_dir.mkdir(parents=True, exist_ok=True)
    (goga_dir / "config.yml").write_text(
        "\n".join(
            [
                "language: python",
                "image: qarium/goga:latest",
                "build:",
                "  task_executor:",
                "    agent: claude",
                "pipeline:",
                "  agent: claude",
            ]
        )
        + "\n"
    )
    # Copy the reference workflow-file so the host-side existence check (step 6)
    # passes and the launcher resolves ``GOGA_WORKFLOW_NAME=feature-phases``.
    workflows_dir = goga_dir / "workflows"
    workflows_dir.mkdir(parents=True, exist_ok=True)
    (workflows_dir / "feature-phases.yml").write_text(_FEATURE_WORKFLOW.read_text())


def _mock_docker_internals(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mock docker side effects so the real launcher runs without docker.

    ``_check_docker`` → True; ``_allocate_port`` → fixed; git identity → empty;
    docker launch subprocesses → a no-op process whose ``wait`` returns 0. The
    launcher's workflow layer (steps 9-11) still runs for real, so the workflow
    log line is emitted and the env-file entries are written.
    """
    monkeypatch.setattr(_rpc_mod, "_check_docker", lambda: True)
    monkeypatch.setattr(_rpc_mod, "_allocate_port", lambda: 50401)
    monkeypatch.setattr(_rpc_mod, "_read_git_config", lambda: {})
    mock_proc = mock.Mock()
    mock_proc.wait.return_value = 0
    monkeypatch.setattr(subprocess, "Popen", lambda *_a, **_k: mock_proc)
    monkeypatch.setattr(subprocess, "run", lambda *_a, **_k: mock.Mock())


def _capture_env(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    """Monkeypatch ``_write_env_file`` to capture the env dict it is handed."""
    captured: dict[str, str] = {}
    real_write = _rpc_mod._write_env_file

    def capture(env: dict[str, str], extra_env: tuple[str, ...] = ()) -> Path:
        captured.update(env)
        return real_write(env, extra_env)

    monkeypatch.setattr(_rpc_mod, "_write_env_file", capture)
    return captured


class TestPipelineCommandWorkflowIntegration:
    """``goga pipeline deploy --workflow`` drives the real launcher workflow layer."""

    def test_pipeline_command_feature_phases_emits_log_line_and_env_entry(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``--workflow feature-phases`` emits the log line and the env-file entry.

        The CLI command validates ``<cwd>/.goga/workflows/feature-phases.yml``
        exists (step 6) then dispatches into the REAL launcher with docker
        internals mocked (no real container), so the workflow layer (steps 9-11)
        genuinely runs: step 9 resolves
        ``workflow_env={"GOGA_WORKFLOW_NAME": "feature-phases"}`` /
        ``workflow_log_name="feature-phases"``; step 10 emits the log line; step
        11 writes the env-file entry. The dashboard URL line stays absent.
        """
        _write_project(tmp_path)
        monkeypatch.chdir(tmp_path)
        _mock_docker_internals(monkeypatch)
        captured = _capture_env(monkeypatch)

        runner = CliRunner()
        result = runner.invoke(pipeline, ["deploy", "--workflow", "feature-phases"])

        assert result.exit_code == 0
        assert 'Pipeline running with workflow "feature-phases"' in result.output
        assert captured["GOGA_WORKFLOW_NAME"] == "feature-phases"
        assert "GOGA_WORKFLOW_DISABLED" not in captured
        # The dashboard URL line was removed from this cell entirely.
        assert "Web UI:" not in result.output

    def test_pipeline_command_feature_phases_forwards_env_file_to_docker(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The workflow env-file reaches the ``docker run`` argv (full handoff).

        Distinct from the log-line/env-entry sibling: this pins the FULL cross-cell
        handoff from the CLI flag through the launcher's workflow decision matrix
        into the actual ``docker run`` argv. The launcher writes a private env-file
        carrying ``GOGA_WORKFLOW_NAME=feature-phases`` and forwards it to docker via
        ``--env-file <path>``; the mocked ``subprocess.Popen`` captures that argv so
        we can prove the workflow name rides all the way to the container boundary
        (no real docker daemon required). The env-file is read at launch time
        because the launcher unlinks it in its finally block once the run returns.
        """
        _write_project(tmp_path)
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(_rpc_mod, "_check_docker", lambda: True)
        monkeypatch.setattr(_rpc_mod, "_allocate_port", lambda: 50401)
        monkeypatch.setattr(_rpc_mod, "_read_git_config", lambda: {})

        captured_argv: list[list[str]] = []
        captured_env_contents: list[str] = []
        mock_proc = mock.Mock()
        mock_proc.wait.return_value = 0

        def capture_popen(argv: list[str], *_a: object, **_k: object) -> object:
            captured_argv.append(list(argv))
            # Read the env-file NOW — the launcher's finally unlinks it post-run.
            for i, token in enumerate(argv):
                env_path = None
                if token == "--env-file" and i + 1 < len(argv):
                    env_path = argv[i + 1]
                elif token.startswith("--env-file="):
                    env_path = token.split("=", 1)[1]
                if env_path is not None:
                    captured_env_contents.append(Path(env_path).read_text())
                    break
            return mock_proc

        monkeypatch.setattr(subprocess, "Popen", capture_popen)
        monkeypatch.setattr(subprocess, "run", lambda *_a, **_k: mock.Mock())

        runner = CliRunner()
        result = runner.invoke(pipeline, ["deploy", "--workflow", "feature-phases"])

        assert result.exit_code == 0
        # The container was launched exactly once with an env-file forwarded.
        assert len(captured_argv) == 1
        assert len(captured_env_contents) == 1
        # The env-file that docker received carries the workflow name (and only it).
        assert "GOGA_WORKFLOW_NAME=feature-phases" in captured_env_contents[0]
        assert "GOGA_WORKFLOW_DISABLED" not in captured_env_contents[0]


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
