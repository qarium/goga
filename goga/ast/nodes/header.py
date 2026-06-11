from __future__ import annotations

from dataclasses import dataclass, field

from .common import AnnotationsNode
from .document import DocumentNode


@dataclass(kw_only=True)
class HeaderNode(DocumentNode):
    """Header section containing imports, usages, and type declarations."""

    imports: ImportsNode = field(default_factory=lambda: ImportsNode())  # noqa: PLW0108
    usages: UsagesNode = field(default_factory=lambda: UsagesNode())  # noqa: PLW0108
    annotations: AnnotationsNode = field(default_factory=lambda: AnnotationsNode(root=None))
    types: list[str] = field(default_factory=list)


@dataclass(kw_only=True)
class ImportsNode(DocumentNode):
    types: list[ImportTypeItemNode] = field(default_factory=list)
    usages: list[ImportUsageItemNode] = field(default_factory=list)


@dataclass(kw_only=True)
class ImportTypeItemNode(DocumentNode):
    """Single type import entry with source path and optional alias."""

    type_name: set[str] = field(default_factory=set)
    from_path: str = ""
    alias: str = ""


@dataclass(kw_only=True)
class ImportUsageItemNode(DocumentNode):
    """Single usage import entry with source path and optional alias."""

    usage_name: set[str] = field(default_factory=set)
    from_path: str = ""
    alias: str = ""


@dataclass(kw_only=True)
class UsagesNode(DocumentNode):
    """Container for usage item declarations."""

    items: list[UsageItemNode] = field(default_factory=list)


@dataclass(kw_only=True)
class UsageItemNode(DocumentNode):
    """Single usage declaration with name and annotations."""

    name: str = ""
    annotations: AnnotationsNode = field(default_factory=lambda: AnnotationsNode(root=None))
