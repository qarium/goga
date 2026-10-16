"""Contract tests for the ``--workflow`` / ``--no-workflow`` / ``-p`` flags on the ``pipeline`` command.

These tests pin the click-command contract declared in
``goga/commands/pipeline/CODEMANIFEST`` for the workflow-flag and
contributor-profile extensions of the ``pipeline`` entity:

- a ``--workflow NAME`` option (``str``, non-flag, default ``None``)
- a ``--no-workflow`` flag option (``is_flag=True``, default ``False``)
- a ``-p/--profile NAME`` option (``str``, non-flag, default ``None``) — the
  contributor-profile activation channel; the ``-p`` short alias MOVED here
  from ``--parallel``
- ``--parallel`` is long-only (its former ``-p`` alias belongs to ``--profile``;
  the Docker ``-p port:host`` port-publish token is a separate namespace)
- the underlying ``pipeline(...)`` callback signature exposes
  ``workflow: str | None``, ``no_workflow: bool``, ``profile: str | None``
- the flags are advertised in ``--help``

Where a dispatch is exercised, ``run_pipeline_container`` is mocked so these
tests stay focused on the click surface (no docker dependency). The dispatch
contract kwargs themselves are pinned in ``test_pipeline.py`` /
``test_pipeline_dispatch.py``; this file pins only the flag surfaces.
"""

from __future__ import annotations

import sys
import typing
from pathlib import Path
from unittest import mock

import click
import pytest
from click.testing import CliRunner
from goga.commands.pipeline import pipeline
from goga.commands.pipeline.pipeline import pipeline as pipeline_cmd

from tests.commands.pipeline.conftest import write_minimal_config as _write_config

# goga.commands.pipeline.pipeline is shadowed in the package __init__ by the
# pipeline Click command, so a string-based mock.patch path walking through it
# fails on Python 3.10. Resolve the real module via sys.modules, mirroring the
# sibling test_pipeline.py / test_pipeline_dispatch.py modules.
_pipeline_module = sys.modules["goga.commands.pipeline.pipeline"]


# --- Contract obligation ---


class TestPipelineWorkflowFlagContract:
    def test_pipeline_is_importable_and_is_click_command(self) -> None:
        """``from goga.commands.pipeline import pipeline`` yields a click.Command (sanity)."""
        assert isinstance(pipeline, click.Command)
        assert not isinstance(pipeline, click.Group)

    def test_pipeline_has_workflow_option(self) -> None:
        """The pipeline command registers a ``--workflow`` click Option."""
        param_names = [p.name for p in pipeline.params]
        assert "workflow" in param_names

    def test_pipeline_workflow_option_is_str_and_defaults_none(self) -> None:
        """``--workflow`` is a non-flag str option defaulting to None."""
        workflow_param = next(p for p in pipeline.params if p.name == "workflow")
        assert isinstance(workflow_param, click.Option)
        assert workflow_param.is_flag is False
        assert workflow_param.default is None

    def test_pipeline_workflow_option_has_long_flag(self) -> None:
        """The registered long form is ``--workflow``."""
        workflow_param = next(p for p in pipeline.params if p.name == "workflow")
        assert "--workflow" in workflow_param.opts

    def test_pipeline_has_no_workflow_option(self) -> None:
        """The pipeline command registers a ``--no-workflow`` click Option."""
        param_names = [p.name for p in pipeline.params]
        assert "no_workflow" in param_names

    def test_pipeline_no_workflow_option_is_flag_and_defaults_false(self) -> None:
        """``--no-workflow`` is a flag defaulting to False."""
        no_workflow_param = next(p for p in pipeline.params if p.name == "no_workflow")
        assert isinstance(no_workflow_param, click.Option)
        assert no_workflow_param.is_flag is True
        assert no_workflow_param.default is False

    def test_pipeline_no_workflow_option_has_long_flag(self) -> None:
        """The registered long form is ``--no-workflow``."""
        no_workflow_param = next(p for p in pipeline.params if p.name == "no_workflow")
        assert "--no-workflow" in no_workflow_param.opts


# --- Callback signature contract ---


class TestPipelineCallbackWorkflowSignature:
    def test_pipeline_callback_has_workflow_and_no_workflow_parameters(self) -> None:
        """The decorated callback exposes workflow / no_workflow parameters."""
        parameters = pipeline_cmd.callback.__annotations__
        assert "workflow" in parameters
        assert "no_workflow" in parameters

    def test_pipeline_callback_workflow_annotation_is_optional_str(self) -> None:
        """The ``workflow`` callback parameter is typed ``str | None``."""
        hints = typing.get_type_hints(pipeline_cmd.callback)
        assert hints["workflow"] == str | None

    def test_pipeline_callback_no_workflow_annotation_is_bool(self) -> None:
        """The ``no_workflow`` callback parameter is typed ``bool``."""
        hints = typing.get_type_hints(pipeline_cmd.callback)
        assert hints["no_workflow"] is bool


# --- Help + CliRunner surface ---


class TestPipelineWorkflowFlagSurface:
    def test_help_lists_workflow_flags(self) -> None:
        """``--help`` advertises both workflow flags."""
        runner = CliRunner()
        result = runner.invoke(pipeline, ["--help"])
        assert result.exit_code == 0
        assert "--workflow" in result.output
        assert "--no-workflow" in result.output

    def test_pipeline_accepts_workflow_flag_via_clirunner(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``--workflow NAME`` parses cleanly and forwards workflow=<name>."""
        _write_config(tmp_path)
        # Step 6 validates <cwd>/.goga/workflows/<name>.yml exists on the host.
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

    def test_pipeline_accepts_no_workflow_flag_via_clirunner(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``--no-workflow`` parses cleanly and forwards no_workflow=True."""
        _write_config(tmp_path)
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        with mock.patch.object(_pipeline_module, "run_pipeline_container", return_value=0) as mock_run:
            result = runner.invoke(pipeline, ["deploy", "--no-workflow"])

        assert result.exit_code == 0
        mock_run.assert_called_once()
        assert mock_run.call_args.kwargs["no_workflow"] is True
        assert mock_run.call_args.kwargs["workflow"] is None


# --- -p/--profile flag contract (the short alias moved from --parallel) ---


class TestPipelineProfileFlagContract:
    def test_pipeline_has_profile_option(self) -> None:
        """The pipeline command registers a ``profile`` click Option."""
        param_names = [p.name for p in pipeline.params]
        assert "profile" in param_names

    def test_pipeline_profile_option_is_str_and_defaults_none(self) -> None:
        """``-p/--profile`` is a non-flag str option defaulting to None."""
        profile_param = next(p for p in pipeline.params if p.name == "profile")
        assert isinstance(profile_param, click.Option)
        assert profile_param.is_flag is False
        assert profile_param.default is None

    def test_pipeline_profile_option_has_short_and_long_flags(self) -> None:
        """The registered forms are ``-p`` (short alias) and ``--profile`` (long)."""
        profile_param = next(p for p in pipeline.params if p.name == "profile")
        assert "-p" in profile_param.opts
        assert "--profile" in profile_param.opts


class TestPipelineCallbackProfileSignature:
    def test_pipeline_callback_has_profile_parameter(self) -> None:
        """The decorated callback exposes a `profile` parameter."""
        parameters = pipeline_cmd.callback.__annotations__
        assert "profile" in parameters

    def test_pipeline_callback_profile_annotation_is_optional_str(self) -> None:
        """The ``profile`` callback parameter is typed ``str | None``."""
        hints = typing.get_type_hints(pipeline_cmd.callback)
        assert hints["profile"] == str | None


class TestPipelineProfileFlagSurface:
    def test_help_lists_profile_flag(self) -> None:
        """``--help`` advertises ``-p`` bound to ``--profile``."""
        runner = CliRunner()
        result = runner.invoke(pipeline, ["--help"])
        assert result.exit_code == 0
        # The rendered row pairs the short alias with the profile long form.
        assert "-p, --profile" in result.output
        assert "--profile" in result.output

    def test_pipeline_accepts_profile_short_flag_via_clirunner(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``-p NAME`` parses cleanly and forwards profile=<name>."""
        _write_config(tmp_path)
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        with mock.patch.object(_pipeline_module, "run_pipeline_container", return_value=0) as mock_run:
            result = runner.invoke(pipeline, ["deploy", "-p", "mixa"])

        assert result.exit_code == 0
        mock_run.assert_called_once()
        assert mock_run.call_args.kwargs["profile"] == "mixa"

    def test_pipeline_accepts_profile_long_flag_via_clirunner(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``--profile NAME`` parses identically to the short form."""
        _write_config(tmp_path)
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        with mock.patch.object(_pipeline_module, "run_pipeline_container", return_value=0) as mock_run:
            result = runner.invoke(pipeline, ["deploy", "--profile", "mixa"])

        assert result.exit_code == 0
        mock_run.assert_called_once()
        assert mock_run.call_args.kwargs["profile"] == "mixa"


# --- --parallel flag contract (long-only since -p moved to --profile) ---


class TestPipelineParallelFlagContract:
    def test_pipeline_has_parallel_option(self) -> None:
        """The pipeline command registers a ``--parallel`` click Option."""
        param_names = [p.name for p in pipeline.params]
        assert "parallel" in param_names

    def test_pipeline_parallel_option_is_int_and_defaults_none(self) -> None:
        """``--parallel`` is a non-flag int option defaulting to None (unbounded)."""
        parallel_param = next(p for p in pipeline.params if p.name == "parallel")
        assert isinstance(parallel_param, click.Option)
        assert parallel_param.is_flag is False
        assert parallel_param.default is None
        # type=int ⇒ Click materialises an int param type so ``--parallel foo`` is rejected.
        assert parallel_param.type.name == "integer"

    def test_pipeline_parallel_option_is_long_only(self) -> None:
        """The registered form is ``--parallel`` only — the ``-p`` alias belongs to ``--profile``."""
        parallel_param = next(p for p in pipeline.params if p.name == "parallel")
        assert parallel_param.opts == ["--parallel"]
        assert not parallel_param.secondary_opts


class TestPipelineCallbackParallelSignature:
    def test_pipeline_callback_has_parallel_parameter(self) -> None:
        """The decorated callback exposes a `parallel` parameter."""
        parameters = pipeline_cmd.callback.__annotations__
        assert "parallel" in parameters

    def test_pipeline_callback_parallel_annotation_is_optional_int(self) -> None:
        """The ``parallel`` callback parameter is typed ``int | None``."""
        hints = typing.get_type_hints(pipeline_cmd.callback)
        assert hints["parallel"] == int | None


class TestPipelineParallelFlagSurface:
    def test_help_lists_parallel_flag(self) -> None:
        """``--help`` advertises ``--parallel`` without a short alias."""
        runner = CliRunner()
        result = runner.invoke(pipeline, ["--help"])
        assert result.exit_code == 0
        assert "--parallel" in result.output

    def test_pipeline_accepts_parallel_flag_via_clirunner(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``--parallel N`` parses cleanly and forwards parallel=<N>."""
        _write_config(tmp_path)
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        with mock.patch.object(_pipeline_module, "run_pipeline_container", return_value=0) as mock_run:
            result = runner.invoke(pipeline, ["deploy", "--parallel", "4"])

        assert result.exit_code == 0
        mock_run.assert_called_once()
        assert mock_run.call_args.kwargs["parallel"] == 4
