"""The authored-facts read view of the schema domain hooks zone.

``CellFacts`` is the per-cell read view delivered to every subscribed hook
of the hard ``schema/amend_cell`` checkpoint: the authored facts of one
cell as resolved by the calling walk. ``DependencyFacts`` is the imported
facts of one dependency — the source path with its imported type names and
usage names. Both are pure facts: the constructing operation passes
resolved values and nothing is read inside either record — the authored
projection only, identical in every run regardless of filters; never
another tool's contributions, generated data, or the run's filter
parameters.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class CellFacts:
    """The authored facts of one cell — the per-cell read view.

    Pure facts: the constructing operation (the schema walk) passes
    resolved values, nothing is read inside. The record is the authored
    projection only — identical in every run regardless of filters; never
    another tool's contributions, generated data, or the run's filter
    parameters.

    Args:
        path: the normalized cell path.
        description: the footer description of the cell manifest.
        types: the entity and routine names of the cell body.
        usages: the usages file names of the cell.
        dependencies: the cell's imports grouped per source path.
        children: the authored children paths of the document tree.
    """

    path: str
    description: str
    types: list[str]
    usages: list[str]
    dependencies: list[DependencyFacts]
    children: list[str]


@dataclass(frozen=True, kw_only=True)
class DependencyFacts:
    """The imported facts of one dependency — pure data.

    Constructed by the caller from the document's imports; nothing is read
    inside.

    Args:
        path: the source path of the import.
        types: the imported type names.
        usages: the imported usage names.
    """

    path: str
    types: list[str]
    usages: list[str]
