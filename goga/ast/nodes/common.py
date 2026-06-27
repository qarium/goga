from __future__ import annotations

from dataclasses import dataclass, field

from .document import DocumentNode


@dataclass(kw_only=True)
class AnnotationsNode(DocumentNode):
    """Annotations providing URL, filepath, links, and free-text metadata."""

    url: str | None = None
    filepath: str | None = None
    links: list[str] = field(default_factory=list)
    text: str = ""
