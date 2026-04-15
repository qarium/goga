from __future__ import annotations


class BaseASTError(Exception):
    """Base exception for all AST errors."""

    def __init__(self, message: str) -> None:
        super().__init__(message)

    @property
    def message(self) -> str:
        return str(self.args[0])
