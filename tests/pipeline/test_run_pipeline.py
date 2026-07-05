from __future__ import annotations

import inspect
import sys
from pathlib import Path
from unittest import mock
from unittest.mock import call

import pytest
from goga.pipeline import run_pipeline

# goga.pipeline.run_pipeline is shadowed in the package __init__ by the
# run_pipeline function, so a string-based mock.patch path walking through it
# fails on Python 3.10. Resolve the real module via sys.modules and patch its
# run_flow attribute directly. Per [[feedback_mock_patch_module_shadowing]].
_run_pipeline_module = sys.modules["goga.pipeline.run_pipeline"]


class TestRunPipelineContract:
    def test_run_pipeline_importable_from_facade(self) -> None:
        """run_pipeline is importable from the goga.pipeline facade."""
        assert run_pipeline is not None

    def test_run_pipeline_signature_matches_contract(self) -> None:
        """run_pipeline exposes the (name, project_dir, user_dir, port) signature."""
        signature = inspect.signature(run_pipeline)
        parameters = list(signature.parameters)

        assert parameters == ["name", "project_dir", "user_dir", "port"]

    def test_run_pipeline_returns_int(self, tmp_path: Path) -> None:
        """run_pipeline returns 0 on a successful (exit 0) afm invocation."""
        project_dir = tmp_path / "pipelines"
        project_dir.mkdir()
        (project_dir / "deploy.yml").write_text("pipeline")

        with mock.patch.object(
            _run_pipeline_module,
            "run_flow",
            return_value=0,
        ):
            exit_code = run_pipeline("deploy", project_dir, tmp_path / "user_pipelines", 50321)

        assert exit_code == 0


class TestRunPipelineLogic:
    def test_run_pipeline_passes_absolute_project_path_and_port_to_run_flow(self, tmp_path: Path) -> None:
        """Project source wins; the absolute path and integer port reach run_flow."""
        project_dir = tmp_path / "pipelines"
        project_dir.mkdir()
        (project_dir / "deploy.yml").write_text("pipeline")
        user_dir = tmp_path / "user_pipelines"
        user_dir.mkdir()
        (user_dir / "deploy.yml").write_text("pipeline")

        with mock.patch.object(
            _run_pipeline_module,
            "run_flow",
            return_value=0,
        ) as mock_run_flow:
            exit_code = run_pipeline("deploy", project_dir, user_dir, 50321)

        assert exit_code == 0
        mock_run_flow.assert_called_once_with(project_dir / "deploy.yml", 50321)

    def test_run_pipeline_resolves_user_source_when_only_in_user_dir(self, tmp_path: Path) -> None:
        """A pipeline present only in user_dir is resolved against the user directory, port forwarded."""
        project_dir = tmp_path / "pipelines"
        project_dir.mkdir()
        user_dir = tmp_path / "user_pipelines"
        user_dir.mkdir()
        (user_dir / "deploy.yml").write_text("pipeline")

        with mock.patch.object(
            _run_pipeline_module,
            "run_flow",
            return_value=0,
        ) as mock_run_flow:
            exit_code = run_pipeline("deploy", project_dir, user_dir, 50321)

        assert exit_code == 0
        mock_run_flow.assert_called_once_with(user_dir / "deploy.yml", 50321)

    def test_run_pipeline_returns_nonzero_when_name_not_found(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A missing pipeline name returns nonzero with a clear message, without invoking run_flow."""
        project_dir = tmp_path / "pipelines"
        user_dir = tmp_path / "user_pipelines"

        with mock.patch.object(_run_pipeline_module, "run_flow") as mock_run_flow:
            exit_code = run_pipeline("nonexistent", project_dir, user_dir, 50321)

        assert exit_code != 0
        mock_run_flow.assert_not_called()
        captured = capsys.readouterr()
        assert "missing" in captured.err

    def test_run_pipeline_rejects_yml_suffixed_name(self, tmp_path: Path) -> None:
        """A name carrying the '.yml' suffix never matches an entry (entry names are extension-less)."""
        project_dir = tmp_path / "pipelines"
        project_dir.mkdir()
        (project_dir / "deploy.yml").write_text("pipeline")

        with mock.patch.object(_run_pipeline_module, "run_flow") as mock_run_flow:
            exit_code = run_pipeline("deploy.yml", project_dir, tmp_path / "user_pipelines", 50321)

        assert exit_code != 0
        mock_run_flow.assert_not_called()

    def test_run_pipeline_propagates_run_flow_exit_code(self, tmp_path: Path) -> None:
        """run_pipeline propagates run_flow's exit code unchanged."""
        project_dir = tmp_path / "pipelines"
        project_dir.mkdir()
        (project_dir / "deploy.yml").write_text("pipeline")

        with mock.patch.object(
            _run_pipeline_module,
            "run_flow",
            return_value=7,
        ):
            exit_code = run_pipeline("deploy", project_dir, tmp_path / "user_pipelines", 50321)

        assert exit_code == 7

    def test_run_pipeline_propagates_missing_binary_exit_code(self, tmp_path: Path) -> None:
        """run_pipeline propagates run_flow's 127 (missing afm binary) exit code."""
        project_dir = tmp_path / "pipelines"
        project_dir.mkdir()
        (project_dir / "deploy.yml").write_text("pipeline")

        with mock.patch.object(
            _run_pipeline_module,
            "run_flow",
            return_value=127,
        ):
            exit_code = run_pipeline("deploy", project_dir, tmp_path / "user_pipelines", 50321)

        assert exit_code == 127

    def test_run_pipeline_forwards_distinct_port_values(self, tmp_path: Path) -> None:
        """The port integer is forwarded verbatim to run_flow — single source of truth."""
        project_dir = tmp_path / "pipelines"
        project_dir.mkdir()
        (project_dir / "deploy.yml").write_text("pipeline")

        with mock.patch.object(
            _run_pipeline_module,
            "run_flow",
            return_value=0,
        ) as mock_run_flow:
            run_pipeline("deploy", project_dir, tmp_path / "user_pipelines", 8080)

        assert mock_run_flow.call_args == call(project_dir / "deploy.yml", 8080)
