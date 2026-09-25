"""Logic tests for the ``--workflow`` / ``--no-workflow`` flags on the ``pipeline`` Click command.

Negative cases (exit 1, BEFORE container launch):
- ``--workflow custom --no-workflow`` are mutually exclusive
- ``--workflow custom`` names a file absent at
  ``<cwd>/.goga/workflows/custom.yml``
- a leading-dash ``-w``/``-s`` value is unparsable by the in-container
  argparse parser (``-s --no-workflow`` swallows the flag as the value)
- a dash-leading pipeline name (``-- -weird``) composes the same unparsable
  in-container argv

Edge cases (no host-side validation; dispatch proceeds):
- ``--no-workflow`` alone forwards the flag with no host-side validation
- no workflow flags forwards the basename auto-match to the container
- the listing form silently ignores a dash ``-s`` value (only the run and
  card forms carry skips)

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
                "  agent: claude",
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

    def test_w_and_no_workflow_combination_rejected_host_side(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``-w x --no-workflow`` (short alias) exits 1 with a clean message; no docker.

        The host owns the exclusivity: the contradictory surface is rejected
        before any container launch regardless of the flag form, and the
        check fires before the existence validation — the file ``x.yml`` need
        not exist.
        """
        _write_config(tmp_path)
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        with (
            mock.patch.object(_pipeline_module, "run_pipeline_container", return_value=0) as mock_run,
            mock.patch.object(_pipeline_module, "run_pipeline_info_container", return_value=0) as mock_info,
        ):
            result = runner.invoke(pipeline, ["deploy", "-w", "x", "--no-workflow"])

        assert result.exit_code == 1
        assert "mutually exclusive" in result.output
        mock_run.assert_not_called()
        mock_info.assert_not_called()

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

    def test_pipeline_command_leading_dash_skip_value_rejected_host_side(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``-s --no-workflow`` (flag swallowed as the skip value) exits 1 host-side.

        Click consumes any next token as an option value, so the typo parses
        on the host with ``skip=("--no-workflow",)`` — but the in-container
        argparse parser classifies a leading-dash token as an option, and the
        composed argv dies there as ``expected one argument`` only after the
        launch ceremony. Step 2.5 rejects the form before any docker
        activity, in every form that carries a skip.
        """
        _write_config(tmp_path)
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        with (
            mock.patch.object(_pipeline_module, "run_pipeline_container", return_value=0) as mock_run,
            mock.patch.object(_pipeline_module, "run_pipeline_info_container", return_value=0) as mock_info,
        ):
            result = runner.invoke(pipeline, ["deploy", "-s", "--no-workflow"])
            card_result = runner.invoke(pipeline, ["deploy", "--info", "-s", "-w"])

        assert result.exit_code == 1
        assert "invalid skip name '--no-workflow'" in result.output
        assert card_result.exit_code == 1
        assert "invalid skip name '-w'" in card_result.output
        mock_run.assert_not_called()
        mock_info.assert_not_called()

    def test_pipeline_command_leading_dash_workflow_value_rejected_host_side(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A leading-dash ``--workflow`` value exits 1 even when the file exists.

        A workflow file literally named ``-x.yml`` passes the containment and
        existence checks, but the composed ``["-w", "-x"]`` argv is
        unparsable in-container (argparse reads ``-x`` as an option) — so the
        dash prefix is a form error before any launch, like the ``..``
        escape.
        """
        _write_config(tmp_path)
        workflows_dir = tmp_path / ".goga" / "workflows"
        workflows_dir.mkdir(parents=True, exist_ok=True)
        (workflows_dir / "-x.yml").write_text("prompt: hi\n")
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        with mock.patch.object(_pipeline_module, "run_pipeline_container", return_value=0) as mock_run:
            result = runner.invoke(pipeline, ["deploy", "--workflow", "-x"])

        assert result.exit_code == 1
        assert "invalid workflow name '-x'" in result.output
        mock_run.assert_not_called()

    def test_pipeline_command_leading_dash_pipeline_name_rejected_host_side(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``goga pipeline -- -weird`` (dash-leading name) exits 1 host-side.

        Click's ``--`` hands a dash-leading token to the positional, so the
        name parses on the host with ``name="-weird"`` — but the composed
        ``["run", "-weird", ...]`` argv is unparsable in-container (argparse
        reads the name as an option and reports the missing positional) only
        after the launch ceremony. Step 2.5 rejects the form before any
        docker activity, like a dash ``-w``/``-s`` value.
        """
        _write_config(tmp_path)
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        with mock.patch.object(_pipeline_module, "run_pipeline_container", return_value=0) as mock_run:
            result = runner.invoke(pipeline, ["--", "-weird"])

        assert result.exit_code == 1
        assert "invalid pipeline name '-weird'" in result.output
        mock_run.assert_not_called()

    def test_pipeline_command_list_mode_missing_workflow_exits_one(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The listing form still runs the host-side ``--workflow`` validation.

        Per CODEMANIFEST, steps 2.3 (mutual exclusion) and 2.4 (existence) are
        unconditional — they run BEFORE dispatch regardless of the form. So
        ``goga pipeline --list --workflow missing`` exits 1 when the file is
        absent; neither launcher runs. (The former discovery-mode variant — a
        bare ``--workflow`` with no name — now names no form at all and exits 1
        at step 2.2 instead.)
        """
        _write_config(tmp_path)
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        with (
            mock.patch.object(_pipeline_module, "run_pipeline_container", return_value=0) as mock_run,
            mock.patch.object(_pipeline_module, "run_pipeline_info_container", return_value=0) as mock_info,
        ):
            result = runner.invoke(pipeline, ["--list", "--workflow", "missing"])

        assert result.exit_code == 1
        assert "workflow 'missing' not found" in result.output
        mock_run.assert_not_called()
        mock_info.assert_not_called()


# --- Edge cases (no host-side validation; dispatch proceeds) ---


class TestPipelineWorkflowFlagEdge:
    def test_pipeline_command_no_workflow_only_passes(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """``--no-workflow`` alone performs NO host-side validation.

        ``--no-workflow`` is a pure flag forwarded to ``run_pipeline_container``
        as ``no_workflow=True``; the decision travels onward in the
        in-container subcommand argv (a ``--no-workflow`` token — never an
        env-file entry), and the launcher prints no workflow log line for it.
        The host neither validates a file nor blocks dispatch.
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
        forwarded — it travels onward in the in-container subcommand argv as a
        ``-w`` token.
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

    def test_pipeline_command_list_form_silently_ignores_dash_skip_value(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The listing form silently ignores a dash ``-s`` value — dispatch proceeds.

        The listing launcher carries no skip names (the contract: the listing
        forms silently ignore ``-s``), so the step 2.5 dash guard acts only
        where skips travel — the run and card forms. ``goga pipeline --list
        -s -x`` lists as if the flag were absent; the info launcher runs, the
        run launcher never.
        """
        _write_config(tmp_path)
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        with (
            mock.patch.object(_pipeline_module, "run_pipeline_container", return_value=0) as mock_run,
            mock.patch.object(_pipeline_module, "run_pipeline_info_container", return_value=0) as mock_info,
        ):
            result = runner.invoke(pipeline, ["--list", "-s", "-x"])

        assert result.exit_code == 0
        mock_info.assert_called_once()
        mock_run.assert_not_called()
