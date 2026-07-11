"""Integration test: ``run_pipeline_container`` mounts detected credentials read-only.

Cross-cell integration for ``goga/commands/pipeline``: in run mode the real
``resolve_credential_mounts()`` (called inside ``_build_run_cmd``) detects a
codex credential file on disk and the assembled docker command carries the
read-only bind-mount ``-v <host>:/home/goga/.codex/auth.json:ro``.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest import mock

from goga.commands.pipeline.run_pipeline_container import run_pipeline_container
from goga.config import BuildConfig, Config, PipelineConfig, TaskExecutorConfig

# goga.commands.pipeline.run_pipeline_container is the real submodule; resolve
# it via sys.modules so string-based mock.patch paths walk the actual module.
_rpc_mod = sys.modules["goga.commands.pipeline.run_pipeline_container"]


def _make_config() -> Config:
    """Build a minimal Config satisfying the schema."""
    return Config(
        lang="python",
        image="qarium/goga:latest",
        dockerfile=None,
        build=BuildConfig(task_executor=TaskExecutorConfig(agent="claude")),
        pipeline=PipelineConfig(agent="claude", env={}),
    )


class TestPipelineCredentialMountIntegration:
    def test_run_mode_mounts_codex_credential_read_only(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """Run mode assembles a read-only bind-mount for the detected codex credential."""
        config = _make_config()

        # Place a codex credential under the redirected home so the real
        # resolve_credential_mounts() — called inside _build_run_cmd — detects
        # exactly one credential file. Detection uses Path.expanduser(), which
        # reads $HOME directly on CPython 3.12+, so $HOME is redirected (a real
        # ~/.codex/auth.json exists on the host and would otherwise leak in).
        codex = tmp_path / ".codex" / "auth.json"
        codex.parent.mkdir(parents=True, exist_ok=True)
        codex.write_text("{}")
        monkeypatch.setenv("HOME", str(tmp_path))

        # Stub the runtime pieces UNRELATED to credential detection so the run
        # path is deterministic and never touches the host's git/subprocess.
        # resolve_credential_mounts is intentionally left real — that is the
        # entity under integration test here.
        proj = tmp_path / "proj"
        proj.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        monkeypatch.setattr(Path, "cwd", lambda: proj)
        monkeypatch.setattr("goga.runtime.paths.resolve_git_branch", lambda: "feature-x")
        monkeypatch.setattr(_rpc_mod, "_check_docker", lambda: True)
        monkeypatch.setattr(_rpc_mod, "_allocate_port", lambda: 50321)
        monkeypatch.setattr(_rpc_mod, "_read_git_config", lambda: {})

        mock_proc = mock.Mock()
        mock_proc.wait.return_value = 0
        with (
            mock.patch.object(subprocess, "Popen", return_value=mock_proc) as mock_popen,
            mock.patch.object(subprocess, "run"),
        ):
            run_pipeline_container(
                name="deploy",
                config=config,
                extra_env=(),
                proxy=None,
                hosts={},
                clean=False,
                update=False,
            )

        cmd = mock_popen.call_args[0][0]
        host_path = str(tmp_path / ".codex" / "auth.json")
        assert "-v" in cmd
        assert f"{host_path}:/home/goga/.codex/auth.json:ro" in cmd
