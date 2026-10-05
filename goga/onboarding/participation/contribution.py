"""The config contribution surface of one tool."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass(kw_only=True)
class ToolContribution:
    """The moment-two surface of one tool — the contribution context delivered to the hook, with its buffer.

    Attributes:
        tool: The tool identity of the owning tool.
        invited: The invitation marker — False marks a subscribed tool the
            session did not invite.
        answers: The isolated answer view of the tool — the core answers
            plus its own under local names.
        amendments: The buffered amendments — the path and the value, in
            call order.
        files: The buffered config files — the file name and the data, in
            call order.

    Requirements:
        writing the same file again replaces at write time — the buffer
        keeps every entry in call order; substituting a user's answer is
        silent — the engine commits the buffers, the surface applies
        nothing itself.
    """

    tool: str
    invited: bool
    answers: dict
    amendments: list[tuple[str, str | bool | dict]] = field(init=False, default_factory=list)
    files: list[tuple[str, dict]] = field(init=False, default_factory=list)

    def answer(self, id: str, value: str | bool | dict) -> None:
        """Buffer one amendment of the collected configuration.

        Args:
            id: The dot-path of the addressed entry.
            value: The amendment value.
        """
        self.amendments.append((id, value))

    def write_config(self, file: str, data: dict) -> None:
        """Buffer one config file of the tool.

        Args:
            file: The file name inside the tool's config directory.
            data: The serializable mapping of the file.
        """
        self.files.append((file, data))
