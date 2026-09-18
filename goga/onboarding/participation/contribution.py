"""The config contribution surface of one tool.

The entity declared in the cell CODEMANIFEST with ``location: contribution.py``:
the moment-two surface ``ToolContribution``. The surface is delivered to one
tool's amend-config hook — the invitation marker, the isolated answer view,
and the staged buffer of the amendments and the config files. The buffered
contribution applies only after every hook of the tool completed without
failure.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass(kw_only=True)
class ToolContribution:
    """The moment-two surface of one tool — the contribution context and its staged buffer.

    The object an amend-config hook receives as ``context``: the invitation
    marker the hook checks first, the isolated answer view of the tool, and
    the buffers of its contribution. The contribution is staged — the engine
    applies the buffered amendments and writes the buffered files only after
    every hook of the tool completed without failure; a tool never writes
    its config files itself.

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
