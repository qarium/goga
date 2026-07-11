"""Integration tests for ``goga/commands/build`` ralphex runtime isolation.

End-to-end cross-entity coverage for the runtime-isolation contract introduced
in the ralphex-runtime-isolation design (Task 4). These tests wire the real
``resolve_build_runtime_dir`` / ``clean_build_runtime_dir`` facades together
with the real ``goga.runtime.resolve_runtime_dir`` path composition and the
``build`` click command, exercising the full Algorithm steps 11 (resolve +
mkdir), 12 (conditional wipe) and 15 (nested bind-mount).

They complement (not duplicate) ``test_build.py``: where the unit/logic tests
isolate each facade, these tests assert the *cross-entity invariants* that only
hold when the pieces are wired together — chiefly that the path *resolved* is
the same path *wiped* is the same path *mounted*, that the host runtime path
never reaches the container via the env-file, and that a signal-driven exit
runs the finally cleanup (env-file unlink, ``docker kill``, signal-handler
restore) while leaving the runtime directory intact for the next run.
"""

from __future__ import annotations

import signal
import subprocess
from contextlib import ExitStack
from pathlib import Path
from unittest import mock

from click.testing import CliRunner
from goga.commands import build as build_cmd
from goga.commands.build.build import resolve_build_runtime_dir
from goga.config import BuildConfig, Config, PipelineConfig, TaskExecutorConfig

_build_mod = __import__("goga.commands.build.build", fromlist=["build"])


def _valid_config(*, image: str | None = "qarium/goga:latest") -> Config:
    """Return a minimal valid Config for the build flow."""
    return Config(
        lang="python",
        image=image,
        dockerfile=None,
        build=BuildConfig(task_executor=TaskExecutorConfig(agent="claude")),
        pipeline=PipelineConfig(agent="claude"),
    )


def _pin_runtime_under(tmp_path: Path, monkeypatch) -> None:
    """Redirect home/cwd/branch so the runtime dir lands under tmp_path.

    After this the real ``resolve_build_runtime_dir()`` yields a deterministic
    path under ``tmp_path/home/.goga/runtime/builds/...`` without touching the
    real host home directory or shelling out to git.
    """
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    monkeypatch.setattr("goga.runtime.paths.resolve_git_branch", lambda: "test-branch")


def _build_patches(
    *,
    popen_return: object | None = None,
    popen_side_effect=None,
    run_side_effect=None,
) -> tuple:
    """Return the common mock context managers for an end-to-end build run.

    Only the docker/config surfaces are mocked — the runtime-dir facades,
    ``goga.runtime`` path composition, and the real filesystem run unmodified so
    the cross-entity invariants are genuinely exercised.

    ``subprocess.run`` is always mocked because the finally-block ``docker
    kill`` calls ``subprocess.run`` internally, and ``subprocess.run`` opens its
    own ``Popen`` as a context manager — which would otherwise hit the patched
    (non-context-manager) ``Popen``. Tests that need to inspect the kill call
    pass ``run_side_effect``.
    """
    popen = mock.patch.object(
        subprocess,
        "Popen",
        return_value=popen_return,
        side_effect=popen_side_effect,
    )
    run = mock.patch.object(subprocess, "run", side_effect=run_side_effect)
    return (
        mock.patch.object(_build_mod, "_check_docker", return_value=True),
        mock.patch.object(_build_mod, "_read_git_config", return_value={}),
        mock.patch.object(_build_mod, "load_config", return_value=_valid_config()),
        mock.patch.object(_build_mod, "resolve_credential_mounts", return_value=[]),
        popen,
        run,
    )


class TestBuildRuntimeIsolationEndToEnd:
    """Cross-entity: resolve → wipe → mount → launch use one consistent path."""

    def test_clean_true_wipes_and_mounts_same_resolved_path(self, tmp_path: Path, monkeypatch) -> None:
        """``--clean`` wipes the resolved dir AND mounts that exact path read-write."""
        _pin_runtime_under(tmp_path, monkeypatch)

        # The real resolve yields the single path used by every downstream step.
        runtime_dir = resolve_build_runtime_dir()
        runtime_dir.mkdir(parents=True, exist_ok=True)
        (runtime_dir / "old-state.json").write_text("{}")

        captured: dict = {}

        def _fake_popen(cmd, *args, **kwargs):
            captured["cmd"] = list(cmd)
            proc = mock.Mock()
            proc.wait.return_value = 0
            return proc

        env_path = tmp_path / "env"
        with ExitStack() as stack:
            stack.enter_context(mock.patch.object(_build_mod, "_write_env_file", return_value=env_path))
            for cm in _build_patches(popen_side_effect=_fake_popen):
                stack.enter_context(cm)
            result = CliRunner().invoke(build_cmd, ["plan.md", "--clean"])

        assert result.exit_code == 0, result.output

        # Step 12: the resolved dir was wiped by the real clean_build_runtime_dir.
        assert not (runtime_dir / "old-state.json").exists()
        assert runtime_dir.exists()  # recreated empty (idempotent wipe+mkdir)

        # Step 15: that SAME resolved path is the nested bind-mount source.
        cmd = captured["cmd"]
        assert f"{runtime_dir}:/workspace/.ralphex" in cmd
        # Cross-entity identity: the path wiped is the path mounted.
        mount_sources = [arg for arg in cmd if arg.endswith(":/workspace/.ralphex")]
        assert mount_sources == [f"{runtime_dir}:/workspace/.ralphex"]

    def test_clean_false_preserves_runtime_dir_across_runs(self, tmp_path: Path, monkeypatch) -> None:
        """Without ``--clean`` the runtime dir survives, with its contents, and is still mounted."""
        _pin_runtime_under(tmp_path, monkeypatch)

        runtime_dir = resolve_build_runtime_dir()
        runtime_dir.mkdir(parents=True, exist_ok=True)
        (runtime_dir / "progress.json").write_text('{"step": 3}')

        captured: dict = {}

        def _fake_popen(cmd, *args, **kwargs):
            captured["cmd"] = list(cmd)
            proc = mock.Mock()
            proc.wait.return_value = 0
            return proc

        env_path = tmp_path / "env"
        with ExitStack() as stack:
            stack.enter_context(mock.patch.object(_build_mod, "_write_env_file", return_value=env_path))
            for cm in _build_patches(popen_side_effect=_fake_popen):
                stack.enter_context(cm)
            result = CliRunner().invoke(build_cmd, ["plan.md"])

        assert result.exit_code == 0, result.output

        # Default-persist: ralphex progress survives untouched for the next run.
        assert (runtime_dir / "progress.json").read_text() == '{"step": 3}'

        # The nested mount is still present even when not cleaning.
        cmd = captured["cmd"]
        assert f"{runtime_dir}:/workspace/.ralphex" in cmd

    def test_runtime_setup_failure_does_not_write_secret_env_file(self, tmp_path: Path, monkeypatch) -> None:
        """A runtime-dir setup failure must not leave the secret env file on disk.

        The env file carries git identity and ``task_executor`` secrets and is
        only unlinked by the finally block, so it must not be created before the
        runtime-dir setup — which can raise on a read-only home or a permission
        error. Regression guard for the prepare-runtime-before-env-file ordering.
        """
        _pin_runtime_under(tmp_path, monkeypatch)

        with ExitStack() as stack:
            stack.enter_context(mock.patch.object(_build_mod, "_check_docker", return_value=True))
            stack.enter_context(mock.patch.object(_build_mod, "_read_git_config", return_value={}))
            stack.enter_context(mock.patch.object(_build_mod, "load_config", return_value=_valid_config()))
            write_env = stack.enter_context(mock.patch.object(_build_mod, "_write_env_file"))
            stack.enter_context(
                mock.patch.object(_build_mod, "resolve_build_runtime_dir", side_effect=OSError("read-only home"))
            )
            result = CliRunner().invoke(build_cmd, ["plan.md"])

        assert result.exit_code != 0
        # The secret-bearing env file was never written because the runtime-dir
        # setup (which runs first) raised before _write_env_file was reached.
        write_env.assert_not_called()


class TestBuildHostPathIsolation:
    """The host runtime path never reaches the container; only /workspace/.ralphex does."""

    def test_host_runtime_path_absent_from_env_file_and_env_args(self, tmp_path: Path, monkeypatch) -> None:
        """Neither the env-file contents nor an explicit ``-e`` arg carry the host path."""
        _pin_runtime_under(tmp_path, monkeypatch)

        runtime_dir = resolve_build_runtime_dir()

        captured_cmd: dict = {}
        captured_env: dict = {}

        def _fake_popen(cmd, *args, **kwargs):
            captured_cmd["cmd"] = list(cmd)
            proc = mock.Mock()
            proc.wait.return_value = 0
            return proc

        def _fake_write_env(env, extra_env):
            captured_env["env"] = dict(env)
            captured_env["extra"] = tuple(extra_env)
            return tmp_path / "env"

        with ExitStack() as stack:
            stack.enter_context(mock.patch.object(_build_mod, "_write_env_file", side_effect=_fake_write_env))
            for cm in _build_patches(popen_side_effect=_fake_popen):
                stack.enter_context(cm)
            # Pass an explicit -e to prove the host path is never injected there either.
            result = CliRunner().invoke(build_cmd, ["plan.md", "-e", "EXTRA=keep-me"])

        assert result.exit_code == 0, result.output

        # The host runtime path must not appear in any env-file value, in the
        # raw extra-env strings, or in the broader runtime path-shape substring.
        for value in captured_env["env"].values():
            assert str(runtime_dir) not in value
            assert ".goga/runtime/builds" not in value
        for pair in captured_env["extra"]:
            assert str(runtime_dir) not in pair
            assert ".goga/runtime/builds" not in pair

        # The container sees only the /workspace/.ralphex mount target; the host
        # path appears solely as that mount's *source* (which is correct and
        # required), never as an env-file/--env payload.
        cmd = captured_cmd["cmd"]
        assert "/workspace/.ralphex" in " ".join(cmd)
        assert f"{runtime_dir}:/workspace/.ralphex" in cmd


class TestBuildSignalExitCleanup:
    """A signal-driven exit runs the finally cleanup but preserves the runtime dir."""

    def test_signal_exit_unlinks_env_kills_container_restores_handler_and_keeps_runtime_dir(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """SIGTERM during ``docker_proc.wait()`` triggers finally; runtime dir survives."""
        _pin_runtime_under(tmp_path, monkeypatch)

        runtime_dir = resolve_build_runtime_dir()
        runtime_dir.mkdir(parents=True, exist_ok=True)
        (runtime_dir / "progress.json").write_text('{"step": 7}')

        # A real env file so we can observe the finally-block unlink.
        env_path = tmp_path / "env"
        env_path.write_text("SECRET=sk-xxx\n")
        assert env_path.exists()

        # Simulate the SIGTERM handler firing mid-wait: the handler raises
        # SystemExit(128 + SIGTERM), which propagates into the finally block.
        mock_proc = mock.Mock()
        mock_proc.wait.side_effect = SystemExit(128 + signal.SIGTERM)

        run_calls: list = []

        def _fake_run(cmd, *args, **kwargs):
            run_calls.append(list(cmd))
            return mock.Mock(returncode=0)

        original_handler = signal.getsignal(signal.SIGTERM)
        with ExitStack() as stack:
            stack.enter_context(mock.patch.object(_build_mod, "_write_env_file", return_value=env_path))
            for cm in _build_patches(popen_return=mock_proc, run_side_effect=_fake_run):
                stack.enter_context(cm)
            result = CliRunner().invoke(build_cmd, ["plan.md"])

        # The SystemExit(128+SIGTERM) surfaces as the click exit code.
        assert result.exit_code == 128 + signal.SIGTERM

        # Finally: the env file carrying secrets was unlinked.
        assert not env_path.exists()

        # Finally: the container was killed.
        kill_cmds = [c for c in run_calls if c[:2] == ["docker", "kill"]]
        assert len(kill_cmds) == 1
        assert kills_target_build_container(kill_cmds[0])

        # Finally: the SIGTERM handler was restored to its pre-build value.
        assert signal.getsignal(signal.SIGTERM) is original_handler

        # The runtime dir is NOT deleted in finally — it survives across runs.
        assert runtime_dir.exists()
        assert (runtime_dir / "progress.json").read_text() == '{"step": 7}'


def kills_target_build_container(kill_cmd: list[str]) -> bool:
    """True if a ``docker kill`` command targets a ``goga-build-*`` container."""
    if len(kill_cmd) < 3:
        return False
    return kill_cmd[0] == "docker" and kill_cmd[1] == "kill" and kill_cmd[2].startswith("goga-build-")
