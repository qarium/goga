from __future__ import annotations

import inspect
from pathlib import Path
from unittest import mock

import click
from click.testing import CliRunner
from goga.commands.flow import flow
from goga.commands.flow.flow import ls, run


class TestFlowContract:
    def test_flow_importable_from_facade(self) -> None:
        """flow is importable from the goga.commands.flow facade."""
        assert flow is not None

    def test_flow_is_a_click_group(self) -> None:
        """flow is a click.Group instance."""
        assert isinstance(flow, click.Group)

    def test_flow_has_ls_and_run_subcommands(self) -> None:
        """flow exposes the ls and run subcommands."""
        assert "ls" in flow.commands
        assert "run" in flow.commands

    def test_run_callback_signature_includes_name(self) -> None:
        """The run callback declares the positional name argument."""
        parameters = inspect.signature(run.callback).parameters

        assert "name" in parameters

    def test_ls_does_not_accept_arguments(self) -> None:
        """The ls callback takes no positional flow arguments."""
        parameters = inspect.signature(ls.callback).parameters

        assert "name" not in parameters


class TestFlowLogic:
    def test_ls_command_outputs_project_marker(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """ls annotates project flows with (project) and leaves user flows bare."""
        project_tmp = tmp_path / "project"
        project_tmp.mkdir()
        user_tmp = tmp_path / "user"
        user_tmp.mkdir()

        project_flows = project_tmp / ".goga" / "flows"
        project_flows.mkdir(parents=True)
        (project_flows / "deploy.yml").write_text("flow")

        user_flows = user_tmp / ".goga" / "flows"
        user_flows.mkdir(parents=True)
        (user_flows / "build.yml").write_text("flow")

        monkeypatch.setattr(Path, "cwd", lambda: project_tmp)
        monkeypatch.setattr(Path, "home", lambda: user_tmp)

        runner = CliRunner()
        result = runner.invoke(flow, ["ls"])

        assert result.exit_code == 0
        assert "deploy (project)" in result.output
        assert "build" in result.output
        assert "build (project)" not in result.output

    def test_run_command_propagates_exit_code_via_ctx(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """run delegates to run_flow and propagates its exit code via ctx."""
        monkeypatch.setattr(Path, "cwd", lambda: tmp_path)
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        flows_dir = tmp_path / ".goga" / "flows"
        flows_dir.mkdir(parents=True)
        (flows_dir / "deploy.yml").write_text("flow")

        runner = CliRunner()
        with mock.patch("goga.commands.flow.flow.run_flow", return_value=42):
            result = runner.invoke(flow, ["run", "deploy"])

        assert result.exit_code == 42

    def test_ls_command_empty_output_when_no_flows(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """ls produces no output (and exit code 0) when no flows exist."""
        monkeypatch.setattr(Path, "cwd", lambda: tmp_path)
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        runner = CliRunner()
        result = runner.invoke(flow, ["ls"])

        assert result.exit_code == 0
        assert result.output == ""
