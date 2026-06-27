"""Contract package — public API for source code contract extraction."""

from .data import (
    BaseContract,
    EntityContract,
    MethodContract,
    PropertyContract,
    RoutineContract,
)
from .dispatcher import contract
from .python import python_contract

try:
    from .golang import golang_contract
except ImportError:
    golang_contract = None  # type: ignore[assignment]

try:
    from .javascript import javascript_contract
except ImportError:
    javascript_contract = None  # type: ignore[assignment]

try:
    from .kotlin import kotlin_contract
except ImportError:
    kotlin_contract = None  # type: ignore[assignment]

try:
    from .swift import swift_contract
except ImportError:
    swift_contract = None  # type: ignore[assignment]

__all__ = [
    "BaseContract",
    "EntityContract",
    "MethodContract",
    "PropertyContract",
    "RoutineContract",
    "contract",
    "golang_contract",
    "javascript_contract",
    "kotlin_contract",
    "python_contract",
    "swift_contract",
]
