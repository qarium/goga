from goga.contract.data import (
    BaseContract,
    EntityContract,
    MethodContract,
    PropertyContract,
    RoutineContract,
)
from goga.contract.dispatcher import contract
from goga.contract.python import python_contract

try:
    from goga.contract.golang import golang_contract
except ImportError:
    golang_contract = None  # type: ignore[assignment]

try:
    from goga.contract.javascript import javascript_contract
except ImportError:
    javascript_contract = None  # type: ignore[assignment]

__all__ = [
    "BaseContract",
    "EntityContract",
    "MethodContract",
    "PropertyContract",
    "RoutineContract",
    "contract",
    "golang_contract",
    "javascript_contract",
    "python_contract",
]
