from __future__ import annotations

from dataclasses import dataclass, field

from .base import Node
from .common import AnnotationsNode
from .document import DocumentNode


@dataclass(kw_only=True)
class BodyNode(DocumentNode):
    """Body section containing entity and routine type definitions."""
    types: dict[str, list[Node]] = field(default_factory=dict)
    entities: list[EntityTypeNode] = field(default_factory=list)
    routines: list[RoutineTypeNode] = field(default_factory=list)


@dataclass(kw_only=True)
class RoutineTypeNode(DocumentNode):
    """Routine (function/procedure) definition with name and signature."""
    name: str = ""
    signature: str = ""
    location: str = ""
    annotations: AnnotationsNode = field(default_factory=lambda: AnnotationsNode(root=None))
    embedded: bool = False


@dataclass(kw_only=True)
class EntityTypeNode(DocumentNode):
    """Entity (class/struct) definition with properties and methods."""
    name: str = ""
    signature: str = ""
    location: str = ""
    annotations: AnnotationsNode = field(default_factory=lambda: AnnotationsNode(root=None))
    properties: list[PropertyNode] = field(default_factory=list)
    methods: list[MethodNode] = field(default_factory=list)
    embedded: bool = False
    mutations: list[tuple[str, str]] = field(default_factory=list)


@dataclass(kw_only=True)
class MethodNode(DocumentNode):
    """Method definition belonging to an entity."""
    name: str = ""
    signature: str = ""
    annotations: AnnotationsNode = field(default_factory=lambda: AnnotationsNode(root=None))


@dataclass(kw_only=True)
class PropertyNode(DocumentNode):
    """Property definition belonging to an entity."""
    name: str = ""
    type: str = ""
    annotations: AnnotationsNode = field(default_factory=lambda: AnnotationsNode(root=None))
