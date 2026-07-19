"""End-to-end integration tests for the host-side launcher afm-config tmpfile.

Task 9 of the afm-custom-prompts plan: cross-boundary verification that
``run_pipeline_container`` (run mode) drives the REAL ``DockerRunner.run``
docker-runtime boundary, mounts a five-field afm-config tmpfile read-only at
the fixed in-container path ``/home/goga/.afm/config.yaml``, and that the
launcher's ``finally`` cleanup unlinks the secret tmpfile/env-file while the
persistent afm state host directory survives.

Unlike ``test_run_pipeline_container_afm_config.py`` (which pins the
``_write_afm_config_tmpfile`` writer and the five-field content in isolation),
these tests exercise the full run-mode path THROUGH ``DockerRunner.run`` — the
docker runtime boundary — capturing the assembled ``docker run`` argv from the
``subprocess.Popen`` call and reading the tmpfile that was actually mounted.
``DockerRunner.run`` is spied (``wraps=`` the real method) so the integration
boundary itself is asserted, while ``subprocess.Popen`` is mocked so no real
container launches.
"""

from __future__ import annotations

import importlib
import subprocess
from pathlib import Path
from unittest import mock

import yaml
from goga.commands.pipeline.run_pipeline_container import (
    run_pipeline_container as rpc,
)
from goga.config import BuildConfig, Config, PipelineConfig, TaskExecutorConfig
from goga.docker import DockerRunner

# Resolve the real submodule directly: the package __init__ re-exports the
# `run_pipeline_container` function, which shadows the submodule name in
# attribute access on Python 3.10. Patching the module by attribute affects the
# code under test.
_rpc_mod = importlib.import_module("goga.commands.pipeline.run_pipeline_container")

# The afm-config tmpfile is mounted read-only at this fixed in-container path.
_AFM_MOUNT_SUFFIX = ":/home/goga/.afm/config.yaml:ro"


def _make_config(
    *,
    image: str | None = "goga:test",
    pipeline_agent: str = "claude",
    pipeline_env: dict[str, str] | None = None,
) -> Config:
    """Build a minimal Config satisfying the schema (top-level image, pipeline block)."""
    return Config(
        lang="python",
        image=image,
        dockerfile=None,
        build=BuildConfig(task_executor=TaskExecutorConfig(agent="claude")),
        pipeline=PipelineConfig(agent=pipeline_agent, env=pipeline_env or {}),
    )


def _apply_run_mode_common_mocks(tmp_path: Path, monkeypatch) -> Path:
    """Patch the run-mode plumbing so the test stays under tmp_path and offline.

    Mirrors the convention in tests/commands/pipeline/: redirect HOME, stub the
    afm runtime dir under tmp_path (so the persistent afm-state directory never
    touches the real ~/.goga/), and pin the port/wrapper/git identity. Returns
    the patched persistent afm state host directory.
    """
    monkeypatch.setattr(_rpc_mod, "_check_docker", lambda: True)
    monkeypatch.setattr(_rpc_mod, "_allocate_port", lambda: 50321)
    monkeypatch.setattr(_rpc_mod, "_read_git_config", lambda: {})
    monkeypatch.setattr(
        _rpc_mod,
        "resolve_wrapper_path",
        lambda _agent: "/home/goga/bin/claude-as-claude.sh",
    )
    runtime_dir = tmp_path / "runtime"
    monkeypatch.setattr(_rpc_mod, "resolve_pipeline_runtime_dir", lambda _name: runtime_dir)
    # Credential-mount resolution reads $HOME via expanduser(); the autouse
    # _isolate_home fixture already redirects HOME under tmp_path, but pin it
    # explicitly so credential detection stays deterministic (no host mounts).
    monkeypatch.setattr(_rpc_mod, "resolve_credential_mounts", lambda: [])
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    return runtime_dir


# --- end-to-end run mode through the DockerRunner.run boundary ---


class TestIntegrationLauncherTmpfile:
    def test_run_mode_mounts_and_validates_five_field_tmpfile(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """Run mode mounts a five-field afm-config tmpfile read-only at the fixed path.

        End-to-end through the REAL ``DockerRunner.run`` docker-runtime boundary:
        ``subprocess.Popen`` is mocked so no container launches, but the runner
        still assembles the real ``docker run`` argv (captured from the Popen
        call). The afm-config tmpfile is unlinked by the launcher's ``finally``,
        so the writer is wrapped to snapshot its bytes before the unlink. The
        snapshot parses (via ``yaml.safe_load``) to five fields:
        ``client.command`` (the resolved wrapper path), ``theme: goga``,
        ``open_browser: false``, ``proxy`` as a nested map (``{"enabled": False}``
        — NOT a flat dotted-key), and ``prompts_dir: /home/goga/pipeline/prompts``.
        """
        config = _make_config(image="goga:test", pipeline_agent="claude", pipeline_env={})
        _apply_run_mode_common_mocks(tmp_path, monkeypatch)

        captured_afm = tmp_path / "captured-afm-config.yaml"
        real_afm = _rpc_mod._write_afm_config_tmpfile

        def capture_afm(wrapper_path: str) -> Path:
            path = real_afm(wrapper_path)
            captured_afm.write_bytes(path.read_bytes())
            return path

        monkeypatch.setattr(_rpc_mod, "_write_afm_config_tmpfile", capture_afm)

        mock_proc = mock.Mock()
        mock_proc.wait.return_value = 0
        # `side_effect=DockerRunner.run` instead of the original `wraps=`:
        # `autospec=True, wraps=Class.method` returns a fresh MagicMock on
        # Python 3.10 instead of the wraps result (autospec's spec-instance
        # machinery clobbers the return-value proxy that `wraps` relies on),
        # so `result == 0` fails with `MagicMock == 0`. `side_effect` both
        # invokes the real method (so the real `docker run` argv is assembled
        # through `subprocess.Popen`) AND propagates its return value across
        # 3.10–3.13. `autospec=True` stays — without it `patch.object` on a
        # class-level mock would not bind `self` and the real run would raise
        # `TypeError: missing positional argument 'args'`.
        with (
            mock.patch.object(
                DockerRunner,
                "run",
                autospec=True,
                side_effect=DockerRunner.run,
            ) as spy_run,
            mock.patch.object(subprocess, "Popen", return_value=mock_proc) as mock_popen,
            mock.patch.object(subprocess, "run"),
        ):
            result = rpc(
                name="deploy",
                config=config,
                extra_env=(),
                proxy=None,
                hosts={},
                clean=False,
                update=False,
            )

        assert result == 0
        # The launcher delegated to the docker-runtime boundary exactly once
        # (DockerRunner.run was the integration point under test).
        spy_run.assert_called_once()

        # The captured argv came from the Popen call and went through
        # DockerRunner.run (a real ``docker run`` argv).
        docker_argv = mock_popen.call_args[0][0]
        assert docker_argv[:2] == ["docker", "run"]

        # The mounted tmpfile source path is non-empty and targets the fixed
        # in-container path; StopIteration here means the mount is missing.
        config_mount = next(a for a in docker_argv if _AFM_MOUNT_SUFFIX in a)
        assert config_mount.split(":")[0]  # the tmpfile source path was non-empty

        parsed = yaml.safe_load(captured_afm.read_text())
        # exactly five top-level keys (proxy is nested under its own key)
        assert len(parsed) == 5
        assert parsed["client.command"] == "/home/goga/bin/claude-as-claude.sh"
        assert parsed["theme"] == "goga"
        assert parsed["open_browser"] is False
        # proxy is a nested map, not a flat dotted-key
        assert parsed["proxy"] == {"enabled": False}
        assert "proxy.enabled" not in parsed  # anti-regression
        assert parsed["prompts_dir"] == "/home/goga/pipeline/prompts"


# --- cleanup semantics: secret tmpfile unlinked, persistent dir survives ---


class TestIntegrationLauncherCleanup:
    def test_tmpfile_unlinked_but_persistent_dir_survives_finally(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """The launcher's finally unlinks the secret tmpfile/env-file but keeps the persistent dir.

        After ``run_pipeline_container`` returns, BOTH the afm-config tmpfile and
        the env-file must be gone (the launcher's ``finally`` block preserves the
        leak-prevention semantics), while the persistent afm state host directory
        (bind-mounted read-write at ``/home/goga/pipeline``) survives — it holds
        afm run state across runs and across the signal-exit path.
        """
        config = _make_config()
        runtime_dir = _apply_run_mode_common_mocks(tmp_path, monkeypatch)

        created_afm: list[Path] = []
        created_env: list[Path] = []
        real_afm = _rpc_mod._write_afm_config_tmpfile
        real_env = _rpc_mod._write_env_file

        def track_afm(wrapper_path: str) -> Path:
            path = real_afm(wrapper_path)
            created_afm.append(path)
            return path

        def track_env(env: dict[str, str], extra_env: tuple[str, ...] = ()) -> Path:
            path = real_env(env, extra_env)
            created_env.append(path)
            return path

        monkeypatch.setattr(_rpc_mod, "_write_afm_config_tmpfile", track_afm)
        monkeypatch.setattr(_rpc_mod, "_write_env_file", track_env)

        mock_proc = mock.Mock()
        mock_proc.wait.return_value = 0
        with (
            mock.patch.object(subprocess, "Popen", return_value=mock_proc),
            mock.patch.object(subprocess, "run"),
        ):
            result = rpc(
                name="deploy",
                config=config,
                extra_env=(),
                proxy=None,
                hosts={},
                clean=False,
                update=False,
            )

        assert result == 0
        # both secret files were created and then unlinked by the finally block
        assert created_afm
        assert created_env
        assert all(not p.exists() for p in created_afm)
        assert all(not p.exists() for p in created_env)
        # the persistent afm state host directory survives every exit path
        assert runtime_dir.exists()
