from __future__ import annotations


class BaseASTError(Exception):
    """Base exception for all AST errors."""

    def __init__(self, message: str) -> None:
        """Initialize the error with a human-readable message.

        Args:
            message: Description of the error condition.
        """
        super().__init__(message)

    @property
    def message(self) -> str:
        """Human-readable description of the error condition."""
        return str(self.args[0])
