"""Shared helpers of the ``goga commands pipeline`` test zone.

Hoists the three copy-pasted shapes of the suite: the minimal
``ProjectConfig`` factory, the minimal ``.goga/config.yml`` writer, and the
run-mode plumbing mocks that keep the launcher tests under ``tmp_path`` and
offline.
"""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

from goga.config import BuildConfig, PipelineConfig, ProjectConfig

# Resolve the real submodule directly: the package __init__ re-exports the
# ``run_pipeline_container`` function, which shadows the submodule name in
# attribute access on Python 3.10.
_rpc_mod = importlib.import_module("goga.commands.pipeline.run_pipeline_container")


def make_config(
    *,
    image: str | None = "qarium/goga:latest",
    pipeline_agent: str | None = "claude",
    pipeline_env: dict[str, str] | None = None,
) -> ProjectConfig:
    """Build a minimal ``ProjectConfig`` satisfying the schema (top-level image, pipeline block).

    ``pipeline_agent`` may be ``None`` to model a config where the agent is
    intentionally left unconfigured (the agent is then expected to come from
    the workflow per-stage overrides); ``image`` may be ``None`` to model a
    config the docker guard must reject.
    """
    return ProjectConfig(
        language="python",
        image=image,
        dockerfile=None,
        build=BuildConfig(agent="claude"),
        pipeline=PipelineConfig(agent=pipeline_agent, env=pipeline_env or {}),
    )


def write_minimal_config(tmp_path: Path, *, with_pipeline: bool = True) -> Path:
    """Materialize the minimal ``.goga/config.yml`` under ``tmp_path``.

    Args:
        tmp_path: Project root used as the working directory for the test.
        with_pipeline: When ``False`` the ``pipeline:`` block is omitted,
            producing a schema error (``pipeline`` section required) that the
            command surfaces as a ``click.ClickException``.

    Returns:
        ``tmp_path`` (the project root).
    """
    goga_dir = tmp_path / ".goga"
    goga_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        "language: python",
        "image: qarium/goga:latest",
        "build:",
        "  agent: claude",
    ]
    if with_pipeline:
        lines += [
            "pipeline:",
            "  agent: claude",
        ]
    (goga_dir / "config.yml").write_text("\n".join(lines) + "\n")
    return tmp_path


def apply_run_mode_common_mocks(tmp_path: Path, monkeypatch: Any) -> Path:
    """Patch the run-mode plumbing so the test stays under ``tmp_path`` and offline.

    The established convention of the pipeline suite: the autouse
    ``_isolate_home`` fixture (``tests/conftest.py``) already redirects
    ``$HOME`` away from the real ``~/.goga/``; HOME is set again here to
    ``tmp_path`` (and the cwd changed to it) so the home config load and the
    persistent runtime dir stay under the tmp tree and ``Path.cwd()``
    resolves to the project dir goga bind-mounts. The docker check, port
    allocation, and git identity are pinned; ``resolve_wrapper_path`` and
    ``resolve_pipeline_runtime_dir`` are patched to tmp/offline stand-ins so
    the persistent afm-state directory never touches the real ``~/.goga/``
    and the git-branch resolution is bypassed.

    Returns:
        The patched persistent afm state host directory (under ``tmp_path``).
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
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    return runtime_dir
