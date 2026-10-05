"""Identity vocabulary of the pipeline run events — pure fact carriers validated at construction."""

from __future__ import annotations

from dataclasses import dataclass

_SOURCES: tuple[str, ...] = ("project", "user")
_DECISION_KINDS: tuple[str, ...] = ("disabled", "explicit", "auto-match", "silent-miss")


@dataclass(kw_only=True)
class PipelineIdentity:
    """The identity of the pipeline every event of a run is about.

    Args:
        name: the discovered pipeline name — the file stem without the
            ``.yml`` extension; must be non-empty and carry no path
            separators and no ``.yml`` suffix.
        display_name: the authored pipeline name from the DSL header; may
            differ from the discovered stem; empty when the header names
            none.
        description: the pipeline description from the DSL header.
        source: the origin of the pipeline-file — exactly ``project`` or
            ``user``.

    Raises:
        ValueError: if ``name`` is empty, carries a path separator, or ends
            with ``.yml``, or if ``source`` is not ``project`` or ``user``.
    """

    name: str
    display_name: str = ""
    description: str
    source: str

    def __post_init__(self) -> None:
        """Validate the ``name`` rules and the ``source`` literal.

        Raises:
            ValueError: If the name is empty, carries a path separator, ends
                with ``.yml``, or the source is not ``project``/``user``.
        """
        if not self.name:
            raise ValueError("pipeline name must not be empty")

        if "/" in self.name or "\\" in self.name:
            raise ValueError("pipeline name must not contain path separators ('/' or '\\')")

        if self.name.endswith(".yml"):
            raise ValueError("pipeline name must not include the '.yml' extension")

        if self.source not in _SOURCES:
            raise ValueError(f"pipeline source must be one of {_SOURCES}, got {self.source!r}")


@dataclass(kw_only=True)
class WorkflowDecision:
    """The workflow decision of one composition — the resolution outcome.

    Args:
        kind: the outcome of the workflow resolution — exactly one of
            ``disabled``, ``explicit``, ``auto-match``, ``silent-miss``.
        workflow_name: the resolved workflow name — present for ``explicit``
            and ``auto-match``, ``None`` otherwise.

    Raises:
        ValueError: if ``kind`` is not one of the four fixed values.
    """

    kind: str
    workflow_name: str | None

    def __post_init__(self) -> None:
        """Validate the ``kind`` literal.

        Raises:
            ValueError: If ``kind`` is not one of the four fixed values.
        """
        if self.kind not in _DECISION_KINDS:
            raise ValueError(f"workflow decision kind must be one of {_DECISION_KINDS}, got {self.kind!r}")


@dataclass(kw_only=True)
class WorkIdentity:
    """The topics-shaped identity of the current work.

    Args:
        branch: the current branch name as resolved by the operation.
        slug: the normalized topic slug, or ``None`` in the branch-only
            form.
        year: the resolved year as four digits, or ``None`` in the
            branch-only form.
    """

    branch: str
    slug: str | None = None
    year: str | None = None
