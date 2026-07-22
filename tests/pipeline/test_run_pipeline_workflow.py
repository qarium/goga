from __future__ import annotations

import sys
from pathlib import Path
from unittest import mock

import pytest
from goga.pipeline import run_pipeline
from goga.pipeline.compiler import (
    BodyFormat,
    FlowDocument,
    PhasesBody,
    PipelineDocument,
    PipelineHeader,
)

# goga.pipeline.run_pipeline is shadowed in the package __init__ by the
# run_pipeline function, so a string-based mock.patch path walking through it
# fails on Python 3.10. Resolve the real module via sys.modules and patch its
# compile_flow / run_flow / _resolve_defaults_dir attributes directly. Per
# [[feedback_mock_patch_module_shadowing]].
_run_pipeline_module = sys.modules["goga.pipeline.run_pipeline"]

# The four materialized afm prompt-file stems (planning/implementation/review
# from the overridable roles via translate_role, plus the always-default
# summary). Used only to populate the patched defaults directory so
# materialization does not depend on the real package assets in these
# workflow-focused tests.
_PROMPT_STEMS = ("planning", "implementation", "review", "summary")


def _fake_documents() -> tuple[PipelineDocument, FlowDocument]:
    """Build the documents tuple ``compile_flow`` returns, for mock wiring.

    ``agents`` is None so materialization copies the patched defaults verbatim.
    """
    pipeline_doc = PipelineDocument(
        header=PipelineHeader(name="deploy", description="d"),
        format=BodyFormat.PHASES,
        body=PhasesBody(steps=[]),
    )
    flow_doc = FlowDocument(name="deploy", description="d", stages=[])
    return (pipeline_doc, flow_doc)


def _patch_defaults(monkeypatch: pytest.MonkeyPatch, defaults_dir: Path) -> None:
    """Point ``_resolve_defaults_dir`` at a tmp dir holding four default files."""
    defaults_dir.mkdir(parents=True, exist_ok=True)
    for stem in _PROMPT_STEMS:
        (defaults_dir / f"{stem}.md").write_text(f"default {stem}\n")
    monkeypatch.setattr(_run_pipeline_module, "_resolve_defaults_dir", lambda: defaults_dir)


@pytest.fixture
def isolated_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """chdir into tmp_path and set AFM_DIR at <tmp>/.afm — mirror the in-container layout.

    Workflow resolution is CWD-based (``Path.cwd() / ".goga" / "workflows"``), so
    each test controls the resolved workflow path by writing under ``tmp_path /
    .goga/workflows/``. The pipeline file is placed at ``tmp_path / .goga /
    pipelines/`` to mirror the real project layout (project_dir passed
    explicitly to run_pipeline; CWD independent).
    """
    monkeypatch.chdir(tmp_path)
    afm_dir = (tmp_path / ".afm").resolve()
    monkeypatch.setenv("AFM_DIR", str(afm_dir))
    return tmp_path


class TestRunPipelineWorkflowResolution:
    """Step 6 — workflow environment resolution (GOGA_WORKFLOW_DISABLED > NAME > basename)."""

    def test_run_pipeline_with_workflow_env_name(
        self, tmp_path: Path, isolated_cwd: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """GOGA_WORKFLOW_NAME set → its workflow-file is parsed and forwarded to compile_flow."""
        _patch_defaults(monkeypatch, tmp_path / "defaults")
        monkeypatch.setenv("GOGA_WORKFLOW_NAME", "custom")
        monkeypatch.delenv("GOGA_WORKFLOW_DISABLED", raising=False)

        # Workflow-file at <cwd>/.goga/workflows/custom.yml (CWD-based resolution).
        workflows_dir = tmp_path / ".goga" / "workflows"
        workflows_dir.mkdir(parents=True)
        (workflows_dir / "custom.yml").write_text("prompt: Custom top-level prompt\n")

        project_dir = tmp_path / ".goga" / "pipelines"
        project_dir.mkdir(parents=True)
        (project_dir / "deploy.yml").write_text("pipeline")

        with (
            mock.patch.object(_run_pipeline_module, "compile_flow", return_value=_fake_documents()) as mock_compile,
            mock.patch.object(_run_pipeline_module, "run_flow", return_value=0),
        ):
            exit_code = run_pipeline("deploy", project_dir, tmp_path / "user", 50321)

        assert exit_code == 0
        workflow = mock_compile.call_args.kwargs["workflow"]
        assert workflow is not None
        assert workflow.prompt is not None
        assert workflow.prompt == "Custom top-level prompt"

    def test_run_pipeline_workflow_disabled_env_overrides_name(
        self, tmp_path: Path, isolated_cwd: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """GOGA_WORKFLOW_DISABLED=1 wins over GOGA_WORKFLOW_NAME even when the file exists."""
        _patch_defaults(monkeypatch, tmp_path / "defaults")
        monkeypatch.setenv("GOGA_WORKFLOW_DISABLED", "1")
        monkeypatch.setenv("GOGA_WORKFLOW_NAME", "ignored")

        # The named workflow-file exists on disk, but disabled must still win.
        workflows_dir = tmp_path / ".goga" / "workflows"
        workflows_dir.mkdir(parents=True)
        (workflows_dir / "ignored.yml").write_text("prompt: should be ignored\n")

        project_dir = tmp_path / ".goga" / "pipelines"
        project_dir.mkdir(parents=True)
        (project_dir / "deploy.yml").write_text("pipeline")

        with (
            mock.patch.object(_run_pipeline_module, "compile_flow", return_value=_fake_documents()) as mock_compile,
            mock.patch.object(_run_pipeline_module, "run_flow", return_value=0),
        ):
            exit_code = run_pipeline("deploy", project_dir, tmp_path / "user", 50321)

        assert exit_code == 0
        assert mock_compile.call_args.kwargs["workflow"] is None

    def test_run_pipeline_basename_fallback_silent_miss(
        self, tmp_path: Path, isolated_cwd: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No workflow env + no basename file → workflow=None, no exception."""
        _patch_defaults(monkeypatch, tmp_path / "defaults")
        monkeypatch.delenv("GOGA_WORKFLOW_DISABLED", raising=False)
        monkeypatch.delenv("GOGA_WORKFLOW_NAME", raising=False)

        # No .goga/workflows/ dir at all — the basename fallback (deploy.yml) misses.
        project_dir = tmp_path / ".goga" / "pipelines"
        project_dir.mkdir(parents=True)
        (project_dir / "deploy.yml").write_text("pipeline")

        with (
            mock.patch.object(_run_pipeline_module, "compile_flow", return_value=_fake_documents()) as mock_compile,
            mock.patch.object(_run_pipeline_module, "run_flow", return_value=0),
        ):
            exit_code = run_pipeline("deploy", project_dir, tmp_path / "user", 50321)

        assert exit_code == 0
        assert mock_compile.call_args.kwargs["workflow"] is None

    def test_run_pipeline_basename_fallback_hit(
        self, tmp_path: Path, isolated_cwd: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No workflow env but <cwd>/.goga/workflows/<name>.yml exists → basename fallback applies it."""
        _patch_defaults(monkeypatch, tmp_path / "defaults")
        monkeypatch.delenv("GOGA_WORKFLOW_DISABLED", raising=False)
        monkeypatch.delenv("GOGA_WORKFLOW_NAME", raising=False)

        # Basename fallback: workflow-file named after the pipeline ("deploy.yml").
        workflows_dir = tmp_path / ".goga" / "workflows"
        workflows_dir.mkdir(parents=True)
        (workflows_dir / "deploy.yml").write_text("stages:\n  build:\n    agent: codex\n")

        project_dir = tmp_path / ".goga" / "pipelines"
        project_dir.mkdir(parents=True)
        (project_dir / "deploy.yml").write_text("pipeline")

        with (
            mock.patch.object(_run_pipeline_module, "compile_flow", return_value=_fake_documents()) as mock_compile,
            mock.patch.object(_run_pipeline_module, "run_flow", return_value=0),
        ):
            exit_code = run_pipeline("deploy", project_dir, tmp_path / "user", 50321)

        assert exit_code == 0
        workflow = mock_compile.call_args.kwargs["workflow"]
        assert workflow is not None
        assert workflow.prompt is None
        # The basename-matched workflow carries the parsed per-stage override.
        assert "build" in workflow.stages
        assert workflow.stages["build"].agent == "codex"

    def test_run_pipeline_propagates_workflow_syntax_error(
        self, tmp_path: Path, isolated_cwd: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A malformed resolved workflow-file surfaces WorkflowSyntaxError unchanged."""
        from goga.pipeline.workflow import WorkflowSyntaxError

        _patch_defaults(monkeypatch, tmp_path / "defaults")
        monkeypatch.delenv("GOGA_WORKFLOW_DISABLED", raising=False)
        monkeypatch.setenv("GOGA_WORKFLOW_NAME", "custom")

        workflows_dir = tmp_path / ".goga" / "workflows"
        workflows_dir.mkdir(parents=True)
        # Unknown top-level key → structural error from parse_workflow.
        (workflows_dir / "custom.yml").write_text("bogus_key: value\n")

        project_dir = tmp_path / ".goga" / "pipelines"
        project_dir.mkdir(parents=True)
        (project_dir / "deploy.yml").write_text("pipeline")

        with (
            mock.patch.object(_run_pipeline_module, "compile_flow") as mock_compile,
            mock.patch.object(_run_pipeline_module, "run_flow", return_value=0) as mock_run_flow,
            pytest.raises(WorkflowSyntaxError, match="unknown key in workflow"),
        ):
            run_pipeline("deploy", project_dir, tmp_path / "user", 50321)

        # The structural workflow error surfaces before compile_flow runs.
        mock_compile.assert_not_called()
        mock_run_flow.assert_not_called()

    def test_run_pipeline_workflow_name_missing_file_silent_miss(
        self, tmp_path: Path, isolated_cwd: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """GOGA_WORKFLOW_NAME set but its file absent → workflow=None (silent miss).

        A named workflow that does not exist is a defensive silent miss, not an
        error — the named-resolution path must return ``None`` exactly like the
        basename fallback miss, never raise.
        """
        _patch_defaults(monkeypatch, tmp_path / "defaults")
        monkeypatch.delenv("GOGA_WORKFLOW_DISABLED", raising=False)
        monkeypatch.setenv("GOGA_WORKFLOW_NAME", "custom")

        # .goga/workflows/ dir exists but custom.yml does NOT.
        (tmp_path / ".goga" / "workflows").mkdir(parents=True)
        project_dir = tmp_path / ".goga" / "pipelines"
        project_dir.mkdir(parents=True)
        (project_dir / "deploy.yml").write_text("pipeline")

        with (
            mock.patch.object(_run_pipeline_module, "compile_flow", return_value=_fake_documents()) as mock_compile,
            mock.patch.object(_run_pipeline_module, "run_flow", return_value=0),
        ):
            exit_code = run_pipeline("deploy", project_dir, tmp_path / "user", 50321)

        assert exit_code == 0
        assert mock_compile.call_args.kwargs["workflow"] is None

    def test_run_pipeline_workflow_name_path_traversal_silent_miss(
        self, tmp_path: Path, isolated_cwd: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A path-traversal GOGA_WORKFLOW_NAME is a silent miss, never a traversal.

        Workflow paths are project-only by design (CODEMANIFEST step 6b): a name
        that escapes ``<cwd>/.goga/workflows/`` via ``..`` or an absolute prefix
        resolves to ``None`` inside the container, never parsing a file outside
        the project workflows dir.
        """
        _patch_defaults(monkeypatch, tmp_path / "defaults")
        monkeypatch.delenv("GOGA_WORKFLOW_DISABLED", raising=False)
        monkeypatch.setenv("GOGA_WORKFLOW_NAME", "../../etc/evil")

        project_dir = tmp_path / ".goga" / "pipelines"
        project_dir.mkdir(parents=True)
        (project_dir / "deploy.yml").write_text("pipeline")

        with (
            mock.patch.object(_run_pipeline_module, "compile_flow", return_value=_fake_documents()) as mock_compile,
            mock.patch.object(_run_pipeline_module, "run_flow", return_value=0),
            # parse_workflow must never be invoked for a traversal name.
            mock.patch.object(_run_pipeline_module, "parse_workflow") as mock_parse,
        ):
            exit_code = run_pipeline("deploy", project_dir, tmp_path / "user", 50321)

        assert exit_code == 0
        assert mock_compile.call_args.kwargs["workflow"] is None
        mock_parse.assert_not_called()
