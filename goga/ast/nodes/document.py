from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from .base import Node

if TYPE_CHECKING:
    from .body import BodyNode
    from .footer import FooterNode
    from .header import HeaderNode


@dataclass(kw_only=True)
class DocumentRoot(Node):
    """Root node representing a parsed document with header, body, and footer."""

    path: str = ""
    links: dict[str, list[Node]] = field(default_factory=dict)
    embeddings: list[tuple[str, str]] = field(default_factory=list)
    header: HeaderNode = field(default_factory=lambda: _create_header())  # noqa: PLW0108
    body: BodyNode = field(default_factory=lambda: _create_body())  # noqa: PLW0108
    footer: FooterNode = field(default_factory=lambda: _create_footer())  # noqa: PLW0108
    types: dict[str, list[Node]] = field(default_factory=dict)
    children: list[DocumentRoot] = field(default_factory=list)


@dataclass(kw_only=True)
class DocumentNode(Node):
    """Node that belongs to a specific document and holds a reference to its root."""

    root: DocumentRoot | None = None


# Lazy import helpers to avoid circular imports at module level
def _create_header() -> Any:
    """Create a default HeaderNode via lazy import to avoid circular dependencies."""
    from .header import HeaderNode  # noqa: PLC0415

    return HeaderNode()


def _create_body() -> Any:
    """Create a default BodyNode via lazy import to avoid circular dependencies."""
    from .body import BodyNode  # noqa: PLC0415

    return BodyNode()


def _create_footer() -> Any:
    """Create a default FooterNode via lazy import to avoid circular dependencies."""
    from .footer import FooterNode  # noqa: PLC0415

    return FooterNode()
