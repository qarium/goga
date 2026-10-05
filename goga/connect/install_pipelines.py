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
    """Copy ``goga_tool_*`` pipelines into ``pipelines_dir`` as namespaced ``<tool>:<name>.yml``."""
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
    """Recreate ``pipelines_dir`` and fill it with internal and tool pipelines, namespaced as ``<tool>:<name>.yml``.

    Args:
        pipelines_dir: Target pipelines directory (typically ``~/.goga/pipelines/``);
            fully recreated.
        force_overwrite: Let a ``goga_tool_*`` pipeline overwrite an existing file
            on a residual namespaced conflict; otherwise it is skipped with a warning.

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
