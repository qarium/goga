"""Value model for a single row of the pipeline overview."""

from __future__ import annotations

from dataclasses import dataclass

from .pipeline_entry import PipelineSource


@dataclass(kw_only=True)
class PipelineSummary:
    """One row of the pipeline overview: a discovered pipeline with its description.

    The ``name`` is the discovered stem (without extension) exactly as
    :func:`~goga.pipeline.list_pipelines.list_pipelines` reported it — not the
    author-facing ``name`` from the DSL header. ``source`` records whether the
    pipeline was discovered in the project-level or user-level pipelines
    directory, and ``description`` is the pipeline's DSL header description.

    Args:
        name: discovered pipeline name without extension; validated with the
            same rules as :class:`~goga.pipeline.pipeline_entry.PipelineEntry`.
        source: origin of the pipeline (``PipelineSource.PROJECT`` or
            ``PipelineSource.USER``).
        description: description from the pipeline DSL header; may be empty.

    Raises:
        ValueError: if ``name`` carries a path separator, ends with ``.yml``,
            or is empty.
    """

    name: str
    source: PipelineSource
    description: str

    def __post_init__(self) -> None:
        """Validate ``name`` — reject separators, ``.yml`` suffix, and empty values."""
        if not self.name:
            raise ValueError("pipeline name must not be empty")

        if "/" in self.name or "\\" in self.name:
            raise ValueError("pipeline name must not contain path separators ('/' or '\\')")

        if self.name.endswith(".yml"):
            raise ValueError("pipeline name must not include the '.yml' extension")
