from __future__ import annotations

import inspect
import sys
from pathlib import Path
from unittest import mock

import pytest
from goga.pipeline import pipeline_cli
from goga.pipeline.compiler import StructuralError

# Importing ``pipeline_cli`` from the package __init__ shadows the ``cli``
# submodule name in attribute access, so a string-based ``mock.patch`` path is
# unreliable on Python 3.10. Resolve the real module via ``sys.modules`` and
# patch its ``run_pipeline`` attribute directly. Per
# [[feedback_mock_patch_module_shadowing]].
_cli_module = sys.modules["goga.pipeline.cli"]


class TestPipelineCliContract:
    def test_pipeline_cli_importable_from_facade(self) -> None:
        """pipeline_cli is importable from the goga.pipeline facade."""
        assert pipeline_cli is not None

    def test_pipeline_cli_signature_has_argv_and_returns_int(self) -> None:
        """pipeline_cli exposes the (argv) -> int signature."""
        signature = inspect.signature(pipeline_cli)

        assert "argv" in signature.parameters
        assert signature.return_annotation in (int, "int")

    def test_run_subparser_accepts_parallel_option(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The `run` subparser accepts an optional `--parallel N` (int) flag.

        Before the option exists argparse rejects `--parallel` as an unknown
        argument (SystemExit code 2); after wiring it in the CLI accepts it and
        returns 0.
        """
        monkeypatch.setattr(Path, "cwd", lambda: tmp_path)
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        with mock.patch.object(_cli_module, "run_pipeline", return_value=0):
            exit_code = pipeline_cli(["run", "deploy", "--port", "50321", "--parallel", "4"])

        assert exit_code == 0

    def test_parallel_option_optional_threads_none_when_absent(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """`--parallel` is optional: its absence threads `parallel=None` to run_pipeline."""
        monkeypatch.setattr(Path, "cwd", lambda: tmp_path)
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        with mock.patch.object(_cli_module, "run_pipeline", return_value=0) as mock_run_pipeline:
            exit_code = pipeline_cli(["run", "deploy", "--port", "50321"])

        assert exit_code == 0
        assert "parallel" in mock_run_pipeline.call_args.kwargs
        assert mock_run_pipeline.call_args.kwargs["parallel"] is None


class TestPipelineCliLogic:
    def test_pipeline_cli_list_prints_header_and_entries(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """list echoes the header then one entry per line, project source suffixed."""
        project_root = tmp_path / "project"
        project_root.mkdir()
        project_dir = project_root / ".goga" / "pipelines"
        project_dir.mkdir(parents=True)
        (project_dir / "deploy.yml").write_text("pipeline")

        user_root = tmp_path / "user"
        user_root.mkdir()
        user_dir = user_root / ".goga" / "pipelines"
        user_dir.mkdir(parents=True)
        (user_dir / "rollback.yml").write_text("pipeline")

        monkeypatch.setattr(Path, "cwd", lambda: project_root)
        monkeypatch.setattr(Path, "home", lambda: user_root)

        exit_code = pipeline_cli(["list"])

        assert exit_code == 0
        captured = capsys.readouterr()
        assert captured.out.startswith("Available pipelines:\n")
        assert "  deploy (project)" in captured.out
        assert "  rollback" in captured.out

    def test_pipeline_cli_list_prints_header_on_empty_dir(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """An empty set of directories still prints the header line and returns 0."""
        project_root = tmp_path / "project"
        project_root.mkdir()
        user_root = tmp_path / "user"
        user_root.mkdir()

        monkeypatch.setattr(Path, "cwd", lambda: project_root)
        monkeypatch.setattr(Path, "home", lambda: user_root)

        exit_code = pipeline_cli(["list"])

        assert exit_code == 0
        captured = capsys.readouterr()
        assert captured.out == "Available pipelines:\n"

    def test_pipeline_cli_run_passes_name_dirs_and_port_to_run_pipeline(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """run forwards NAME, the resolved dirs, and PORT to run_pipeline (parallel defaults None)."""
        project_root = tmp_path / "project"
        project_root.mkdir()
        user_root = tmp_path / "user"
        user_root.mkdir()

        monkeypatch.setattr(Path, "cwd", lambda: project_root)
        monkeypatch.setattr(Path, "home", lambda: user_root)

        with mock.patch.object(
            _cli_module,
            "run_pipeline",
            return_value=0,
        ) as mock_run_pipeline:
            exit_code = pipeline_cli(["run", "deploy", "--port", "50321"])

        assert exit_code == 0
        project_dir = project_root / ".goga" / "pipelines"
        user_dir = user_root / ".goga" / "pipelines"
        mock_run_pipeline.assert_called_once_with("deploy", project_dir, user_dir, 50321, parallel=None)

    def test_pipeline_cli_passes_parallel_to_run_pipeline(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """`run ... --parallel N` threads parallel=N through to run_pipeline."""
        monkeypatch.setattr(Path, "cwd", lambda: tmp_path)
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        with mock.patch.object(
            _cli_module,
            "run_pipeline",
            return_value=0,
        ) as mock_run_pipeline:
            exit_code = pipeline_cli(["run", "deploy", "--port", "50321", "--parallel", "4"])

        assert exit_code == 0
        project_dir = tmp_path / ".goga" / "pipelines"
        user_dir = tmp_path / ".goga" / "pipelines"
        mock_run_pipeline.assert_called_once_with("deploy", project_dir, user_dir, 50321, parallel=4)

    def test_pipeline_cli_parallel_defaults_none(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Absence of --parallel threads parallel=None (omitted downstream as a flag)."""
        monkeypatch.setattr(Path, "cwd", lambda: tmp_path)
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        with mock.patch.object(
            _cli_module,
            "run_pipeline",
            return_value=0,
        ) as mock_run_pipeline:
            exit_code = pipeline_cli(["run", "deploy", "--port", "50321"])

        assert exit_code == 0
        assert mock_run_pipeline.call_args.kwargs["parallel"] is None

    def test_pipeline_cli_run_without_port_exits_with_2(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Missing required --port is an argparse error → exit code 2."""
        monkeypatch.setattr(Path, "cwd", lambda: tmp_path)
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        with pytest.raises(SystemExit) as exc_info:
            pipeline_cli(["run", "deploy"])

        assert exc_info.value.code == 2

    def test_pipeline_cli_run_without_name_exits_with_2(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Missing required NAME positional is an argparse error → exit code 2."""
        monkeypatch.setattr(Path, "cwd", lambda: tmp_path)
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        with pytest.raises(SystemExit) as exc_info:
            pipeline_cli(["run", "--port", "50321"])

        assert exc_info.value.code == 2

    def test_pipeline_cli_run_with_non_int_port_exits_with_2(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A non-integer --port is an argparse error → exit code 2."""
        monkeypatch.setattr(Path, "cwd", lambda: tmp_path)
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        with pytest.raises(SystemExit) as exc_info:
            pipeline_cli(["run", "deploy", "--port", "abc"])

        assert exc_info.value.code == 2

    def test_pipeline_cli_run_malformed_pipeline_reports_error_and_returns_1(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """A StructuralError from run_pipeline is reported as a clean stderr message, exit 1."""
        monkeypatch.setattr(Path, "cwd", lambda: tmp_path)
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        with mock.patch.object(
            _cli_module,
            "run_pipeline",
            side_effect=StructuralError("unsupported body format"),
        ):
            exit_code = pipeline_cli(["run", "deploy", "--port", "50321"])

        assert exit_code == 1
        captured = capsys.readouterr()
        assert "malformed" in captured.err
        assert "deploy" in captured.err
        assert "unsupported body format" in captured.err

    def test_pipeline_cli_run_runtime_error_reports_error_and_returns_1(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """A RuntimeError from run_pipeline (e.g. AFM_DIR unset) is reported cleanly, exit 1."""
        monkeypatch.setattr(Path, "cwd", lambda: tmp_path)
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        with mock.patch.object(
            _cli_module,
            "run_pipeline",
            side_effect=RuntimeError("AFM_DIR not set"),
        ):
            exit_code = pipeline_cli(["run", "deploy", "--port", "50321"])

        assert exit_code == 1
        captured = capsys.readouterr()
        assert "AFM_DIR not set" in captured.err

    def test_pipeline_cli_run_yaml_error_reports_error_and_returns_1(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Invalid YAML in the pipeline file is reported as a clean stderr message, exit 1."""
        import yaml

        monkeypatch.setattr(Path, "cwd", lambda: tmp_path)
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        with mock.patch.object(
            _cli_module,
            "run_pipeline",
            side_effect=yaml.YAMLError("bad indentation"),
        ):
            exit_code = pipeline_cli(["run", "deploy", "--port", "50321"])

        assert exit_code == 1
        captured = capsys.readouterr()
        assert "invalid YAML" in captured.err
        assert "deploy" in captured.err

    def test_pipeline_cli_run_oserror_reports_error_and_returns_1(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """An OSError (unreadable pipeline / missing flow dir) is reported cleanly, exit 1."""
        monkeypatch.setattr(Path, "cwd", lambda: tmp_path)
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        with mock.patch.object(
            _cli_module,
            "run_pipeline",
            side_effect=FileNotFoundError("[Errno 2] No such file or directory: '/x/flow.yml'"),
        ):
            exit_code = pipeline_cli(["run", "deploy", "--port", "50321"])

        assert exit_code == 1
        captured = capsys.readouterr()
        assert "could not be read or written" in captured.err
