"""Contract tests for the workflow-flag extension of ``run_pipeline_container``.

These tests pin the CODEMANIFEST contract for the ``workflow`` / ``no_workflow``
parameters added to ``run_pipeline_container``:

- the signature exposes ``workflow: str | None`` and ``no_workflow: bool`` as the
  final two parameters (after ``update``)
- ``workflow`` defaults to ``None`` and ``no_workflow`` defaults to ``False``
- the function still returns the container exit code (an ``int``) in both modes

The dispatch target (``DockerRunner.run`` / ``subprocess.Popen``) is mocked so
these tests stay focused on the launcher signature surface (no docker
dependency). The decision-matrix behavior, the workflow log line, and the
env-file workflow entries are pinned in ``test_run_pipeline_container_workflow.py``.
"""

from __future__ import annotations

import inspect
import subprocess
import sys
import typing
from pathlib import Path
from unittest import mock

from goga.commands.pipeline.run_pipeline_container import (
    run_pipeline_container as rpc,
)

# Resolve the real submodule via sys.modules (the package __init__ binds the
# function name `run_pipeline_container`, which would shadow string-based
# mock.patch paths walking through the package on Python 3.10).
_rpc_mod = sys.modules["goga.commands.pipeline.run_pipeline_container"]


def _make_config():
    """Build a minimal Config with a pipeline section for run-mode dispatch."""
    from goga.config import BuildConfig, Config, PipelineConfig, TaskExecutorConfig

    return Config(
        lang="python",
        image="qarium/goga:latest",
        dockerfile=None,
        build=BuildConfig(task_executor=TaskExecutorConfig(agent="claude")),
        pipeline=PipelineConfig(agent="claude", env={}),
    )


class TestRunPipelineContainerWorkflowSignature:
    def test_signature_has_workflow_and_no_workflow_as_final_params(self) -> None:
        """``workflow`` then ``no_workflow`` are the final two signature parameters."""
        params = list(inspect.signature(rpc).parameters)
        assert params[-2] == "workflow"
        assert params[-1] == "no_workflow"

    def test_workflow_param_is_optional_str(self) -> None:
        """``workflow`` is typed ``str | None`` and defaults to ``None``."""
        param = inspect.signature(rpc).parameters["workflow"]
        assert param.default is None
        type_hints = typing.get_type_hints(rpc)
        assert type_hints["workflow"] == str | None

    def test_no_workflow_param_is_bool(self) -> None:
        """``no_workflow`` is typed ``bool`` and defaults to ``False``."""
        param = inspect.signature(rpc).parameters["no_workflow"]
        assert param.default is False
        type_hints = typing.get_type_hints(rpc)
        assert type_hints["no_workflow"] is bool


class TestRunPipelineContainerStillReturnsExitCode:
    def test_run_mode_returns_container_exit_code(self, tmp_path: Path, monkeypatch) -> None:
        """Run mode with workflow forwarded still returns the container exit code."""
        config = _make_config()
        monkeypatch.setattr(_rpc_mod, "_check_docker", lambda: True)
        monkeypatch.setattr(_rpc_mod, "_allocate_port", lambda: 50321)
        monkeypatch.setattr(_rpc_mod, "_read_git_config", lambda: {})
        monkeypatch.chdir(tmp_path)

        mock_proc = mock.Mock()
        mock_proc.wait.return_value = 42
        with (
            mock.patch.object(subprocess, "Popen", return_value=mock_proc),
            mock.patch.object(subprocess, "run"),
        ):
            exit_code = rpc("deploy", config, workflow="custom", no_workflow=False)

        assert exit_code == 42
        assert isinstance(exit_code, int)

    def test_discovery_mode_returns_container_exit_code(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """Discovery mode ignores the workflow flags and returns the exit code."""
        config = _make_config()
        monkeypatch.setattr(_rpc_mod, "_check_docker", lambda: True)
        monkeypatch.chdir(tmp_path)

        mock_proc = mock.Mock()
        mock_proc.wait.return_value = 7
        with (
            mock.patch.object(subprocess, "Popen", return_value=mock_proc),
            mock.patch.object(subprocess, "run"),
        ):
            exit_code = rpc(None, config, workflow="custom", no_workflow=True)

        assert exit_code == 7
