"""Contract tests for the workflow/profile extensions of ``run_pipeline_container``.

These tests pin the CODEMANIFEST contract of ``run_pipeline_container``:

- the full declared parameter order, ending ``workflow, no_workflow, profile,
  skip, parallel, home_profiles``
- ``workflow`` / ``no_workflow`` / ``profile`` / ``parallel`` /
  ``home_profiles`` defaults and annotations; ``skip`` defaults to the empty
  tuple
- the function still returns the container exit code (an ``int``)

The launcher is RUN-ONLY: ``name`` is a required ``str`` (never ``None``) and
the module no longer defines the ``_run_discovery`` helper — the listing and
info forms live in ``run_pipeline_info_container``. The workflow log-line
helper is gone too: the launch feedback line prints in-container, so the host
module defines neither ``_run_discovery`` nor ``_resolve_workflow_log_name``.

The dispatch target (``DockerRunner.run`` / ``subprocess.Popen``) is mocked so
these tests stay focused on the launcher signature surface (no docker
dependency). The decision-matrix behavior, the profile carriage env lines, and
the argv channel are pinned in ``test_run_pipeline_container_workflow.py``.
"""

from __future__ import annotations

import inspect
import subprocess
import sys
import typing
from pathlib import Path
from typing import Any
from unittest import mock

from goga.commands.pipeline.run_pipeline_container import (
    run_pipeline_container as rpc,
)

# Resolve the real submodule via sys.modules (the package __init__ binds the
# function name `run_pipeline_container`, which would shadow string-based
# mock.patch paths walking through the package on Python 3.10).
_rpc_mod = sys.modules["goga.commands.pipeline.run_pipeline_container"]


def _make_config():
    """Build a minimal ProjectConfig with a pipeline section for run-mode dispatch."""
    from goga.config import BuildConfig, PipelineConfig, ProjectConfig

    return ProjectConfig(
        language="python",
        image="qarium/goga:latest",
        dockerfile=None,
        build=BuildConfig(agent="claude"),
        pipeline=PipelineConfig(agent="claude", env={}),
    )


class TestRunPipelineContainerWorkflowSignature:
    def test_signature_has_the_declared_final_params(self) -> None:
        """The signature ends ``...parallel, home_profiles, fail_on_error, port``."""
        params = list(inspect.signature(rpc).parameters)
        assert params == [
            "name",
            "config",
            "extra_env",
            "proxy",
            "hosts",
            "clean",
            "update",
            "workflow",
            "no_workflow",
            "profile",
            "skip",
            "parallel",
            "home_profiles",
            "fail_on_error",
            "port",
        ]


class TestRunPipelineContainerRunOnlySignature:
    def test_name_param_is_required_str(self) -> None:
        """``name`` is a plain ``str`` — the launcher is run-only (no ``None`` mode)."""
        param = inspect.signature(rpc).parameters["name"]
        assert param.default is inspect.Parameter.empty
        type_hints = typing.get_type_hints(rpc)
        assert type_hints["name"] is str

    def test_module_has_no_run_discovery_helper(self) -> None:
        """The ``_run_discovery`` helper is gone — its coverage moved to ``run_pipeline_info_container``."""
        assert not hasattr(_rpc_mod, "_run_discovery")

    def test_module_has_no_workflow_log_name_helper(self) -> None:
        """The host-side workflow log helper is gone — the feedback line prints in-container."""
        assert not hasattr(_rpc_mod, "_resolve_workflow_log_name")


class TestRunPipelineContainerProfileSignature:
    def test_profile_param_is_optional_str_after_no_workflow(self) -> None:
        """``profile`` is typed ``str | None``, defaults to ``None``, and follows ``no_workflow``."""
        params = list(inspect.signature(rpc).parameters)
        assert params[params.index("no_workflow") + 1] == "profile"
        assert params[params.index("profile") + 1] == "skip"
        param = inspect.signature(rpc).parameters["profile"]
        assert param.default is None
        assert typing.get_type_hints(rpc)["profile"] == str | None

    def test_home_profiles_param_is_optional_mapping_before_fail_on_error(self) -> None:
        """``home_profiles`` is a bundle mapping defaulting to ``None``, just before ``fail_on_error``."""
        params = list(inspect.signature(rpc).parameters)
        assert params[params.index("home_profiles") + 1] == "fail_on_error"
        param = inspect.signature(rpc).parameters["home_profiles"]
        assert param.default is None
        assert typing.get_type_hints(rpc)["home_profiles"] == dict[str, dict[str, Any]] | None

    def test_run_named_accepts_profile_and_home_profiles(self) -> None:
        """The internal ``_run_named`` helper threads both new parameters."""
        _run_named = _rpc_mod._run_named
        params = inspect.signature(_run_named).parameters
        assert "profile" in params
        assert "home_profiles" in params
        assert params["profile"].default is None
        assert params["home_profiles"].default is None


class TestRunPipelineContainerParallelSignature:
    def test_parallel_is_final_param_default_none(self) -> None:
        """``parallel`` is the final signature parameter and defaults to ``None``."""
        param = inspect.signature(rpc).parameters["parallel"]
        assert param.default is None
        type_hints = typing.get_type_hints(rpc)
        assert type_hints["parallel"] == int | None

    def test_run_named_accepts_parallel(self) -> None:
        """The internal ``_run_named`` helper accepts a ``parallel`` parameter."""
        _run_named = _rpc_mod._run_named
        params = list(inspect.signature(_run_named).parameters)
        assert "parallel" in params
        parallel_param = inspect.signature(_run_named).parameters["parallel"]
        assert parallel_param.default is None

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


class TestRunPipelineContainerFailOnErrorContract:
    def test_fail_on_error_keeps_default_false_before_port(self) -> None:
        """``fail_on_error`` stays typed ``bool`` with default ``False``, just before the final ``port``."""
        params = list(inspect.signature(rpc).parameters)
        assert params[params.index("fail_on_error") + 1] == "port"

        param = inspect.signature(rpc).parameters["fail_on_error"]
        assert param.default is False
        assert typing.get_type_hints(rpc)["fail_on_error"] is bool

    def test_compose_run_args_accepts_fail_on_error_default_false(self) -> None:
        """``_compose_run_args`` gains ``fail_on_error`` last, defaulting to ``False``.

        The default keeps every existing call site valid (the flag appends only
        when explicitly True).
        """
        params = inspect.signature(_rpc_mod._compose_run_args).parameters
        assert list(params)[-1] == "fail_on_error"
        assert params["fail_on_error"].default is False

    def test_run_named_threads_fail_on_error_and_port(self) -> None:
        """The internal ``_run_named`` helper threads ``fail_on_error`` and the final ``port``."""
        params = inspect.signature(_rpc_mod._run_named).parameters
        assert params["fail_on_error"].default is False
        assert list(params)[-1] == "port"
        assert params["port"].default is None


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
