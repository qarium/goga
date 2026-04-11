from __future__ import annotations


class BaseCodemanifestError(Exception):
    """Base exception for all codemanifest errors."""

    def __init__(self, message: str) -> None:
        super().__init__(message)

    @property
    def message(self) -> str:
        return str(self.args[0])
