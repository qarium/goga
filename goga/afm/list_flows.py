from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError

from .flow_entry import FlowEntry, Source


def list_flows(project_dir: Path, user_dir: Path) -> list[FlowEntry]:
    """Discover flow files across two source directories.

    Flat-scans (non-recursive) the top-level ``*.yml`` files in each directory,
    drops the ``.yml`` extension to form the flow name, and returns one
    ``FlowEntry`` per unique name. The project source wins on name conflicts:
    when a name exists in both directories, only the project entry is kept.

    A missing source directory is treated as empty (no error is raised). Files
    whose stem is not a valid flow name (e.g. a stray top-level ``.yml``) are
    skipped rather than raising.

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

    def _scan(source_dir: Path, source: Source) -> None:
        if not source_dir.is_dir():
            return
        for yml_path in sorted(source_dir.glob("*.yml")):
            try:
                entry = FlowEntry(name=yml_path.stem, source=source)
            except ValidationError:
                continue
            if entry.name in seen_names:
                continue
            entries.append(entry)
            seen_names.add(entry.name)

    _scan(project_dir, Source.PROJECT)
    _scan(user_dir, Source.USER)

    return entries
