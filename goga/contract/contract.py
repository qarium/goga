"""Contract item dataclass hierarchy."""

from dataclasses import dataclass, field


@dataclass(kw_only=True)
class BaseContract:
    """Base contract with name, signature, and computed contract field."""

    name: str = ""
    signature: str = ""
    contract: str = field(init=False)

    def __post_init__(self) -> None:
        self.contract = f"{self.name}{self.signature}"


@dataclass(kw_only=True)
class PropertyContract(BaseContract):
    """Contract for a class property."""


@dataclass(kw_only=True)
class MethodContract(BaseContract):
    """Contract for a class method."""


@dataclass(kw_only=True)
class EntityContract(BaseContract):
    """Contract for a class entity with properties and methods."""

    properties: list[PropertyContract] = field(default_factory=list)
    methods: list[MethodContract] = field(default_factory=list)


@dataclass(kw_only=True)
class RoutineContract(BaseContract):
    """Contract for a routine (function)."""
