from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from goga.codemanifest.nodes.document import DocumentNode, DocumentRoot


@dataclass
class Node:
    parent: DocumentNode | DocumentRoot | None = None
    data: dict[str, Any] = field(default_factory=dict)
