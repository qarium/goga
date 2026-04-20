"""Python contract extraction — extracts facade from Python packages."""

import importlib
import inspect

from .contract import ContractItem


def python_contract(cell_path: str) -> list[ContractItem]:
    """Extract the contract (facade) from a Python package.

    Args:
        cell_path: Path to the package in ``path/to/cell`` format.

    Returns:
        List of ContractItem instances representing the package facade.

    Raises:
        ModuleNotFoundError: If the package cannot be imported.
    """
    module_path = cell_path.strip("/").replace("/", ".")
    module = importlib.import_module(module_path)

    all_names = getattr(module, "__all__", None)
    if all_names is None:
        return []

    result: list[ContractItem] = []
    for name in all_names:
        obj = getattr(module, name)
        if not (inspect.isfunction(obj) or inspect.isclass(obj)):
            continue
        if inspect.isclass(obj):
            sig = inspect.signature(obj.__init__)
            params = list(sig.parameters.values())
            if params and params[0].name == "self":
                params = params[1:]
            sig = sig.replace(parameters=params)
        else:
            sig = inspect.signature(obj)
        result.append(ContractItem(name=name, signature=str(sig)))

    return result
