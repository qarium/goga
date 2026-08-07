"""End-to-end integration tests for the ``-p/--parallel`` flow (Flow A).

Verifies the optional concurrency cap threads across every cell boundary
introduced by the ``up-afm-version`` feature — host Click CLI → docker argv →
in-container argparse → ``run_pipeline`` → ``run_flow`` → ``afm --max-parallel``
— and that ``None`` (the default) materializes as an OMITTED flag on every
boundary (backward compatible). The architecture splits the work across a
host/docker boundary, so the two halves are stitched here:

- Host half: ``goga pipeline NAME -p N`` → ``run_pipeline_container`` assembles
  the in-container argv; docker is mocked at the ``DockerRunner.run`` boundary.
- Container half: ``pipeline_cli run NAME --port P --parallel N`` → ``run_flow``
  → ``afm run``; the ``afm`` binary is mocked at the ``subprocess.run`` boundary.

Mocking follows ``[[feedback_mock_patch_module_shadowing]]``: the package
``__init__`` re-exports the submodule functions under the same names, which
shadows string-based ``mock.patch`` paths on Python 3.10, so the real modules
are resolved via ``sys.modules`` and patched by attribute.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest import mock
from unittest.mock import MagicMock

from click.testing import CliRunner
from goga.cli import app
from goga.config import BuildConfig, PipelineConfig, ProjectConfig, TaskExecutorConfig
from goga.pipeline import pipeline_cli
from goga.pipeline.compiler import (
    BodyFormat,
    FlowDocument,
    PhasesBody,
    PipelineDocument,
    PipelineHeader,
)

# goga.afm.run_flow is shadowed in the package __init__ by the run_flow
# function; resolve the real module via sys.modules and patch its subprocess
# attribute directly.
_run_flow_module = sys.modules["goga.afm.run_flow"]
# goga.commands.pipeline.run_pipeline_container shadows its submodule name.
_rpc_module = sys.modules["goga.commands.pipeline.run_pipeline_container"]
# goga.commands.pipeline.pipeline shadows its submodule name too.
_pipeline_module = sys.modules["goga.commands.pipeline.pipeline"]
# goga.pipeline.run_pipeline is shadowed in the package __init__ by the
# run_pipeline function; resolve it so compile_flow can be patched there.
_run_pipeline_module = sys.modules["goga.pipeline.run_pipeline"]


def _make_config() -> ProjectConfig:
    """Build a minimal ProjectConfig satisfying the new schema (top-level image, pipeline block)."""
    return ProjectConfig(
        lang="python",
        image="qarium/goga:latest",
        dockerfile=None,
        build=BuildConfig(task_executor=TaskExecutorConfig(agent="claude")),
        pipeline=PipelineConfig(agent="claude"),
    )


def _fake_documents() -> tuple[PipelineDocument, FlowDocument]:
    """Build the documents tuple ``compile_flow`` returns, for mock wiring.

    Mirrors ``tests/pipeline/test_run_pipeline._fake_documents`` and the
    ``tests/integration/test_pipeline_cli._fake_documents`` helper.
    """
    pipeline_doc = PipelineDocument(
        header=PipelineHeader(name="deploy", description="d", roles=None),
        format=BodyFormat.PHASES,
        body=PhasesBody(steps=[]),
    )
    flow_doc = FlowDocument(name="deploy", description="d", stages=[])
    return (pipeline_doc, flow_doc)


def _capture_docker(monkeypatch) -> dict[str, object]:
    """Replace ``DockerRunner.run`` with a recorder of (args, params).

    Mirrors ``tests/commands/pipeline/test_run_pipeline_container._capture_docker``.
    Returns the dict populated with the captured in-container ``args`` list and
    the docker-run ``params`` dict (minus the separate ``extra_args`` keyword).
    """
    captured: dict[str, object] = {"args": None, "params": None}

    def _record(_self, args, extra_args=None, **params):
        captured["args"] = list(args)
        captured["params"] = {k: v for k, v in params.items() if k != "extra_args"}
        return 0

    monkeypatch.setattr(_rpc_module.DockerRunner, "run", _record)
    return captured


class TestParallelHostCliToContainerArgv:
    """Host half: ``goga pipeline NAME -p N`` threads ``parallel`` into the in-container argv.

    The Click ``-p/--parallel`` value reaches the real ``run_pipeline_container``
    (boundary 1: ``parallel == N`` is forwarded), which appends ``--parallel <N>``
    to the in-container ``run`` argv after ``--port`` (boundary 2). The Docker
    ``-p <port>:<port>`` port-publish token stays isolated from it.
    """

    def _invoke_host(self, tmp_path: Path, args: list[str], monkeypatch) -> tuple[int, dict[str, object]]:
        """Invoke the host ``goga pipeline`` command and return (exit_code, docker_capture)."""
        config = _make_config()
        monkeypatch.chdir(tmp_path)
        # Host-side docker launcher helpers.
        monkeypatch.setattr(_rpc_module, "_check_docker", lambda: True)
        monkeypatch.setattr(_rpc_module, "_allocate_port", lambda: 50321)
        monkeypatch.setattr(_rpc_module, "_read_git_config", lambda: {})
        # ProjectConfig load returns the new-schema ProjectConfig.
        monkeypatch.setattr(_pipeline_module, "load_project_config", lambda: config)
        captured = _capture_docker(monkeypatch)

        runner = CliRunner()
        with mock.patch.object(subprocess, "run"):
            result = runner.invoke(app, ["pipeline", *args])
        return result.exit_code, captured

    def test_parallel_threads_host_cli_to_container_argv(self, tmp_path: Path, monkeypatch) -> None:
        """``-p 4`` reaches ``run_pipeline_container`` and the in-container argv as ``--parallel 4``."""
        # Spy on the dispatched ``run_pipeline_container`` to capture the ``parallel``
        # kwarg while still delegating to the real function (so the docker argv is
        # actually assembled and the deep boundary is exercised).
        real_rpc = _rpc_module.run_pipeline_container
        seen: dict[str, object] = {}

        def spy(**kwargs: object) -> int:
            seen["parallel"] = kwargs.get("parallel")
            return real_rpc(**kwargs)  # type: ignore[arg-type]

        monkeypatch.setattr(_pipeline_module, "run_pipeline_container", spy)

        exit_code, captured = self._invoke_host(tmp_path, ["deploy", "-p", "4"], monkeypatch)

        assert exit_code == 0
        # Boundary 1: Click -p 4 threads to run_pipeline_container as parallel=4.
        assert seen["parallel"] == 4
        # Boundary 2: real run_pipeline_container appends --parallel 4 after --port.
        args = captured["args"]
        assert "--parallel" in args
        assert args.index("--parallel") > args.index("50321")
        assert args[args.index("--parallel") + 1] == "4"
        # The Docker -p <port>:<port> port-publish token is isolated from parallel.
        assert captured["params"]["p"] == "50321:50321"

    def test_parallel_none_omitted_through_chain(self, tmp_path: Path, monkeypatch) -> None:
        """Without ``-p`` the host half emits no ``--parallel`` anywhere in the argv chain.

        Host half (this test): ``goga pipeline deploy`` ⇒ no ``--parallel`` in the
        in-container argv. The container half (``--max-parallel`` omitted at the
        afm boundary) is covered by ``TestParallelContainerCliToRunFlow``.
        """
        exit_code, captured = self._invoke_host(tmp_path, ["deploy"], monkeypatch)

        assert exit_code == 0
        assert "--parallel" not in captured["args"]


class TestParallelContainerCliToRunFlow:
    """Container half: ``pipeline_cli run --parallel N`` → ``run_flow`` → ``afm --max-parallel N``.

    Drives the in-container path directly (the path that ``python -m goga.pipeline
    run <name> --port <port> [--parallel N]`` takes inside the goga Docker image),
    with the ``afm`` binary mocked at the subprocess boundary.
    """

    @staticmethod
    def _write_project(tmp_path: Path, name: str = "deploy") -> Path:
        """Create a project CWD carrying a ``<name>.yml`` pipeline file; return the CWD."""
        project_tmp = tmp_path / "project"
        project_pipelines = project_tmp / ".goga" / "pipelines"
        project_pipelines.mkdir(parents=True)
        (project_pipelines / f"{name}.yml").write_text("pipeline")
        return project_tmp

    @staticmethod
    def _afm_argv(mock_subprocess: MagicMock) -> list[str] | None:
        """Extract the ``afm`` argv from the recorded subprocess calls, if any.

        ``run_pipeline`` also calls ``subprocess.run`` (the ``git config --get
        remote.origin.url`` probe via ``resolve_project_name``) before afm is
        reached, so the afm invocation is located among the call list.
        """
        afm_calls = [c for c in mock_subprocess.call_args_list if c.args[0][0] == "afm"]
        assert len(afm_calls) == 1
        return list(afm_calls[0].args[0])

    def test_parallel_threads_pipeline_cli_to_run_flow(self, tmp_path: Path, monkeypatch) -> None:
        """``--parallel 4`` threads to ``run_flow`` as ``--max-parallel 4`` in the afm argv."""
        project_tmp = self._write_project(tmp_path)
        monkeypatch.setattr(Path, "cwd", lambda: project_tmp)
        monkeypatch.setattr(Path, "home", lambda: tmp_path / "user")
        afm_dir = (tmp_path / ".afm").resolve()
        monkeypatch.setenv("AFM_DIR", str(afm_dir))

        with (
            mock.patch.object(_run_pipeline_module, "compile_flow", return_value=_fake_documents()),
            mock.patch.object(
                _run_flow_module.subprocess,
                "run",
                return_value=MagicMock(returncode=0),
            ) as mock_subprocess,
        ):
            result = pipeline_cli(["run", "deploy", "--port", "50321", "--parallel", "4"])

        assert result == 0
        argv = self._afm_argv(mock_subprocess)
        # afm invocation shape: afm run --port 50321 --max-parallel 4 <flow path>.
        assert argv[:4] == ["afm", "run", "--port", "50321"]
        assert "--max-parallel" in argv
        assert argv.index("--max-parallel") > argv.index("50321")
        assert argv[argv.index("--max-parallel") + 1] == "4"
        # The compiled flow-file path follows --max-parallel.
        assert argv[-1] == str(afm_dir / "flow.yml")

    def test_parallel_none_omitted_in_afm_argv(self, tmp_path: Path, monkeypatch) -> None:
        """No ``--parallel`` ⇒ ``--max-parallel`` is OMITTED from the afm argv (backward compat).

        Container half of ``test_parallel_none_omitted_through_chain``: ``None``
        threads ``run_pipeline`` → ``run_flow`` and the ``--max-parallel`` flag is
        omitted so afm runs unbounded.
        """
        project_tmp = self._write_project(tmp_path)
        monkeypatch.setattr(Path, "cwd", lambda: project_tmp)
        monkeypatch.setattr(Path, "home", lambda: tmp_path / "user")
        afm_dir = (tmp_path / ".afm").resolve()
        monkeypatch.setenv("AFM_DIR", str(afm_dir))

        with (
            mock.patch.object(_run_pipeline_module, "compile_flow", return_value=_fake_documents()),
            mock.patch.object(
                _run_flow_module.subprocess,
                "run",
                return_value=MagicMock(returncode=0),
            ) as mock_subprocess,
        ):
            result = pipeline_cli(["run", "deploy", "--port", "50321"])

        assert result == 0
        argv = self._afm_argv(mock_subprocess)
        assert "--max-parallel" not in argv
        # The flow path is the last positional (afm unbounded — no --max-parallel).
        assert argv == ["afm", "run", "--port", "50321", str(afm_dir / "flow.yml")]
