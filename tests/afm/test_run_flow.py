from __future__ import annotations

import inspect
from pathlib import Path
from unittest import mock
from unittest.mock import MagicMock

import pytest
from goga.afm import run_flow


class TestRunFlowContract:
    def test_run_flow_importable_from_facade(self) -> None:
        """run_flow is importable from the goga.afm facade."""
        assert run_flow is not None

    def test_run_flow_signature_matches_contract(self) -> None:
        """run_flow exposes the (name, project_dir, user_dir) signature."""
        signature = inspect.signature(run_flow)
        parameters = list(signature.parameters)

        assert parameters == ["name", "project_dir", "user_dir"]

    def test_run_flow_returns_int(self, tmp_path: Path) -> None:
        """run_flow returns an int exit code in a mocked scenario."""
        project_dir = tmp_path / "flows"
        project_dir.mkdir()
        (project_dir / "deploy.yml").write_text("flow")

        with mock.patch(
            "goga.afm.run_flow.subprocess.run",
            return_value=MagicMock(returncode=0),
        ):
            exit_code = run_flow("deploy", project_dir, tmp_path / "user_flows")

        assert isinstance(exit_code, int)


class TestRunFlowLogic:
    def test_run_flow_invokes_flowmanager_with_absolute_path(
        self, tmp_path: Path
    ) -> None:
        """The flow file's absolute path (not the bare name) reaches flowmanager."""
        project_dir = tmp_path / "flows"
        project_dir.mkdir()
        (project_dir / "deploy.yml").write_text("flow")
        user_dir = tmp_path / "user_flows"

        with mock.patch(
            "goga.afm.run_flow.subprocess.run",
            return_value=MagicMock(returncode=0),
        ) as mock_subprocess:
            exit_code = run_flow("deploy", project_dir, user_dir)

        assert exit_code == 0
        mock_subprocess.assert_called_once()
        called_args = mock_subprocess.call_args.args[0]
        assert called_args[2] == str(project_dir / "deploy.yml")

    def test_run_flow_returns_nonzero_when_flow_not_found(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A missing flow name returns nonzero with a clear message, without invoking flowmanager."""
        project_dir = tmp_path / "flows"
        user_dir = tmp_path / "user_flows"

        with mock.patch("goga.afm.run_flow.subprocess.run") as mock_subprocess:
            exit_code = run_flow("nonexistent", project_dir, user_dir)

        assert exit_code == 1
        mock_subprocess.assert_not_called()
        captured = capsys.readouterr()
        assert "nonexistent" in captured.err
        assert "not found" in captured.err

    def test_run_flow_resolves_user_source_when_only_in_user_dir(
        self, tmp_path: Path
    ) -> None:
        """A flow present only in user_dir is resolved against the user directory."""
        project_dir = tmp_path / "flows"
        project_dir.mkdir()
        user_dir = tmp_path / "user_flows"
        user_dir.mkdir()
        (user_dir / "deploy.yml").write_text("flow")

        with mock.patch(
            "goga.afm.run_flow.subprocess.run",
            return_value=MagicMock(returncode=0),
        ) as mock_subprocess:
            exit_code = run_flow("deploy", project_dir, user_dir)

        assert exit_code == 0
        mock_subprocess.assert_called_once()
        called_args = mock_subprocess.call_args.args[0]
        assert called_args[2] == str(user_dir / "deploy.yml")

    def test_run_flow_handles_missing_flowmanager_binary(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A missing flowmanager binary yields a nonzero code and a clear message."""
        project_dir = tmp_path / "flows"
        project_dir.mkdir()
        (project_dir / "deploy.yml").write_text("flow")

        with mock.patch(
            "goga.afm.run_flow.subprocess.run", side_effect=FileNotFoundError
        ):
            exit_code = run_flow("deploy", project_dir, tmp_path / "user_flows")

        assert exit_code != 0
        assert exit_code == 127
        captured = capsys.readouterr()
        assert "flowmanager" in captured.err
        assert "PATH" in captured.err
