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

    On name conflicts with the internal source, the tool pipeline is skipped with a
    warning unless ``force_overwrite`` is set, mirroring the tool-skill installer.
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

        pkg_pipelines = Path(spec.origin).parent / "pipelines"
        if not pkg_pipelines.is_dir():
            continue

        for yml_path in sorted(pkg_pipelines.glob("*.yml")):
            dest = pipelines_dir / yml_path.name
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
    directory.

    Conflict resolution mirrors the existing tool-skill installer: when a pipeline
    name exists in both the internal source and a ``goga_tool_*`` package, the
    tool's pipeline is skipped with a warning unless ``force_overwrite`` is set,
    in which case the tool's pipeline overwrites the internal one.

    Args:
        pipelines_dir: target pipelines directory (typically ``~/.goga/pipelines/``).
        force_overwrite: when ``True``, let ``goga_tool_*`` packages overwrite
            internal-source pipelines on name conflicts.

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
