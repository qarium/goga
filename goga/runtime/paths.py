"""Runtime directory path composition routines for the goga runtime cell.

This module implements the three pure routines declared in
``goga/runtime/CODEMANIFEST`` at ``location: paths.py``:

- ``normalize_project_path(project_path: Path) -> str``
- ``resolve_git_branch() -> str``
- ``resolve_runtime_dir(purpose: str, *suffix_parts: str) -> Path``

All three are pure with respect to the filesystem: they return paths and strings,
they never create directories or write files. The single read-only side effect is
``resolve_git_branch`` asking git for the current branch name. Apply the
``convention`` practice for docstring style and intra-package imports.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


def normalize_project_path(project_path: Path) -> str:
    """Normalize an absolute project path into a filesystem-safe path segment.

    Removes the leading slash (and any leading slashes) and replaces every
    remaining forward slash with a hyphen. The transformation is a literal 1:1
    replacement: consecutive hyphens are not collapsed and trailing hyphens are
    not stripped. Backslashes are preserved (only forward slashes are replaced).

    Example: ``"/Users/wb/IdeaProjects/my/project"`` →
    ``"Users-wb-IdeaProjects-my-project"``.

    Args:
        project_path: Absolute project path (e.g. ``Path.cwd()``).

    Returns:
        A slash-free, hyphen-separated path segment. Pure string transform —
        no filesystem access, no side effects.
    """
    s = str(project_path)
    s = s.lstrip("/")
    s = s.replace("/", "-")
    return s


def resolve_git_branch() -> str:
    """Resolve the current git branch name, falling back to ``"default"``.

    Asks git for the current branch name via ``git branch --show-current`` and
    slugifies it by replacing forward slashes with hyphens. Returns the literal
    ``"default"`` when git is unavailable, the current directory is not a git
    repository, or HEAD is detached — all of which yield an empty answer from
    ``git branch --show-current``.

    Never raises for the documented failure modes. ``FileNotFoundError`` (the git
    binary missing) is caught explicitly so unexpected exceptions still propagate
    during development. The result is not cached: each call asks git anew.

    Returns:
        The slugified current git branch name (forward slashes replaced with
        hyphens), or the literal ``"default"`` fallback.
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
    """Compose the host-side runtime directory path for a given purpose.

    Composes ``~/.goga/runtime/<purpose>/<normalized_project>/<branch>/`` joined
    with any trailing ``suffix_parts`` (in order, with the OS separator). Empty
    ``suffix_parts`` yields the branch-level directory itself. Pure with respect
    to the filesystem — the directory is NOT created here (creation is the
    caller's responsibility).

    ``purpose`` is not validated against a whitelist and ``suffix_parts`` are not
    validated semantically: the caller owns the namespace.

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
