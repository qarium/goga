"""The amendment view of the config domain — the read-and-amend view.

``ConfigAmendment`` is the context one tool receives at the hard
``config/amend_config`` checkpoint: the authored loaded project
configuration — read-only and identical for every tool — plus the buffer
of that one tool's amendments. The view is read-and-amend: reads deliver
the authored values (no staged-application state exists, a tool never sees
another tool's contribution), and :meth:`set` / :meth:`force` are the only
write channels, each buffering one addressed amendment until the delivery
commits it. ``PathAmendment`` is the buffered entry itself — pure data,
constructed by the amendment buffer alone.
"""

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
        """Buffer one amendment that applies only where the authored
        configuration is silent at the path.

        The call buffers into the buffer of this tool alone and changes
        nothing until the delivery commits it; a later amendment of this
        tool on the same path replaces its earlier one. No validation and
        no application live here — a set on a path where the authored
        configuration is not silent is dropped by the merge, silently;
        structural validation of the path and the value belongs to the
        merge as well, so an out-of-vocabulary input is stored verbatim
        and fails there, naming this tool.

        Args:
            path: the dotted leaf path in the authored vocabulary.
            value: the amendment value.
        """

        self._amendments[path] = PathAmendment(path=path, intent="set", value=value)

    def force(self, path: str, value: str | int | bool | list[str]) -> None:
        """Buffer one amendment that overwrites the authored value at the
        path — the tool's explicit override intent.

        The call buffers into the buffer of this tool alone and changes
        nothing until the delivery commits it; a later amendment of this
        tool on the same path replaces its earlier one. No validation and
        no application live here — structural validation of the path and
        the value belongs to the merge, so an out-of-vocabulary input is
        stored verbatim and fails there, naming this tool.

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
