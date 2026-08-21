"""The ``describe_pipelines`` Routine — the pipeline overview with descriptions.

Composes the informational overview of every discovered pipeline: each
pipeline paired with the description from its DSL header. Discovery is fully
delegated to :func:`~goga.pipeline.list_pipelines.list_pipelines` (same
names, sources, and order — the contract is reused, not extended); this
module only reads each discovered file's header via
:func:`~goga.pipeline.compiler.parse_dsl` — no compilation.

Failure semantics are all-or-nothing: the first damaged file (unreadable,
non-YAML, structurally invalid) aborts the whole overview. No partial lists,
no silent skips, no placeholder markers — the error propagates to the
consumer (``pipeline_cli`` renders it).
"""

from __future__ import annotations

import logging
from pathlib import Path

from .compiler import parse_dsl
from .list_pipelines import list_pipelines
from .pipeline_entry import PipelineSource
from .pipeline_summary import PipelineSummary

logger = logging.getLogger(__name__)


def describe_pipelines(project_dir: Path, user_dir: Path) -> list[PipelineSummary]:
    """Compose the pipeline overview: one summary per discovered pipeline.

    Discovery is delegated to ``list_pipelines`` and left untouched — the
    returned order (project entries sorted first, then user entries, name
    conflicts collapsed in favor of the project source) is inherited from it.
    For every entry the pipeline-file of its own source directory is read and
    only its header parsed; the summary ``name`` is the discovered stem, not
    the authored header ``name`` — the authored header ``name`` lands in the
    summary ``display_name``.

    Args:
        project_dir: project-level pipelines directory (typically
            ``<cwd>/.goga/pipelines/``).
        user_dir: user-level pipelines directory (typically
            ``~/.goga/pipelines/``).

    Returns:
        The list of ``PipelineSummary``-es in discovery order.

    Raises:
        OSError: If a discovered pipeline-file cannot be read.
        yaml.YAMLError: If a discovered pipeline-file is not valid YAML.
        StructuralError: If a discovered pipeline-file is structurally
            malformed (missing ``---`` separator, header without string
            name/description, unsupported body format).
    """
    entries = list_pipelines(project_dir, user_dir)

    summaries: list[PipelineSummary] = []

    for entry in entries:
        source_dir = project_dir if entry.source is PipelineSource.PROJECT else user_dir
        text = (source_dir / f"{entry.name}.yml").read_text()
        header, _, _ = parse_dsl(text)
        logger.debug(
            "pipeline overview entry composed",
            extra={"pipeline": entry.name, "source": entry.source.value},
        )
        summaries.append(
            PipelineSummary(
                name=entry.name,
                source=entry.source,
                description=header.description,
                display_name=header.name,
            )
        )

    logger.debug("pipeline overview composed", extra={"count": len(summaries)})

    return summaries
