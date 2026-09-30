"""The comparison-facts read view of the contract domain hooks zone.

``CellFacts`` is the per-cell read view delivered to every subscribed
hook of the hard ``contract/amend_contract`` checkpoint: the comparison
facts of one cell as the calling command's own comparison composes
them. ``TypeFacts`` carries the comparison facts of one declared type,
``FormFacts`` one compared form — the declared string with its extracted
counterpart — and ``MemberFacts`` the compared form of one named member.
All four are pure facts: the constructing operation passes resolved
values and nothing is read inside — the authored projection only,
identical for every tool; one shape for every implementation language.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class CellFacts:
    """The comparison facts of one cell — the per-cell read view.

    Pure facts: the constructing operation passes resolved values,
    nothing is read inside. The record is the authored projection only —
    the declared and extracted forms exactly as the caller's comparison
    composes them; identical for every tool; one shape for every
    implementation language.

    Args:
        path: the normalized cell path.
        types: the comparison facts of each declared type of the cell.
    """

    path: str
    types: list[TypeFacts]


@dataclass(frozen=True, kw_only=True)
class TypeFacts:
    """The comparison facts of one declared type — pure data.

    Constructed by the caller from its own comparison values; nothing is
    read inside.

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
    """One compared form — the declared string and its extracted counterpart.

    Pure strings only — the language-agnostic shape carries no parsed
    structures.

    Args:
        codemanifest: the declared form of the CODEMANIFEST.
        implementation: the extracted counterpart — absent when the
            implementation carries none.
    """

    codemanifest: str
    implementation: str | None


@dataclass(frozen=True, kw_only=True)
class MemberFacts:
    """The compared form of one named member — a property or a method.

    Pure data — constructed by the caller from its own comparison
    values; nothing is read inside.

    Args:
        name: the declared member name.
        form: the compared form of the member.
    """

    name: str
    form: FormFacts
