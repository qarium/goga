from __future__ import annotations

import inspect
from pathlib import Path
from unittest import mock

import click
from click.testing import CliRunner
from goga.commands.pipeline import pipeline
from goga.commands.pipeline.pipeline import pipeline as pipeline_cmd


class TestPipelineContract:
    def test_pipeline_importable_from_facade(self) -> None:
        """pipeline is importable from the goga.commands.pipeline facade."""
        assert pipeline is not None

    def test_pipeline_is_a_click_command(self) -> None:
        """pipeline is a single click.Command (NOT a group — no subcommands)."""
        assert isinstance(pipeline, click.Command)
        assert not isinstance(pipeline, click.Group)

    def test_pipeline_callback_takes_optional_name(self) -> None:
        """The pipeline command exposes an optional positional name argument (required=False)."""
        parameters = inspect.signature(pipeline_cmd.callback).parameters

        assert "name" in parameters
        # The Click-decorated command exposes name as optional (required=False).
        # Click's optional positional argument does not carry a Python default on
        # the callback (it is inspect.Parameter.empty); the relevant property is
        # that the registered argument is not required.
        name_param = next(p for p in pipeline.params if isinstance(p, click.Argument) and p.name == "name")
        assert name_param.required is False


class TestPipelineLogic:
    def test_pipeline_with_name_invokes_run_pipeline_and_propagates_exit(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """pipeline <name> delegates to run_pipeline and propagates its exit code."""
        monkeypatch.setattr(Path, "cwd", lambda: tmp_path)
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        pipelines_dir = tmp_path / ".goga" / "pipelines"
        pipelines_dir.mkdir(parents=True)
        (pipelines_dir / "deploy.yml").write_text("pipeline")

        runner = CliRunner()
        with mock.patch("goga.commands.pipeline.pipeline.run_pipeline", return_value=42):
            result = runner.invoke(pipeline, ["deploy"])

        assert result.exit_code == 42

    def test_pipeline_without_name_lists_pipelines(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """pipeline (no name) prints 'Available pipelines:' header and the list."""
        project_tmp = tmp_path / "project"
        project_tmp.mkdir()
        user_tmp = tmp_path / "user"
        user_tmp.mkdir()

        project_pipelines = project_tmp / ".goga" / "pipelines"
        project_pipelines.mkdir(parents=True)
        (project_pipelines / "deploy.yml").write_text("pipeline")

        user_pipelines = user_tmp / ".goga" / "pipelines"
        user_pipelines.mkdir(parents=True)
        (user_pipelines / "build.yml").write_text("pipeline")

        monkeypatch.setattr(Path, "cwd", lambda: project_tmp)
        monkeypatch.setattr(Path, "home", lambda: user_tmp)

        runner = CliRunner()
        result = runner.invoke(pipeline, [])

        assert result.exit_code == 0
        assert "Available pipelines:" in result.output
        assert "deploy (project)" in result.output
        assert "build" in result.output
        assert "build (project)" not in result.output

    def test_pipeline_without_name_prints_header_even_when_empty(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """The 'Available pipelines:' header is always printed, even for an empty list."""
        monkeypatch.setattr(Path, "cwd", lambda: tmp_path)
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        runner = CliRunner()
        result = runner.invoke(pipeline, [])

        assert result.exit_code == 0
        assert "Available pipelines:" in result.output
