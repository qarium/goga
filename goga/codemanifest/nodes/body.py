from __future__ import annotations

from dataclasses import dataclass, field

from goga.codemanifest.nodes.base import Node
from goga.codemanifest.nodes.common import AnnotationsNode
from goga.codemanifest.nodes.document import DocumentNode


@dataclass
class BodyNode(DocumentNode):
    types: dict[str, list[Node]] = field(default_factory=dict)
    entities: list[EntityTypeNode] = field(default_factory=list)
    routines: list[RoutineTypeNode] = field(default_factory=list)


@dataclass
class RoutineTypeNode(DocumentNode):
    name: str = ""
    signature: str = ""
    location: str = ""
    annotations: AnnotationsNode = field(default_factory=lambda: AnnotationsNode(root=None))
    embedded: bool = False


@dataclass
class EntityTypeNode(DocumentNode):
    name: str = ""
    signature: str = ""
    location: str = ""
    annotations: AnnotationsNode = field(default_factory=lambda: AnnotationsNode(root=None))
    properties: list[PropertyNode] = field(default_factory=list)
    methods: list[MethodNode] = field(default_factory=list)
    embedded: bool = False
    mutations: list[str] = field(default_factory=list)


@dataclass
class MethodNode(DocumentNode):
    name: str = ""
    signature: str = ""
    annotations: AnnotationsNode = field(default_factory=lambda: AnnotationsNode(root=None))


@dataclass
class PropertyNode(DocumentNode):
    name: str = ""
    type: str = ""
    annotations: AnnotationsNode = field(default_factory=lambda: AnnotationsNode(root=None))
