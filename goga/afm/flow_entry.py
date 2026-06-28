from __future__ import annotations

import enum

from pydantic import BaseModel, ConfigDict, field_validator


class Source(str, enum.Enum):
    """Origin of a flow file.

    Attributes:
        PROJECT: the flow lives in the project-level ``<cwd>/.goga/flows/`` directory.
        USER: the flow lives in the user-level ``~/.goga/flows/`` directory.
    """

    PROJECT = "project"
    USER = "user"


class FlowEntry(BaseModel):
    """A single discovered flow file: its name and where it comes from.

    The ``name`` is the flow identifier without extension (e.g. ``"deploy"``);
    the ``.yml`` extension is implied and never stored. ``source`` records
    whether the flow was discovered in the project-level or user-level flows
    directory.

    Args:
        name: flow name without extension; must not contain path separators
            (``/`` or ``\\``) and must not end with ``.yml``.
        source: origin of the flow (``Source.PROJECT`` or ``Source.USER``).

    Raises:
        pydantic.ValidationError: if ``name`` carries a path separator or the
            ``.yml`` extension, or if construction uses positional arguments.
    """

    model_config = ConfigDict(kw_only=True)

    name: str
    source: Source

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str) -> str:
        """Reject names carrying path separators or the .yml extension.

        Args:
            value: the candidate flow name.

        Returns:
            The validated name, unchanged.

        Raises:
            ValueError: if the name contains ``/`` or ``\\``, or ends with ``.yml``.
        """
        if "/" in value or "\\" in value:
            raise ValueError("flow name must not contain path separators ('/' or '\\')")

        if value.endswith(".yml"):
            raise ValueError("flow name must not include the '.yml' extension")

        return value
