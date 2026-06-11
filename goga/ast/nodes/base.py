from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .document import DocumentNode, DocumentRoot


@dataclass(kw_only=True)
class Node:
    """Base AST node with optional parent reference and arbitrary data."""

    parent: DocumentNode | DocumentRoot | None = None
    data: dict[str, Any] = field(default_factory=dict)
