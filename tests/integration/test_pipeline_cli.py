"""End-to-end integration tests for the ``pipeline`` command under the
docker-hosted architecture.

These exercise the cross-cell paths introduced by the pipeline-to-docker-afm
migration. The architecture splits the work across a host/docker boundary:

    host:       goga pipeline <name> -> goga.commands.pipeline.pipeline
                                          -> goga.commands.pipeline.run_pipeline_container
                                          -> docker run ... python -m goga.pipeline run <name> --port <port>
    container:  python -m goga.pipeline run <name> --port <port>
                  -> goga.pipeline.pipeline_cli
                  -> goga.pipeline.run_pipeline
                  -> goga.afm.run_flow
                  -> subprocess.run(["afm", "run", "--port", <port>, <flow_path>])

Because the host never imports a Type from ``goga/pipeline`` (the docker runtime
boundary), the two halves are tested separately and then stitched together at
the docker ``subprocess.Popen`` boundary:

- The in-container half is exercised by calling ``pipeline_cli`` directly, with
  ``afm`` mocked at the ``goga.afm.run_flow.subprocess.run`` boundary.
- The host half is exercised via ``CliRunner`` with docker mocked at the
  ``subprocess.Popen`` boundary; the container's exit code is simulated by the
  ``Popen.wait()`` return value, which stands in for ``pipeline_cli``'s return
  code from inside the container.

Mocking follows ``[[feedback_mock_patch_module_shadowing]]``: the package
``__init__`` re-exports the submodule functions under the same names, which
shadows string-based ``mock.patch`` paths on Python 3.10, so the real modules
are resolved via ``sys.modules`` and patched by attribute.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from unittest import mock
from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner
from goga.cli import app
from goga.config import BuildConfig, Config, PipelineConfig, TaskExecutorConfig
from goga.pipeline import pipeline_cli

# goga.afm.run_flow is shadowed in the package __init__ by the run_flow
# function, so a string-based mock.patch path walking through it fails on
# Python 3.10. Resolve the real module via sys.modules and patch its subprocess
# attribute directly.
_run_flow_module = sys.modules["goga.afm.run_flow"]

# goga.commands.pipeline.run_pipeline_container likewise shadows its submodule
# name; resolve it for monkeypatching host-side helpers.
_rpc_module = sys.modules["goga.commands.pipeline.run_pipeline_container"]
# goga.commands.pipeline.pipeline shadows its submodule name too.
_pipeline_module = sys.modules["goga.commands.pipeline.pipeline"]


def _make_config() -> Config:
    """Build a minimal Config satisfying the new schema (top-level image, pipeline block)."""
    return Config(
        lang="python",
        image="qarium/goga:latest",
        dockerfile=None,
        build=BuildConfig(task_executor=TaskExecutorConfig(agent="claude")),
        pipeline=PipelineConfig(agent="claude"),
    )


class TestInContainerRunPath:
    """Cross-entity: ``pipeline_cli run`` -> ``run_pipeline`` -> ``run_flow`` -> afm.

    These drive the in-container half of the flow directly (the path that
    ``python -m goga.pipeline run <name> --port <port>`` takes inside the goga
    Docker image), with the ``afm`` binary mocked at the subprocess boundary.
    """

    def test_run_invokes_afm_run_with_port_and_path(self, tmp_path: Path, monkeypatch) -> None:
        """``pipeline_cli run`` reaches ``run_flow`` and invokes ``afm run --port``."""
        project_tmp = tmp_path / "project"
        project_pipelines = project_tmp / ".goga" / "pipelines"
        project_pipelines.mkdir(parents=True)
        (project_pipelines / "deploy.yml").write_text("pipeline")

        user_tmp = tmp_path / "user"

        monkeypatch.setattr(Path, "cwd", lambda: project_tmp)
        monkeypatch.setattr(Path, "home", lambda: user_tmp)

        with mock.patch.object(
            _run_flow_module.subprocess,
            "run",
            return_value=MagicMock(returncode=0),
        ) as mock_subprocess:
            result = pipeline_cli(["run", "deploy", "--port", "50321"])

        assert result == 0
        mock_subprocess.assert_called_once()
        called_args = mock_subprocess.call_args.args[0]
        # afm invocation shape: afm run --port <port> <resolved absolute flow path>.
        assert called_args[0] == "afm"
        assert called_args[1] == "run"
        assert called_args[2] == "--port"
        assert called_args[3] == "50321"
        # The resolved absolute pipeline path (not the bare name) reaches the binary.
        assert called_args[4] == str((project_pipelines / "deploy.yml").resolve())

    def test_run_missing_pipeline_is_nonzero_without_afm(self, tmp_path: Path, monkeypatch) -> None:
        """``pipeline_cli run <missing>`` returns nonzero without invoking afm."""
        monkeypatch.setattr(Path, "cwd", lambda: tmp_path)
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        with mock.patch.object(_run_flow_module.subprocess, "run") as mock_subprocess:
            result = pipeline_cli(["run", "missing", "--port", "50321"])

        assert result != 0
        mock_subprocess.assert_not_called()

    def test_run_propagates_nonzero_afm_exit_code(self, tmp_path: Path, monkeypatch) -> None:
        """``pipeline_cli run`` propagates a non-zero afm exit code verbatim."""
        project_tmp = tmp_path / "project"
        project_pipelines = project_tmp / ".goga" / "pipelines"
        project_pipelines.mkdir(parents=True)
        (project_pipelines / "deploy.yml").write_text("pipeline")

        monkeypatch.setattr(Path, "cwd", lambda: project_tmp)
        monkeypatch.setattr(Path, "home", lambda: tmp_path / "user")

        with mock.patch.object(
            _run_flow_module.subprocess,
            "run",
            return_value=MagicMock(returncode=7),
        ):
            result = pipeline_cli(["run", "deploy", "--port", "50321"])

        # The afm exit code flows run_flow -> run_pipeline -> pipeline_cli verbatim.
        assert result == 7

    def test_run_propagates_127_when_afm_missing(self, tmp_path: Path, monkeypatch) -> None:
        """afm missing inside the container propagates exit code 127."""
        project_tmp = tmp_path / "project"
        project_pipelines = project_tmp / ".goga" / "pipelines"
        project_pipelines.mkdir(parents=True)
        (project_pipelines / "deploy.yml").write_text("pipeline")

        monkeypatch.setattr(Path, "cwd", lambda: project_tmp)
        monkeypatch.setattr(Path, "home", lambda: tmp_path / "user")

        with mock.patch.object(_run_flow_module.subprocess, "run", side_effect=FileNotFoundError):
            result = pipeline_cli(["run", "deploy", "--port", "50321"])

        assert result == 127

    def test_run_resolves_project_source_on_name_conflict(self, tmp_path: Path, monkeypatch) -> None:
        """A name in both sources resolves to the project path reaching afm."""
        project_tmp = tmp_path / "project"
        project_pipelines = project_tmp / ".goga" / "pipelines"
        project_pipelines.mkdir(parents=True)
        (project_pipelines / "shared.yml").write_text("project-shared")

        user_tmp = tmp_path / "user"
        user_pipelines = user_tmp / ".goga" / "pipelines"
        user_pipelines.mkdir(parents=True)
        (user_pipelines / "shared.yml").write_text("user-shared")

        monkeypatch.setattr(Path, "cwd", lambda: project_tmp)
        monkeypatch.setattr(Path, "home", lambda: user_tmp)

        with mock.patch.object(
            _run_flow_module.subprocess,
            "run",
            return_value=MagicMock(returncode=0),
        ) as mock_subprocess:
            result = pipeline_cli(["run", "shared", "--port", "50321"])

        assert result == 0
        called_args = mock_subprocess.call_args.args[0]
        # Project wins on conflict: the project path reaches afm, not the user path.
        assert called_args[4] == str((project_pipelines / "shared.yml").resolve())


class TestInContainerListPath:
    """Cross-entity: ``pipeline_cli list`` -> ``list_pipelines`` -> filesystem."""

    def test_list_prints_header_and_entries(self, tmp_path: Path, monkeypatch, capsys) -> None:
        """``list`` prints the header, project pipelines with ``(project)``, user pipelines bare."""
        project_tmp = tmp_path / "project"
        project_pipelines = project_tmp / ".goga" / "pipelines"
        project_pipelines.mkdir(parents=True)
        (project_pipelines / "deploy.yml").write_text("pipeline")

        user_tmp = tmp_path / "user"
        user_pipelines = user_tmp / ".goga" / "pipelines"
        user_pipelines.mkdir(parents=True)
        (user_pipelines / "rollback.yml").write_text("pipeline")

        monkeypatch.setattr(Path, "cwd", lambda: project_tmp)
        monkeypatch.setattr(Path, "home", lambda: user_tmp)

        result = pipeline_cli(["list"])

        assert result == 0
        out = capsys.readouterr().out
        assert out.startswith("Available pipelines:\n")
        assert "  deploy (project)" in out
        assert "  rollback" in out
        assert "rollback (project)" not in out

    def test_list_project_wins_on_name_conflict(self, tmp_path: Path, monkeypatch, capsys) -> None:
        """A name present in both sources appears once, annotated as project."""
        project_tmp = tmp_path / "project"
        project_pipelines = project_tmp / ".goga" / "pipelines"
        project_pipelines.mkdir(parents=True)
        (project_pipelines / "shared.yml").write_text("project-shared")

        user_tmp = tmp_path / "user"
        user_pipelines = user_tmp / ".goga" / "pipelines"
        user_pipelines.mkdir(parents=True)
        (user_pipelines / "shared.yml").write_text("user-shared")

        monkeypatch.setattr(Path, "cwd", lambda: project_tmp)
        monkeypatch.setattr(Path, "home", lambda: user_tmp)

        result = pipeline_cli(["list"])

        assert result == 0
        out = capsys.readouterr().out
        assert "  shared (project)" in out
        # The user duplicate is suppressed.
        assert out.count("shared") == 1

    def test_list_prints_header_when_empty(self, tmp_path: Path, monkeypatch, capsys) -> None:
        """The header is printed before an empty list."""
        monkeypatch.setattr(Path, "cwd", lambda: tmp_path)
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        result = pipeline_cli(["list"])

        assert result == 0
        out = capsys.readouterr().out
        assert out == "Available pipelines:\n"


class TestHostEndToEnd:
    """Host half: ``goga pipeline <name>`` -> docker -> exit-code propagation.

    Docker is mocked at the ``subprocess.Popen`` boundary; ``Popen.wait()``
    returning ``N`` simulates the in-container ``pipeline_cli`` having returned
    ``N``. The assertion verifies that ``N`` propagates through
    ``run_pipeline_container`` -> ``ctx.exit`` -> CliRunner.
    """

    @pytest.mark.parametrize("exit_code", [0, 1, 7, 42, 127, 130])
    def test_pipeline_run_end_to_end_propagates_afm_exit_code(
        self, tmp_path: Path, monkeypatch, exit_code: int
    ) -> None:
        """The in-container exit code propagates across the docker boundary to the host."""
        config = _make_config()

        monkeypatch.chdir(tmp_path)
        # Host-side docker launcher helpers.
        monkeypatch.setattr(_rpc_module, "_check_docker", lambda: True)
        monkeypatch.setattr(_rpc_module, "_allocate_port", lambda: 50321)
        monkeypatch.setattr(_rpc_module, "_read_git_config", lambda: {})
        # Config load returns the new-schema Config.
        monkeypatch.setattr(_pipeline_module, "load_config", lambda: config)

        # Simulate the in-container path: Popen.wait() returns the code that
        # `pipeline_cli` would have produced. Patch pipeline_cli at its real
        # module too so the in-container entry is explicitly stubbed (it is
        # never reached because docker is mocked — the host has no Python import
        # of pipeline_cli — but the patch documents the simulated return).
        mock_proc = MagicMock()
        mock_proc.wait.return_value = exit_code

        runner = CliRunner()
        with (
            mock.patch.object(sys.modules["goga.pipeline.cli"], "pipeline_cli", return_value=exit_code),
            mock.patch.object(subprocess, "Popen", return_value=mock_proc) as mock_popen,
            mock.patch.object(subprocess, "run"),
        ):
            result = runner.invoke(app, ["pipeline", "deploy"])

        assert result.exit_code == exit_code
        # The docker command carries the in-container `run` invocation shape.
        cmd = mock_popen.call_args[0][0]
        assert "run" in cmd
        assert "deploy" in cmd
        assert "--port" in cmd
        assert "50321" in cmd


class TestCommandRegistration:
    """The ``pipeline`` command is registered on ``app``; legacy ``flow`` is not."""

    def test_flow_command_not_registered(self) -> None:
        """The legacy 'flow' command is NOT registered on the app group."""
        assert "flow" not in app.commands

    def test_pipeline_command_registered(self) -> None:
        """The 'pipeline' command is registered on the app group."""
        assert "pipeline" in app.commands

    def test_root_help_lists_pipeline_not_flow(self) -> None:
        """goga --help lists 'pipeline' and does NOT list 'flow'."""
        runner = CliRunner()
        result = runner.invoke(app, ["--help"])

        assert result.exit_code == 0
        assert "pipeline" in result.output
        assert "flow" not in result.output


class TestPythonMEntrypoint:
    """``python -m goga.pipeline`` runpy entrypoint regressions.

    The package ``__init__`` must not import ``pipeline_cli`` from
    ``__main__`` — otherwise ``runpy`` finds ``goga.pipeline.__main__`` in
    ``sys.modules`` before executing it and emits a ``RuntimeWarning`` for
    ``python -m goga.pipeline``. The CLI implementation lives in ``cli.py``;
    ``__main__.py`` is a thin wrapper that delegates to it.
    """

    def test_python_m_pipeline_does_not_emit_runtime_warning(self) -> None:
        """``python -m goga.pipeline list`` runs without any RuntimeWarning."""
        project_root = Path(__file__).parent.parent.parent
        result = subprocess.run(
            [
                sys.executable,
                "-W",
                "error::RuntimeWarning",
                "-m",
                "goga.pipeline",
                "list",
            ],
            cwd=project_root,
            env={**os.environ, "GOGA_DOCKER": "1"},
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 0, result.stderr
        assert "RuntimeWarning" not in result.stderr
        assert "Available pipelines:" in result.stdout

    def test_main_module_is_thin_wrapper_around_cli(self) -> None:
        """``__main__.py`` imports ``pipeline_cli`` from ``.cli`` and defines nothing else."""
        main_path = Path(__file__).parent.parent.parent / "goga" / "pipeline" / "__main__.py"
        source = main_path.read_text()

        assert "from .cli import pipeline_cli" in source
        assert "def pipeline_cli" not in source
