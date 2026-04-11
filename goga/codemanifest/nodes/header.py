from __future__ import annotations

from dataclasses import dataclass, field

from goga.codemanifest.nodes.common import AnnotationsNode
from goga.codemanifest.nodes.document import DocumentNode


@dataclass
class HeaderNode(DocumentNode):
    imports: ImportsNode = field(default_factory=lambda: ImportsNode())
    usages: UsagesNode = field(default_factory=lambda: UsagesNode())
    annotations: AnnotationsNode = field(default_factory=lambda: AnnotationsNode(root=None))
    types: list[str] = field(default_factory=list)


@dataclass
class ImportsNode(DocumentNode):
    items: list[ImportItemNode] = field(default_factory=list)


@dataclass
class ImportItemNode(DocumentNode):
    type_name: set[str] = field(default_factory=set)
    from_path: str = ""
    alias: str = ""


@dataclass
class UsagesNode(DocumentNode):
    items: list[UsageItemNode] = field(default_factory=list)


@dataclass
class UsageItemNode(DocumentNode):
    name: str = ""
    annotations: AnnotationsNode = field(default_factory=lambda: AnnotationsNode(root=None))
