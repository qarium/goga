"""Second analysis stage — derive the language units with their facades.

Pure grouping over the collected file facts: a directory becomes a unit per
the language unit rule (a python package directory contains ``__init__.py``,
a javascript module directory contains ``index.js``, the compiled languages
take every directory with sources), a unit owns exactly the source files of
its own directory, and the facade comes from the language facade rules. No
file is read here — directory nesting is rebuilt from paths by the renderer.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from ..facts import FileFacts, Unit

_UNIT_MARKERS: dict[str, str | None] = {
    "python": "__init__.py",
    "golang": None,
    "javascript": "index.js",
    "kotlin": None,
    "swift": None,
}

_FacadeDeriver = Callable[[list[FileFacts]], list[str]]


def derive_units(facts: list[FileFacts], language: str) -> list[Unit]:
    """Derive the language units of the project with their facade types.

    Args:
        facts: File facts of all analyzed files.
        language: The single configured language — python, golang,
            javascript, kotlin, swift.

    Returns:
        One ``Unit`` per language unit, in deterministic path order; a unit
        with an empty facade survives with ``is_cell=False``.

    Raises:
        ValueError: When the language is not supported.
    """
    if language not in _UNIT_MARKERS:
        raise ValueError(f"unsupported language: {language!r}; expected one of {sorted(_UNIT_MARKERS)}")

    marker = _UNIT_MARKERS[language]
    deriver = _FACADE_DERIVERS[language]
    by_dir: dict[Path, list[FileFacts]] = {}

    for fact in facts:
        by_dir.setdefault(fact.path.parent, []).append(fact)

    units: list[Unit] = []

    for directory in sorted(by_dir):
        group = by_dir[directory]

        if marker is not None and _file_facts(group, marker) is None:
            continue

        facade = deriver(group)
        units.append(
            Unit(
                path=directory,
                files=sorted(fact.path for fact in group),
                facade=sorted(set(facade)),
                is_cell=facade != [],
            )
        )

    return units


def _file_facts(group: list[FileFacts], name: str) -> FileFacts | None:
    """Return the facts of the file called ``name`` in the unit directory."""
    for fact in group:
        if fact.path.name == name:
            return fact

    return None


def _python_facade(group: list[FileFacts]) -> list[str]:
    """Return the facade of a python package — __all__ or public bindings."""
    init = _file_facts(group, "__init__.py")

    if init is None:
        return []

    if init.exports:
        return list(init.exports)

    return [declaration.name for declaration in init.declarations if declaration.is_public]


def _javascript_facade(group: list[FileFacts]) -> list[str]:
    """Return the facade of a javascript module — exports and public names."""
    index = _file_facts(group, "index.js")

    if index is None:
        return []

    exported = {declaration.name for declaration in index.declarations if declaration.is_public}

    return [*exported, *index.exports]


def _exported_union(group: list[FileFacts]) -> list[str]:
    """Return the public declaration names of every file of the unit."""
    return [declaration.name for fact in group for declaration in fact.declarations if declaration.is_public]


_FACADE_DERIVERS: dict[str, _FacadeDeriver] = {
    "python": _python_facade,
    "golang": _exported_union,
    "javascript": _javascript_facade,
    "kotlin": _exported_union,
    "swift": _exported_union,
}
