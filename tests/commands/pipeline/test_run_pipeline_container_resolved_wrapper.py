from __future__ import annotations

import signal
import subprocess
import sys
from pathlib import Path
from unittest import mock

import click
import pytest
from click.testing import CliRunner
from goga.commands.pipeline import pipeline as pipeline_cmd
from goga.commands.pipeline.run_pipeline_container import (
    _write_afm_config_tmpfile,
)
from goga.commands.pipeline.run_pipeline_container import (
    run_pipeline_container as rpc,
)
from goga.config import BuildConfig, Config, PipelineConfig, TaskExecutorConfig

# goga.commands.pipeline.pipeline is shadowed in the package __init__ by the
# pipeline Click command, so a string-based mock.patch path walking through it
# fails on Python 3.10. Resolve the real module via sys.modules.
_pipeline_module = sys.modules["goga.commands.pipeline.pipeline"]
_rpc_mod = sys.modules["goga.commands.pipeline.run_pipeline_container"]

_AFM_MOUNT_SUFFIX = ":/home/goga/.afm/config.yaml:ro"
_CODEX_AUTH_MOUNT_SUFFIX = ":/home/goga/.codex/auth.json:ro"


def _make_config(*, pipeline_agent: str = "claude") -> Config:
    """Build a minimal Config satisfying the new schema (top-level image, pipeline block)."""
    return Config(
        lang="python",
        image="qarium/goga:latest",
        dockerfile=None,
        build=BuildConfig(task_executor=TaskExecutorConfig(agent="claude")),
        pipeline=PipelineConfig(agent=pipeline_agent, env={}),
    )


def _write_config(
    tmp_path: Path,
    *,
    agent: str = "claude",
    image: str | None = "qarium/goga:latest",
) -> None:
    """Materialize a .goga/config.yml under tmp_path with the requested schema."""
    goga_dir = tmp_path / ".goga"
    goga_dir.mkdir(parents=True, exist_ok=True)

    lines = [
        "language: python",
    ]
    if image is not None:
        lines.append(f"image: {image}")
    lines += [
        "pipeline:",
        f"  agent: {agent}",
        "build:",
        "  task_executor:",
        "    agent: claude",
    ]
    (goga_dir / "config.yml").write_text("\n".join(lines) + "\n")


def _capture_afm_config_popen(captured: dict) -> tuple[object, object]:
    """Build a subprocess.Popen side effect that reads the afm-config tmpfile.

    The afm-config host path is extracted from the run-mode docker command's
    ``-v <host>:/home/goga/.afm/config.yaml:ro`` argument and read back into
    ``captured['afm_content']`` (and the host path into ``captured['afm_host']``)
    before the mocked process returns — capturing the real file content written
    by the integrated ``_write_afm_config_tmpfile`` call.
    """
    mock_proc = mock.Mock()
    mock_proc.wait.return_value = 0

    def popen_side_effect(cmd, *args, **kwargs):
        for i, arg in enumerate(cmd):
            if arg == "-v" and i + 1 < len(cmd) and cmd[i + 1].endswith(_AFM_MOUNT_SUFFIX):
                host = cmd[i + 1][: -len(_AFM_MOUNT_SUFFIX)]
                captured["afm_host"] = host
                captured["afm_content"] = Path(host).read_text()
                break
        captured.setdefault("popen_cmds", []).append(list(cmd))
        return mock_proc

    return mock_proc, popen_side_effect


# --- Contract obligation ---


class TestRunPipelineContainerContract:
    def test_importable_from_module(self) -> None:
        """run_pipeline_container is importable from run_pipeline_container module."""
        from goga.commands.pipeline.run_pipeline_container import (
            run_pipeline_container as imported,
        )

        assert imported is rpc


# --- _write_afm_config_tmpfile unit tests ---


class TestWriteAfmConfigTmpfile:
    def test_writes_resolved_path_with_mode_0600(self) -> None:
        """Content is the resolved wrapper path; the temp file is private (0600)."""
        path = _write_afm_config_tmpfile("/home/goga/bin/codex-as-claude.sh")
        try:
            assert path.read_text() == (
                "client.command: /home/goga/bin/codex-as-claude.sh\n"
                "theme: goga\n"
                "open_browser: false\n"
                "proxy:\n"
                "  enabled: false\n"
                "prompts_dir: /home/goga/pipeline/prompts\n"
            )
            assert (path.stat().st_mode & 0o777) == 0o600
        finally:
            path.unlink(missing_ok=True)

    def test_includes_static_launcher_side_constants(self) -> None:
        """The tmpfile carries the static launcher-side constants: theme, open_browser, proxy.enabled, prompts_dir."""
        path = _write_afm_config_tmpfile("/home/goga/bin/codex-as-claude.sh")
        try:
            lines = path.read_text().splitlines()
            assert "theme: goga" in lines
            assert "open_browser: false" in lines
            assert "proxy:" in lines
            assert "  enabled: false" in lines
            assert "prompts_dir: /home/goga/pipeline/prompts" in lines
        finally:
            path.unlink(missing_ok=True)


# --- Resolved wrapper path in afm-config tmpfile ---


class TestResolvedWrapperAfmConfig:
    def test_run_pipeline_container_writes_resolved_wrapper_to_afm_config(self, tmp_path: Path, monkeypatch) -> None:
        """The afm-config tmpfile carries the resolved absolute wrapper path."""
        config = _make_config(pipeline_agent="codex")
        monkeypatch.setattr(_rpc_mod, "_check_docker", lambda: True)
        monkeypatch.setattr(_rpc_mod, "docker_update", lambda *_: None)
        monkeypatch.setattr(_rpc_mod, "_allocate_port", lambda: 50321)
        monkeypatch.setattr(_rpc_mod, "_read_git_config", lambda: {})
        monkeypatch.chdir(tmp_path)

        captured: dict = {}
        _mock_proc, popen_side_effect = _capture_afm_config_popen(captured)
        with (
            mock.patch.object(subprocess, "Popen", side_effect=popen_side_effect),
            mock.patch.object(subprocess, "run"),
        ):
            result = rpc("deploy", config, ())

        assert result == 0
        assert captured["afm_content"] == (
            "client.command: /home/goga/bin/codex-as-claude.sh\n"
            "theme: goga\n"
            "open_browser: false\n"
            "proxy:\n"
            "  enabled: false\n"
            "prompts_dir: /home/goga/pipeline/prompts\n"
        )
        # the resolved wrapper path tmpfile is bind-mounted read-only, and the
        # mount arg + "-v" flag are present in the assembled docker command.
        cmd = captured["popen_cmds"][0]
        assert "-v" in cmd
        mount_arg = f"{captured['afm_host']}{_AFM_MOUNT_SUFFIX}"
        assert mount_arg in cmd

    @pytest.mark.parametrize("agent", ["claude", "codex", "opencode"])
    def test_afm_config_client_command_is_resolved_path(self, tmp_path: Path, monkeypatch, agent: str) -> None:
        """client.command is the resolved `/home/goga/bin/<agent>-as-claude.sh`.

        Parameterization over multiple agent names pins both the absence of a
        whitelist and the absence of branching by agent name.
        """
        config = _make_config(pipeline_agent=agent)
        monkeypatch.setattr(_rpc_mod, "_check_docker", lambda: True)
        monkeypatch.setattr(_rpc_mod, "docker_update", lambda *_: None)
        monkeypatch.setattr(_rpc_mod, "_allocate_port", lambda: 50321)
        monkeypatch.setattr(_rpc_mod, "_read_git_config", lambda: {})
        monkeypatch.chdir(tmp_path)

        captured: dict = {}
        _mock_proc, popen_side_effect = _capture_afm_config_popen(captured)
        with (
            mock.patch.object(subprocess, "Popen", side_effect=popen_side_effect),
            mock.patch.object(subprocess, "run"),
        ):
            rpc("deploy", config, ())

        assert captured["afm_content"] == (
            f"client.command: /home/goga/bin/{agent}-as-claude.sh\n"
            "theme: goga\n"
            "open_browser: false\n"
            "proxy:\n"
            "  enabled: false\n"
            "prompts_dir: /home/goga/pipeline/prompts\n"
        )


# --- Failure modes (click surface) ---


class TestPipelineFailureModes:
    def test_pipeline_raises_when_image_is_none(self, tmp_path: Path, monkeypatch) -> None:
        """A None image surfaces as a non-zero exit via a ClickException mentioning image."""
        _write_config(tmp_path, image=None)
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(_rpc_mod, "_check_docker", lambda: True)

        runner = CliRunner()
        # standalone_mode=False propagates the ClickException as result.exception
        # instead of Click converting it to SystemExit during CLI handling.
        result = runner.invoke(pipeline_cmd, ["deploy"], standalone_mode=False)

        assert result.exit_code != 0
        assert isinstance(result.exception, click.ClickException)
        assert "image" in str(result.exception).lower()

    def test_pipeline_raises_when_docker_missing(self, tmp_path: Path, monkeypatch) -> None:
        """Missing docker surfaces as a non-zero exit mentioning 'docker not found'."""
        _write_config(tmp_path)
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(_rpc_mod, "_check_docker", lambda: False)

        runner = CliRunner()
        result = runner.invoke(pipeline_cmd, ["deploy"], standalone_mode=False)

        assert result.exit_code != 0
        assert isinstance(result.exception, click.ClickException)
        assert "docker not found" in str(result.exception)


# --- Discovery mode ignores extra_env ---


class TestPipelineDiscoveryExtraEnv:
    def test_pipeline_discovery_ignores_extra_env(self, tmp_path: Path, monkeypatch) -> None:
        """Discovery mode (no name) never writes an env-file, ignoring `-e/--env`."""
        _write_config(tmp_path)
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(_rpc_mod, "_check_docker", lambda: True)
        monkeypatch.setattr(_rpc_mod, "docker_update", lambda *_: None)

        mock_proc = mock.Mock()
        mock_proc.wait.return_value = 0
        with (
            mock.patch.object(subprocess, "Popen", return_value=mock_proc) as mock_popen,
            mock.patch.object(subprocess, "run"),
        ):
            runner = CliRunner()
            result = runner.invoke(pipeline_cmd, ["-e", "FOO=bar"])

        assert result.exit_code == 0
        cmd = mock_popen.call_args[0][0]
        assert "--env-file" not in cmd


# --- codex auth mount ---


class TestCodexAuthMount:
    def test_run_pipeline_container_mounts_codex_auth_when_present(self, tmp_path: Path, monkeypatch) -> None:
        """A present ~/.codex/auth.json is bind-mounted read-only into the container."""
        config = _make_config(pipeline_agent="codex")
        # Credential detection is now agent-agnostic via resolve_credential_mounts(),
        # which resolves `~` via expanduser() (reading $HOME) rather than
        # Path.home(). Redirect $HOME so ~/.codex/auth.json resolves to tmp_path;
        # this also makes Path.home() (used by resolve_pipeline_runtime_dir) resolve
        # there, isolating the persistent runtime dir under tmp_path.
        monkeypatch.setenv("HOME", str(tmp_path))
        (tmp_path / ".codex").mkdir(parents=True)
        (tmp_path / ".codex" / "auth.json").write_text("{}")
        monkeypatch.setattr(_rpc_mod, "_check_docker", lambda: True)
        monkeypatch.setattr(_rpc_mod, "docker_update", lambda *_: None)
        monkeypatch.setattr(_rpc_mod, "_allocate_port", lambda: 50321)
        monkeypatch.setattr(_rpc_mod, "_read_git_config", lambda: {})
        monkeypatch.chdir(tmp_path)

        mock_proc = mock.Mock()
        mock_proc.wait.return_value = 0
        with (
            mock.patch.object(subprocess, "Popen", return_value=mock_proc) as mock_popen,
            mock.patch.object(subprocess, "run"),
        ):
            result = rpc("deploy", config, ())

        assert result == 0
        cmd = mock_popen.call_args[0][0]
        expected_mount = f"{tmp_path}/.codex/auth.json{_CODEX_AUTH_MOUNT_SUFFIX}"
        assert expected_mount in cmd


# --- SIGINT cleanup ---


class TestRunModeSigintCleanup:
    def test_run_pipeline_container_sigint_exits_130_and_cleans_tempfiles(self, tmp_path: Path, monkeypatch) -> None:
        """SIGINT during run unwinds to SystemExit(130), unlinks temp files, kills the container."""
        config = _make_config()
        monkeypatch.setattr(_rpc_mod, "_check_docker", lambda: True)
        monkeypatch.setattr(_rpc_mod, "_allocate_port", lambda: 50321)
        monkeypatch.setattr(_rpc_mod, "_read_git_config", lambda: {})
        monkeypatch.chdir(tmp_path)

        created_paths: list[Path] = []
        real_afm = _rpc_mod._write_afm_config_tmpfile
        real_env = _rpc_mod._write_env_file

        def track_afm(wrapper_path: str) -> Path:
            path = real_afm(wrapper_path)
            created_paths.append(path)
            return path

        def track_env(env: dict[str, str], extra_env: tuple[str, ...] = ()) -> Path:
            path = real_env(env, extra_env)
            created_paths.append(path)
            return path

        monkeypatch.setattr(_rpc_mod, "_write_afm_config_tmpfile", track_afm)
        monkeypatch.setattr(_rpc_mod, "_write_env_file", track_env)

        captured_handlers: dict[int, object] = {}

        def fake_signal(sig: int, handler: object) -> object:
            captured_handlers[sig] = handler
            return signal.SIG_DFL

        def fake_wait() -> int:
            # invoke the installed SIGINT handler inline, as a real signal would
            handler = captured_handlers[signal.SIGINT]
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
            rpc("deploy", config, ())

        assert exc.value.code == 130
        # both temp files were created and then unlinked by the finally cleanup
        assert len(created_paths) == 2
        assert all(not p.exists() for p in created_paths)
        # docker kill was invoked during teardown
        kill_calls = [c for c in mock_run.call_args_list if c.args and c.args[0][:2] == ["docker", "kill"]]
        assert kill_calls
