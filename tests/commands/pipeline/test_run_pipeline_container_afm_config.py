from __future__ import annotations

import importlib
import signal
import subprocess
from pathlib import Path
from unittest import mock

import pytest
import yaml
from goga.commands.pipeline.run_pipeline_container import (
    _write_afm_config_tmpfile,
)
from goga.commands.pipeline.run_pipeline_container import (
    run_pipeline_container as rpc,
)
from goga.config import BuildConfig, Config, PipelineConfig, TaskExecutorConfig

# Resolve the real submodule directly: the package __init__ re-exports the
# `run_pipeline_container` function, which shadows the submodule name in
# attribute access on Python 3.10. importlib.import_module returns the real
# module object (robust to the import statement above being reordered/removed),
# and patching it by attribute affects the code under test.
_rpc_mod = importlib.import_module("goga.commands.pipeline.run_pipeline_container")

# The afm-config tmpfile is mounted read-only at this fixed in-container path.
_AFM_MOUNT_SUFFIX = ":/home/goga/.afm/config.yaml:ro"


def _make_config(
    *,
    image: str | None = "goga:test",
    pipeline_agent: str = "claude",
    pipeline_env: dict[str, str] | None = None,
) -> Config:
    """Build a minimal Config satisfying the new schema (top-level image, pipeline block)."""
    return Config(
        lang="python",
        image=image,
        dockerfile=None,
        build=BuildConfig(task_executor=TaskExecutorConfig(agent="claude")),
        pipeline=PipelineConfig(agent=pipeline_agent, env=pipeline_env or {}),
    )


def _apply_run_mode_common_mocks(tmp_path: Path, monkeypatch) -> None:
    """Patch the run-mode plumbing so the test stays under tmp_path and offline.

    Mirrors the established convention in tests/commands/pipeline/: the plan
    references an autouse `_isolate_home` fixture that does not exist in this
    repo, so $HOME is redirected here instead. ``resolve_pipeline_runtime_dir``
    is patched to a tmp path so the persistent afm-state directory never touches
    the real ~/.goga/ and the git-branch resolution is bypassed.
    """
    monkeypatch.setattr(_rpc_mod, "_check_docker", lambda: True)
    monkeypatch.setattr(_rpc_mod, "_allocate_port", lambda: 50321)
    monkeypatch.setattr(_rpc_mod, "_read_git_config", lambda: {})
    monkeypatch.setattr(
        _rpc_mod,
        "resolve_wrapper_path",
        lambda _agent: "/home/goga/bin/claude-as-claude.sh",
    )
    monkeypatch.setattr(
        _rpc_mod,
        "resolve_pipeline_runtime_dir",
        lambda _name: tmp_path / "runtime",
    )
    # Credential detection (resolve_credential_mounts) resolves ~ via expanduser
    # (reads $HOME); redirect HOME so it finds nothing under tmp_path.
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)


def _wrap_tmp_writer(monkeypatch, capture_path: Path, real_writer, key: str = "afm") -> None:
    """Replace a tmpfile writer with one that preserves bytes past the unlink.

    The launcher's finally block unlinks the afm-config tmpfile and the env-file,
    so reading them after run_pipeline_container returns loses the content. This
    wrapper copies the written bytes to a path under tmp_path before returning
    the original Path, and records the original tmpfile mode for a 0600 check.
    """

    def capture(*args):
        path = real_writer(*args)
        capture_path.write_bytes(path.read_bytes())
        return path

    monkeypatch.setattr(_rpc_mod, key, capture)


# --- Contract tests (selected by `pytest -k contract`) ---


class TestAfmConfigContract:
    def test_write_afm_config_tmpfile_is_callable(self) -> None:
        """_write_afm_config_tmpfile is importable and callable from its module."""
        assert callable(_write_afm_config_tmpfile)


# --- four-field afm-config content ---


class TestAfmConfigFourFieldContent:
    def test_run_pipeline_container_writes_four_field_afm_config(self, tmp_path: Path, monkeypatch) -> None:
        """Run mode writes a four-field afm-config tmpfile at mode 0600.

        The overlay carries exactly four static launcher-side fields: the resolved
        absolute wrapper path as ``client.command`` (never a bare agent name),
        ``theme: goga``, ``open_browser: false``, and ``proxy.enabled: false``.
        The tmpfile is private (mode 0600) and mounted read-only at the fixed
        in-container path /home/goga/.afm/config.yaml.
        """
        config = _make_config(image="goga:test", pipeline_agent="claude", pipeline_env={})
        _apply_run_mode_common_mocks(tmp_path, monkeypatch)

        captured_afm = tmp_path / "captured-afm-config.yaml"
        captured_mode: dict[str, int] = {}
        real_afm = _rpc_mod._write_afm_config_tmpfile

        def capture_afm(wrapper_path: str) -> Path:
            path = real_afm(wrapper_path)
            captured_afm.write_bytes(path.read_bytes())
            captured_mode["mode"] = path.stat().st_mode & 0o777
            return path

        monkeypatch.setattr(_rpc_mod, "_write_afm_config_tmpfile", capture_afm)

        mock_proc = mock.Mock()
        mock_proc.wait.return_value = 0
        with (
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
        parsed = yaml.safe_load(captured_afm.read_text())
        assert parsed["client.command"] == "/home/goga/bin/claude-as-claude.sh"
        assert parsed["theme"] == "goga"
        assert parsed["open_browser"] is False
        assert parsed["proxy"]["enabled"] is False
        # exactly four top-level keys (proxy is nested under its own key)
        assert len(parsed) == 4
        # the original tmpfile was private; the captured copy preserves only bytes,
        # so the mode is captured from the real tmpfile before the finally unlink.
        assert captured_mode["mode"] == 0o600
        # the tmpfile is mounted read-only at the fixed in-container path
        cmd = mock_popen.call_args[0][0]
        assert any(arg.endswith(_AFM_MOUNT_SUFFIX) for arg in cmd)

    def test_run_pipeline_container_proxy_none_omits_proxy_env_rows(self, tmp_path: Path, monkeypatch) -> None:
        """proxy=None writes no HTTP_PROXY/HTTPS_PROXY rows; tmpfile keeps proxy.enabled false.

        The two proxy layers never collide: goga manages the outbound proxy via
        the container env-file (HTTP_PROXY/HTTPS_PROXY/NO_PROXY), while afm's own
        config-level proxy provider must stay off. With proxy=None, no env-file
        proxy rows are written, yet the afm-config tmpfile still carries
        ``proxy.enabled: false`` unconditionally.
        """
        config = _make_config(pipeline_agent="claude", pipeline_env={})
        _apply_run_mode_common_mocks(tmp_path, monkeypatch)

        captured_afm = tmp_path / "captured-afm-config.yaml"
        captured_env = tmp_path / "captured-env-file"
        _wrap_tmp_writer(monkeypatch, captured_afm, _rpc_mod._write_afm_config_tmpfile, "_write_afm_config_tmpfile")
        _wrap_tmp_writer(
            monkeypatch,
            captured_env,
            _rpc_mod._write_env_file,
            "_write_env_file",
        )

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
        env_content = captured_env.read_text()
        assert "HTTP_PROXY" not in env_content
        assert "HTTPS_PROXY" not in env_content
        afm_parsed = yaml.safe_load(captured_afm.read_text())
        assert afm_parsed["proxy"]["enabled"] is False


# --- tmpfile-write error propagation ---


class TestAfmConfigErrorPropagation:
    def test_run_pipeline_container_propagates_tmpfile_write_error(self, tmp_path: Path, monkeypatch) -> None:
        """A tmpfile-write OSError propagates with no docker launch and handlers restored.

        When _write_afm_config_tmpfile raises (disk error, etc.), the launcher
        must NOT invoke docker (Popen never called) and must restore the
        SIGTERM/SIGINT handlers it installed at run-mode entry — the finally
        cleanup unwinds cleanly even though no container was started.
        """
        config = _make_config()
        _apply_run_mode_common_mocks(tmp_path, monkeypatch)

        def raising_afm(_wrapper_path: str) -> Path:
            raise OSError("no space left on device")

        monkeypatch.setattr(_rpc_mod, "_write_afm_config_tmpfile", raising_afm)

        # Distinct "previous handler" sentinel per signum so the restore calls
        # can be verified to pass back exactly what the install calls returned.
        installed: dict[int, object] = {}

        def fake_signal(sig: int, handler: object) -> object:
            if sig not in installed:
                sentinel = object()
                installed[sig] = sentinel
                return sentinel
            return installed[sig]

        mock_proc = mock.Mock()
        mock_proc.wait.return_value = 0
        with (
            mock.patch.object(_rpc_mod.signal, "signal", side_effect=fake_signal) as mock_signal,
            mock.patch.object(subprocess, "Popen", return_value=mock_proc) as mock_popen,
            mock.patch.object(subprocess, "run") as mock_run,
            pytest.raises(OSError, match="no space left on device"),
        ):
            rpc(
                name="deploy",
                config=config,
                extra_env=(),
                proxy=None,
                hosts={},
                clean=False,
                update=False,
            )

        # No container was launched — Popen never reached.
        assert mock_popen.call_count == 0
        # No docker kill/other docker invocation ran (nothing was started).
        kill_calls = [c for c in mock_run.call_args_list if c.args and c.args[0][:2] == ["docker", "kill"]]
        assert kill_calls == []
        # Handlers were installed (SIGTERM, SIGINT) then restored (SIGTERM, SIGINT).
        calls = mock_signal.call_args_list
        assert len(calls) == 4
        sigterm_calls = [c for c in calls if c.args and c.args[0] == signal.SIGTERM]
        sigint_calls = [c for c in calls if c.args and c.args[0] == signal.SIGINT]
        assert len(sigterm_calls) == 2
        assert len(sigint_calls) == 2
        # The restore call (second per signum) passes back the install-time sentinel.
        assert sigterm_calls[1].args[1] is installed[signal.SIGTERM]
        assert sigint_calls[1].args[1] is installed[signal.SIGINT]
