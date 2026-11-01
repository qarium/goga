"""The ``FlowTeamMember`` dataclass — one emitted team member of a flow-file."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(kw_only=True)
class FlowTeamMember:
    """One emitted team member — one run-level assistant of the flow-file, fields in key-emission order.

    Args:
        id: The assistant's authored name — the stable identity the engine
            recognizes on resume.
        title: The display title — the authored name; the dashboard handle
            derives from it.
        profile: The generated profile binding ``goga-<name>`` — the binding
            to the profile the engine configuration materializes for this
            flow.
        instruction: The assistant's instruction — the authored prompt, the
            empty string when none is authored.
        skills: The assistant's own skills — the authored list, an empty
            list when none is authored.
    """

    id: str
    title: str
    profile: str
    instruction: str
    skills: list[str]
