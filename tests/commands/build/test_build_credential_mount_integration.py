"""Integration test: the ``build`` CLI mounts detected credentials read-only.

Cross-cell integration for ``goga/commands/build``: the real
``resolve_credential_mounts()`` (called inside ``build``) detects a
codex credential file on disk and the assembled docker command carries the
read-only bind-mount ``-v <host>:/home/goga/.codex/auth.json:ro``.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest import mock

import yaml
from click.testing import CliRunner
from goga.commands import build as build_cmd

_build_mod = __import__("goga.commands.build.build", fromlist=["build"])


def _write_goga_yml(tmp_path: Path) -> None:
    """Write a minimal .goga/config.yml with an image set."""
    data: dict = {
        "language": "python",
        "image": "qarium/goga:latest",
        "build": {"task_executor": {"agent": "claude"}},
        "pipeline": {"agent": "claude"},
    }
    (tmp_path / ".goga").mkdir(exist_ok=True)
    (tmp_path / ".goga" / "config.yml").write_text(yaml.dump(data))


def _run_build_in_tmp(tmp_path, monkeypatch, args=None):
    """Run the build command from tmp_path (cwd relocated for load_config)."""
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    full_args = ["--skip-manifest-check", *(args or [])]
    return runner.invoke(build_cmd, full_args)


class TestBuildCredentialMountIntegration:
    @mock.patch.object(_build_mod, "_check_docker", return_value=True)
    @mock.patch.object(_build_mod, "_read_git_config", return_value={})
    @mock.patch.object(_build_mod, "_write_env_file")
    def test_build_mounts_codex_credential_read_only(
        self, mock_env, mock_git, mock_docker, tmp_path, monkeypatch
    ) -> None:
        """The assembled docker cmd carries a read-only bind-mount for the codex credential."""
        _write_goga_yml(tmp_path)
        mock_env.return_value = Path("/tmp/env")

        # Place a codex credential under the redirected home so the real
        # resolve_credential_mounts() — called inside build — detects
        # exactly one credential file. Detection uses Path.expanduser(), which
        # reads $HOME directly on CPython 3.12+, so $HOME is redirected (a real
        # ~/.codex/auth.json exists on the host and would otherwise leak in).
        codex = tmp_path / ".codex" / "auth.json"
        codex.parent.mkdir(parents=True, exist_ok=True)
        codex.write_text("{}")
        monkeypatch.setenv("HOME", str(tmp_path))

        mock_proc = mock.Mock()
        mock_proc.wait.return_value = 0
        with (
            mock.patch.object(subprocess, "Popen", return_value=mock_proc) as mock_popen,
            mock.patch.object(subprocess, "run"),
        ):
            _run_build_in_tmp(tmp_path, monkeypatch, ["plan.md"])

        cmd = mock_popen.call_args[0][0]
        host_path = str(tmp_path / ".codex" / "auth.json")
        assert "-v" in cmd
        assert f"{host_path}:/home/goga/.codex/auth.json:ro" in cmd
