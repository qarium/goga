"""The amendment view of the config domain — the read-and-amend view."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..project import ProjectConfig


@dataclass(kw_only=True)
class ConfigAmendment:
    """The read-and-amend view of one tool at the amendment checkpoint.

    Args:
        config: the authored loaded project configuration — read-only and
            identical for every tool; the receiving hook observes authored
            values only, never another tool's contribution.
    """

    config: ProjectConfig

    _amendments: dict[str, PathAmendment] = field(init=False, default_factory=dict, repr=False)

    def set(self, path: str, value: str | int | bool | list[str]) -> None:
        """Buffer one amendment that applies only where the authored configuration is silent at the path.

        Args:
            path: the dotted leaf path in the authored vocabulary.
            value: the amendment value.
        """

        self._amendments[path] = PathAmendment(path=path, intent="set", value=value)

    def force(self, path: str, value: str | int | bool | list[str]) -> None:
        """Buffer one amendment that overwrites the authored value at the path — the tool's explicit override intent.

        Args:
            path: the dotted leaf path in the authored vocabulary.
            value: the amendment value.
        """

        self._amendments[path] = PathAmendment(path=path, intent="force", value=value)


@dataclass(frozen=True, kw_only=True)
class PathAmendment:
    """One buffered amendment — the addressed leaf path, the intent, the value.

    Args:
        path: the dotted leaf path in the authored vocabulary.
        intent: exactly ``set`` or ``force``.
        value: the amendment value.
    """

    path: str
    intent: str
    value: str | int | bool | list[str]
