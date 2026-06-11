from __future__ import annotations

from dataclasses import dataclass

from .document import DocumentNode


@dataclass(kw_only=True)
class FooterNode(DocumentNode):
    """Footer section with author, creation date, and description."""

    author: str = ""
    created_at: str = ""
    description: str = ""
