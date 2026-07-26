"""Logic tests for the workflow layer of ``run_pipeline_container``.

Covers the CODEMANIFEST ``run_pipeline_container`` run-mode Algorithm steps 9-11:

- step 9 — the host-side workflow_env + workflow_log_name decision matrix:
  ``--no-workflow`` → ``GOGA_WORKFLOW_DISABLED=1`` (no log); explicit
  ``--workflow X`` → ``GOGA_WORKFLOW_NAME=X`` (log names X); auto-match fallback
  → no workflow env var (log names the pipeline only when the basename file
  exists on the host)
- step 10 — the ``Pipeline running with workflow "NAME"`` log line is printed to
  stdout ONLY when a workflow will actually be applied; this cell surfaces NO
  dashboard URL line
- step 11 — the workflow_env entries reach the env-file

The log-line tests drive the real launcher through the ``pipeline`` click command
with docker internals mocked (no docker dependency); the env-file tests capture
``_write_env_file`` directly.
"""

from __future__ import annotations

import inspect
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest
from click.testing import CliRunner
from goga.commands.pipeline import pipeline
from goga.commands.pipeline.run_pipeline_container import (
    run_pipeline_container as rpc,
)
from goga.config import BuildConfig, PipelineConfig, ProjectConfig, TaskExecutorConfig

# Resolve the real submodules via sys.modules (the package __init__ binds the
# function/command names, which would shadow string-based mock.patch paths
# walking through the package on Python 3.10).
_rpc_mod = sys.modules["goga.commands.pipeline.run_pipeline_container"]
_pipeline_module = sys.modules["goga.commands.pipeline.pipeline"]


def _make_config(
    *,
    pipeline_agent: str = "claude",
    pipeline_env: dict[str, str] | None = None,
) -> ProjectConfig:
    """Build a minimal ProjectConfig with a pipeline section for run-mode dispatch."""
    return ProjectConfig(
        lang="python",
        image="qarium/goga:latest",
        dockerfile=None,
        build=BuildConfig(task_executor=TaskExecutorConfig(agent="claude")),
        pipeline=PipelineConfig(agent=pipeline_agent, env=pipeline_env or {}),
    )


def _write_config(tmp_path: Path) -> None:
    """Materialize a minimal ``.goga/config.yml`` with a pipeline section."""
    goga_dir = tmp_path / ".goga"
    goga_dir.mkdir(parents=True, exist_ok=True)
    (goga_dir / "config.yml").write_text(
        "\n".join(
            [
                "language: python",
                "image: qarium/goga:latest",
                "build:",
                "  task_executor:",
                "    agent: claude",
                "pipeline:",
                "  agent: claude",
            ]
        )
        + "\n"
    )


def _mock_docker_internals(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mock the docker side effects so the real launcher runs without docker.

    ``_check_docker`` → True; ``_allocate_port`` → fixed; git identity → empty;
    docker build/launch subprocesses → no-ops returning a 0-exit container.
    ``subprocess.run`` returns a plain Mock so ``result.returncode == 0`` is
    False everywhere it is consulted: ``resolve_git_branch`` falls back to
    ``"default"`` (a real branch string, not a Mock) and ``_image_exists``
    reports absent (with ``dockerfile=None`` the build path is a no-op) — neither
    raises, mirroring the sibling tests that patch ``subprocess.run`` with a
    MagicMock.
    """
    monkeypatch.setattr(_rpc_mod, "_check_docker", lambda: True)
    monkeypatch.setattr(_rpc_mod, "_allocate_port", lambda: 50321)
    monkeypatch.setattr(_rpc_mod, "_read_git_config", lambda: {})
    mock_proc = mock.Mock()
    mock_proc.wait.return_value = 0
    monkeypatch.setattr(subprocess, "Popen", lambda *_a, **_k: mock_proc)
    monkeypatch.setattr(subprocess, "run", lambda *_a, **_k: mock.Mock())


# --- Step 10 — workflow log line + dashboard URL removal ---


class TestRunPipelineContainerWorkflowLogLine:
    def test_pipeline_command_workflow_flag_emits_log_line(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Explicit ``--workflow custom`` emits the workflow log line, no dashboard URL.

        The host-side existence check (step 6 in the ``pipeline`` command) passes
        because ``.goga/workflows/custom.yml`` exists, so dispatch reaches the
        real launcher. Step 9 resolves ``workflow_env={"GOGA_WORKFLOW_NAME":
        "custom"}`` / ``workflow_log_name="custom"``; step 10 emits the log line.
        The dashboard URL line is absent (removed by contract).
        """
        _write_config(tmp_path)
        workflows_dir = tmp_path / ".goga" / "workflows"
        workflows_dir.mkdir(parents=True, exist_ok=True)
        (workflows_dir / "custom.yml").write_text("prompt: hi\n")
        monkeypatch.chdir(tmp_path)
        _mock_docker_internals(monkeypatch)

        runner = CliRunner()
        result = runner.invoke(pipeline, ["deploy", "--workflow", "custom"])

        assert result.exit_code == 0
        assert 'Pipeline running with workflow "custom"' in result.output
        assert "Web UI:" not in result.output

    def test_run_pipeline_container_no_workflow_no_log_line(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No workflow flags + no auto-match file emits no log line and no dashboard URL.

        Auto-match fallback (step 9 else-branch): ``.goga/workflows/deploy.yml``
        is absent on the host → ``workflow_log_name=None`` → step 10 emits
        nothing. The dashboard URL line is also absent.
        """
        _write_config(tmp_path)
        monkeypatch.chdir(tmp_path)
        _mock_docker_internals(monkeypatch)

        runner = CliRunner()
        result = runner.invoke(pipeline, ["deploy"])

        assert result.exit_code == 0
        assert "Pipeline running with workflow" not in result.output
        assert "Web UI:" not in result.output

    def test_run_pipeline_container_no_workflow_flag_emits_no_log_line(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``--no-workflow`` emits no workflow log line (step 9 disables + no log).

        ``no_workflow=True`` → ``workflow_log_name=None`` → no log line, even
        though the env-file still carries ``GOGA_WORKFLOW_DISABLED=1``.
        """
        _write_config(tmp_path)
        monkeypatch.chdir(tmp_path)
        _mock_docker_internals(monkeypatch)

        runner = CliRunner()
        result = runner.invoke(pipeline, ["deploy", "--no-workflow"])

        assert result.exit_code == 0
        assert "Pipeline running with workflow" not in result.output
        assert "Web UI:" not in result.output

    def test_run_pipeline_container_auto_match_file_present_emits_log_line(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Auto-match with the basename file present emits the log line naming the pipeline.

        Auto-match fallback (step 9): ``.goga/workflows/deploy.yml`` exists →
        ``workflow_log_name="deploy"`` (the pipeline name, NOT a separate
        workflow name) → step 10 emits the line. The host writes NO workflow env
        var (the in-container routine resolves the basename itself).
        """
        _write_config(tmp_path)
        workflows_dir = tmp_path / ".goga" / "workflows"
        workflows_dir.mkdir(parents=True, exist_ok=True)
        (workflows_dir / "deploy.yml").write_text("prompt: hi\n")
        monkeypatch.chdir(tmp_path)
        _mock_docker_internals(monkeypatch)

        runner = CliRunner()
        result = runner.invoke(pipeline, ["deploy"])

        assert result.exit_code == 0
        assert 'Pipeline running with workflow "deploy"' in result.output
        assert "Web UI:" not in result.output


class TestResolveWorkflowEnvAutoMatchContainment:
    """Auto-match path-traversal containment (CODEMANIFEST step 6b).

    The auto-match fallback composes ``<cwd>/.goga/workflows/<name>.yml`` from the
    pipeline ``name``. A ``name`` escaping the workflows dir via ``..`` or an
    absolute prefix is a silent miss — ``workflow_log_name=None``, no env var —
    even when the escaped path exists on the host, mirroring the
    explicit-``--workflow`` (host) and in-container containment guards. This keeps
    the host log line honest: it never claims a workflow that the in-container
    resolver will refuse to apply.
    """

    def test_auto_match_dotdot_escape_is_silent_miss(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """A ``..`` in the pipeline name never resolves outside the workflows dir."""
        workflows_dir = tmp_path / ".goga" / "workflows"
        workflows_dir.mkdir(parents=True, exist_ok=True)
        # A file reachable only by escaping the workflows dir via ``..``.
        (tmp_path / ".goga" / "outside.yml").write_text("prompt: evil\n")
        monkeypatch.chdir(tmp_path)

        workflow_env, workflow_log_name = _rpc_mod._resolve_workflow_env(
            workflow=None, no_workflow=False, name="../outside"
        )

        assert workflow_env == {}
        assert workflow_log_name is None

    def test_auto_match_absolute_prefix_is_silent_miss(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """An absolute-prefixed pipeline name never resolves outside the workflows dir."""
        workflows_dir = tmp_path / ".goga" / "workflows"
        workflows_dir.mkdir(parents=True, exist_ok=True)
        monkeypatch.chdir(tmp_path)

        workflow_env, workflow_log_name = _rpc_mod._resolve_workflow_env(
            workflow=None, no_workflow=False, name="/etc/evil"
        )

        assert workflow_env == {}
        assert workflow_log_name is None

    def test_auto_match_plain_name_still_resolves(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """A plain pipeline name with a present basename file still resolves (regression guard)."""
        workflows_dir = tmp_path / ".goga" / "workflows"
        workflows_dir.mkdir(parents=True, exist_ok=True)
        (workflows_dir / "deploy.yml").write_text("prompt: hi\n")
        monkeypatch.chdir(tmp_path)

        workflow_env, workflow_log_name = _rpc_mod._resolve_workflow_env(
            workflow=None, no_workflow=False, name="deploy"
        )

        assert workflow_env == {}
        assert workflow_log_name == "deploy"


# --- Step 11 — env-file workflow entries ---


def _capture_env(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    """Monkeypatch ``_write_env_file`` to capture the env dict it is handed."""
    captured: dict[str, str] = {}
    real_write = _rpc_mod._write_env_file

    def capture(env: dict[str, str], extra_env: tuple[str, ...] = ()) -> Path:
        captured.update(env)
        return real_write(env, extra_env)

    monkeypatch.setattr(_rpc_mod, "_write_env_file", capture)
    return captured


class TestRunPipelineContainerSkipContract:
    """Contract: ``run_pipeline_container`` exposes the ``skip`` parameter with a real Python default of ``()``.

    The CODEMANIFEST DSL cannot express the empty-tuple default, so the contract
    pins the semantics as "default empty" and Additional Instruction #4 mandates
    the Python realization carry ``skip: tuple[str, ...] = ()``. These checks
    guard that the launcher's public surface accepts ``skip`` and threads it.
    """

    def test_skip_parameter_is_present(self) -> None:
        params = inspect.signature(rpc).parameters
        assert "skip" in params

    def test_skip_parameter_default_is_empty_tuple(self) -> None:
        params = inspect.signature(rpc).parameters
        assert params["skip"].default == ()


class TestRunPipelineContainerWorkflowEnvFile:
    def test_run_pipeline_container_no_workflow_env_file_entry(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``--no-workflow`` writes ``GOGA_WORKFLOW_DISABLED=1`` into the env-file."""
        config = _make_config()
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(_rpc_mod, "_check_docker", lambda: True)
        monkeypatch.setattr(_rpc_mod, "_allocate_port", lambda: 50321)
        monkeypatch.setattr(_rpc_mod, "_read_git_config", lambda: {})
        captured = _capture_env(monkeypatch)
        mock_proc = mock.Mock()
        mock_proc.wait.return_value = 0
        with (
            mock.patch.object(subprocess, "Popen", return_value=mock_proc),
            mock.patch.object(subprocess, "run"),
        ):
            rpc("deploy", config, no_workflow=True)

        assert captured["GOGA_WORKFLOW_DISABLED"] == "1"
        # mutually exclusive path — no NAME var is written
        assert "GOGA_WORKFLOW_NAME" not in captured

    def test_run_pipeline_container_workflow_env_file_entry(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Explicit ``--workflow custom`` writes ``GOGA_WORKFLOW_NAME=custom`` into the env-file."""
        config = _make_config()
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(_rpc_mod, "_check_docker", lambda: True)
        monkeypatch.setattr(_rpc_mod, "_allocate_port", lambda: 50321)
        monkeypatch.setattr(_rpc_mod, "_read_git_config", lambda: {})
        captured = _capture_env(monkeypatch)
        mock_proc = mock.Mock()
        mock_proc.wait.return_value = 0
        with (
            mock.patch.object(subprocess, "Popen", return_value=mock_proc),
            mock.patch.object(subprocess, "run"),
        ):
            rpc("deploy", config, workflow="custom")

        assert captured["GOGA_WORKFLOW_NAME"] == "custom"
        assert "GOGA_WORKFLOW_DISABLED" not in captured

    def test_run_pipeline_container_auto_match_env_file_no_workflow_vars(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Auto-match fallback writes NEITHER workflow env var into the env-file.

        With no workflow flags and the basename ``.goga/workflows/deploy.yml``
        present, the host writes no workflow env var — the in-container
        ``run_pipeline`` resolves the basename fallback itself. Only the log
        line (step 10) names the workflow; the env-file stays workflow-free.
        """
        config = _make_config()
        workflows_dir = tmp_path / ".goga" / "workflows"
        workflows_dir.mkdir(parents=True, exist_ok=True)
        (workflows_dir / "deploy.yml").write_text("prompt: hi\n")
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(_rpc_mod, "_check_docker", lambda: True)
        monkeypatch.setattr(_rpc_mod, "_allocate_port", lambda: 50321)
        monkeypatch.setattr(_rpc_mod, "_read_git_config", lambda: {})
        captured = _capture_env(monkeypatch)
        mock_proc = mock.Mock()
        mock_proc.wait.return_value = 0
        with (
            mock.patch.object(subprocess, "Popen", return_value=mock_proc),
            mock.patch.object(subprocess, "run"),
        ):
            rpc("deploy", config)

        assert "GOGA_WORKFLOW_NAME" not in captured
        assert "GOGA_WORKFLOW_DISABLED" not in captured

    def test_run_pipeline_container_auto_match_absent_env_file_no_workflow_vars(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Auto-match fallback with the basename file absent writes no workflow env var.

        The silent-miss path: ``.goga/workflows/deploy.yml`` does not exist →
        ``workflow_env={}`` and ``workflow_log_name=None``. No env var, no log.
        """
        config = _make_config()
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(_rpc_mod, "_check_docker", lambda: True)
        monkeypatch.setattr(_rpc_mod, "_allocate_port", lambda: 50321)
        monkeypatch.setattr(_rpc_mod, "_read_git_config", lambda: {})
        captured = _capture_env(monkeypatch)
        mock_proc = mock.Mock()
        mock_proc.wait.return_value = 0
        with (
            mock.patch.object(subprocess, "Popen", return_value=mock_proc),
            mock.patch.object(subprocess, "run"),
        ):
            rpc("deploy", config)

        assert "GOGA_WORKFLOW_NAME" not in captured
        assert "GOGA_WORKFLOW_DISABLED" not in captured

    def test_run_pipeline_container_writes_skip_env_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Non-empty ``skip`` writes ``GOGA_SKIP_STAGES=<csv>`` into the env-file.

        Run mode threads ``skip`` end-to-end: ``run_pipeline_container`` →
        ``_run_named`` → ``_build_env_file``. The launcher joins the stage names
        comma-separated (Additional Instruction #3 — single env-layering point).
        The host does NOT validate the names (in-container only).
        """
        config = _make_config()
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(_rpc_mod, "_check_docker", lambda: True)
        monkeypatch.setattr(_rpc_mod, "_allocate_port", lambda: 50321)
        monkeypatch.setattr(_rpc_mod, "_read_git_config", lambda: {})
        captured = _capture_env(monkeypatch)
        mock_proc = mock.Mock()
        mock_proc.wait.return_value = 0
        with (
            mock.patch.object(subprocess, "Popen", return_value=mock_proc),
            mock.patch.object(subprocess, "run"),
        ):
            rpc("deploy", config, skip=("build", "test"))

        assert captured["GOGA_SKIP_STAGES"] == "build,test"

    def test_run_pipeline_container_empty_skip_omits_env_entry(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Empty ``skip`` omits the ``GOGA_SKIP_STAGES`` entry from the env-file.

        ``GOGA_SKIP_STAGES`` is written ONLY when ``skip`` is non-empty — the
        entry is absent (not an empty string) when the default empty tuple is
        forwarded, so the in-container ``run_pipeline`` step 6e no-ops.
        """
        config = _make_config()
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(_rpc_mod, "_check_docker", lambda: True)
        monkeypatch.setattr(_rpc_mod, "_allocate_port", lambda: 50321)
        monkeypatch.setattr(_rpc_mod, "_read_git_config", lambda: {})
        captured = _capture_env(monkeypatch)
        mock_proc = mock.Mock()
        mock_proc.wait.return_value = 0
        with (
            mock.patch.object(subprocess, "Popen", return_value=mock_proc),
            mock.patch.object(subprocess, "run"),
        ):
            rpc("deploy", config, skip=())

        assert "GOGA_SKIP_STAGES" not in captured
