from __future__ import annotations

# ruff: noqa: PLC0415 — lazy imports required by contract
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from goga.contract.data import EntityContract, RoutineContract


def contract(lang: str, cell_path: str) -> list[EntityContract | RoutineContract]:
    """Extract contracts from a cell source file for the given language.

    Args:
        lang: Programming language identifier (python, golang, javascript, kotlin, swift).
        cell_path: Path to the cell source file.

    Returns:
        List of extracted entity and routine contracts.

    Raises:
        ValueError: If the language is not supported.
    """
    if lang == "python":
        from .python import python_contract

        return python_contract(cell_path)
    if lang == "golang":
        from .golang import golang_contract

        return golang_contract(cell_path)
    if lang == "javascript":
        from .javascript import javascript_contract

        return javascript_contract(cell_path)
    if lang == "kotlin":
        from .kotlin import kotlin_contract

        return kotlin_contract(cell_path)
    if lang == "swift":
        from .swift import swift_contract

        return swift_contract(cell_path)
    raise ValueError(f"unsupported language: {lang}")
