from __future__ import annotations

import importlib.metadata
import importlib.util
import shutil
import sys
from pathlib import Path


def _get_internal_pipelines_dir() -> Path:
    """Resolve the internal ``goga/assets/pipelines/`` source directory shipped with the package."""
    return Path(__file__).parent.parent / "assets" / "pipelines"


def _copy_internal_pipelines(pipelines_dir: Path) -> None:
    """Copy flat ``*.yml`` files from the internal source into ``pipelines_dir``."""
    internal_source = _get_internal_pipelines_dir()
    if not internal_source.is_dir():
        return

    for yml_path in sorted(internal_source.glob("*.yml")):
        shutil.copy2(yml_path, pipelines_dir / yml_path.name)


def _copy_tool_pipelines(pipelines_dir: Path, force_overwrite: bool) -> None:
    """Copy flat ``*.yml`` pipelines from ``goga_tool_*`` packages into ``pipelines_dir``.

    Each tool pipeline is namespaced under its tool so the pipeline is addressable
    as ``goga pipeline <tool>:<name>``: the file for
    ``goga_tool_<tool>/pipelines/<name>.yml`` is installed as ``<tool>:<name>.yml``.
    This eliminates name collisions both between a tool pipeline and an
    internal-source pipeline (which stays un-prefixed) and between two tools that
    ship the same pipeline name.

    The tool prefix is normalized to the canonical hyphenated tool name: the
    underscored Python top-level module name (``goga_tool_hello_world``) yields the
    user-facing tool identifier ``hello-world``, so the pipeline lands at
    ``hello-world:<name>.yml`` and is run as ``goga pipeline hello-world:<name>``.
    The on-disk package layout keeps its underscores; only the namespace prefix is
    normalized.

    A residual conflict can only occur when a namespaced destination already exists
    (e.g. a tool literally ships a ``<tool>:<name>.yml`` file that collides with
    another). Such a residual conflict is skipped with a warning unless
    ``force_overwrite`` is set, mirroring the tool-skill installer.
    """
    pkg_map = importlib.metadata.packages_distributions()
    for top_level_name in sorted(pkg_map):
        if not top_level_name.startswith("goga_tool_"):
            continue

        try:
            spec = importlib.util.find_spec(top_level_name)
        except (ModuleNotFoundError, ValueError):
            continue

        if spec is None or spec.origin is None:
            continue

        # Normalize the underscored Python top-level name to the canonical
        # hyphenated tool identifier (goga_tool_hello_world -> hello-world) so the
        # pipeline prefix matches the package name and is addressable as
        # `goga pipeline hello-world:<name>`. The on-disk package layout keeps its
        # underscores; only the user-facing namespace prefix is normalized.
        tool_name = top_level_name.removeprefix("goga_tool_").replace("_", "-")
        pkg_pipelines = Path(spec.origin).parent / "pipelines"
        if not pkg_pipelines.is_dir():
            continue

        for yml_path in sorted(pkg_pipelines.glob("*.yml")):
            dest = pipelines_dir / f"{tool_name}:{yml_path.name}"

            if dest.exists() and not force_overwrite:
                print(
                    f"Warning: pipeline {dest.name} already exists, skipping",
                    file=sys.stderr,
                )
                continue
            shutil.copy2(yml_path, dest)


def install_pipelines(pipelines_dir: Path, force_overwrite: bool = False) -> int:
    """Recreate ``pipelines_dir`` and populate it with flat ``*.yml`` pipeline files.

    The target directory is fully recreated (deleted then created). Flat
    ``*.yml`` files are copied first from the internal ``goga/assets/pipelines/``
    source, then from each installed ``goga_tool_*`` package's ``pipelines/``
    directory. Each tool pipeline is namespaced under its tool — installed as
    ``<tool>:<name>.yml`` and addressable as ``goga pipeline <tool>:<name>`` — so a
    tool pipeline can no longer collide with an internal-source pipeline (which
    stays un-prefixed) or with another tool's same-named pipeline. The tool prefix
    is normalized to the canonical hyphenated tool name: the underscored top-level
    module name (e.g. ``goga_tool_hello_world``) becomes the user-facing identifier
    ``hello-world``, so the pipeline is run as ``goga pipeline hello-world:<name>``.

    Residual conflict resolution mirrors the existing tool-skill installer: when a
    namespaced destination already exists (the only way a collision can still occur
    after namespacing), the tool's pipeline is skipped with a warning unless
    ``force_overwrite`` is set, in which case the tool's pipeline overwrites it.

    Args:
        pipelines_dir: target pipelines directory (typically ``~/.goga/pipelines/``).
        force_overwrite: when ``True``, let a ``goga_tool_*`` pipeline overwrite an
            existing file on a residual namespaced conflict.

    Returns:
        ``0`` on success, ``1`` on ``OSError``/``shutil.Error``.
    """
    try:
        shutil.rmtree(pipelines_dir, ignore_errors=True)
        pipelines_dir.mkdir(parents=True, exist_ok=True)
        _copy_internal_pipelines(pipelines_dir)
        _copy_tool_pipelines(pipelines_dir, force_overwrite)
    except (OSError, shutil.Error) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    return 0
