from __future__ import annotations

from dataclasses import dataclass

from goga.codemanifest.nodes.document import DocumentNode


@dataclass
class FooterNode(DocumentNode):
    author: str = ""
    created_at: str = ""
    description: str = ""
