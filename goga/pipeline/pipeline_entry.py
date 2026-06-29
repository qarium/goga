from __future__ import annotations

import enum
from dataclasses import dataclass


class PipelineSource(str, enum.Enum):
    """Origin of a pipeline file.

    Attributes:
        PROJECT: the pipeline lives in the project-level ``<cwd>/.goga/pipelines/`` directory.
        USER: the pipeline lives in the user-level ``~/.goga/pipelines/`` directory.
    """

    PROJECT = "project"
    USER = "user"


@dataclass(kw_only=True)
class PipelineEntry:
    """A single discovered pipeline file: its name and where it comes from.

    The ``name`` is the pipeline identifier without extension (e.g.
    ``"deploy"``); the ``.yml`` extension is implied and never stored. ``source``
    records whether the pipeline was discovered in the project-level or
    user-level pipelines directory.

    Args:
        name: pipeline name without extension; must not contain path separators
            (``/`` or ``\\``), must not end with ``.yml``, and must not be empty.
        source: origin of the pipeline (``PipelineSource.PROJECT`` or
            ``PipelineSource.USER``).

    Raises:
        ValueError: if ``name`` carries a path separator, ends with ``.yml``,
            or is empty.
    """

    name: str
    source: PipelineSource

    def __post_init__(self) -> None:
        """Validate ``name`` — reject separators, ``.yml`` suffix, and empty values."""
        if not self.name:
            raise ValueError("pipeline name must not be empty")

        if "/" in self.name or "\\" in self.name:
            raise ValueError("pipeline name must not contain path separators ('/' or '\\')")

        if self.name.endswith(".yml"):
            raise ValueError("pipeline name must not include the '.yml' extension")
