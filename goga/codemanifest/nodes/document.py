from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional

from goga.codemanifest.nodes.base import Node

if TYPE_CHECKING:
    from goga.codemanifest.nodes.body import BodyNode
    from goga.codemanifest.nodes.footer import FooterNode
    from goga.codemanifest.nodes.header import HeaderNode


@dataclass
class DocumentRoot(Node):
    path: str = ""
    links: dict[str, list[Node]] = field(default_factory=dict)
    embeddings: list[tuple[str, str]] = field(default_factory=list)
    header: HeaderNode = field(default_factory=lambda: _create_header())
    body: BodyNode = field(default_factory=lambda: _create_body())
    footer: FooterNode = field(default_factory=lambda: _create_footer())
    types: dict[str, list[Node]] = field(default_factory=dict)
    children: list[DocumentRoot] = field(default_factory=list)


@dataclass
class DocumentNode(Node):
    root: Optional[DocumentRoot] = None


# Lazy import helpers to avoid circular imports at module level
def _create_header() -> Any:
    from goga.codemanifest.nodes.header import HeaderNode

    return HeaderNode()


def _create_body() -> Any:
    from goga.codemanifest.nodes.body import BodyNode

    return BodyNode()


def _create_footer() -> Any:
    from goga.codemanifest.nodes.footer import FooterNode

    return FooterNode()
