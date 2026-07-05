from __future__ import annotations

import signal
import subprocess
import sys
from pathlib import Path
from unittest import mock

import click
import pytest
from goga.commands.pipeline import run_pipeline_container
from goga.commands.pipeline.run_pipeline_container import run_pipeline_container as rpc
from goga.config import BuildConfig, Config, PipelineConfig, TaskExecutorConfig

# Resolve the real submodule via sys.modules (the package __init__ binds the
# function name `run_pipeline_container`, which would shadow string-based
# mock.patch paths walking through the package on Python 3.10).
_rpc_mod = sys.modules["goga.commands.pipeline.run_pipeline_container"]


def _make_config(
    *,
    image: str | None = "qarium/goga:latest",
    pipeline_agent: str = "claude",
    pipeline_env: dict[str, str] | None = None,
) -> Config:
    """Build a minimal Config satisfying the new schema (top-level image, pipeline block)."""
    return Config(
        lang="python",
        image=image,
        build=BuildConfig(task_executor=TaskExecutorConfig(agent="claude")),
        pipeline=PipelineConfig(agent=pipeline_agent, env=pipeline_env or {}),
    )


# --- Contract tests ---


class TestRunPipelineContainerContract:
    def test_importable_from_facade(self) -> None:
        """run_pipeline_container is importable from goga.commands.pipeline."""
        assert run_pipeline_container is rpc

    def test_signature_name_and_config(self) -> None:
        """Signature is exactly (name, config)."""
        import inspect

        params = list(inspect.signature(rpc).parameters)
        assert params == ["name", "config"]


# --- Discovery mode ---


class TestPipelineDiscovery:
    def test_pipeline_discovery_launches_container_with_list_command(self, tmp_path: Path, monkeypatch) -> None:
        """Discovery mode assembles `-m goga.pipeline list` with no port/env-file/-p."""
        config = _make_config()
        monkeypatch.setattr(_rpc_mod, "_check_docker", lambda: True)
        monkeypatch.chdir(tmp_path)

        mock_proc = mock.Mock()
        mock_proc.wait.return_value = 0
        with (
            mock.patch.object(subprocess, "Popen", return_value=mock_proc) as mock_popen,
            mock.patch.object(subprocess, "run"),
        ):
            result = run_pipeline_container(None, config)

        assert result == 0
        cmd = mock_popen.call_args[0][0]
        # discovery runs the list subcommand
        assert "-m" in cmd
        assert "goga.pipeline" in cmd
        assert "list" in cmd
        # discovery has no port publishing, no env-file, no --port
        assert "-p" not in cmd
        assert "--port" not in cmd
        assert "--env-file" not in cmd
        # project mounted as /workspace working directory
        assert "-w" in cmd
        assert "/workspace" in cmd

    def test_pipeline_discovery_installs_and_restores_signal_handlers(self, tmp_path: Path, monkeypatch) -> None:
        """Discovery mode installs SIGTERM/SIGINT handlers and kills the container on cleanup."""
        config = _make_config()
        monkeypatch.setattr(_rpc_mod, "_check_docker", lambda: True)
        monkeypatch.chdir(tmp_path)

        mock_proc = mock.Mock()
        mock_proc.wait.return_value = 0
        with (
            mock.patch.object(_rpc_mod.signal, "signal") as mock_signal,
            mock.patch.object(subprocess, "Popen", return_value=mock_proc),
            mock.patch.object(subprocess, "run") as mock_run,
        ):
            run_pipeline_container(None, config)

        # handlers installed at start and restored at end
        sigterm_calls = [c for c in mock_signal.call_args_list if c.args and c.args[0] == signal.SIGTERM]
        sigint_calls = [c for c in mock_signal.call_args_list if c.args and c.args[0] == signal.SIGINT]
        assert len(sigterm_calls) == 2
        assert len(sigint_calls) == 2
        # the finally cleanup ran `docker kill <container>`
        kill_calls = [c for c in mock_run.call_args_list if c.args and c.args[0][:2] == ["docker", "kill"]]
        assert kill_calls


# --- Run mode docker command shape ---


class TestPipelineRunCommand:
    def test_pipeline_run_launches_container_with_port_and_afm_config(
        self, tmp_path: Path, monkeypatch, capsys
    ) -> None:
        """Run mode publishes the port, mounts the afm config, passes env-file, prints Web UI."""
        config = _make_config(pipeline_agent="claude")
        monkeypatch.setattr(_rpc_mod, "_check_docker", lambda: True)
        monkeypatch.setattr(_rpc_mod, "_allocate_port", lambda: 50321)
        monkeypatch.setattr(_rpc_mod, "_read_git_config", lambda: {})
        monkeypatch.chdir(tmp_path)

        mock_proc = mock.Mock()
        mock_proc.wait.return_value = 0
        with (
            mock.patch.object(subprocess, "Popen", return_value=mock_proc) as mock_popen,
            mock.patch.object(subprocess, "run"),
        ):
            run_pipeline_container("deploy", config)

        cmd = mock_popen.call_args[0][0]
        # same port reaches -p and --port
        assert "-p" in cmd
        assert "50321:50321" in cmd
        assert "run" in cmd
        assert "deploy" in cmd
        assert "--port" in cmd
        assert "50321" in cmd
        # afm config mounted read-only at the in-container path
        assert any(arg.endswith(":/home/goga/.afm/config.yaml:ro") for arg in cmd)
        assert "--env-file" in cmd

        out = capsys.readouterr().out
        assert "Web UI: http://localhost:50321" in out

    def test_pipeline_run_does_not_mount_afm_state_under_workspace(self, tmp_path: Path, monkeypatch) -> None:
        """afm state is never mounted under /workspace."""
        config = _make_config()
        monkeypatch.setattr(_rpc_mod, "_check_docker", lambda: True)
        monkeypatch.setattr(_rpc_mod, "_allocate_port", lambda: 50321)
        monkeypatch.setattr(_rpc_mod, "_read_git_config", lambda: {})
        monkeypatch.chdir(tmp_path)

        mock_proc = mock.Mock()
        mock_proc.wait.return_value = 0
        with (
            mock.patch.object(subprocess, "Popen", return_value=mock_proc) as mock_popen,
            mock.patch.object(subprocess, "run"),
        ):
            run_pipeline_container("deploy", config)

        cmd = mock_popen.call_args[0][0]
        assert not any(arg.endswith(":/workspace/.afm") for arg in cmd)
        assert not any(arg.endswith(":/workspace/.afm/config.yaml") for arg in cmd)


# --- afm config tmpfile ---


class TestAfmConfigTmpfile:
    def test_pipeline_run_writes_afm_config_tmpfile_with_client_command(self) -> None:
        """The afm-config tmpfile carries `client.command: <agent>` and mode 0600."""
        afm_path = _rpc_mod._write_afm_config_tmpfile("claude")
        try:
            content = afm_path.read_text()
            mode = afm_path.stat().st_mode & 0o777
        finally:
            afm_path.unlink(missing_ok=True)

        assert content == "client.command: claude\n"
        assert mode == 0o600


# --- env file combination ---


class TestPipelineEnvFile:
    def test_pipeline_env_file_combines_pipeline_env_and_git(self, tmp_path: Path, monkeypatch) -> None:
        """The env file merges config.pipeline.env and git identity (non-overlapping keys)."""
        config = _make_config(pipeline_env={"FOO": "1"})
        monkeypatch.setattr(_rpc_mod, "_read_git_config", lambda: {"GIT_AUTHOR_NAME": "u"})
        monkeypatch.setattr(_rpc_mod, "_check_docker", lambda: True)
        monkeypatch.setattr(_rpc_mod, "_allocate_port", lambda: 50321)
        monkeypatch.chdir(tmp_path)

        captured_env: dict[str, str] = {}
        real_write = _rpc_mod._write_env_file

        def capture(env: dict[str, str]) -> Path:
            captured_env.update(env)
            return real_write(env)

        monkeypatch.setattr(_rpc_mod, "_write_env_file", capture)

        mock_proc = mock.Mock()
        mock_proc.wait.return_value = 0
        with (
            mock.patch.object(subprocess, "Popen", return_value=mock_proc),
            mock.patch.object(subprocess, "run"),
        ):
            run_pipeline_container("deploy", config)

        # pipeline.env + git identity are merged into the env dict.
        assert captured_env["FOO"] == "1"
        assert captured_env["GIT_AUTHOR_NAME"] == "u"

    def test_pipeline_env_overrides_git_on_conflict(self, tmp_path: Path, monkeypatch) -> None:
        """config.pipeline.env wins over git identity when the same key is set in both.

        Mirrors goga/commands/build where task_executor.env overrides git env
        (env = {**git_env, **config.pipeline.env}).
        """
        config = _make_config(pipeline_env={"GIT_AUTHOR_NAME": "from-pipeline"})
        monkeypatch.setattr(_rpc_mod, "_read_git_config", lambda: {"GIT_AUTHOR_NAME": "from-git"})
        monkeypatch.setattr(_rpc_mod, "_check_docker", lambda: True)
        monkeypatch.setattr(_rpc_mod, "_allocate_port", lambda: 50321)
        monkeypatch.chdir(tmp_path)

        captured_env: dict[str, str] = {}
        real_write = _rpc_mod._write_env_file

        def capture(env: dict[str, str]) -> Path:
            captured_env.update(env)
            return real_write(env)

        monkeypatch.setattr(_rpc_mod, "_write_env_file", capture)

        mock_proc = mock.Mock()
        mock_proc.wait.return_value = 0
        with (
            mock.patch.object(subprocess, "Popen", return_value=mock_proc),
            mock.patch.object(subprocess, "run"),
        ):
            run_pipeline_container("deploy", config)

        assert captured_env["GIT_AUTHOR_NAME"] == "from-pipeline"


# --- failure modes ---


class TestPipelineFailureModes:
    def test_pipeline_raises_clickexception_when_docker_missing(self, monkeypatch) -> None:
        """Missing docker raises a ClickException mentioning docker."""
        config = _make_config()
        monkeypatch.setattr(_rpc_mod, "_check_docker", lambda: False)

        with pytest.raises(click.ClickException, match="docker"):
            run_pipeline_container("deploy", config)

    def test_pipeline_raises_clickexception_when_config_image_is_none(self, monkeypatch) -> None:
        """A None image raises a ClickException mentioning image."""
        config = _make_config(image=None)
        monkeypatch.setattr(_rpc_mod, "_check_docker", lambda: True)

        with pytest.raises(click.ClickException, match="image"):
            run_pipeline_container("deploy", config)


# --- image pull ---


class TestPipelinePullImage:
    def test_pipeline_pull_image_failure_warns_and_continues(self, tmp_path: Path, monkeypatch, caplog) -> None:
        """A failing `docker pull` is logged as a warning and the launch proceeds."""
        import logging

        config = _make_config()
        monkeypatch.setattr(_rpc_mod, "_check_docker", lambda: True)
        monkeypatch.setattr(_rpc_mod, "_allocate_port", lambda: 50321)
        monkeypatch.setattr(_rpc_mod, "_read_git_config", lambda: {})
        monkeypatch.chdir(tmp_path)

        def fake_run(cmd, *args, **kwargs):
            # `docker pull` fails; other docker calls (kill cleanup) succeed.
            if cmd[:2] == ["docker", "pull"]:
                return mock.Mock(returncode=1)
            return mock.Mock(returncode=0)

        mock_proc = mock.Mock()
        mock_proc.wait.return_value = 0
        with (
            mock.patch.object(subprocess, "Popen", return_value=mock_proc),
            mock.patch.object(subprocess, "run", side_effect=fake_run),
            caplog.at_level(logging.WARNING, logger=_rpc_mod.logger.name),
        ):
            result = run_pipeline_container("deploy", config)

        # a warning was emitted for the failed pull, and the launch still proceeded
        assert any("failed to pull image" in rec.message for rec in caplog.records)
        assert result == 0


# --- signal handling ---


class TestPipelineSignals:
    def test_pipeline_run_installs_and_restores_sigterm_handler(self, tmp_path: Path, monkeypatch) -> None:
        """SIGTERM handler is installed at start and restored at end."""
        config = _make_config()
        monkeypatch.setattr(_rpc_mod, "_check_docker", lambda: True)
        monkeypatch.setattr(_rpc_mod, "_allocate_port", lambda: 50321)
        monkeypatch.setattr(_rpc_mod, "_read_git_config", lambda: {})
        monkeypatch.chdir(tmp_path)

        mock_proc = mock.Mock()
        mock_proc.wait.return_value = 0
        with (
            mock.patch.object(_rpc_mod.signal, "signal") as mock_signal,
            mock.patch.object(subprocess, "Popen", return_value=mock_proc),
            mock.patch.object(subprocess, "run"),
        ):
            run_pipeline_container("deploy", config)

        sigterm_calls = [c for c in mock_signal.call_args_list if c.args and c.args[0] == signal.SIGTERM]
        # one install at start, one restore at end
        assert len(sigterm_calls) == 2

    def test_pipeline_run_returns_130_on_sigint(self, tmp_path: Path, monkeypatch) -> None:
        """SIGINT during run results in exit code 130 and a docker kill."""
        config = _make_config()
        monkeypatch.setattr(_rpc_mod, "_check_docker", lambda: True)
        monkeypatch.setattr(_rpc_mod, "_allocate_port", lambda: 50321)
        monkeypatch.setattr(_rpc_mod, "_read_git_config", lambda: {})
        monkeypatch.chdir(tmp_path)

        captured: dict[int, object] = {}

        def fake_signal(sig: int, handler: object) -> object:
            captured[sig] = handler
            return signal.SIG_DFL

        def fake_wait() -> int:
            # invoke the installed SIGINT handler inline, as a real signal would
            handler = captured[signal.SIGINT]
            assert callable(handler)
            handler(signal.SIGINT, None)
            return 0

        mock_proc = mock.Mock()
        mock_proc.wait = fake_wait

        with (
            mock.patch.object(_rpc_mod.signal, "signal", side_effect=fake_signal),
            mock.patch.object(subprocess, "Popen", return_value=mock_proc),
            mock.patch.object(subprocess, "run") as mock_run,
            pytest.raises(SystemExit) as exc,
        ):
            run_pipeline_container("deploy", config)

        assert exc.value.code == 130
        # the handler (and/or finally) ran `docker kill` via subprocess.run
        kill_calls = [c for c in mock_run.call_args_list if c.args and c.args[0][:2] == ["docker", "kill"]]
        assert kill_calls

    def test_pipeline_run_propagates_127_when_afm_missing_in_container(self, tmp_path: Path, monkeypatch) -> None:
        """afm missing inside the container propagates exit code 127."""
        config = _make_config()
        monkeypatch.setattr(_rpc_mod, "_check_docker", lambda: True)
        monkeypatch.setattr(_rpc_mod, "_allocate_port", lambda: 50321)
        monkeypatch.setattr(_rpc_mod, "_read_git_config", lambda: {})
        monkeypatch.chdir(tmp_path)

        mock_proc = mock.Mock()
        mock_proc.wait.return_value = 127
        with (
            mock.patch.object(subprocess, "Popen", return_value=mock_proc),
            mock.patch.object(subprocess, "run"),
        ):
            result = run_pipeline_container("deploy", config)

        assert result == 127
