"""Integration tests for the direct substrate, the fail-on-error chain, and the ``!ENV`` config chain.

The three cross-package scenarios of the ``pipeline-settings-calibration``
feature that span the host/container boundary, stitched in one place per the
integration placement rule:

- D5 (fail-on-error): one test drives every hop of the chain in sequence —
  the host Click flag → the direct-substrate child argv → the in-container
  argparse surface → the run coordination → the engine argv — each hop fed
  the captured output of the previous hop, proving the chain never silently
  drops the flag.
- D1 (substrate parity): the same launch inputs through both execution
  substrates produce the SAME composed argv and the SAME composed env lines
  (one composition, two sinks — per ``direct-runner``).
- D3 (environment-driven configuration): a ``!ENV``-referencing project
  configuration resolves at load time into the effective config the run
  coordination consumes — the resolved agent reaches the written afm
  configuration.

Spawns are mocked at the process boundary only (``subprocess.Popen`` of
``run_direct``, ``subprocess.run`` of ``run_flow``); every other layer of the
chain runs for real. Mocking follows the module-shadowing rule of the suite:
package ``__init__`` re-exports shadow their submodule names on attribute
access (Python 3.10), so the real modules are resolved via ``sys.modules``
and patched by attribute.
"""

from __future__ import annotations

import importlib
import os
import subprocess
from pathlib import Path
from unittest import mock
from unittest.mock import MagicMock

import goga.docker.runner
import pytest
import yaml
from click.testing import CliRunner
from goga.commands.pipeline.pipeline import pipeline as pipeline_cmd
from goga.config import load_project_config
from goga.pipeline import pipeline_cli
from goga.pipeline.compiler import (
    BodyFormat,
    FlowDocument,
    PhasesBody,
    PipelineDocument,
    PipelineHeader,
)

from tests.commands.pipeline.conftest import (
    DirectSpawnPopen,
    apply_run_mode_common_mocks,
    make_config,
)

# The shadowed submodules resolved directly: the package __init__ re-exports
# the functions under the submodule names, which shadows the submodule name in
# attribute access on Python 3.10 (the tests/commands/pipeline conftest rule).
_run_flow_module = importlib.import_module("goga.afm.run_flow")
_run_pipeline_module = importlib.import_module("goga.pipeline.run_pipeline")
_rpc_module = importlib.import_module("goga.commands.pipeline.run_pipeline_container")
_afm_config_module = importlib.import_module("goga.pipeline.afm_config")

# The minimal pipeline DSL text of the in-container discovery step (the header
# parse requires a valid mapping header and the ``---`` body separator).
_PIPELINE_FILE_TEXT = "name: Deploy\ndescription: d\n---\n\nbuild:\n  title: Build\n"


def _fake_documents() -> tuple[PipelineDocument, FlowDocument]:
    """Build the documents tuple ``compile_flow`` returns, for mock wiring.

    Mirrors ``tests/integration/test_parallel_flow._fake_documents``.
    """
    pipeline_doc = PipelineDocument(
        header=PipelineHeader(name="deploy", description="d", roles=None),
        format=BodyFormat.PHASES,
        body=PhasesBody(steps=[]),
    )
    flow_doc = FlowDocument(name="deploy", description="d", stages=[])
    return (pipeline_doc, flow_doc)


def _write_pipeline_file(project_root: Path, name: str = "deploy") -> None:
    """Write the minimal pipeline file the in-container discovery step finds."""
    pipelines = project_root / ".goga" / "pipelines"

    pipelines.mkdir(parents=True, exist_ok=True)
    (pipelines / f"{name}.yml").write_text(_PIPELINE_FILE_TEXT)


class TestFailOnErrorChainEndToEnd:
    """D5: the fail-fast flag threads through every hop, host Click to engine argv."""

    def test_fail_on_error_threads_click_to_engine_argv(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        in_container_pipeline_run_context: Path,
    ) -> None:
        """Each hop forwards the flag: click → child argv → argparse → run_pipeline → run_flow → afm argv."""
        project_root = in_container_pipeline_run_context
        _write_pipeline_file(project_root)
        apply_run_mode_common_mocks(project_root, monkeypatch)
        # A distinct user-level pipelines root so project/user discovery cannot
        # collide (the project file is the only discoverable pipeline).
        monkeypatch.setattr(Path, "home", lambda: project_root / "user")
        monkeypatch.setenv("AFM_DIR", str((project_root / ".afm").resolve()))

        # Hop 1 — the host Click surface on the direct substrate: the flag
        # reaches the composed child argv and no docker machinery runs. The
        # Popen fake is scoped to the invoke: it replaces the SHARED
        # subprocess module attribute, and the later hops run real probes
        # (the hop-3 git-branch resolution) through the real Popen.
        monkeypatch.setenv("GOGA_DOCKER", "1")
        spawn = DirectSpawnPopen(returncode=0)
        docker_build = mock.Mock()
        docker_update = mock.Mock()
        monkeypatch.setattr(_rpc_module, "docker_build_if_not_exist", docker_build)
        monkeypatch.setattr(_rpc_module, "docker_update", docker_update)

        with mock.patch.object(goga.docker.runner.subprocess, "Popen", spawn):
            result = CliRunner().invoke(pipeline_cmd, ["deploy", "--fail-on-error"])

        assert result.exit_code == 0
        assert len(spawn.calls) == 1
        child_argv = spawn.calls[0][0]
        assert child_argv == [
            "python3",
            "-m",
            "goga.pipeline",
            "run",
            "deploy",
            "--port",
            "50321",
            "--fail-on-error",
        ]
        docker_build.assert_not_called()
        docker_update.assert_not_called()

        # Hop 2 — the in-container argparse surface fed the argv hop 1
        # composed (minus the ``python3 -m goga.pipeline`` entry tokens): the
        # run coordination is invoked with ``fail_on_error=True``.
        with mock.patch.object(_run_pipeline_module, "run_pipeline", return_value=0) as mock_run_pipeline:
            cli_exit = pipeline_cli(child_argv[3:])

        assert cli_exit == 0
        forwarded = mock_run_pipeline.call_args
        assert forwarded is not None
        assert forwarded.args[0] == "deploy"
        assert forwarded.args[3] == 50321
        assert forwarded.kwargs["fail_on_error"] is True

        # Hop 3 — the run coordination fed hop 2's forwarded call (compile
        # mocked at its boundary; the launch mocked at run_flow): the engine
        # call carries ``exit_on_fail=True``.
        with (
            mock.patch.object(_run_pipeline_module, "compile_flow", return_value=_fake_documents()),
            mock.patch.object(_run_pipeline_module, "run_flow", return_value=0) as mock_run_flow,
        ):
            run_exit = _run_pipeline_module.run_pipeline(*forwarded.args, **forwarded.kwargs)

        assert run_exit == 0
        flow_call = mock_run_flow.call_args
        assert flow_call is not None
        assert flow_call.kwargs["exit_on_fail"] is True
        assert flow_call.kwargs["max_parallel"] is None

        # Hop 4 — the engine argv: run_flow fed hop 3's call appends
        # ``--exit-on-fail`` after ``--port``, before the positional flow path.
        with mock.patch.object(
            _run_flow_module.subprocess,
            "run",
            return_value=MagicMock(returncode=0),
        ) as mock_subprocess:
            flow_exit = _run_flow_module.run_flow(*flow_call.args, **flow_call.kwargs)

        assert flow_exit == 0
        afm_calls = [c for c in mock_subprocess.call_args_list if c.args[0][0] == "afm"]
        assert len(afm_calls) == 1
        assert list(afm_calls[0].args[0]) == [
            "afm",
            "run",
            "--port",
            "50321",
            "--exit-on-fail",
            str(flow_call.args[0]),
        ]


class TestDirectSubstrateParity:
    """D1: one composition, two sinks — the substrates share the argv and env composers."""

    def test_both_substrates_compose_the_same_argv_and_env_lines(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The direct child argv/env equal the shared composition the host substrate writes."""
        config = make_config()
        apply_run_mode_common_mocks(tmp_path, monkeypatch)

        # Host arm — record the DockerRunner args and the env-file lines at
        # run time (the launcher unlinks the env-file in its finally).
        host: dict[str, list] = {"args": [], "env_lines": []}
        run_calls: list[int] = []

        def _record_run(_self, args, extra_args=None, **params):
            run_calls.append(1)
            host["args"] = list(args)
            host["env_lines"] = Path(str(params["env_file"])).read_text().splitlines()
            return 0

        monkeypatch.setattr(_rpc_module.DockerRunner, "run", _record_run)
        monkeypatch.setattr(_rpc_module, "docker_build_if_not_exist", mock.Mock())
        monkeypatch.setattr(_rpc_module, "docker_update", mock.Mock())

        with mock.patch.object(subprocess, "run"):
            host_exit = _rpc_module.run_pipeline_container("deploy", config, extra_env=("K=V",), fail_on_error=True)

        assert host_exit == 0
        assert len(run_calls) == 1

        # Direct arm — the SAME launch inputs with the substrate marker set.
        monkeypatch.setenv("GOGA_DOCKER", "1")
        spawn = DirectSpawnPopen(returncode=0)
        monkeypatch.setattr(goga.docker.runner.subprocess, "Popen", spawn)

        direct_exit = _rpc_module.run_pipeline_container("deploy", config, extra_env=("K=V",), fail_on_error=True)

        assert direct_exit == 0
        # The docker substrate ran exactly once (the host arm) — the direct
        # arm added no DockerRunner launch.
        assert len(run_calls) == 1
        assert len(spawn.calls) == 1
        direct_argv, direct_env = spawn.calls[0]

        # The child argv is the shared argv composition prefixed with the
        # program token — and identical to what the host arm handed
        # DockerRunner (composition sharing, not re-derivation).
        expected_args = _rpc_module._compose_run_args("deploy", 50321, None, False, None, (), None, True)
        assert direct_argv == ["python3", *expected_args]
        assert expected_args == host["args"]
        assert direct_argv[1:] == host["args"]

        # The child env layer is the parse of the SAME lines the host arm
        # wrote into its env-file — every composed key lands in the child env
        # with its composed value, applied OVER the inherited environment.
        expected_overlay = _rpc_module._env_overlay(host["env_lines"])
        assert expected_overlay
        for key, value in expected_overlay.items():
            assert direct_env[key] == value

        assert direct_env["K"] == "V"
        assert direct_env["AFM_DIR"] == "/home/goga/pipeline"
        # Inheritance outside the composition stays untouched.
        assert direct_env["PATH"] == os.environ["PATH"]


class TestEnvDrivenConfigChain:
    """D3: ``!ENV`` references resolve at load time into the effective run configuration."""

    @pytest.mark.parametrize(
        ("env_value", "expected_command"),
        [("claude", "/home/goga/bin/claude-as-claude.sh"), (None, None)],
        ids=["set-resolves-the-agent", "unset-resolves-absent"],
    )
    def test_env_referenced_agent_reaches_the_written_afm_config(
        self,
        monkeypatch: pytest.MonkeyPatch,
        in_container_pipeline_run_context: Path,
        env_value: str | None,
        expected_command: str | None,
    ) -> None:
        """``pipeline.agent: !ENV PIPELINE_AGENT`` threads the resolved agent into the afm config write."""
        project_root = in_container_pipeline_run_context
        config_text = "language: python\npipeline:\n  agent: !ENV PIPELINE_AGENT\n"
        (project_root / ".goga" / "config.yml").write_text(config_text)
        _write_pipeline_file(project_root)
        monkeypatch.setenv("AFM_DIR", str((project_root / ".afm").resolve()))

        if env_value is None:
            monkeypatch.delenv("PIPELINE_AGENT", raising=False)
        else:
            monkeypatch.setenv("PIPELINE_AGENT", env_value)

        config = load_project_config()

        assert config.pipeline is not None
        assert config.pipeline.agent == env_value

        with (
            mock.patch.object(_run_pipeline_module, "compile_flow", return_value=_fake_documents()),
            mock.patch.object(_run_pipeline_module, "run_flow", return_value=0),
        ):
            exit_code = _run_pipeline_module.run_pipeline(
                "deploy",
                project_root / ".goga" / "pipelines",
                project_root / "user" / ".goga" / "pipelines",
                50321,
            )

        assert exit_code == 0
        written = yaml.safe_load(_afm_config_module._AFM_CONFIG_PATH.read_text())

        if expected_command is None:
            assert "client" not in written
        else:
            assert written["client"] == {"command": expected_command}
