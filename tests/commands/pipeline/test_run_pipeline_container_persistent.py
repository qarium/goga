"""Contract, logic, and edge tests for the extended ``run_pipeline_container``.

These pin the persistent-afm-state, proxy, hosts, clean, and update behavior
declared in ``goga/commands/pipeline/CODEMANIFEST`` for the entity
``run_pipeline_container(name, config, extra_env, proxy, hosts, clean, update)
-> exit_code``.

Coverage focus (Task 10):

- New signature accepted (``proxy``, ``hosts``, ``clean``, ``update``).
- Discovery mode (``name=None``) ignores ``extra_env``/``proxy``/``clean`` —
  no env-file, no afm mount, no AFM_DIR/HTTP_PROXY anywhere.
- Run mode writes an env-file carrying ``AFM_DIR=/home/goga/pipeline``.
- The persistent afm state host directory is bind-mounted read-write at
  ``/home/goga/pipeline`` and SURVIVES the ``finally`` cleanup — including the
  signal-exit path (``SystemExit(130)``).
- ``--clean`` wipes the persistent directory BEFORE launch.
- ``hosts`` becomes ``--add-host`` flags in both modes.
- ``update`` gates the image pull in both modes.
- Credential mounts come from ``resolve_credential_mounts()`` (agent-agnostic),
  replacing the previous hardcoded ``~/.codex/auth.json`` mount.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest import mock

import click
import pytest
from goga.commands.pipeline.run_pipeline_container import (
    resolve_pipeline_runtime_dir,
    run_pipeline_container,
)
from goga.config import BuildConfig, PipelineConfig, ProjectConfig, TaskExecutorConfig

# goga.commands.pipeline.run_pipeline_container is the real submodule; resolve
# it via sys.modules so string-based mock.patch paths walk the actual module
# (the package __init__ binds the function name as an alias).
_rpc_mod = sys.modules["goga.commands.pipeline.run_pipeline_container"]


def _make_config(
    *,
    image: str | None = "qarium/goga:latest",
    pipeline_agent: str = "claude",
    pipeline_env: dict[str, str] | None = None,
) -> ProjectConfig:
    """Build a minimal ProjectConfig satisfying the schema."""
    return ProjectConfig(
        lang="python",
        image=image,
        dockerfile=None,
        build=BuildConfig(task_executor=TaskExecutorConfig(agent="claude")),
        pipeline=PipelineConfig(agent=pipeline_agent, env=pipeline_env or {}),
    )


def _stub_runtime(monkeypatch, tmp_path: Path, *, branch: str = "main") -> Path:
    """Redirect home/cwd/git-branch so resolve_pipeline_runtime_dir is deterministic.

    Returns the home tmp dir; the project lives at ``<home>/proj``.
    """
    home = tmp_path / "home"
    proj = home / "proj"
    proj.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(Path, "home", lambda: home)
    monkeypatch.setattr(Path, "cwd", lambda: proj)
    monkeypatch.setattr("goga.runtime.paths.resolve_git_branch", lambda: branch)
    # Credential-mount resolution reads $HOME via expanduser(), not Path.home(),
    # so monkeypatching Path.home does not isolate it from the host's real
    # credential files. Patch it at the module level for deterministic isolation
    # in tests that are not specifically about credential mounts.
    monkeypatch.setattr(_rpc_mod, "resolve_credential_mounts", lambda: [])
    return home


# --- Contract tests ---


class TestRunPipelineContainerContract:
    def test_signature_includes_new_parameters(self) -> None:
        """The signature exposes proxy/hosts/clean/update/workflow/no_workflow after extra_env."""
        import inspect

        params = list(inspect.signature(run_pipeline_container).parameters)
        assert params[:4] == ["name", "config", "extra_env", "proxy"]
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
        ]

    def test_discovery_mode_does_not_write_env_file(self, tmp_path: Path, monkeypatch) -> None:
        """Discovery mode never writes an env-file (no AFM_DIR, no afm mount)."""
        config = _make_config()
        monkeypatch.setattr(_rpc_mod, "_check_docker", lambda: True)
        monkeypatch.chdir(tmp_path)

        mock_proc = mock.Mock()
        mock_proc.wait.return_value = 0
        with (
            mock.patch.object(_rpc_mod, "_write_env_file") as mock_env,
            mock.patch.object(subprocess, "Popen", return_value=mock_proc) as mock_popen,
            mock.patch.object(subprocess, "run"),
        ):
            run_pipeline_container(None, config)

        mock_env.assert_not_called()
        cmd = mock_popen.call_args[0][0]
        assert "--env-file" not in cmd
        assert not any(arg.endswith(":/home/goga/.afm/config.yaml:ro") for arg in cmd)

    def test_run_mode_writes_env_file_with_afm_dir(self, tmp_path: Path, monkeypatch) -> None:
        """Run mode writes an env-file carrying AFM_DIR=/home/goga/pipeline."""
        config = _make_config()
        _stub_runtime(monkeypatch, tmp_path)
        monkeypatch.setattr(_rpc_mod, "_check_docker", lambda: True)
        monkeypatch.setattr(_rpc_mod, "_allocate_port", lambda: 50321)
        monkeypatch.setattr(_rpc_mod, "_read_git_config", lambda: {})

        captured_env: dict[str, str] = {}
        real_write = _rpc_mod._write_env_file

        def capture(env: dict[str, str], extra_env: tuple[str, ...] = ()) -> Path:
            captured_env.update(env)
            return real_write(env, extra_env)

        monkeypatch.setattr(_rpc_mod, "_write_env_file", capture)

        mock_proc = mock.Mock()
        mock_proc.wait.return_value = 0
        with (
            mock.patch.object(subprocess, "Popen", return_value=mock_proc),
            mock.patch.object(subprocess, "run"),
        ):
            run_pipeline_container("deploy", config)

        assert captured_env["AFM_DIR"] == "/home/goga/pipeline"


# --- Logic tests (positive): persistent afm state dir ---


class TestPersistentDir:
    def test_persistent_dir_mounted_and_survives(self, tmp_path: Path, monkeypatch) -> None:
        """Run mode mounts the persistent dir rw at /home/goga/pipeline and leaves it on disk."""
        config = _make_config()
        _stub_runtime(monkeypatch, tmp_path)
        monkeypatch.setattr(_rpc_mod, "_check_docker", lambda: True)
        monkeypatch.setattr(_rpc_mod, "_allocate_port", lambda: 50321)
        monkeypatch.setattr(_rpc_mod, "_read_git_config", lambda: {})

        runtime_dir = resolve_pipeline_runtime_dir("deploy")
        assert not runtime_dir.exists()

        mock_proc = mock.Mock()
        mock_proc.wait.return_value = 0
        with (
            mock.patch.object(subprocess, "Popen", return_value=mock_proc) as mock_popen,
            mock.patch.object(subprocess, "run"),
        ):
            run_pipeline_container("deploy", config)

        cmd = mock_popen.call_args[0][0]
        # read-write mount at the in-container persistent state path (no :ro)
        assert "-v" in cmd
        assert f"{runtime_dir}:/home/goga/pipeline" in cmd
        assert not any(arg == f"{runtime_dir}:/home/goga/pipeline:ro" for arg in cmd)
        # the directory survives the finally cleanup
        assert runtime_dir.exists()

    def test_persistent_dir_survives_signal_exit(self, tmp_path: Path, monkeypatch) -> None:
        """The persistent dir survives even the signal-exit (SystemExit) path."""
        config = _make_config()
        _stub_runtime(monkeypatch, tmp_path)
        monkeypatch.setattr(_rpc_mod, "_check_docker", lambda: True)
        monkeypatch.setattr(_rpc_mod, "_allocate_port", lambda: 50321)
        monkeypatch.setattr(_rpc_mod, "_read_git_config", lambda: {})

        runtime_dir = resolve_pipeline_runtime_dir("deploy")

        mock_proc = mock.Mock()
        mock_proc.wait.side_effect = SystemExit(130)
        with (
            mock.patch.object(_rpc_mod.signal, "signal"),
            mock.patch.object(subprocess, "Popen", return_value=mock_proc),
            mock.patch.object(subprocess, "run"),
            pytest.raises(SystemExit) as exc_info,
        ):
            run_pipeline_container("deploy", config)

        assert exc_info.value.code == 130
        # created before launch, never deleted in finally — survives the signal path
        assert runtime_dir.exists()


# --- Logic tests (negative): failure modes ---


class TestPersistentFailureModes:
    def test_docker_missing_raises_clickexception(self, monkeypatch) -> None:
        """Missing docker raises a ClickException mentioning 'docker not found in PATH'."""
        config = _make_config()
        monkeypatch.setattr(_rpc_mod, "_check_docker", lambda: False)

        with pytest.raises(click.ClickException, match="docker not found in PATH"):
            run_pipeline_container("deploy", config)


# --- Logic tests (edge): discovery ignores proxy/clean/extra_env; clean wipes ---


class TestPersistentEdge:
    def test_discovery_ignores_proxy_clean_and_extra_env(self, tmp_path: Path, monkeypatch) -> None:
        """Discovery ignores proxy/clean/extra_env: no env-file, no afm mount, no AFM_DIR/HTTP_PROXY."""
        config = _make_config()
        monkeypatch.setattr(_rpc_mod, "_check_docker", lambda: True)
        monkeypatch.chdir(tmp_path)

        mock_proc = mock.Mock()
        mock_proc.wait.return_value = 0
        with (
            mock.patch.object(_rpc_mod, "_write_env_file") as mock_env,
            mock.patch.object(subprocess, "Popen", return_value=mock_proc) as mock_popen,
            mock.patch.object(subprocess, "run"),
        ):
            run_pipeline_container(
                None,
                config,
                ("TOKEN=sk-xxx",),
                "http://corp:3128",
                {},
                True,  # clean=True — must be ignored in discovery
            )

        mock_env.assert_not_called()
        cmd = mock_popen.call_args[0][0]
        assert "--env-file" not in cmd
        assert "-p" not in cmd
        assert not any(arg.endswith(":/home/goga/.afm/config.yaml:ro") for arg in cmd)

    def test_clean_wipes_before_launch(self, tmp_path: Path, monkeypatch) -> None:
        """--clean wipes the persistent dir before launch (stale file absent afterward)."""
        config = _make_config()
        _stub_runtime(monkeypatch, tmp_path)
        monkeypatch.setattr(_rpc_mod, "_check_docker", lambda: True)
        monkeypatch.setattr(_rpc_mod, "_allocate_port", lambda: 50321)
        monkeypatch.setattr(_rpc_mod, "_read_git_config", lambda: {})

        runtime_dir = resolve_pipeline_runtime_dir("deploy")
        runtime_dir.mkdir(parents=True, exist_ok=True)
        stale = runtime_dir / "stale-run-state.json"
        stale.write_text("{}")
        assert stale.exists()

        mock_proc = mock.Mock()
        mock_proc.wait.return_value = 0
        with (
            mock.patch.object(subprocess, "Popen", return_value=mock_proc),
            mock.patch.object(subprocess, "run"),
        ):
            run_pipeline_container("deploy", config, (), None, {}, True, False)

        # wiped before launch, recreated empty; the stale file is gone
        assert runtime_dir.exists()
        assert not stale.exists()
        assert not any(runtime_dir.iterdir())


# --- Logic tests: hosts --add-host flags in both modes ---


class TestHostsFlags:
    def test_run_mode_emits_add_host_flags(self, tmp_path: Path, monkeypatch) -> None:
        """Run mode turns each hosts entry into a --add-host flag."""
        config = _make_config()
        _stub_runtime(monkeypatch, tmp_path)
        monkeypatch.setattr(_rpc_mod, "_check_docker", lambda: True)
        monkeypatch.setattr(_rpc_mod, "_allocate_port", lambda: 50321)
        monkeypatch.setattr(_rpc_mod, "_read_git_config", lambda: {})

        mock_proc = mock.Mock()
        mock_proc.wait.return_value = 0
        with (
            mock.patch.object(subprocess, "Popen", return_value=mock_proc) as mock_popen,
            mock.patch.object(subprocess, "run"),
        ):
            run_pipeline_container("deploy", config, (), None, {"foo.local": "127.0.0.1"}, False, False)

        cmd = mock_popen.call_args[0][0]
        assert "--add-host" in cmd
        assert "foo.local:127.0.0.1" in cmd

    def test_discovery_mode_emits_add_host_flags(self, tmp_path: Path, monkeypatch) -> None:
        """Discovery mode also honours hosts (add-host flags)."""
        config = _make_config()
        monkeypatch.setattr(_rpc_mod, "_check_docker", lambda: True)
        monkeypatch.chdir(tmp_path)

        mock_proc = mock.Mock()
        mock_proc.wait.return_value = 0
        with (
            mock.patch.object(subprocess, "Popen", return_value=mock_proc) as mock_popen,
            mock.patch.object(subprocess, "run"),
        ):
            run_pipeline_container(None, config, (), None, {"foo.local": "127.0.0.1"}, False, False)

        cmd = mock_popen.call_args[0][0]
        assert "--add-host" in cmd
        assert "foo.local:127.0.0.1" in cmd


# --- Logic tests: update / conditional image refresh (build vs pull) ---


class TestConditionalUpdate:
    """--update delegates to docker_update(image, dockerfile) in both modes.

    With ``config.dockerfile`` None (the default here) docker_update takes the
    PULL branch; a set Dockerfile takes the BUILD branch. These tests assert the
    delegation call shape, not the pull/build internals (those live in the
    ``goga/docker`` cell tests).
    """

    def test_update_false_skips_docker_update_run_mode(self, tmp_path: Path, monkeypatch) -> None:
        """Run mode with update=False does not refresh the image."""
        config = _make_config()
        _stub_runtime(monkeypatch, tmp_path)
        monkeypatch.setattr(_rpc_mod, "_check_docker", lambda: True)
        monkeypatch.setattr(_rpc_mod, "_allocate_port", lambda: 50321)
        monkeypatch.setattr(_rpc_mod, "_read_git_config", lambda: {})

        mock_proc = mock.Mock()
        mock_proc.wait.return_value = 0
        with (
            mock.patch.object(_rpc_mod, "docker_update") as mock_update,
            mock.patch.object(subprocess, "Popen", return_value=mock_proc),
            mock.patch.object(subprocess, "run"),
        ):
            run_pipeline_container("deploy", config, (), None, {}, False, False)

        mock_update.assert_not_called()

    def test_update_true_delegates_docker_update_run_mode(self, tmp_path: Path, monkeypatch) -> None:
        """Run mode with update=True delegates to docker_update before launch."""
        config = _make_config()
        _stub_runtime(monkeypatch, tmp_path)
        monkeypatch.setattr(_rpc_mod, "_check_docker", lambda: True)
        monkeypatch.setattr(_rpc_mod, "_allocate_port", lambda: 50321)
        monkeypatch.setattr(_rpc_mod, "_read_git_config", lambda: {})

        mock_proc = mock.Mock()
        mock_proc.wait.return_value = 0
        with (
            mock.patch.object(_rpc_mod, "docker_update") as mock_update,
            mock.patch.object(subprocess, "Popen", return_value=mock_proc),
            mock.patch.object(subprocess, "run"),
        ):
            run_pipeline_container("deploy", config, (), None, {}, False, True)

        # dockerfile is None → docker_update(image, None) takes the pull branch.
        mock_update.assert_called_once_with(config.image, config.dockerfile)

    def test_update_false_skips_docker_update_discovery(self, tmp_path: Path, monkeypatch) -> None:
        """Discovery mode with update=False does not refresh the image."""
        config = _make_config()
        monkeypatch.setattr(_rpc_mod, "_check_docker", lambda: True)
        monkeypatch.chdir(tmp_path)

        mock_proc = mock.Mock()
        mock_proc.wait.return_value = 0
        with (
            mock.patch.object(_rpc_mod, "docker_update") as mock_update,
            mock.patch.object(subprocess, "Popen", return_value=mock_proc),
            mock.patch.object(subprocess, "run"),
        ):
            run_pipeline_container(None, config, (), None, {}, False, False)

        mock_update.assert_not_called()

    def test_update_true_delegates_docker_update_discovery(self, tmp_path: Path, monkeypatch) -> None:
        """Discovery mode with update=True delegates to docker_update before launch."""
        config = _make_config()
        monkeypatch.setattr(_rpc_mod, "_check_docker", lambda: True)
        monkeypatch.chdir(tmp_path)

        mock_proc = mock.Mock()
        mock_proc.wait.return_value = 0
        with (
            mock.patch.object(_rpc_mod, "docker_update") as mock_update,
            mock.patch.object(subprocess, "Popen", return_value=mock_proc),
            mock.patch.object(subprocess, "run"),
        ):
            run_pipeline_container(None, config, (), None, {}, False, True)

        mock_update.assert_called_once_with(config.image, config.dockerfile)


# --- Logic tests: proxy env vars (run mode) ---


class TestProxyEnv:
    def test_run_mode_proxy_populates_env_file(self, tmp_path: Path, monkeypatch) -> None:
        """A non-None proxy writes HTTP_PROXY/HTTPS_PROXY/NO_PROXY into the env-file."""
        config = _make_config()
        _stub_runtime(monkeypatch, tmp_path)
        monkeypatch.setattr(_rpc_mod, "_check_docker", lambda: True)
        monkeypatch.setattr(_rpc_mod, "_allocate_port", lambda: 50321)
        monkeypatch.setattr(_rpc_mod, "_read_git_config", lambda: {})

        captured_env: dict[str, str] = {}
        real_write = _rpc_mod._write_env_file

        def capture(env: dict[str, str], extra_env: tuple[str, ...] = ()) -> Path:
            captured_env.update(env)
            return real_write(env, extra_env)

        monkeypatch.setattr(_rpc_mod, "_write_env_file", capture)

        mock_proc = mock.Mock()
        mock_proc.wait.return_value = 0
        with (
            mock.patch.object(subprocess, "Popen", return_value=mock_proc),
            mock.patch.object(subprocess, "run"),
        ):
            run_pipeline_container("deploy", config, (), "http://corp:3128", {}, False, False)

        assert captured_env["HTTP_PROXY"] == "http://corp:3128"
        assert captured_env["HTTPS_PROXY"] == "http://corp:3128"
        assert captured_env["NO_PROXY"] == "localhost,127.0.0.1"
        assert captured_env["AFM_DIR"] == "/home/goga/pipeline"

    def test_run_mode_no_proxy_omits_proxy_vars(self, tmp_path: Path, monkeypatch) -> None:
        """A None proxy leaves HTTP_PROXY/HTTPS_PROXY/NO_PROXY unset."""
        config = _make_config()
        _stub_runtime(monkeypatch, tmp_path)
        monkeypatch.setattr(_rpc_mod, "_check_docker", lambda: True)
        monkeypatch.setattr(_rpc_mod, "_allocate_port", lambda: 50321)
        monkeypatch.setattr(_rpc_mod, "_read_git_config", lambda: {})

        captured_env: dict[str, str] = {}
        real_write = _rpc_mod._write_env_file

        def capture(env: dict[str, str], extra_env: tuple[str, ...] = ()) -> Path:
            captured_env.update(env)
            return real_write(env, extra_env)

        monkeypatch.setattr(_rpc_mod, "_write_env_file", capture)

        mock_proc = mock.Mock()
        mock_proc.wait.return_value = 0
        with (
            mock.patch.object(subprocess, "Popen", return_value=mock_proc),
            mock.patch.object(subprocess, "run"),
        ):
            run_pipeline_container("deploy", config, (), None, {}, False, False)

        assert "HTTP_PROXY" not in captured_env
        assert "HTTPS_PROXY" not in captured_env
        assert "NO_PROXY" not in captured_env


# --- Logic tests: credential mounts via resolve_credential_mounts loop ---


class TestCredentialMountLoop:
    def test_run_mode_uses_resolve_credential_mounts_loop(self, tmp_path: Path, monkeypatch) -> None:
        """Run mode bind-mounts every tuple from resolve_credential_mounts() read-only."""
        config = _make_config()
        _stub_runtime(monkeypatch, tmp_path)
        monkeypatch.setattr(_rpc_mod, "_check_docker", lambda: True)
        monkeypatch.setattr(_rpc_mod, "_allocate_port", lambda: 50321)
        monkeypatch.setattr(_rpc_mod, "_read_git_config", lambda: {})
        # agent-agnostic loop: any tuple returned becomes a read-only mount
        monkeypatch.setattr(
            _rpc_mod,
            "resolve_credential_mounts",
            lambda: [("/host/claude/.credentials.json", "/home/goga/.claude/.credentials.json")],
        )

        mock_proc = mock.Mock()
        mock_proc.wait.return_value = 0
        with (
            mock.patch.object(subprocess, "Popen", return_value=mock_proc) as mock_popen,
            mock.patch.object(subprocess, "run"),
        ):
            run_pipeline_container("deploy", config)

        cmd = mock_popen.call_args[0][0]
        assert "-v" in cmd
        assert "/host/claude/.credentials.json:/home/goga/.claude/.credentials.json:ro" in cmd
        # the hardcoded codex-only mount is gone — detection is agent-agnostic
        assert not any(arg.endswith(":/home/goga/.codex/auth.json:ro") and "auth.json" in arg for arg in cmd)


# --- Task 6: goga.runtime delegation end-to-end through the run-mode path ---


class TestGogaRuntimeDelegation:
    """End-to-end verification that the renamed facades delegate to ``goga.runtime``.

    Unlike ``test_run_helpers.py`` (which exercises the facades in isolation via
    ``mock.patch`` of ``resolve_runtime_dir``), these tests drive the full
    ``run_pipeline_container`` run-mode path with ``Path.home()``/``Path.cwd()``/
    ``resolve_git_branch`` redirected, so the real ``resolve_runtime_dir`` →
    ``normalize_project_path`` → ``resolve_git_branch`` composition produces the
    documented host path layout end-to-end.
    """

    def test_resolve_pipeline_runtime_dir_composes_documented_path(self, tmp_path: Path, monkeypatch) -> None:
        """resolve_pipeline_runtime_dir('deploy') → ~/.goga/runtime/pipelines/<normalized>/<branch>/deploy."""
        from goga.runtime.paths import normalize_project_path

        # Redirect home/cwd so resolve_runtime_dir is deterministic; drive the
        # REAL resolve_git_branch (feature/x → feature-x slugification) end-to-end
        # by mocking subprocess.run instead of stubbing resolve_git_branch itself.
        home = tmp_path / "home"
        proj = home / "proj"
        proj.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(Path, "home", lambda: home)
        monkeypatch.setattr(Path, "cwd", lambda: proj)
        completed = subprocess.CompletedProcess(
            args=["git", "branch", "--show-current"],
            returncode=0,
            stdout="feature/x\n",
            stderr="",
        )

        with mock.patch("goga.runtime.paths.subprocess.run", return_value=completed):
            actual = resolve_pipeline_runtime_dir("deploy")

        expected = (
            home
            / ".goga"
            / "runtime"
            / "pipelines"
            / normalize_project_path(proj)
            / "feature-x"  # slugified by resolve_git_branch: forward slash → hyphen
            / "deploy"
        )

        assert actual == expected
        assert actual.is_absolute()
        # the facade is pure — it must not create the directory tree
        assert not actual.parent.exists()

    def test_runtime_dir_created_before_launch_mounted_rw_survives_finally(self, tmp_path: Path, monkeypatch) -> None:
        """The runtime dir is mkdir'd before launch, mounted rw at /home/goga/pipeline, and survives finally."""
        config = _make_config()
        _stub_runtime(monkeypatch, tmp_path)
        monkeypatch.setattr(_rpc_mod, "_check_docker", lambda: True)
        monkeypatch.setattr(_rpc_mod, "_allocate_port", lambda: 50321)
        monkeypatch.setattr(_rpc_mod, "_read_git_config", lambda: {})

        runtime_dir = resolve_pipeline_runtime_dir("deploy")
        assert not runtime_dir.exists()  # nothing created yet

        mock_proc = mock.Mock()
        mock_proc.wait.return_value = 0
        with (
            mock.patch.object(subprocess, "Popen", return_value=mock_proc) as mock_popen,
            mock.patch.object(subprocess, "run"),
        ):
            run_pipeline_container("deploy", config)

        # created before launch (mkdir -p, idempotent) and survives the finally cleanup
        assert runtime_dir.exists()
        cmd = mock_popen.call_args[0][0]
        assert f"{runtime_dir}:/home/goga/pipeline" in cmd
        # read-write: the persistent-state mount carries no :ro suffix
        assert not any(arg == f"{runtime_dir}:/home/goga/pipeline:ro" for arg in cmd)

    def test_clean_wipes_runtime_dir_but_mount_remains(self, tmp_path: Path, monkeypatch) -> None:
        """--clean wipes old-state.json before launch; the mount flag is still present."""
        config = _make_config()
        _stub_runtime(monkeypatch, tmp_path)
        monkeypatch.setattr(_rpc_mod, "_check_docker", lambda: True)
        monkeypatch.setattr(_rpc_mod, "_allocate_port", lambda: 50321)
        monkeypatch.setattr(_rpc_mod, "_read_git_config", lambda: {})

        runtime_dir = resolve_pipeline_runtime_dir("deploy")
        runtime_dir.mkdir(parents=True, exist_ok=True)
        stale = runtime_dir / "old-state.json"
        stale.write_text("{}")
        assert stale.exists()

        mock_proc = mock.Mock()
        mock_proc.wait.return_value = 0
        with (
            mock.patch.object(subprocess, "Popen", return_value=mock_proc) as mock_popen,
            mock.patch.object(subprocess, "run"),
        ):
            run_pipeline_container("deploy", config, (), None, {}, True, False)

        # wiped before launch, recreated empty
        assert runtime_dir.exists()
        assert not stale.exists()
        assert not any(runtime_dir.iterdir())
        # the mount is still wired even after the wipe
        cmd = mock_popen.call_args[0][0]
        assert f"{runtime_dir}:/home/goga/pipeline" in cmd

    def test_default_perserve_preserves_progress_json(self, tmp_path: Path, monkeypatch) -> None:
        """clean=False preserves pre-existing progress.json across the run."""
        config = _make_config()
        _stub_runtime(monkeypatch, tmp_path)
        monkeypatch.setattr(_rpc_mod, "_check_docker", lambda: True)
        monkeypatch.setattr(_rpc_mod, "_allocate_port", lambda: 50321)
        monkeypatch.setattr(_rpc_mod, "_read_git_config", lambda: {})

        runtime_dir = resolve_pipeline_runtime_dir("deploy")
        runtime_dir.mkdir(parents=True, exist_ok=True)
        progress = runtime_dir / "progress.json"
        progress.write_text('{"step": 3}')

        mock_proc = mock.Mock()
        mock_proc.wait.return_value = 0
        with (
            mock.patch.object(subprocess, "Popen", return_value=mock_proc),
            mock.patch.object(subprocess, "run"),
        ):
            run_pipeline_container("deploy", config, (), None, {}, False, False)

        # default-persist: the pre-existing state file is untouched
        assert progress.exists()
        assert progress.read_text() == '{"step": 3}'

    def test_host_path_isolation_no_host_path_leaks_into_env_or_target(self, tmp_path: Path, monkeypatch) -> None:
        """The container-side target is /home/goga/pipeline; the host path never leaks into the env-file."""
        config = _make_config()
        _stub_runtime(monkeypatch, tmp_path)
        monkeypatch.setattr(_rpc_mod, "_check_docker", lambda: True)
        monkeypatch.setattr(_rpc_mod, "_allocate_port", lambda: 50321)
        monkeypatch.setattr(_rpc_mod, "_read_git_config", lambda: {})

        runtime_dir = resolve_pipeline_runtime_dir("deploy")
        host_marker = ".goga/runtime/pipelines"

        env_contents: list[str] = []
        real_write = _rpc_mod._write_env_file

        def capture(env: dict[str, str], extra_env: tuple[str, ...] = ()) -> Path:
            path = real_write(env, extra_env)
            env_contents.append(path.read_text())
            return path

        monkeypatch.setattr(_rpc_mod, "_write_env_file", capture)

        mock_proc = mock.Mock()
        mock_proc.wait.return_value = 0
        with (
            mock.patch.object(subprocess, "Popen", return_value=mock_proc) as mock_popen,
            mock.patch.object(subprocess, "run"),
        ):
            run_pipeline_container("deploy", config, (), None, {}, False, False)

        cmd = mock_popen.call_args[0][0]
        # the only container-side target is /home/goga/pipeline, sourced from the host runtime dir
        assert f"{runtime_dir}:/home/goga/pipeline" in cmd
        # the env-file carries AFM_DIR as the container-side path, never the host path
        env_text = "\n".join(env_contents)
        assert "AFM_DIR=/home/goga/pipeline\n" in env_text
        assert host_marker not in env_text
        # any docker arg mentioning the host runtime path is the bind-mount SOURCE
        # (host:/home/goga/pipeline), never a standalone leaked value
        for arg in cmd:
            if host_marker in arg:
                assert arg == f"{runtime_dir}:/home/goga/pipeline"
