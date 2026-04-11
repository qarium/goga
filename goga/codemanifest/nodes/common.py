from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from goga.codemanifest.nodes.document import DocumentNode


@dataclass
class AnnotationsNode(DocumentNode):
    url: Optional[str] = None
    filepath: Optional[str] = None
    links: list[str] = field(default_factory=list)
    text: str = ""
