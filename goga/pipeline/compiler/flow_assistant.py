"""The ``FlowAssistant`` dataclass — one emitted stage attachment entry of a flow-file."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(kw_only=True)
class FlowAssistant:
    """One emitted stage attachment entry — one assistant attached to one stage, fields in key-emission order.

    The entry carries NO ``skills`` key: the afm engine (v2.x) strict-parses
    ``stages[].assistants`` entries and rejects any key outside
    ``profile/title/instruction/mode/trigger``. An assistant's skills reach
    the engine through its ``team`` member entry, which accepts them.

    Args:
        profile: The generated profile binding ``goga-<name>``.
        title: The assistant's name.
        instruction: The authored prompt — the empty string when none is
            authored.
        mode: The gate mapping — ``"required"`` when the effective gate is
            true, ``"advisory"`` otherwise.
        trigger: The engagement mapping — ``"one_shot"`` from ``start``,
            ``"checkpoints"`` from ``checkpoints`` (written explicitly, never
            inherited from the engine's ``one_shot`` default),
            ``"on_completion"`` from ``finish``.
    """

    profile: str
    title: str
    instruction: str
    mode: str
    trigger: str
