"""Runtime directory path composition routines for the goga runtime cell."""

from __future__ import annotations

import subprocess
from pathlib import Path


def normalize_project_path(project_path: Path) -> str:
    """Normalize an absolute project path into a filesystem-safe path segment.

    Args:
        project_path: Absolute project path (e.g. ``Path.cwd()``).

    Returns:
        A slash-free, hyphen-separated path segment — a pure string transform
        with no collapsing and no filesystem access.
    """
    s = str(project_path)
    s = s.lstrip("/")
    s = s.replace("/", "-")
    return s


def resolve_git_branch() -> str:
    """Resolve the current git branch name, falling back to ``"default"``.

    Returns:
        The slugified branch name (slashes → hyphens), or the literal ``"default"``
        when git is missing, the cwd is not a repository, or HEAD is detached.
    """
    try:
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return "default"

    if result.returncode == 0 and result.stdout.strip() != "":
        return result.stdout.strip().replace("/", "-")
    return "default"


def resolve_runtime_dir(purpose: str, *suffix_parts: str) -> Path:
    """Compose the host-side runtime directory path for a purpose — the directory itself is never created.

    Args:
        purpose: Runtime namespace segment (e.g. ``"builds"`` or ``"pipelines"``).
            Becomes the directory immediately under ``~/.goga/runtime/``.
        *suffix_parts: Zero or more trailing path segments appended after the
            branch directory.

    Returns:
        The composed absolute host path
        ``~/.goga/runtime/<purpose>/<normalized_project>/<branch>/<*suffix_parts>``.
    """
    cwd = Path.cwd()
    normalized = normalize_project_path(cwd)
    branch = resolve_git_branch()
    runtime_dir = Path.home() / ".goga" / "runtime" / purpose / normalized / branch
    for part in suffix_parts:
        runtime_dir = runtime_dir / part
    return runtime_dir
