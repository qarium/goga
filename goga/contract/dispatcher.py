from __future__ import annotations

# ruff: noqa: PLC0415 — lazy imports required by contract
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from goga.contract.data import EntityContract, RoutineContract


def contract(lang: str, cell_path: str) -> list[EntityContract | RoutineContract]:
    if lang == "python":
        from .python import python_contract

        return python_contract(cell_path)
    if lang == "golang":
        from .golang import golang_contract

        return golang_contract(cell_path)
    raise ValueError(f"unsupported language: {lang}")
