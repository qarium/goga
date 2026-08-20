from __future__ import annotations

import inspect
import sys
from pathlib import Path
from unittest import mock

import pytest
from goga.pipeline import pipeline_cli
from goga.pipeline.compiler import StructuralError
from goga.pipeline.pipeline_card import CardStage, PipelineCard

# Importing ``pipeline_cli`` from the package __init__ shadows the ``cli``
# submodule name in attribute access, so a string-based ``mock.patch`` path is
# unreliable on Python 3.10. Resolve the real module via ``sys.modules`` and
# patch its ``run_pipeline`` attribute directly. Per
# [[feedback_mock_patch_module_shadowing]].
_cli_module = sys.modules["goga.pipeline.cli"]

# General Setup fixtures (STAGES DSL file + workflow files).
_DEPLOY_YML = """\
name: Deploy
description: Deploy the service
---

build:
  title: Build
test:
  title: Test
  depends_on:
    - build
"""


def _write_pipeline(cwd: Path, name: str, text: str) -> Path:
    """Write a pipeline-file into ``<cwd>/.goga/pipelines/`` and return its path."""
    project_dir = cwd / ".goga" / "pipelines"
    project_dir.mkdir(parents=True, exist_ok=True)
    path = project_dir / f"{name}.yml"
    path.write_text(text)
    return path


class TestPipelineCliContract:
    def test_pipeline_cli_importable_from_facade(self) -> None:
        """pipeline_cli is importable from the goga.pipeline facade."""
        assert pipeline_cli is not None

    def test_pipeline_cli_signature_has_argv_and_returns_int(self) -> None:
        """pipeline_cli exposes the (argv) -> int signature."""
        signature = inspect.signature(pipeline_cli)

        assert "argv" in signature.parameters
        assert signature.return_annotation in (int, "int")

    def test_list_subparser_accepts_info_flag(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """The `list` subparser accepts `--info` (and its `-i` short form).

        Before the flag exists argparse rejects `--info` as an unknown
        argument (SystemExit code 2); after wiring it in the CLI dispatches
        the overview and returns 0.
        """
        monkeypatch.setattr(Path, "cwd", lambda: tmp_path)
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        with mock.patch.object(
            _cli_module, "describe_pipelines", return_value=[]
        ) as mock_describe:
            exit_code = pipeline_cli(["list", "--info"])

        assert exit_code == 0
        assert mock_describe.called

    def test_run_subparser_accepts_info_and_workflow_flags(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """`run` accepts `--info` with `-w WF`, and separately `--no-workflow`."""
        monkeypatch.setattr(Path, "cwd", lambda: tmp_path)
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        card = PipelineCard(name="Deploy", description="Deploy the service", stages=[])
        with mock.patch.object(_cli_module, "describe_pipeline", return_value=card) as mock_describe:
            exit_code = pipeline_cli(["run", "deploy", "--info", "-w", "hardening"])

        assert exit_code == 0
        assert mock_describe.call_args.kwargs["workflow"] == "hardening"

        with mock.patch.object(_cli_module, "describe_pipeline", return_value=card) as mock_describe:
            exit_code = pipeline_cli(["run", "deploy", "--info", "--no-workflow"])

        assert exit_code == 0
        assert mock_describe.call_args.kwargs["no_workflow"] is True

    def test_run_subparser_accepts_port_and_parallel(
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
            exit_code = pipeline_cli(["run", "deploy", "--port", "9999", "--parallel", "4"])

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

    def test_pipeline_cli_run_ignores_workflow_flags(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A plain run accepts `-w`/`--no-workflow` but ignores them — the decision travels via env."""
        monkeypatch.setattr(Path, "cwd", lambda: tmp_path)
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        with mock.patch.object(
            _cli_module,
            "run_pipeline",
            return_value=0,
        ) as mock_run_pipeline:
            exit_code = pipeline_cli(["run", "deploy", "--port", "50321", "-w", "hardening"])

        assert exit_code == 0
        project_dir = tmp_path / ".goga" / "pipelines"
        user_dir = tmp_path / ".goga" / "pipelines"
        # run_pipeline receives no workflow argument — the host launcher owns
        # the decision and delivers it through GOGA_WORKFLOW_* env vars.
        mock_run_pipeline.assert_called_once_with("deploy", project_dir, user_dir, 50321, parallel=None)


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
        """A run without --info and without --port fails the post-check → exit code 2."""
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

    def test_pipeline_cli_run_workflow_syntax_error_reports_error_and_returns_1(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """A WorkflowSyntaxError from run_pipeline is reported cleanly, exit 1 (no traceback)."""
        from goga.pipeline.workflow import WorkflowSyntaxError

        monkeypatch.setattr(Path, "cwd", lambda: tmp_path)
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        with mock.patch.object(
            _cli_module,
            "run_pipeline",
            side_effect=WorkflowSyntaxError("loop must be >= 1"),
        ):
            exit_code = pipeline_cli(["run", "deploy", "--port", "50321"])

        assert exit_code == 1
        captured = capsys.readouterr()
        assert "malformed workflow" in captured.err
        assert "deploy" in captured.err
        assert "loop must be >= 1" in captured.err
        assert "Traceback" not in captured.err


class TestPipelineCliInfoOperations:
    def test_pipeline_cli_list_info_prints_overview(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """`list --info` prints one `* {name}[ (project)]` bullet with name/description fields per pipeline."""
        _write_pipeline(tmp_path, "deploy", _DEPLOY_YML)

        monkeypatch.setattr(Path, "cwd", lambda: tmp_path)
        monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")

        exit_code = pipeline_cli(["list", "--info"])

        assert exit_code == 0
        captured = capsys.readouterr()
        assert captured.out == "* deploy (project)\n    name: Deploy\n    description: Deploy the service\n"

    def test_pipeline_cli_list_info_short_flag_identical(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """`list -i` output is byte-identical to `list --info`."""
        _write_pipeline(tmp_path, "deploy", _DEPLOY_YML)

        monkeypatch.setattr(Path, "cwd", lambda: tmp_path)
        monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")

        pipeline_cli(["list", "--info"])
        long_output = capsys.readouterr().out
        pipeline_cli(["list", "-i"])
        short_output = capsys.readouterr().out

        assert short_output == long_output

    def test_pipeline_cli_run_info_prints_card(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """`run NAME --info` prints card fields, a `---` separator, and `* {id}:` stage bullets; no port needed."""
        _write_pipeline(tmp_path, "deploy", _DEPLOY_YML)

        monkeypatch.setattr(Path, "cwd", lambda: tmp_path)
        monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")

        exit_code = pipeline_cli(["run", "deploy", "--info"])

        assert exit_code == 0
        captured = capsys.readouterr()
        assert captured.out == (
            "name: Deploy\ndescription: Deploy the service\n\n---\n\n"
            "* build:\n    title: Build\n* test:\n    title: Test\n"
        )

    def test_pipeline_cli_run_info_threads_workflow_flags(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """`-w WF` and `--no-workflow` thread through to describe_pipeline verbatim."""
        card = PipelineCard(
            name="Deploy", description="Deploy the service", stages=[CardStage(id="build", title="Build")]
        )
        monkeypatch.setattr(Path, "cwd", lambda: tmp_path)
        monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")

        with mock.patch.object(_cli_module, "describe_pipeline", return_value=card) as mock_describe:
            pipeline_cli(["run", "deploy", "--info", "-w", "hardening"])

        assert mock_describe.call_args.kwargs["workflow"] == "hardening"
        assert mock_describe.call_args.kwargs["no_workflow"] is False

        with mock.patch.object(_cli_module, "describe_pipeline", return_value=card) as mock_describe:
            pipeline_cli(["run", "deploy", "--info", "--no-workflow"])

        assert mock_describe.call_args.kwargs["workflow"] is None
        assert mock_describe.call_args.kwargs["no_workflow"] is True

    def test_pipeline_cli_run_without_info_and_without_port_exits_2(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """`run NAME` (no --info, no --port) is the conditional-required error → SystemExit 2."""
        monkeypatch.setattr(Path, "cwd", lambda: tmp_path)
        monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")

        with pytest.raises(SystemExit) as exc_info:
            pipeline_cli(["run", "deploy"])

        assert exc_info.value.code == 2

    def test_pipeline_cli_info_operations_render_clean_stderr(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """A damaged DSL renders `Error: ...` on stderr, exit 1, empty stdout — no traceback."""
        _write_pipeline(tmp_path, "deploy", ":\n  [broken")

        monkeypatch.setattr(Path, "cwd", lambda: tmp_path)
        monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")

        exit_code = pipeline_cli(["list", "--info"])

        assert exit_code == 1
        captured = capsys.readouterr()
        assert captured.err.startswith("Error:")
        assert "Traceback" not in captured.err
        assert captured.out == ""

        exit_code = pipeline_cli(["run", "deploy", "--info"])

        assert exit_code == 1
        captured = capsys.readouterr()
        assert captured.err.startswith("Error:")
        assert "Traceback" not in captured.err
        assert captured.out == ""

    def test_pipeline_cli_list_info_empty_discovery_prints_nothing(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Empty discovery in overview mode prints nothing (no header) and returns 0."""
        monkeypatch.setattr(Path, "cwd", lambda: tmp_path)
        monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")

        exit_code = pipeline_cli(["list", "--info"])

        assert exit_code == 0
        captured = capsys.readouterr()
        assert captured.out == ""

    def test_pipeline_cli_run_info_ignores_port(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """`--port` alongside `--info` is accepted and has no effect on the card."""
        _write_pipeline(tmp_path, "deploy", _DEPLOY_YML)

        monkeypatch.setattr(Path, "cwd", lambda: tmp_path)
        monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")

        exit_code = pipeline_cli(["run", "deploy", "--info", "--port", "9999"])

        assert exit_code == 0
        captured = capsys.readouterr()
        assert captured.out == (
            "name: Deploy\ndescription: Deploy the service\n\n---\n\n"
            "* build:\n    title: Build\n* test:\n    title: Test\n"
        )

    def test_pipeline_cli_list_info_reports_missing_pipeline_cleanly(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """A RuntimeError from an info operation (e.g. missing pipeline) renders cleanly."""
        monkeypatch.setattr(Path, "cwd", lambda: tmp_path)
        monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")

        exit_code = pipeline_cli(["run", "ghost", "--info"])

        assert exit_code == 1
        captured = capsys.readouterr()
        assert captured.err.startswith("Error:")
        assert "pipeline 'ghost' is missing" in captured.err
        assert "Traceback" not in captured.err

    def test_pipeline_cli_overview_uses_discovered_stem_names(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """The overview bullet uses the discovered stem, and the user source carries no suffix."""
        _write_pipeline(tmp_path, "deploy", _DEPLOY_YML)
        user_dir = tmp_path / "home" / ".goga" / "pipelines"
        user_dir.mkdir(parents=True)
        (user_dir / "release.yml").write_text("name: Release\ndescription: Cut a release\n---\n{}\n")

        monkeypatch.setattr(Path, "cwd", lambda: tmp_path)
        monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")

        exit_code = pipeline_cli(["list", "--info"])

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "* deploy (project)\n    name: Deploy\n    description: Deploy the service\n" in captured.out
        assert "* release\n    name: Release\n    description: Cut a release\n" in captured.out

    def test_pipeline_cli_non_utf8_pipeline_renders_clean_error(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """A non-UTF-8 pipeline-file renders `Error: ...` (exit 1) in both info forms — no traceback."""
        pipeline_path = _write_pipeline(tmp_path, "deploy", _DEPLOY_YML)
        raw = pipeline_path.read_bytes()
        pipeline_path.write_bytes(raw.replace(raw[len(raw) // 2 : len(raw) // 2 + 1], b"\xff", 1))

        monkeypatch.setattr(Path, "cwd", lambda: tmp_path)
        monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")

        exit_code = pipeline_cli(["list", "--info"])

        assert exit_code == 1
        captured = capsys.readouterr()
        assert captured.err.startswith("Error:")
        assert "Traceback" not in captured.err
        assert captured.out == ""

        exit_code = pipeline_cli(["run", "deploy", "--info"])

        assert exit_code == 1
        captured = capsys.readouterr()
        assert captured.err.startswith("Error:")
        assert "Traceback" not in captured.err
        assert captured.out == ""

    def test_pipeline_cli_run_non_utf8_pipeline_renders_clean_error(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """A non-UTF-8 pipeline-file in run mode renders `Error: ...` (exit 1) — no traceback."""
        pipeline_path = _write_pipeline(tmp_path, "deploy", _DEPLOY_YML)
        raw = pipeline_path.read_bytes()
        pipeline_path.write_bytes(raw.replace(raw[len(raw) // 2 : len(raw) // 2 + 1], b"\xff", 1))

        monkeypatch.setattr(Path, "cwd", lambda: tmp_path)
        monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")

        exit_code = pipeline_cli(["run", "deploy", "--port", "50321"])

        assert exit_code == 1
        captured = capsys.readouterr()
        assert captured.err.startswith("Error:")
        assert "Traceback" not in captured.err
