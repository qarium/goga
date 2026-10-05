from __future__ import annotations

from pathlib import Path

from .pipeline_entry import PipelineEntry, PipelineSource


def list_pipelines(project_dir: Path, user_dir: Path) -> list[PipelineEntry]:
    """Discover pipeline files across two source directories.

    Args:
        project_dir: project-level pipelines directory (typically
            ``<cwd>/.goga/pipelines/``); a missing directory is treated as empty.
        user_dir: user-level pipelines directory (typically
            ``~/.goga/pipelines/``); a missing directory is treated as empty.

    Returns:
        The combined list of ``PipelineEntry``-s, one per unique pipeline name,
        with project entries preceding user entries — the project entry wins on
        name conflicts, and files whose stem is not a valid pipeline name are
        skipped rather than raising.
    """
    entries: list[PipelineEntry] = []
    seen_names: set[str] = set()

    def _scan(source_dir: Path, source: PipelineSource) -> None:
        if not source_dir.is_dir():
            return
        for yml_path in sorted(source_dir.glob("*.yml")):
            try:
                entry = PipelineEntry(name=yml_path.stem, source=source)
            except ValueError:
                continue
            if entry.name in seen_names:
                continue
            entries.append(entry)
            seen_names.add(entry.name)

    _scan(project_dir, PipelineSource.PROJECT)
    _scan(user_dir, PipelineSource.USER)

    return entries
