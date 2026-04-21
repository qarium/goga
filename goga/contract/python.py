"""Python contract extraction — extracts facade from Python packages."""

import inspect
import types
from importlib import import_module

from .contract import (
    EntityContract,
    MethodContract,
    PropertyContract,
    RoutineContract,
)


def _extract_properties(
    cls: type,
) -> list[PropertyContract]:
    """Extract public @property descriptors from a class."""
    properties: list[PropertyContract] = []
    for name, attr in inspect.getmembers(cls):
        if name.startswith("_"):
            continue
        if not isinstance(attr, property):
            continue
        if attr.fget is None:
            continue
        try:
            sig_str = str(inspect.signature(attr.fget))
        except (ValueError, TypeError):
            continue
        sig = sig_str.rsplit("->", 1)[-1].strip() if "->" in sig_str else ""
        properties.append(PropertyContract(name=name, signature=sig))
    return properties


def _extract_methods(
    cls: type,
) -> list[MethodContract]:
    """Extract public methods from a class via MRO walk."""
    methods: list[MethodContract] = []
    seen: set[str] = set()
    for klass in cls.__mro__:
        if klass is object:
            continue
        for name, attr in klass.__dict__.items():
            if name.startswith("_"):
                continue
            if name in seen:
                continue
            if isinstance(attr, (types.FunctionType, staticmethod, classmethod)):
                seen.add(name)
                try:
                    bound = getattr(cls, name)
                    sig = inspect.signature(bound)
                except (ValueError, TypeError):
                    continue
                params = list(sig.parameters.values())
                # Remove self for regular methods (getattr returns unbound for plain functions)
                if isinstance(attr, types.FunctionType) and params and params[0].name == "self":
                    params = params[1:]
                    sig = sig.replace(parameters=params)
                methods.append(MethodContract(name=name, signature=str(sig)))
    return methods


def python_contract(cell_path: str) -> list[EntityContract | RoutineContract]:
    """Extract the contract (facade) from a Python package.

    Args:
        cell_path: Path to the package in ``path/to/cell`` format.

    Returns:
        List of EntityContract and RoutineContract instances representing the package facade.

    Raises:
        ModuleNotFoundError: If the package cannot be imported.
    """
    module_path = cell_path.strip("/").replace("/", ".")
    module = import_module(module_path)

    all_names = getattr(module, "__all__", None)
    if all_names is None:
        return []

    result: list[EntityContract | RoutineContract] = []
    for name in all_names:
        obj = getattr(module, name)
        if not (callable(obj) and not inspect.ismodule(obj)):
            continue
        if inspect.isclass(obj):
            sig = inspect.signature(obj.__init__)
            params = list(sig.parameters.values())
            if params and params[0].name == "self":
                params = params[1:]
            sig = sig.replace(parameters=params)
            properties = _extract_properties(obj)
            methods = _extract_methods(obj)
            result.append(
                EntityContract(
                    name=name,
                    signature=str(sig),
                    properties=properties,
                    methods=methods,
                )
            )
        else:
            sig = inspect.signature(obj)
            result.append(RoutineContract(name=name, signature=str(sig)))

    return result
