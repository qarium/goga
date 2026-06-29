from __future__ import annotations

import importlib.metadata
import importlib.util
import shutil
import sys
from pathlib import Path


def _get_internal_flows_dir() -> Path:
    """Resolve the internal ``goga/assets/flows/`` source directory shipped with the package."""
    return Path(__file__).parent.parent / "assets" / "flows"


def _copy_internal_flows(flows_dir: Path) -> None:
    """Copy flat ``*.yml`` files from the internal source into ``flows_dir``."""
    internal_source = _get_internal_flows_dir()
    if not internal_source.is_dir():
        return

    for yml_path in sorted(internal_source.glob("*.yml")):
        shutil.copy2(yml_path, flows_dir / yml_path.name)


def _copy_tool_flows(flows_dir: Path, force_overwrite: bool) -> None:
    """Copy flat ``*.yml`` flows from ``goga_tool_*`` packages into ``flows_dir``.

    On name conflicts with the internal source, the tool flow is skipped with a
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

        pkg_flows = Path(spec.origin).parent / "flows"
        if not pkg_flows.is_dir():
            continue

        for yml_path in sorted(pkg_flows.glob("*.yml")):
            dest = flows_dir / yml_path.name
            if dest.exists() and not force_overwrite:
                print(
                    f"Warning: flow {dest.name} already exists, skipping",
                    file=sys.stderr,
                )
                continue
            shutil.copy2(yml_path, dest)


def install_flows(flows_dir: Path, force_overwrite: bool = False) -> int:
    """Recreate ``flows_dir`` and populate it with flat ``*.yml`` flow files.

    The target directory is fully recreated (deleted then created). Flat
    ``*.yml`` files are copied first from the internal ``goga/assets/flows/`` source,
    then from each installed ``goga_tool_*`` package's ``flows/`` directory.

    Conflict resolution mirrors the existing tool-skill installer: when a flow
    name exists in both the internal source and a ``goga_tool_*`` package, the
    tool's flow is skipped with a warning unless ``force_overwrite`` is set, in
    which case the tool's flow overwrites the internal one.

    Args:
        flows_dir: target flows directory (typically ``~/.goga/flows/``).
        force_overwrite: when ``True``, let ``goga_tool_*`` packages overwrite
            internal-source flows on name conflicts.

    Returns:
        ``0`` on success, ``1`` on ``OSError``/``shutil.Error``.
    """
    try:
        shutil.rmtree(flows_dir, ignore_errors=True)
        flows_dir.mkdir(parents=True, exist_ok=True)
        _copy_internal_flows(flows_dir)
        _copy_tool_flows(flows_dir, force_overwrite)
    except (OSError, shutil.Error) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    return 0
