from __future__ import annotations

import inspect
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
# compile_flow / run_flow attributes directly. Per [[feedback_mock_patch_module_shadowing]].
_run_pipeline_module = sys.modules["goga.pipeline.run_pipeline"]


def _fake_documents() -> tuple[PipelineDocument, FlowDocument]:
    """Build the documents tuple ``compile_flow`` returns, for mock wiring.

    ``agents`` is None (no header block) so materialization falls back to the
    real package defaults — kept out of the workflow-contract assertions.
    """
    pipeline_doc = PipelineDocument(
        header=PipelineHeader(name="deploy", description="d"),
        format=BodyFormat.PHASES,
        body=PhasesBody(steps=[]),
    )
    flow_doc = FlowDocument(name="deploy", description="d", stages=[])
    return (pipeline_doc, flow_doc)


def _write_pipeline(directory: Path, name: str = "deploy") -> None:
    """Create an empty pipeline file so name resolution matches it."""
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{name}.yml").write_text("pipeline")


class TestRunPipelineWorkflowContract:
    """Contract: run_pipeline forwards a ``workflow=`` kwarg to compile_flow.

    The public signature is unchanged (``name, project_dir, user_dir, port``) —
    the workflow is environment-driven, not a parameter. compile_flow always
    receives a ``workflow`` keyword argument (``None`` when nothing resolved, or
    a ``WorkflowDocument`` when a workflow-file resolved).
    """

    def test_run_pipeline_signature_unchanged(self) -> None:
        """run_pipeline still exposes the (name, project_dir, user_dir, port) signature."""
        parameters = list(inspect.signature(run_pipeline).parameters)
        assert parameters == ["name", "project_dir", "user_dir", "port"]

    def test_run_pipeline_forwards_none_workflow_when_no_env(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No workflow env and no basename file → compile_flow receives workflow=None."""
        monkeypatch.delenv("GOGA_WORKFLOW_DISABLED", raising=False)
        monkeypatch.delenv("GOGA_WORKFLOW_NAME", raising=False)
        monkeypatch.chdir(tmp_path)
        afm_dir = (tmp_path / ".afm").resolve()
        monkeypatch.setenv("AFM_DIR", str(afm_dir))

        project_dir = tmp_path / "pipelines"
        _write_pipeline(project_dir)

        with (
            mock.patch.object(_run_pipeline_module, "compile_flow", return_value=_fake_documents()) as mock_compile,
            mock.patch.object(_run_pipeline_module, "run_flow", return_value=0),
        ):
            run_pipeline("deploy", project_dir, tmp_path / "user", 50321)

        # compile_flow always receives a workflow= kwarg; here it is None.
        assert "workflow" in mock_compile.call_args.kwargs
        assert mock_compile.call_args.kwargs["workflow"] is None


class TestRunPipelineProjectNameContract:
    """Contract: run_pipeline forwards a ``project_name=`` kwarg to compile_flow.

    The project name is derived in-container from the git origin remote URL via
    :func:`resolve_project_name` (step 7) and passed to :func:`compile_flow` so the
    compiled flow-file description gets a ``[<project-name>]`` prefix (Part 2). It
    is OUTPUT-only context — never a ``run_pipeline`` parameter — and mirrors the
    ``root_dir`` pattern: derived from the environment, never read from config, and
    ``resolve_project_name`` never raises (``None`` simply means no prefix).
    """

    def _setup(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
        """chdir into tmp_path, set AFM_DIR, and write a matching pipeline file."""
        monkeypatch.delenv("GOGA_WORKFLOW_DISABLED", raising=False)
        monkeypatch.delenv("GOGA_WORKFLOW_NAME", raising=False)
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("AFM_DIR", str((tmp_path / ".afm").resolve()))
        project_dir = tmp_path / "pipelines"
        _write_pipeline(project_dir)
        return project_dir

    def test_run_pipeline_forwards_resolved_project_name(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """resolve_project_name() → "widget" → compile_flow receives project_name="widget"."""
        project_dir = self._setup(tmp_path, monkeypatch)
        monkeypatch.setattr(_run_pipeline_module, "resolve_project_name", lambda: "widget")

        with (
            mock.patch.object(_run_pipeline_module, "compile_flow", return_value=_fake_documents()) as mock_compile,
            mock.patch.object(_run_pipeline_module, "run_flow", return_value=0),
        ):
            run_pipeline("deploy", project_dir, tmp_path / "user", 50321)

        # compile_flow receives project_name= as a separate keyword, matching the
        # value resolve_project_name() returned at step 7.
        assert "project_name" in mock_compile.call_args.kwargs
        assert mock_compile.call_args.kwargs["project_name"] == "widget"

    def test_run_pipeline_forwards_none_project_name_when_unresolved(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """resolve_project_name() → None → compile_flow receives project_name=None (no prefix)."""
        project_dir = self._setup(tmp_path, monkeypatch)
        monkeypatch.setattr(_run_pipeline_module, "resolve_project_name", lambda: None)

        with (
            mock.patch.object(_run_pipeline_module, "compile_flow", return_value=_fake_documents()) as mock_compile,
            mock.patch.object(_run_pipeline_module, "run_flow", return_value=0),
        ):
            run_pipeline("deploy", project_dir, tmp_path / "user", 50321)

        assert mock_compile.call_args.kwargs["project_name"] is None

    def test_run_pipeline_calls_resolve_project_name_once(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """run_pipeline invokes resolve_project_name() exactly once (step 7)."""
        project_dir = self._setup(tmp_path, monkeypatch)

        calls = []

        def fake_resolve() -> str | None:
            calls.append(True)
            return "widget"

        monkeypatch.setattr(_run_pipeline_module, "resolve_project_name", fake_resolve)

        with (
            mock.patch.object(_run_pipeline_module, "compile_flow", return_value=_fake_documents()),
            mock.patch.object(_run_pipeline_module, "run_flow", return_value=0),
        ):
            run_pipeline("deploy", project_dir, tmp_path / "user", 50321)

        assert len(calls) == 1
