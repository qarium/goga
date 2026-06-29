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
        """run_flow returns 0 on a successful (exit 0) flowmanager invocation."""
        project_dir = tmp_path / "flows"
        project_dir.mkdir()
        (project_dir / "deploy.yml").write_text("flow")

        with mock.patch(
            "goga.afm.run_flow.subprocess.run",
            return_value=MagicMock(returncode=0),
        ):
            exit_code = run_flow("deploy", project_dir, tmp_path / "user_flows")

        assert exit_code == 0


class TestRunFlowLogic:
    def test_run_flow_invokes_flowmanager_with_absolute_path(self, tmp_path: Path) -> None:
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

    def test_run_flow_resolves_user_source_when_only_in_user_dir(self, tmp_path: Path) -> None:
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

        with mock.patch("goga.afm.run_flow.subprocess.run", side_effect=FileNotFoundError):
            exit_code = run_flow("deploy", project_dir, tmp_path / "user_flows")

        assert exit_code != 0
        assert exit_code == 127
        captured = capsys.readouterr()
        assert "flowmanager" in captured.err
        assert "PATH" in captured.err

    def test_run_flow_handles_non_executable_flowmanager_binary(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A present-but-not-executable flowmanager yields a nonzero code and a clear message, without raising."""
        project_dir = tmp_path / "flows"
        project_dir.mkdir()
        (project_dir / "deploy.yml").write_text("flow")

        with mock.patch("goga.afm.run_flow.subprocess.run", side_effect=PermissionError("denied")):
            exit_code = run_flow("deploy", project_dir, tmp_path / "user_flows")

        assert exit_code != 0
        assert exit_code == 126
        captured = capsys.readouterr()
        assert "flowmanager" in captured.err

    def test_run_flow_propagates_nonzero_flowmanager_exit_code(self, tmp_path: Path) -> None:
        """A non-zero flowmanager exit code is propagated unchanged (not collapsed to 1)."""
        project_dir = tmp_path / "flows"
        project_dir.mkdir()
        (project_dir / "deploy.yml").write_text("flow")

        with mock.patch(
            "goga.afm.run_flow.subprocess.run",
            return_value=MagicMock(returncode=7),
        ):
            exit_code = run_flow("deploy", project_dir, tmp_path / "user_flows")

        assert exit_code == 7

    def test_run_flow_passes_absolute_path_even_for_relative_source(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """run_flow enforces its absolute-path contract regardless of caller input.

        flowmanager resolves the positional arg against its own CWD, so a relative
        path would read the wrong file. Even when the caller passes a relative
        source directory, flowmanager must receive an absolute path.
        """
        project_dir = tmp_path / "flows"
        project_dir.mkdir()
        (project_dir / "deploy.yml").write_text("flow")
        monkeypatch.chdir(tmp_path)

        with mock.patch(
            "goga.afm.run_flow.subprocess.run",
            return_value=MagicMock(returncode=0),
        ) as mock_subprocess:
            exit_code = run_flow("deploy", Path("flows"), Path("user_flows"))

        assert exit_code == 0
        passed_path = Path(mock_subprocess.call_args.args[0][2])
        assert passed_path.is_absolute()
        assert passed_path == (tmp_path / "flows" / "deploy.yml").resolve()
