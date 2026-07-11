"""End-to-end integration tests for the resolved wrapper path flow.

These stitch together the cross-cell path introduced by the
``unified-agent-wrappers-resolution`` migration. A single leaf routine —
``resolve_wrapper_path`` in ``goga/agents/wrapper`` — is re-exported through the
``goga.agents`` facade and consumed by both host-side launchers:

    goga/agents/wrapper/resolve.py  (leaf)
        -> goga/agents/__init__.py  (facade re-export)
            -> goga/build/build.py            (writes .ralphex/config claude_command)
            -> goga/commands/pipeline/...     (writes afm-config tmpfile client.command)

The integration boundary is the facade import
``from goga.agents import resolve_wrapper_path``: each consumer resolves the bare
agent name from its own config block (``build.task_executor.agent`` /
``pipeline.agent``) and writes the resulting absolute path into a different
config surface. These tests verify both consumers receive the exact value
``resolve_wrapper_path`` produces for the same agent, and that the two surfaces
agree with each other.

The docker/subprocess boundary is mocked per
``[[feedback_mock_patch_module_shadowing]]``: the package ``__init__`` re-exports
submodule functions, which shadows string-based ``mock.patch`` paths on Python
3.10, so the real modules are resolved via ``sys.modules`` and patched by
attribute.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest
from goga.agents import resolve_wrapper_path
from goga.build import build
from goga.commands.pipeline.run_pipeline_container import (
    run_pipeline_container as rpc,
)
from goga.config import load_config

# goga.commands.pipeline.run_pipeline_container shadows its submodule name in the
# package __init__, so resolve the real module via sys.modules for
# monkeypatching host-side helpers.
_rpc_mod = sys.modules["goga.commands.pipeline.run_pipeline_container"]

_AFM_MOUNT_SUFFIX = ":/home/goga/.afm/config.yaml:ro"


def _write_config(tmp_path: Path, *, agent: str, image: str = "goga:latest") -> None:
    """Materialize a .goga/config.yml with both consumer agent blocks set to agent."""
    goga_dir = tmp_path / ".goga"
    goga_dir.mkdir(parents=True, exist_ok=True)

    lines = [
        "language: python",
        f"image: {image}",
        "pipeline:",
        f"  agent: {agent}",
        "build:",
        "  task_executor:",
        f"    agent: {agent}",
    ]
    (goga_dir / "config.yml").write_text("\n".join(lines) + "\n")


def _load_config(tmp_path: Path, monkeypatch) -> object:
    """Chdir into tmp_path and load the .goga/config.yml written there."""
    monkeypatch.chdir(tmp_path)
    return load_config()


def _capture_afm_config_popen(captured: dict) -> object:
    """Build a subprocess.Popen side effect that reads the afm-config tmpfile.

    The afm-config host path is extracted from the run-mode docker command's
    ``-v <host>:/home/goga/.afm/config.yaml:ro`` argument and read back into
    ``captured['afm_content']`` before the mocked process returns — capturing the
    real file content written by the integrated ``_write_afm_config_tmpfile``
    call.
    """
    mock_proc = mock.Mock()
    mock_proc.wait.return_value = 0

    def popen_side_effect(cmd, *args, **kwargs):
        for i, arg in enumerate(cmd):
            if arg == "-v" and i + 1 < len(cmd) and cmd[i + 1].endswith(_AFM_MOUNT_SUFFIX):
                host = cmd[i + 1][: -len(_AFM_MOUNT_SUFFIX)]
                captured["afm_content"] = Path(host).read_text()
                break
        return mock_proc

    return popen_side_effect


# --- build consumer: .ralphex/config claude_command ---


class TestBuildResolvedPathFlow:
    @pytest.mark.parametrize("agent", ["claude", "codex", "opencode"])
    def test_build_resolved_path_matches_resolve_wrapper_path(
        self,
        tmp_path: Path,
        monkeypatch,
        agent: str,
    ) -> None:
        """build() writes the resolve_wrapper_path(agent) value into claude_command."""
        _write_config(tmp_path, agent=agent)
        config = _load_config(tmp_path, monkeypatch)
        monkeypatch.setattr(shutil, "which", lambda *_: True)
        cli_options = {"dry_run": True, "skip_manifest_check": True}

        result = build("plan.md", config, cli_options)

        assert result == 0
        config_text = (tmp_path / ".ralphex" / "config").read_text()

        # The facade is the single source of truth: claude_command must equal
        # exactly what resolve_wrapper_path returns for this agent.
        for line in config_text.splitlines():
            if line.startswith("claude_command = "):
                claude_command = line[len("claude_command = ") :]
                assert claude_command == resolve_wrapper_path(agent)
                return
        pytest.fail("claude_command line not found in .ralphex/config")


# --- pipeline consumer: afm-config tmpfile client.command ---


class TestPipelineResolvedPathFlow:
    @pytest.mark.parametrize("agent", ["claude", "codex", "opencode"])
    def test_pipeline_resolved_path_matches_resolve_wrapper_path(
        self,
        tmp_path: Path,
        monkeypatch,
        agent: str,
    ) -> None:
        """The afm-config client.command equals resolve_wrapper_path(agent)."""
        _write_config(tmp_path, agent=agent)
        config = _load_config(tmp_path, monkeypatch)
        monkeypatch.setattr(_rpc_mod, "_check_docker", lambda: True)
        monkeypatch.setattr(_rpc_mod, "docker_update", lambda *_: None)
        monkeypatch.setattr(_rpc_mod, "_allocate_port", lambda: 50321)
        monkeypatch.setattr(_rpc_mod, "_read_git_config", lambda: {})

        captured: dict = {}
        popen_side_effect = _capture_afm_config_popen(captured)
        with (
            mock.patch.object(subprocess, "Popen", side_effect=popen_side_effect),
            mock.patch.object(subprocess, "run"),
        ):
            result = rpc("deploy", config, ())

        assert result == 0
        assert "afm_content" in captured, "afm-config tmpfile was not captured"

        expected = resolve_wrapper_path(agent)
        assert captured["afm_content"] == (
            f"client.command: {expected}\n"
            "theme: goga\n"
            "open_browser: false\n"
            "proxy:\n"
            "  enabled: false\n"
        )


# --- cross-consumer consistency ---


class TestResolvedPathConsistency:
    @pytest.mark.parametrize("agent", ["claude", "codex", "opencode"])
    def test_resolved_path_consistent_between_build_and_pipeline(
        self,
        tmp_path: Path,
        monkeypatch,
        agent: str,
    ) -> None:
        """For the same agent, both consumers write the identical wrapper path."""
        _write_config(tmp_path, agent=agent)
        config = _load_config(tmp_path, monkeypatch)

        # --- build side: capture .ralphex/config claude_command ---
        monkeypatch.setattr(shutil, "which", lambda *_: True)
        build_options = {"dry_run": True, "skip_manifest_check": True}
        build_result = build("plan.md", config, build_options)
        assert build_result == 0
        build_config_text = (tmp_path / ".ralphex" / "config").read_text()
        build_path: str | None = None
        for line in build_config_text.splitlines():
            if line.startswith("claude_command = "):
                build_path = line[len("claude_command = ") :]
                break
        assert build_path is not None, "claude_command line not found in .ralphex/config"

        # build() may have created .ralphex/; the pipeline side is docker-bound and
        # does not touch it, so no cleanup is needed between the two invocations.

        # --- pipeline side: capture afm-config client.command ---
        monkeypatch.setattr(_rpc_mod, "_check_docker", lambda: True)
        monkeypatch.setattr(_rpc_mod, "docker_update", lambda *_: None)
        monkeypatch.setattr(_rpc_mod, "_allocate_port", lambda: 50321)
        monkeypatch.setattr(_rpc_mod, "_read_git_config", lambda: {})

        captured: dict = {}
        popen_side_effect = _capture_afm_config_popen(captured)
        with (
            mock.patch.object(subprocess, "Popen", side_effect=popen_side_effect),
            mock.patch.object(subprocess, "run"),
        ):
            pipeline_result = rpc("deploy", config, ())
        assert pipeline_result == 0
        assert "afm_content" in captured, "afm-config tmpfile was not captured"

        # afm content is "client.command: <path>\ntheme: goga\nopen_browser: false\nproxy:\n  enabled: false\n";
        # extract the first line to compare the wrapper path against the build side.
        afm_first_line = captured["afm_content"].splitlines()[0]
        assert afm_first_line.startswith("client.command: ")
        pipeline_path = afm_first_line[len("client.command: ") :]

        # Both consumers, driven by the same facade import, agree on the path and
        # match the canonical absolute convention.
        assert build_path == pipeline_path
        assert build_path == f"/home/goga/bin/{agent}-as-claude.sh"
