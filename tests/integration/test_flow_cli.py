"""End-to-end integration tests for the ``flow`` CLI group.

These exercise the full cross-cell path through the root ``app`` group:

    goga flow run <name> -> flow.run -> goga.afm.run_flow -> subprocess.run(["flowmanager", ...])
    goga flow ls        -> flow.ls  -> goga.afm.list_flows -> filesystem

The ``flowmanager`` binary is mocked at the subprocess boundary so the real
binary is never invoked. The flow group is registered on ``app`` under the name
``flow`` (per ``goga/CODEMANIFEST`` ``app()`` annotation), so all invocations
target ``["flow", ...]``.
"""

from __future__ import annotations

from pathlib import Path
from unittest import mock
from unittest.mock import MagicMock

from click.testing import CliRunner
from goga.cli import app


class TestFlowCliCrossEntity:
    def test_run_invokes_flowmanager_with_absolute_path(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """goga flow run reaches run_flow and passes the absolute flow path."""
        project_tmp = tmp_path / "project"
        project_tmp.mkdir()
        user_tmp = tmp_path / "user"
        user_tmp.mkdir()

        project_flows = project_tmp / ".goga" / "flows"
        project_flows.mkdir(parents=True)
        (project_flows / "deploy.yml").write_text("flow")

        monkeypatch.setattr(Path, "cwd", lambda: project_tmp)
        monkeypatch.setattr(Path, "home", lambda: user_tmp)

        runner = CliRunner()
        with mock.patch(
            "goga.afm.run_flow.subprocess.run",
            return_value=MagicMock(returncode=0),
        ) as mock_subprocess:
            result = runner.invoke(app, ["flow", "run", "deploy"])

        assert result.exit_code == 0
        mock_subprocess.assert_called_once()
        called_args = mock_subprocess.call_args.args[0]
        assert called_args[0] == "flowmanager"
        assert called_args[1] == "run"
        # The absolute flow path (not the bare name) reaches the binary.
        assert called_args[2] == str(project_flows / "deploy.yml")

    def test_run_missing_flow_is_nonzero_without_subprocess(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """goga flow run <missing> returns nonzero without invoking flowmanager."""
        monkeypatch.setattr(Path, "cwd", lambda: tmp_path)
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        runner = CliRunner()
        with mock.patch("goga.afm.run_flow.subprocess.run") as mock_subprocess:
            result = runner.invoke(app, ["flow", "run", "missing"])

        assert result.exit_code != 0
        mock_subprocess.assert_not_called()


class TestFlowCliList:
    def test_ls_marks_project_flows_only(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """goga flow ls annotates project flows with (project) and user flows bare."""
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
        result = runner.invoke(app, ["flow", "ls"])

        assert result.exit_code == 0
        assert "deploy (project)" in result.output
        assert "build" in result.output
        assert "build (project)" not in result.output
