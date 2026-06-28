from __future__ import annotations

from pathlib import Path

from .flow_entry import FlowEntry, Source


def list_flows(project_dir: Path, user_dir: Path) -> list[FlowEntry]:
    """Discover flow files across two source directories.

    Flat-scans (non-recursive) the top-level ``*.yml`` files in each directory,
    drops the ``.yml`` extension to form the flow name, and returns one
    ``FlowEntry`` per unique name. The project source wins on name conflicts:
    when a name exists in both directories, only the project entry is kept.

    A missing source directory is treated as empty (no error is raised).

    Args:
        project_dir: project-level flows directory (typically
            ``<cwd>/.goga/flows/``).
        user_dir: user-level flows directory (typically ``~/.goga/flows/``).

    Returns:
        The combined list of ``FlowEntry``-s, one per unique flow name, with
        project entries preceding user entries.
    """
    entries: list[FlowEntry] = []
    seen_names: set[str] = set()

    if project_dir.is_dir():
        for yml_path in sorted(project_dir.glob("*.yml")):
            name = yml_path.stem
            entries.append(FlowEntry(name=name, source=Source.PROJECT))
            seen_names.add(name)

    if user_dir.is_dir():
        for yml_path in sorted(user_dir.glob("*.yml")):
            name = yml_path.stem
            if name not in seen_names:
                entries.append(FlowEntry(name=name, source=Source.USER))

    return entries
