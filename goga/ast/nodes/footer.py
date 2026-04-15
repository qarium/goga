from __future__ import annotations

from dataclasses import dataclass

from .document import DocumentNode


@dataclass
class FooterNode(DocumentNode):
    author: str = ""
    created_at: str = ""
    description: str = ""
