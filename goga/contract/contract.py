"""Contract item dataclass."""

from dataclasses import dataclass


@dataclass(kw_only=True)
class ContractItem:
    """Represents a single item on a package facade."""

    name: str = ""
    signature: str = ""
