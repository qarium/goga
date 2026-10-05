"""The comparison-facts read view of the contract domain hooks zone."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class CellFacts:
    """The comparison facts of one cell — the per-cell read view; pure facts, nothing is read inside.

    Args:
        path: the normalized cell path.
        types: the comparison facts of each declared type of the cell.
    """

    path: str
    types: list[TypeFacts]


@dataclass(frozen=True, kw_only=True)
class TypeFacts:
    """The comparison facts of one declared type — pure data, nothing is read inside.

    Args:
        name: the declared type name.
        signature: the compared signature of the type.
        properties: the compared property members — empty for a routine.
        methods: the compared method members — empty for a routine.
    """

    name: str
    signature: FormFacts
    properties: list[MemberFacts]
    methods: list[MemberFacts]


@dataclass(frozen=True, kw_only=True)
class FormFacts:
    """One compared form — the declared string and its extracted counterpart; pure strings only.

    Args:
        codemanifest: the declared form of the CODEMANIFEST.
        implementation: the extracted counterpart — absent when the
            implementation carries none.
    """

    codemanifest: str
    implementation: str | None


@dataclass(frozen=True, kw_only=True)
class MemberFacts:
    """The compared form of one named member — a property or a method; pure data, nothing is read inside.

    Args:
        name: the declared member name.
        form: the compared form of the member.
    """

    name: str
    form: FormFacts
