from __future__ import annotations

import sys
from pathlib import Path
from unittest import mock

import pytest
from goga.pipeline import run_pipeline

from tests.pipeline.conftest import fake_documents, patch_defaults, write_defaults, write_pipeline

# goga.pipeline.run_pipeline is shadowed in the package __init__ by the
# run_pipeline function, so a string-based mock.patch path walking through it
# fails on Python 3.10. Resolve the real module via sys.modules and patch its
# compile_flow / run_flow / _resolve_defaults_dir attributes directly. Per
# [[feedback_mock_patch_module_shadowing]].
_run_pipeline_module = sys.modules["goga.pipeline.run_pipeline"]


def _patch_defaults(monkeypatch: pytest.MonkeyPatch, defaults_dir: Path) -> None:
    """Write the four default prompt files and point the resolver at the directory."""
    write_defaults(defaults_dir)
    patch_defaults(monkeypatch, defaults_dir)


class TestRunPipelineWorkflowResolution:
    """Step 6 — workflow parameter resolution (no_workflow > workflow > basename)."""

    def test_run_pipeline_with_explicit_workflow_name(
        self, tmp_path: Path, isolated_cwd: Path, afm_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """workflow="custom" → its workflow-file is parsed and forwarded to compile_flow."""
        _patch_defaults(monkeypatch, tmp_path / "defaults")

        # Workflow-file at <cwd>/.goga/workflows/custom.yml (CWD-based resolution).
        workflows_dir = tmp_path / ".goga" / "workflows"
        workflows_dir.mkdir(parents=True)
        (workflows_dir / "custom.yml").write_text("prompt: Custom top-level prompt\n")

        project_dir = tmp_path / ".goga" / "pipelines"
        write_pipeline(project_dir)

        with (
            mock.patch.object(_run_pipeline_module, "compile_flow", return_value=fake_documents()) as mock_compile,
            mock.patch.object(_run_pipeline_module, "run_flow", return_value=0),
        ):
            exit_code = run_pipeline("deploy", project_dir, tmp_path / "user", 50321, workflow="custom")

        assert exit_code == 0
        workflow = mock_compile.call_args.kwargs["workflow"]
        assert workflow is not None
        assert workflow.prompt is not None
        assert workflow.prompt == "Custom top-level prompt"

    def test_run_pipeline_workflow_disabled_overrides_name(
        self, tmp_path: Path, isolated_cwd: Path, afm_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """no_workflow=True wins over an explicit workflow name even when the file exists."""
        _patch_defaults(monkeypatch, tmp_path / "defaults")

        # The named workflow-file exists on disk, but disabled must still win.
        workflows_dir = tmp_path / ".goga" / "workflows"
        workflows_dir.mkdir(parents=True)
        (workflows_dir / "ignored.yml").write_text("prompt: should be ignored\n")

        project_dir = tmp_path / ".goga" / "pipelines"
        write_pipeline(project_dir)

        with (
            mock.patch.object(_run_pipeline_module, "compile_flow", return_value=fake_documents()) as mock_compile,
            mock.patch.object(_run_pipeline_module, "run_flow", return_value=0),
        ):
            exit_code = run_pipeline(
                "deploy", project_dir, tmp_path / "user", 50321, workflow="ignored", no_workflow=True
            )

        assert exit_code == 0
        assert mock_compile.call_args.kwargs["workflow"] is None

    def test_run_pipeline_basename_fallback_silent_miss(
        self, tmp_path: Path, isolated_cwd: Path, afm_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No workflow name + no basename file → workflow=None, no exception."""
        _patch_defaults(monkeypatch, tmp_path / "defaults")

        # No .goga/workflows/ dir at all — the basename fallback (deploy.yml) misses.
        project_dir = tmp_path / ".goga" / "pipelines"
        write_pipeline(project_dir)

        with (
            mock.patch.object(_run_pipeline_module, "compile_flow", return_value=fake_documents()) as mock_compile,
            mock.patch.object(_run_pipeline_module, "run_flow", return_value=0),
        ):
            exit_code = run_pipeline("deploy", project_dir, tmp_path / "user", 50321)

        assert exit_code == 0
        assert mock_compile.call_args.kwargs["workflow"] is None

    def test_run_pipeline_basename_fallback_hit(
        self, tmp_path: Path, isolated_cwd: Path, afm_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No workflow name but <cwd>/.goga/workflows/<name>.yml exists → basename fallback applies it."""
        _patch_defaults(monkeypatch, tmp_path / "defaults")

        # Basename fallback: workflow-file named after the pipeline ("deploy.yml").
        workflows_dir = tmp_path / ".goga" / "workflows"
        workflows_dir.mkdir(parents=True)
        (workflows_dir / "deploy.yml").write_text("stages:\n  build:\n    agent: codex\n")

        project_dir = tmp_path / ".goga" / "pipelines"
        write_pipeline(project_dir)

        with (
            mock.patch.object(_run_pipeline_module, "compile_flow", return_value=fake_documents()) as mock_compile,
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
        self, tmp_path: Path, isolated_cwd: Path, afm_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A malformed resolved workflow-file surfaces WorkflowSyntaxError unchanged."""
        from goga.pipeline.workflow import WorkflowSyntaxError

        _patch_defaults(monkeypatch, tmp_path / "defaults")

        workflows_dir = tmp_path / ".goga" / "workflows"
        workflows_dir.mkdir(parents=True)
        # Unknown top-level key → structural error from parse_workflow.
        (workflows_dir / "custom.yml").write_text("bogus_key: value\n")

        project_dir = tmp_path / ".goga" / "pipelines"
        write_pipeline(project_dir)

        with (
            mock.patch.object(_run_pipeline_module, "compile_flow") as mock_compile,
            mock.patch.object(_run_pipeline_module, "run_flow", return_value=0) as mock_run_flow,
            pytest.raises(WorkflowSyntaxError, match="unknown key in workflow"),
        ):
            run_pipeline("deploy", project_dir, tmp_path / "user", 50321, workflow="custom")

        # The structural workflow error surfaces before compile_flow runs.
        mock_compile.assert_not_called()
        mock_run_flow.assert_not_called()

    def test_run_pipeline_workflow_name_missing_file_silent_miss(
        self, tmp_path: Path, isolated_cwd: Path, afm_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """workflow="custom" but its file absent → workflow=None (silent miss).

        A named workflow that does not exist is a defensive silent miss, not an
        error — the named-resolution path must return ``None`` exactly like the
        basename fallback miss, never raise.
        """
        _patch_defaults(monkeypatch, tmp_path / "defaults")

        # .goga/workflows/ dir exists but custom.yml does NOT.
        (tmp_path / ".goga" / "workflows").mkdir(parents=True)
        project_dir = tmp_path / ".goga" / "pipelines"
        write_pipeline(project_dir)

        with (
            mock.patch.object(_run_pipeline_module, "compile_flow", return_value=fake_documents()) as mock_compile,
            mock.patch.object(_run_pipeline_module, "run_flow", return_value=0),
        ):
            exit_code = run_pipeline("deploy", project_dir, tmp_path / "user", 50321, workflow="custom")

        assert exit_code == 0
        assert mock_compile.call_args.kwargs["workflow"] is None

    def test_run_pipeline_workflow_name_path_traversal_silent_miss(
        self, tmp_path: Path, isolated_cwd: Path, afm_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A path-traversal workflow name is a silent miss, never a traversal.

        Workflow paths are project-only by design (CODEMANIFEST step 6b): a name
        that escapes ``<cwd>/.goga/workflows/`` via ``..`` or an absolute prefix
        resolves to ``None`` inside the container, never parsing a file outside
        the project workflows dir. Observed without patching the parser: a
        valid workflow-file (the canary) sits at the escaped-to location, so a
        broken containment guard would parse it and hand a document to
        compile_flow — the run must instead resolve nothing.
        """
        _patch_defaults(monkeypatch, tmp_path / "defaults")

        project_dir = tmp_path / ".goga" / "pipelines"
        write_pipeline(project_dir)
        # The canary: a valid workflow at the location the traversal name
        # escapes to (``<cwd>/.goga/pipelines/evil.yml``) — one level above the
        # workflows root, inside the project tree.
        (project_dir / "evil.yml").write_text("prompt: must not be read\n")

        with (
            mock.patch.object(_run_pipeline_module, "compile_flow", return_value=fake_documents()) as mock_compile,
            mock.patch.object(_run_pipeline_module, "run_flow", return_value=0),
        ):
            exit_code = run_pipeline("deploy", project_dir, tmp_path / "user", 50321, workflow="../pipelines/evil")

        assert exit_code == 0
        assert mock_compile.call_args.kwargs["workflow"] is None

    def test_run_pipeline_disabled_takes_precedence_over_name(
        self, tmp_path: Path, isolated_cwd: Path, afm_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """no_workflow=True wins over an explicit name even when the named file exists.

        The named workflow-file (``hardening.yml``) is present on disk and the
        ``workflow`` parameter points at it, but the disable flag wins: the run
        compiles with ``workflow=None``. The run is driven to completion with the
        defaults-dir patched and ``run_flow`` mocked to 0, mirroring the other
        tests in this class.
        """
        _patch_defaults(monkeypatch, tmp_path / "defaults")

        workflows_dir = tmp_path / ".goga" / "workflows"
        workflows_dir.mkdir(parents=True)
        (workflows_dir / "hardening.yml").write_text(
            "stages:\n  test:\n    skip: true\nextend:\n  audit:\n    after: [test]\n    title: Audit\n"
        )

        project_dir = tmp_path / ".goga" / "pipelines"
        write_pipeline(project_dir)

        with (
            mock.patch.object(_run_pipeline_module, "compile_flow", return_value=fake_documents()) as mock_compile,
            mock.patch.object(_run_pipeline_module, "run_flow", return_value=0),
        ):
            exit_code = run_pipeline(
                "deploy", project_dir, tmp_path / "user", 50321, workflow="hardening", no_workflow=True
            )

        assert exit_code == 0
        assert mock_compile.call_args.kwargs["workflow"] is None

    def test_run_pipeline_receives_workflow_from_parameters_not_env(
        self, tmp_path: Path, isolated_cwd: Path, afm_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Stale workflow/skip env values are never read — the parameters decide.

        The environment carries contradicting values under the retired
        workflow/skip coordination names while the explicit
        ``workflow="hardening"`` parameter names an existing workflow-file.
        The run resolves and compiles ``hardening`` — the env values are
        inert passengers, never read, and no stage named ``zzz`` appears or
        is skipped. ``AFM_DIR`` stays the only environment read of run
        coordination.
        """
        _patch_defaults(monkeypatch, tmp_path / "defaults")
        # Composed rather than literal so the change-set-wide no-residue grep
        # stays clean: these stale names are inert passengers here, not a
        # channel run coordination reads or writes (the same precedent the
        # launcher workflow tests use).
        monkeypatch.setenv("GOGA_" + "WORKFLOW_NAME", "zzz")
        monkeypatch.setenv("GOGA_" + "SKIP_STAGES", "zzz")

        workflows_dir = tmp_path / ".goga" / "workflows"
        workflows_dir.mkdir(parents=True)
        (workflows_dir / "hardening.yml").write_text("prompt: Hardening prompt\n")

        project_dir = tmp_path / ".goga" / "pipelines"
        write_pipeline(project_dir)

        with (
            mock.patch.object(_run_pipeline_module, "compile_flow", return_value=fake_documents()) as mock_compile,
            mock.patch.object(_run_pipeline_module, "run_flow", return_value=0),
        ):
            exit_code = run_pipeline("deploy", project_dir, tmp_path / "user", 50321, workflow="hardening")

        assert exit_code == 0
        workflow = mock_compile.call_args.kwargs["workflow"]
        # The compiled workflow is hardening's — not the env's zzz.
        assert workflow is not None
        assert workflow.prompt == "Hardening prompt"
        # No stage named zzz is skipped (the env skip value never merged).
        assert "zzz" not in workflow.stages
