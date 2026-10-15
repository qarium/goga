"""Third analysis stage — resolve every imported or used name to its unit.

The project-wide indexes are built over the complete units and facts first;
the per-language origin rules then resolve each import to its exact defining
unit, wildcard and plain imports expand through the usage refs recorded by
``collect_facts``, and the kept resolutions aggregate into one link per unit
pair. Unresolvable, external, self, ambiguous, and non-cell-source names are
dropped silently — resolution never fails.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from ..facts import CellLink, FileFacts, ImportRef, Unit

_SUPPORTED_LANGUAGES = frozenset({"python", "golang", "javascript", "kotlin", "swift"})

_PYTHON_SOURCE_BASES = (Path(), Path("src"))

_Resolutions = list[tuple[Path, list[str]]]


@dataclass(frozen=True, kw_only=True)
class _Indexes:
    """Project-wide lookup structures shared by the origin rules.

    Attributes:
        unit_by_dir: Unit path to unit, over every derived unit.
        facts_by_path: Analyzed file path to its facts.
        module_index: Python module string to unit path, derived per
            candidate root in priority order — the project root first, then
            ``src``; within a root the package dir before the module file.
        package_index: Kotlin package to the unit paths declaring it.
        facade_index: Facade name to the unit paths carrying it.
        go_module: Module path of the first directive in the root go.mod;
            empty when the file is absent.
    """

    unit_by_dir: dict[Path, Unit]
    facts_by_path: dict[Path, FileFacts]
    module_index: dict[str, Path] = field(default_factory=dict)
    package_index: dict[str, list[Path]] = field(default_factory=dict)
    facade_index: dict[str, list[Path]] = field(default_factory=dict)
    go_module: str = ""


_Resolver = Callable[[ImportRef, FileFacts, "_Indexes"], _Resolutions]


def resolve_links(units: list[Unit], facts: list[FileFacts], language: str, root: Path) -> list[CellLink]:
    """Resolve every imported or used name to its exact defining unit.

    Args:
        units: All derived units of the project.
        facts: File facts of all analyzed files.
        language: The single configured language — python, golang,
            javascript, kotlin, swift.
        root: Absolute project root.

    Returns:
        One ``CellLink`` per importing and defining unit pair, in
        deterministic (source, target) path order, with sorted unique
        facade types.

    Raises:
        ValueError: When the language is not supported.
    """
    if language not in _SUPPORTED_LANGUAGES:
        raise ValueError(f"unsupported language: {language!r}; expected one of {sorted(_SUPPORTED_LANGUAGES)}")

    indexes = _build_indexes(units, facts, language, root)
    resolver = _RESOLVERS[language]
    pairs: dict[tuple[Path, Path], set[str]] = {}

    for fact in facts:
        source_unit = indexes.unit_by_dir.get(fact.path.parent)

        if source_unit is None or not source_unit.is_cell:
            continue

        for ref in fact.imports:
            for origin, names in resolver(ref, fact, indexes):
                if origin == source_unit.path:
                    continue

                facade = indexes.unit_by_dir[origin].facade
                kept = {name for name in names if name in facade}

                if kept:
                    pairs.setdefault((source_unit.path, origin), set()).update(kept)

    return [
        CellLink(source=source, target=target, types=sorted(pairs[(source, target)]))
        for source, target in sorted(pairs)
    ]


def _build_indexes(units: list[Unit], facts: list[FileFacts], language: str, root: Path) -> _Indexes:
    """Build the project-wide lookup structures of ``language``."""
    unit_by_dir = {unit.path: unit for unit in units}
    facts_by_path = {fact.path: fact for fact in facts}
    package_index: dict[str, list[Path]] = {}
    facade_index: dict[str, list[Path]] = {}

    if language == "kotlin":
        package_index = _package_index(facts, unit_by_dir)

    if language == "swift":
        facade_index = _facade_index(units)

    return _Indexes(
        unit_by_dir=unit_by_dir,
        facts_by_path=facts_by_path,
        module_index=_python_module_index(units, facts, unit_by_dir) if language == "python" else {},
        package_index=package_index,
        facade_index=facade_index,
        go_module=_go_module_path(root) if language == "golang" else "",
    )


def _python_module_index(units: list[Unit], facts: list[FileFacts], unit_by_dir: dict[Path, Unit]) -> dict[str, Path]:
    """Map every python module string to its unit, candidate roots in priority order."""
    module_index: dict[str, Path] = {}

    for base in _PYTHON_SOURCE_BASES:
        for unit in units:
            relative = _relative_to(unit.path, base)

            if relative is not None and relative.parts:
                module_index.setdefault(".".join(relative.parts), unit.path)

        for fact in facts:
            if fact.path.name == "__init__.py":
                continue

            parent_unit = unit_by_dir.get(fact.path.parent)

            if parent_unit is None:
                continue

            relative = _relative_to(fact.path, base)

            if relative is not None and relative.parts:
                module_index.setdefault(".".join(relative.with_suffix("").parts), parent_unit.path)

    return module_index


def _relative_to(path: Path, base: Path) -> Path | None:
    """Return ``path`` relative to ``base``, or None when it is not under it."""
    try:
        return path.relative_to(base)
    except ValueError:
        return None


_GO_MODULE_DIRECTIVE_PARTS = 2


def _go_module_path(root: Path) -> str:
    """Return the module path of the first module directive in the root go.mod."""
    go_mod = root / "go.mod"

    if not go_mod.is_file():
        return ""

    for line in go_mod.read_text(encoding="utf-8").splitlines():
        parts = line.strip().split(None, 1)

        if len(parts) == _GO_MODULE_DIRECTIVE_PARTS and parts[0] == "module":
            return parts[1].strip().strip('"')

    return ""


def _package_index(facts: list[FileFacts], unit_by_dir: dict[Path, Unit]) -> dict[str, list[Path]]:
    """Map every declared kotlin package to the unit paths declaring it."""
    index: dict[str, list[Path]] = {}

    for fact in facts:
        if not fact.module:
            continue

        unit = unit_by_dir.get(fact.path.parent)

        if unit is None:
            continue

        unit_paths = index.setdefault(fact.module, [])

        if unit.path not in unit_paths:
            unit_paths.append(unit.path)

    return index


def _facade_index(units: list[Unit]) -> dict[str, list[Path]]:
    """Map every facade name to the unit paths carrying it."""
    index: dict[str, list[Path]] = {}

    for unit in units:
        for name in unit.facade:
            index.setdefault(name, []).append(unit.path)

    return index


def _expanded_names(ref: ImportRef, fact: FileFacts) -> list[str]:
    """Return the usage names recorded for the base import of ``ref``.

    Args:
        ref: The base import ref — a wildcard, plain, or namespace import
            carrying no names of its own.
        fact: Facts of the importing file.

    Returns:
        The sorted unique names of the usage refs of ``fact`` that share
        the base import's specifier and flags; files are never re-read or
        re-parsed.
    """
    names: set[str] = set()

    for other in fact.imports:
        if (
            other.specifier == ref.specifier
            and other.is_relative == ref.is_relative
            and other.is_wildcard == ref.is_wildcard
        ):
            names.update(other.names)

    return sorted(names)


# --- python ---


def _python_resolutions(ref: ImportRef, fact: FileFacts, indexes: _Indexes) -> _Resolutions:
    """Resolve one python import ref against the module and relative indexes."""
    names = _expanded_names(ref, fact) if ref.is_wildcard or not ref.names else ref.names

    if ref.is_relative:
        origin = _python_relative_origin(ref.specifier, fact, indexes)
    else:
        origin = indexes.module_index.get(ref.specifier)

    if origin is None:
        return []

    return [(origin, names)]


def _python_relative_origin(specifier: str, fact: FileFacts, indexes: _Indexes) -> Path | None:
    """Resolve one relative python specifier against the importing file."""
    level = len(specifier) - len(specifier.lstrip("."))
    base = _ancestor_directory(fact.path.parent, level - 1)

    if base is None:
        return None

    module_part = specifier[level:]

    if not module_part:
        return _python_target_origin(base, indexes)

    return _python_target_origin(base / Path(*module_part.split(".")), indexes)


def _ancestor_directory(directory: Path, up: int) -> Path | None:
    """Return ``directory`` walked ``up`` parent steps, or None past the root."""
    current = directory

    for _ in range(up):
        if not current.parents:
            return None

        current = current.parents[0]

    return current


def _python_target_origin(directory: Path, indexes: _Indexes) -> Path | None:
    """Resolve one python directory as a package dir, else as a module file's directory."""
    unit = indexes.unit_by_dir.get(directory)

    if unit is not None:
        return unit.path

    if not directory.name:
        return None

    module_file = directory.with_suffix(".py")

    if module_file in indexes.facts_by_path:
        parent_unit = indexes.unit_by_dir.get(module_file.parent)

        if parent_unit is not None:
            return parent_unit.path

    return None


# --- golang ---


def _golang_resolutions(ref: ImportRef, fact: FileFacts, indexes: _Indexes) -> _Resolutions:
    """Resolve one golang import path against the go.mod module path."""
    if not indexes.go_module:
        return []

    module = indexes.go_module

    if ref.specifier == module:
        origin = Path()
    elif ref.specifier.startswith(f"{module}/"):
        origin = Path(*ref.specifier[len(module) + 1 :].split("/"))
    else:
        return []

    unit = indexes.unit_by_dir.get(origin)

    if unit is None:
        return []

    names = _expanded_names(ref, fact) if ref.is_wildcard or not ref.names else ref.names

    return [(unit.path, names)]


# --- javascript ---


def _javascript_resolutions(ref: ImportRef, fact: FileFacts, indexes: _Indexes) -> _Resolutions:
    """Resolve one javascript specifier with Node-style relative resolution."""
    specifier = ref.specifier

    if not (specifier.startswith(".") or specifier.startswith("/")):
        return []

    file = _javascript_resolved_file(specifier, fact.path.parent, indexes)

    if file is None:
        return []

    unit = indexes.unit_by_dir.get(file.parent)

    if unit is None:
        return []

    names = _expanded_names(ref, fact) if ref.is_wildcard or not ref.names else ref.names

    return [(unit.path, _javascript_default_names(names, file, indexes))]


def _javascript_resolved_file(specifier: str, directory: Path, indexes: _Indexes) -> Path | None:
    """Resolve one relative javascript specifier to an analyzed file."""
    cleaned = specifier.rstrip("/")
    candidate = _normalized(directory / cleaned)

    if specifier.endswith(".js"):
        return candidate if candidate in indexes.facts_by_path else None

    if specifier.endswith("/"):
        directory_form = candidate / "index.js"

        return directory_form if directory_form in indexes.facts_by_path else None

    if candidate.name:
        file_form = candidate.with_name(f"{candidate.name}.js")

        if file_form in indexes.facts_by_path:
            return file_form

    directory_form = candidate / "index.js"

    return directory_form if directory_form in indexes.facts_by_path else None


def _javascript_default_names(names: list[str], file: Path, indexes: _Indexes) -> list[str]:
    """Map every ``default`` entry to the default-exported name of ``file``.

    The default-exported name is the file's last export when it names a
    public declaration — export clauses are recorded before the named
    default, so a named default lands last. The flat export list cannot
    distinguish a trailing clause export from a named default, so a file
    with clause exports but no named default may map the entry to that
    clause name — a known v1 limitation.

    Args:
        names: Imported names; the literal ``default`` marks a default import.
        file: The resolved file the import lands on.
        indexes: Project-wide lookup structures.

    Returns:
        The names with each ``default`` entry replaced element-wise by the
        default-exported name of ``file``; a file with no export matching a
        public declaration maps the entry to nothing.
    """
    if "default" not in names:
        return names

    fact = indexes.facts_by_path.get(file)
    default_name = ""

    if fact is not None and fact.exports:
        candidate = fact.exports[-1]

        if any(declaration.name == candidate and declaration.is_public for declaration in fact.declarations):
            default_name = candidate

    mapped: list[str] = []

    for name in names:
        if name != "default":
            mapped.append(name)
        elif default_name:
            mapped.append(default_name)

    return mapped


def _normalized(path: Path) -> Path:
    """Return ``path`` with ``.`` and ``..`` components collapsed."""
    return Path(os.path.normpath(path))


# --- kotlin ---


def _kotlin_resolutions(ref: ImportRef, fact: FileFacts, indexes: _Indexes) -> _Resolutions:
    """Resolve one kotlin import against the packages declared by the units."""
    if ref.is_wildcard:
        names = _expanded_names(ref, fact)

        return [(unit_path, names) for unit_path in indexes.package_index.get(ref.specifier, [])]

    package, _, name = ref.specifier.rpartition(".")

    if not package:
        return []

    resolutions: _Resolutions = []

    for unit_path in indexes.package_index.get(package, []):
        if name in indexes.unit_by_dir[unit_path].facade:
            resolutions.append((unit_path, [name]))

    return resolutions


# --- swift ---


def _swift_resolutions(ref: ImportRef, _fact: FileFacts, indexes: _Indexes) -> _Resolutions:
    """Resolve one swift usage ref by project-wide type-name uniqueness."""
    if ref.specifier:
        return []

    resolutions: _Resolutions = []

    for name in ref.names:
        unit_paths = indexes.facade_index.get(name, [])

        if len(unit_paths) == 1:
            resolutions.append((unit_paths[0], [name]))

    return resolutions


_RESOLVERS: dict[str, _Resolver] = {
    "python": _python_resolutions,
    "golang": _golang_resolutions,
    "javascript": _javascript_resolutions,
    "kotlin": _kotlin_resolutions,
    "swift": _swift_resolutions,
}
