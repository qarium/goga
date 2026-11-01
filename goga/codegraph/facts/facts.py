"""Shared data records of the code analysis — the facts vocabulary.

Every record carries facts extracted from the project sources: immutable
data classes per the project convention — frozen, keyword-only construction,
empty defaults. The records carry data only, no behavior; the analysis
stages own all logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True, kw_only=True)
class Declaration:
    """One named code declaration found in a source file.

    Attributes:
        path: File that defines the declaration, relative to the project root.
        name: Declaration name as written in the source.
        is_public: True when public under the language visibility rules.
    """

    path: Path = Path()
    name: str = ""
    is_public: bool = False


@dataclass(frozen=True, kw_only=True)
class ImportRef:
    """One import statement or name usage collected from a source file.

    Attributes:
        source: File that contains the import or usage.
        specifier: Raw module, package, or specifier string as written; empty
            for pure name usages.
        names: Imported or used names; empty for wildcard imports and Python
            plain imports; the literal ``default`` marks a JavaScript default
            import.
        is_relative: True when the import uses a relative form — Python
            relative imports, JavaScript relative specifiers.
        is_wildcard: True when the import is a star import.
    """

    source: Path = Path()
    specifier: str = ""
    names: list[str] = field(default_factory=list)
    is_relative: bool = False
    is_wildcard: bool = False

    def __post_init__(self) -> None:
        """Copy the caller-owned name list into a fresh list."""
        object.__setattr__(self, "names", list(self.names))


@dataclass(frozen=True, kw_only=True)
class FileFacts:
    """Analysis result of one source file.

    Attributes:
        path: Analyzed file, relative to the project root.
        declarations: Named declarations of the file.
        imports: Imports and name usages of the file.
        exports: Explicit export list declared by the file; empty when the
            file declares none — Python ``__all__``; JavaScript the exported
            names of export clauses plus the name declared by a named default
            export.
        module: Package or module declaration of the file; empty string when
            the language declares none.
    """

    path: Path = Path()
    declarations: list[Declaration] = field(default_factory=list)
    imports: list[ImportRef] = field(default_factory=list)
    exports: list[str] = field(default_factory=list)
    module: str = ""

    def __post_init__(self) -> None:
        """Copy every caller-owned sequence into fresh lists."""
        object.__setattr__(self, "declarations", list(self.declarations))
        object.__setattr__(self, "imports", list(self.imports))
        object.__setattr__(self, "exports", list(self.exports))


@dataclass(frozen=True, kw_only=True)
class Unit:
    """One language unit of the project — a candidate prospective cell.

    Attributes:
        path: Unit directory, relative to the project root.
        files: Source files of the unit.
        facade: Sorted unique public type names of the unit.
        is_cell: True when the unit has a facade and is a prospective cell;
            a unit without a facade survives as a structural ancestor only.
    """

    path: Path = Path()
    files: list[Path] = field(default_factory=list)
    facade: list[str] = field(default_factory=list)
    is_cell: bool = False

    def __post_init__(self) -> None:
        """Copy every caller-owned sequence into fresh lists."""
        object.__setattr__(self, "files", list(self.files))
        object.__setattr__(self, "facade", list(self.facade))


@dataclass(frozen=True, kw_only=True)
class CellLink:
    """One resolved reference between two units.

    Attributes:
        source: Importing unit directory.
        target: Defining unit directory.
        types: Sorted unique facade types of ``target`` imported by ``source``.
    """

    source: Path = Path()
    target: Path = Path()
    types: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Copy the caller-owned type list into a fresh list."""
        object.__setattr__(self, "types", list(self.types))


@dataclass(frozen=True, kw_only=True)
class CodegraphNode:
    """One node of the output tree — the code-derived analogue of a schema node.

    Attributes:
        cell: Cell path relative to the project root.
        types: Facade type names of the cell.
        dependencies: Target cell path to the imported facade types; no usages
            key.
        children: Nested child nodes.
        tools: The committed tools overlay of the node; empty when no tool
            contributed.
    """

    cell: str = ""
    types: list[str] = field(default_factory=list)
    dependencies: dict[str, list[str]] = field(default_factory=dict)
    children: list[CodegraphNode] = field(default_factory=list)
    tools: dict[str, dict[str, object]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Copy every caller-owned container into fresh containers."""
        dependencies = {key: list(value) for key, value in self.dependencies.items()}

        object.__setattr__(self, "types", list(self.types))
        object.__setattr__(self, "dependencies", dependencies)
        object.__setattr__(self, "children", list(self.children))
