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
