from __future__ import annotations

import inspect
from pathlib import Path
from unittest import mock
from unittest.mock import MagicMock

import pytest
from goga.pipeline import run_pipeline


class TestRunPipelineContract:
    def test_run_pipeline_importable_from_facade(self) -> None:
        """run_pipeline is importable from the goga.pipeline facade."""
        assert run_pipeline is not None

    def test_run_pipeline_signature_matches_contract(self) -> None:
        """run_pipeline exposes the (name, project_dir, user_dir) signature."""
        signature = inspect.signature(run_pipeline)
        parameters = list(signature.parameters)

        assert parameters == ["name", "project_dir", "user_dir"]

    def test_run_pipeline_returns_int(self, tmp_path: Path) -> None:
        """run_pipeline returns 0 on a successful (exit 0) flowmanager invocation."""
        project_dir = tmp_path / "pipelines"
        project_dir.mkdir()
        (project_dir / "deploy.yml").write_text("pipeline")

        with mock.patch(
            "goga.pipeline.run_pipeline.run_flow",
            return_value=0,
        ):
            exit_code = run_pipeline("deploy", project_dir, tmp_path / "user_pipelines")

        assert exit_code == 0


class TestRunPipelineLogic:
    def test_run_pipeline_resolves_project_source_and_invokes_run_flow(
        self, tmp_path: Path
    ) -> None:
        """run_pipeline resolves the project pipeline path and calls run_flow with it."""
        project_dir = tmp_path / "pipelines"
        project_dir.mkdir()
        (project_dir / "deploy.yml").write_text("pipeline")
        user_dir = tmp_path / "user_pipelines"

        with mock.patch(
            "goga.pipeline.run_pipeline.run_flow",
            return_value=0,
        ) as mock_run_flow:
            exit_code = run_pipeline("deploy", project_dir, user_dir)

        assert exit_code == 0
        mock_run_flow.assert_called_once()
        called_path = mock_run_flow.call_args.args[0]
        assert called_path == (project_dir / "deploy.yml").resolve()

    def test_run_pipeline_resolves_user_source_when_only_in_user_dir(
        self, tmp_path: Path
    ) -> None:
        """A pipeline present only in user_dir is resolved against the user directory."""
        project_dir = tmp_path / "pipelines"
        project_dir.mkdir()
        user_dir = tmp_path / "user_pipelines"
        user_dir.mkdir()
        (user_dir / "deploy.yml").write_text("pipeline")

        with mock.patch(
            "goga.pipeline.run_pipeline.run_flow",
            return_value=0,
        ) as mock_run_flow:
            exit_code = run_pipeline("deploy", project_dir, user_dir)

        assert exit_code == 0
        mock_run_flow.assert_called_once()
        called_path = mock_run_flow.call_args.args[0]
        assert called_path == (user_dir / "deploy.yml").resolve()

    def test_run_pipeline_returns_nonzero_when_pipeline_not_found(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A missing pipeline name returns nonzero with a clear message, without invoking run_flow."""
        project_dir = tmp_path / "pipelines"
        user_dir = tmp_path / "user_pipelines"

        with mock.patch("goga.pipeline.run_pipeline.run_flow") as mock_run_flow:
            exit_code = run_pipeline("nonexistent", project_dir, user_dir)

        assert exit_code == 1
        mock_run_flow.assert_not_called()
        captured = capsys.readouterr()
        assert "nonexistent" in captured.err
        assert "not found" in captured.err

    def test_run_pipeline_propagates_run_flow_exit_code(self, tmp_path: Path) -> None:
        """run_pipeline propagates run_flow's exit code unchanged."""
        project_dir = tmp_path / "pipelines"
        project_dir.mkdir()
        (project_dir / "deploy.yml").write_text("pipeline")

        with mock.patch(
            "goga.pipeline.run_pipeline.run_flow",
            return_value=7,
        ):
            exit_code = run_pipeline("deploy", project_dir, tmp_path / "user_pipelines")

        assert exit_code == 7

    def test_run_pipeline_propagates_missing_binary_exit_code(self, tmp_path: Path) -> None:
        """run_pipeline propagates run_flow's 127 (missing binary) exit code."""
        project_dir = tmp_path / "pipelines"
        project_dir.mkdir()
        (project_dir / "deploy.yml").write_text("pipeline")

        with mock.patch(
            "goga.pipeline.run_pipeline.run_flow",
            return_value=127,
        ):
            exit_code = run_pipeline("deploy", project_dir, tmp_path / "user_pipelines")

        assert exit_code == 127
