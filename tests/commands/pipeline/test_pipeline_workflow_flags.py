"""Logic tests for the ``--workflow`` / ``--no-workflow`` flags on the ``pipeline`` Click command.

Negative cases (exit 1, BEFORE container launch):
- ``--workflow custom --no-workflow`` are mutually exclusive
- ``--workflow custom`` names a file absent at
  ``<cwd>/.goga/workflows/custom.yml``

Edge cases (no host-side validation; dispatch proceeds):
- ``--no-workflow`` alone forwards the flag with no host-side validation
- no workflow flags forwards the basename auto-match to the container

The dispatch target ``run_pipeline_container`` is mocked so these tests stay
focused on the host-side workflow validation layer (no docker dependency).
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest import mock

import pytest
from click.testing import CliRunner
from goga.commands.pipeline import pipeline

# goga.commands.pipeline.pipeline is shadowed in the package __init__ by the
# pipeline Click command, so a string-based mock.patch path walking through it
# fails on Python 3.10. Resolve the real module via sys.modules, mirroring the
# sibling test modules.
_pipeline_module = sys.modules["goga.commands.pipeline.pipeline"]


def _write_config(tmp_path: Path) -> None:
    """Materialize a minimal ``.goga/config.yml`` with a pipeline section.

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


# --- Negative tests (validation failures, exit 1 BEFORE container launch) ---


class TestPipelineWorkflowFlagValidation:
    def test_pipeline_command_workflow_and_no_workflow_mutually_exclusive(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``--workflow X --no-workflow`` exits 1 with a mutual-exclusion message.

        The mutual-exclusion check (Algorithm step 5) runs BEFORE the host-side
        existence check (step 6) and BEFORE dispatch, so the contradictory CLI
        surface never reaches docker. Step 5 fires regardless of whether the
        named workflow file exists.
        """
        _write_config(tmp_path)
        # Intentionally do NOT create .goga/workflows/custom.yml — step 5 must
        # fire before the step 6 existence check.
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        with mock.patch.object(_pipeline_module, "run_pipeline_container", return_value=0) as mock_run:
            result = runner.invoke(pipeline, ["deploy", "--workflow", "custom", "--no-workflow"])

        assert result.exit_code == 1
        assert "mutually exclusive" in result.output
        # The container is never launched on a contradictory flag combination.
        mock_run.assert_not_called()

    def test_pipeline_command_missing_workflow_file_exits_one(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``--workflow custom`` with no matching file exits 1 with a not-found message.

        The host-side existence check (Algorithm step 6) verifies
        ``<cwd>/.goga/workflows/<name>.yml`` BEFORE container launch; a missing
        file surfaces as a clean message + exit 1 rather than a docker run.
        """
        _write_config(tmp_path)
        # No .goga/workflows/custom.yml on the host.
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        with mock.patch.object(_pipeline_module, "run_pipeline_container", return_value=0) as mock_run:
            result = runner.invoke(pipeline, ["deploy", "--workflow", "custom"])

        assert result.exit_code == 1
        assert "workflow 'custom' not found" in result.output
        # The container is never launched when the workflow file is missing.
        mock_run.assert_not_called()

    def test_pipeline_command_path_traversal_workflow_name_rejected(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A ``--workflow`` name that escapes the workflows dir exits 1.

        Workflow paths are project-only by design (CODEMANIFEST step 6b): a name
        carrying a ``..`` segment (or an absolute prefix) that would resolve
        outside ``<cwd>/.goga/workflows/`` is rejected as a clean message +
        exit 1 BEFORE any filesystem read or container launch — the host never
        stats or parses a file outside the project workflows dir.
        """
        _write_config(tmp_path)
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        with mock.patch.object(_pipeline_module, "run_pipeline_container", return_value=0) as mock_run:
            result = runner.invoke(pipeline, ["deploy", "--workflow", "../etc/evil"])

        assert result.exit_code == 1
        assert "invalid workflow name" in result.output
        mock_run.assert_not_called()

    def test_pipeline_command_discovery_mode_missing_workflow_exits_one(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Discovery mode still runs the host-side ``--workflow`` validation.

        Per CODEMANIFEST, steps 5 (mutual exclusion) and 6 (existence) are
        unconditional — they run BEFORE dispatch regardless of whether ``name``
        is set. So ``goga pipeline --workflow missing`` (no name) exits 1 when
        the file is absent; the workflow LAYER (env-file/log line) is the part
        that is a no-op in discovery, not the flag validation.
        """
        _write_config(tmp_path)
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        with mock.patch.object(_pipeline_module, "run_pipeline_container", return_value=0) as mock_run:
            result = runner.invoke(pipeline, ["--workflow", "missing"])

        assert result.exit_code == 1
        assert "workflow 'missing' not found" in result.output
        mock_run.assert_not_called()


# --- Edge cases (no host-side validation; dispatch proceeds) ---


class TestPipelineWorkflowFlagEdge:
    def test_pipeline_command_no_workflow_only_passes(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """``--no-workflow`` alone performs NO host-side validation.

        ``--no-workflow`` is a pure flag forwarded into the container env-file as
        ``GOGA_WORKFLOW_DISABLED=1``; the host neither validates a file nor blocks
        dispatch. The command proceeds to ``run_pipeline_container`` with
        ``no_workflow=True``.
        """
        _write_config(tmp_path)
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        with mock.patch.object(_pipeline_module, "run_pipeline_container", return_value=0) as mock_run:
            result = runner.invoke(pipeline, ["deploy", "--no-workflow"])

        assert result.exit_code == 0
        mock_run.assert_called_once()
        assert mock_run.call_args.kwargs["no_workflow"] is True
        assert mock_run.call_args.kwargs["workflow"] is None

    def test_pipeline_command_no_flags_no_validation(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """No workflow flags performs NO host-side validation.

        With neither ``--workflow`` nor ``--no-workflow`` set, the host does not
        validate anything and forwards ``workflow=None`` / ``no_workflow=False``;
        the basename auto-match fallback is resolved in-container.
        """
        _write_config(tmp_path)
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        with mock.patch.object(_pipeline_module, "run_pipeline_container", return_value=0) as mock_run:
            result = runner.invoke(pipeline, ["deploy"])

        assert result.exit_code == 0
        mock_run.assert_called_once()
        assert mock_run.call_args.kwargs["workflow"] is None
        assert mock_run.call_args.kwargs["no_workflow"] is False

    def test_pipeline_command_workflow_file_present_dispatches(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``--workflow custom`` with the file present dispatches with workflow=<name>.

        Step 6 passes when ``<cwd>/.goga/workflows/<name>.yml`` exists, so the
        command proceeds to ``run_pipeline_container`` with the workflow name
        forwarded for the in-container env-file.
        """
        _write_config(tmp_path)
        workflows_dir = tmp_path / ".goga" / "workflows"
        workflows_dir.mkdir(parents=True, exist_ok=True)
        (workflows_dir / "custom.yml").write_text("prompt: hi\n")
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        with mock.patch.object(_pipeline_module, "run_pipeline_container", return_value=0) as mock_run:
            result = runner.invoke(pipeline, ["deploy", "--workflow", "custom"])

        assert result.exit_code == 0
        mock_run.assert_called_once()
        assert mock_run.call_args.kwargs["workflow"] == "custom"
        assert mock_run.call_args.kwargs["no_workflow"] is False

    def test_pipeline_command_workflow_and_skip_not_mutually_exclusive(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``--workflow X --skip Y`` coexist: both forwarded, no mutual-exclusion guard.

        Unlike ``--workflow``/``--no-workflow`` (mutually exclusive), ``--skip``
        layers independently: the host validates the workflow file exists and
        forwards BOTH ``workflow`` and ``skip`` to ``run_pipeline_container``; the
        skip directives merge onto the resolved workflow inside the container.
        """
        _write_config(tmp_path)
        workflows_dir = tmp_path / ".goga" / "workflows"
        workflows_dir.mkdir(parents=True, exist_ok=True)
        (workflows_dir / "custom.yml").write_text("prompt: hi\n")
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        with mock.patch.object(_pipeline_module, "run_pipeline_container", return_value=0) as mock_run:
            result = runner.invoke(pipeline, ["deploy", "--workflow", "custom", "--skip", "review"])

        assert result.exit_code == 0
        mock_run.assert_called_once()
        assert mock_run.call_args.kwargs["workflow"] == "custom"
        assert mock_run.call_args.kwargs["skip"] == ("review",)
